"""Agent-mode loop: gives a model sandboxed tools and lets it iterate."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from conclave import cost
from conclave._http import get_timeout, post_with_retry
from conclave.tools import dispatch, schemas_for_tier

BASE_URL = "https://openrouter.ai/api/v1"
MAX_ITERATIONS = 15

AGENT_SYSTEM_PROMPT = """\
You are a coding agent working inside a sandboxed workspace directory. You can \
only see and affect files under that workspace root — paths outside it are not \
reachable. Use the available tools to explore and act; when you are done, reply \
with a final plain-text answer and no further tool calls."""


class AgentError(Exception):
    pass


async def run_agent(
    api_key: str,
    model_id: str,
    tier: str,
    workspace: Path,
    prompt: str,
    max_tokens: int | None = None,
) -> str:
    tools = schemas_for_tier(tier)
    messages: list[dict] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/conclave-mcp/conclave",
        "X-Title": "Conclave",
    }

    async with httpx.AsyncClient(timeout=get_timeout()) as client:
        for _ in range(MAX_ITERATIONS):
            try:
                cost.check_budget(model_id)
            except cost.BudgetExceededError as e:
                raise AgentError(str(e)) from e

            payload: dict = {"model": model_id, "messages": messages, "tools": tools}
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens

            try:
                r = await post_with_retry(
                    client, f"{BASE_URL}/chat/completions", headers, payload
                )
            except httpx.TransportError as e:
                raise AgentError(f"network error calling {model_id}: {e}") from e

            if r.status_code != 200:
                raise AgentError(f"{model_id} returned HTTP {r.status_code}:\n{r.text[:600]}")

            body = r.json()
            if "error" in body:
                raise AgentError(f"{model_id} returned an error: {body['error']}")

            cost.record((body.get("usage") or {}).get("cost"))

            message = body["choices"][0]["message"]
            tool_calls = message.get("tool_calls")

            if not tool_calls:
                return message.get("content") or "(agent returned no content)"

            messages.append(message)
            for call in tool_calls:
                fn = call["function"]
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = dispatch(workspace, tier, fn["name"], args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": result.output,
                    }
                )

    return (
        f"(agent hit the {MAX_ITERATIONS}-iteration limit without a final answer; "
        "the last tool results are above)"
    )
