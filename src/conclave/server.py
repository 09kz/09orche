"""Conclave — delegate work to OpenRouter models from Claude Code."""

import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from conclave import cost
from conclave.agent import AgentError, run_agent
from conclave.client import OpenRouterError, ask
from conclave.config import load_models_or_exit

DEFAULT_SYSTEM_PROMPT = "You are a helpful expert assistant."

AGENT_TOOL_DESCRIPTION = (
    "{base}\n\nAgent mode ({tier}): given a `workspace` directory, this model can "
    "explore and {verb} files there using its own tool calls, iterating until it "
    "has an answer. It cannot see or affect anything outside `workspace`."
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
        print(f"conclave: {name} must be a number (got {raw!r})", file=sys.stderr)
        raise SystemExit(1) from None


def build_server() -> FastMCP:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("conclave: OPENROUTER_API_KEY is not set", file=sys.stderr)
        raise SystemExit(1)

    _validate_numeric_env("CONCLAVE_MAX_COST_USD")
    _validate_numeric_env("CONCLAVE_TIMEOUT_S")

    catalogue = load_models_or_exit()
    mcp = FastMCP("conclave")

    def make_tool(alias: str):
        async def tool(
            prompt: str,
            system_prompt: str = DEFAULT_SYSTEM_PROMPT,
            reasoning_effort: str | None = None,
        ) -> str:
            spec = catalogue[alias]
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
                return f"conclave: {e}"

        return tool

    def make_agent_tool(alias: str, tier: str):
        async def tool(prompt: str, workspace: str, reasoning_effort: str | None = None) -> str:
            spec = catalogue[alias]
            ws_path = Path(workspace).resolve()
            if not ws_path.is_dir():
                return f"conclave: workspace is not a directory: {workspace}"
            try:
                return await run_agent(
                    api_key, spec.id, tier, ws_path, prompt, spec.max_tokens, reasoning_effort
                )
            except AgentError as e:
                return f"conclave: {e}"

        return tool

    for alias, spec in catalogue.items():
        tool_fn = make_tool(alias)
        tool_fn.__name__ = f"ask_{alias}"
        mcp.add_tool(tool_fn, name=f"ask_{alias}", description=spec.description)

        if spec.agent_tools is not None:
            agent_fn = make_agent_tool(alias, spec.agent_tools)
            agent_fn.__name__ = f"agent_{alias}"
            description = AGENT_TOOL_DESCRIPTION.format(
                base=spec.description, tier=spec.agent_tools, verb=_TIER_VERBS[spec.agent_tools]
            )
            mcp.add_tool(agent_fn, name=f"agent_{alias}", description=description)

    @mcp.tool()
    async def list_models() -> str:
        """List the models available in Conclave, with their OpenRouter ids and fallbacks."""
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

    return mcp


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
