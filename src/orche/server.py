"""Orche — delegate work to OpenRouter models from Claude Code."""

import os
import sys
from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP

from orche import cost
from orche.agent import AgentError, run_agent
from orche.client import OpenRouterError, ask
from orche.config import AGENT_TIERS, ConfigError, load_models_or_exit, validate_alias_name
from orche.profiles import Profile
from orche.profiles import load_profiles as _load_profiles
from orche.profiles import save_profile as _save_profile
from orche.reasoning import VALID_EFFORTS

DEFAULT_SYSTEM_PROMPT = "You are a helpful expert assistant."


async def _log(ctx: "Context | None", message: str) -> None:
    """Emit an MCP info log; silently no-ops when there is no live request context."""
    if ctx is None:
        return
    try:
        await ctx.info(message)
    except Exception:
        pass

# Evidence-based, not speculative — see examples/README.md for the measured
# timing experiments these two lines come from. Kept short deliberately:
# this text is repeated in every registered model's tool description, so it
# adds up across a whole catalogue's worth of tools/list output.
USAGE_TIP = (
    "\n\nTips: set reasoning_effort explicitly for code generation — left "
    "unset, a reasoning model can spend its whole budget on hidden "
    "reasoning and return no code. Don't split an implementation from its "
    "own tests across separate calls; independently-generated pieces "
    "reliably drift apart on API details even with matching prompts — "
    "generate them together in one call instead."
)

AGENT_TOOL_DESCRIPTION = (
    "{base}\n\nAgent mode ({tier}): given a `workspace` directory, this model can "
    "explore and {verb} files there using its own tool calls, iterating until it "
    "has an answer. It cannot see or affect anything outside `workspace`. If a "
    "piece of work needs to match another piece's API, have it read that file "
    "from the workspace rather than assuming two calls will agree on an "
    "interface." + USAGE_TIP
)

_TIER_VERBS = {
    "read": "read",
    "read_write": "read and write",
    "full": "read, write, and run shell commands against",
}


def _validate_numeric_env(name: str) -> None:
    raw = os.environ.get(name)
    if raw is None:
        return
    try:
        float(raw)
    except ValueError:
        print(f"orche: {name} must be a number (got {raw!r})", file=sys.stderr)
        raise SystemExit(1) from None


def build_server() -> FastMCP:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("orche: OPENROUTER_API_KEY is not set", file=sys.stderr)
        raise SystemExit(1)

    _validate_numeric_env("ORCHE_MAX_COST_USD")
    _validate_numeric_env("ORCHE_TIMEOUT_S")

    catalogue = load_models_or_exit()
    mcp = FastMCP("orche")

    def make_tool(alias: str):
        async def tool(
            prompt: str,
            system_prompt: str = DEFAULT_SYSTEM_PROMPT,
            reasoning_effort: str | None = None,
            ctx: Context = None,
        ) -> str:
            spec = catalogue[alias]
            short_id = spec.id.split("/")[-1]
            await _log(ctx,f"→ {alias} [{short_id}] thinking…")
            try:
                return await ask(
                    api_key,
                    spec,
                    catalogue,
                    prompt,
                    system_prompt,
                    reasoning_effort=reasoning_effort,
                )
            except OpenRouterError as e:
                return f"orche: {e}"

        return tool

    def make_agent_tool(alias: str, tier: str):
        async def tool(
            prompt: str,
            workspace: str,
            reasoning_effort: str | None = None,
            ctx: Context = None,
        ) -> str:
            spec = catalogue[alias]
            ws_path = Path(workspace).resolve()
            if not ws_path.is_dir():
                return f"orche: workspace is not a directory: {workspace}"
            try:
                return await run_agent(
                    api_key, spec.id, tier, ws_path, prompt, spec.max_tokens, reasoning_effort,
                    ctx=ctx,
                )
            except AgentError as e:
                return f"orche: {e}"

        return tool

    for alias, spec in catalogue.items():
        tool_fn = make_tool(alias)
        tool_fn.__name__ = f"ask_{alias}"
        mcp.add_tool(
            tool_fn, name=f"ask_{alias}", description=spec.description + USAGE_TIP
        )

        if spec.agent_tools is not None:
            agent_fn = make_agent_tool(alias, spec.agent_tools)
            agent_fn.__name__ = f"agent_{alias}"
            description = AGENT_TOOL_DESCRIPTION.format(
                base=spec.description, tier=spec.agent_tools, verb=_TIER_VERBS[spec.agent_tools]
            )
            mcp.add_tool(agent_fn, name=f"agent_{alias}", description=description)

    @mcp.tool()
    async def list_models() -> str:
        """List the models available in Orche, with their OpenRouter ids and fallbacks."""
        lines = []
        for alias, spec in catalogue.items():
            fb = f" -> fallback: {spec.fallback}" if spec.fallback else ""
            agent = f" [agent: {spec.agent_tools}]" if spec.agent_tools else ""
            lines.append(f"ask_{alias:<20} {spec.id}{fb}{agent}")
        return "Available models:\n" + "\n".join(lines)

    @mcp.tool()
    async def spend_status() -> str:
        """Report this session's cumulative OpenRouter spend and budget, if any."""
        return cost.status()

    @mcp.tool()
    async def save_profile(
        name: str,
        base_alias: str,
        system_prompt: str,
        reasoning_effort: str | None = None,
        agent_tools: str | None = None,
    ) -> str:
        """Create or update a named subagent profile: a fixed persona on top of
        an existing model alias, reusable across calls without restating it.
        `base_alias` must be one of the aliases from `list_models`."""
        try:
            validate_alias_name(name)
        except ConfigError as e:
            return f"orche: {e}"
        if base_alias not in catalogue:
            return f"orche: unknown base_alias {base_alias!r}, see list_models"
        if reasoning_effort is not None and reasoning_effort not in VALID_EFFORTS:
            return f"orche: reasoning_effort must be one of {VALID_EFFORTS}"
        if agent_tools is not None and agent_tools not in AGENT_TIERS:
            return f"orche: agent_tools must be one of {AGENT_TIERS}"

        profile = Profile(
            name=name,
            base_alias=base_alias,
            system_prompt=system_prompt.strip(),
            reasoning_effort=reasoning_effort,
            agent_tools=agent_tools,
        )
        try:
            _save_profile(profile)
        except ConfigError as e:
            return f"orche: {e}"
        return f"saved profile {name!r} (base: {base_alias})"

    @mcp.tool()
    async def list_profiles() -> str:
        """List saved subagent profiles, with their base model and overrides."""
        try:
            profiles = _load_profiles()
        except ConfigError as e:
            return f"orche: {e}"
        if not profiles:
            return "No profiles saved yet. Create one with save_profile."
        lines = []
        for p in profiles.values():
            effort = f" [reasoning: {p.reasoning_effort}]" if p.reasoning_effort else ""
            agent = f" [agent: {p.agent_tools}]" if p.agent_tools else ""
            lines.append(f"{p.name:<20} base: {p.base_alias}{effort}{agent}")
        return "Saved profiles:\n" + "\n".join(lines)

    def _resolve_profile(name: str) -> Profile | str:
        """Return the Profile, or an error string if it (or its base) is invalid."""
        try:
            profiles = _load_profiles()
        except ConfigError as e:
            return f"orche: {e}"
        profile = profiles.get(name)
        if profile is None:
            return f"orche: unknown profile {name!r}, see list_profiles"
        if profile.base_alias not in catalogue:
            return (
                f"orche: profile {name!r} references base_alias "
                f"{profile.base_alias!r}, which is no longer in the catalogue"
            )
        return profile

    @mcp.tool(description="Call a saved profile's base model with its saved persona." + USAGE_TIP)
    async def ask_profile(name: str, prompt: str, ctx: Context = None) -> str:
        profile = _resolve_profile(name)
        if isinstance(profile, str):
            return profile
        spec = catalogue[profile.base_alias]
        short_id = spec.id.split("/")[-1]
        await _log(ctx, f"→ {name} [{short_id}] thinking…")
        try:
            return await ask(
                api_key,
                spec,
                catalogue,
                prompt,
                profile.system_prompt,
                reasoning_effort=profile.reasoning_effort,
            )
        except OpenRouterError as e:
            return f"orche: {e}"

    @mcp.tool(
        description="Run a saved profile in agent mode against a workspace directory."
        + USAGE_TIP
    )
    async def agent_profile(name: str, prompt: str, workspace: str, ctx: Context = None) -> str:
        profile = _resolve_profile(name)
        if isinstance(profile, str):
            return profile
        spec = catalogue[profile.base_alias]
        tier = profile.agent_tools or spec.agent_tools
        if tier is None:
            return (
                f"orche: profile {name!r} has no agent_tools tier, and neither "
                f"does its base model {profile.base_alias!r} — set one on the "
                "profile (save_profile) or the base model (models.toml)"
            )
        ws_path = Path(workspace).resolve()
        if not ws_path.is_dir():
            return f"orche: workspace is not a directory: {workspace}"
        try:
            return await run_agent(
                api_key,
                spec.id,
                tier,
                ws_path,
                prompt,
                spec.max_tokens,
                profile.reasoning_effort,
                profile.system_prompt,
                ctx=ctx,
            )
        except AgentError as e:
            return f"orche: {e}"

    return mcp


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
