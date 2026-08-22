"""Conclave — delegate work to OpenRouter models from Claude Code."""

import os
import sys

from mcp.server.fastmcp import FastMCP

from conclave.client import OpenRouterError, ask
from conclave.config import load_models_or_exit

DEFAULT_SYSTEM_PROMPT = "You are a helpful expert assistant."


def build_server() -> FastMCP:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("conclave: OPENROUTER_API_KEY is not set", file=sys.stderr)
        raise SystemExit(1)

    catalogue = load_models_or_exit()
    mcp = FastMCP("conclave")

    def make_tool(alias: str):
        async def tool(prompt: str, system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> str:
            spec = catalogue[alias]
            try:
                return await ask(api_key, spec, catalogue, prompt, system_prompt)
            except OpenRouterError as e:
                return f"conclave: {e}"

        return tool

    for alias, spec in catalogue.items():
        tool_fn = make_tool(alias)
        tool_fn.__name__ = f"ask_{alias}"
        mcp.add_tool(tool_fn, name=f"ask_{alias}", description=spec.description)

    @mcp.tool()
    async def list_models() -> str:
        """List the models available in Conclave, with their OpenRouter ids and fallbacks."""
        lines = []
        for alias, spec in catalogue.items():
            fb = f" -> fallback: {spec.fallback}" if spec.fallback else ""
            lines.append(f"ask_{alias:<20} {spec.id}{fb}")
        return "Available models:\n" + "\n".join(lines)

    return mcp


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
