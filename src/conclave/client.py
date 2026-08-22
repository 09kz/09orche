"""HTTP calls to OpenRouter, with retry and same-catalogue fallback."""

from __future__ import annotations

import httpx

from conclave._http import post_with_retry
from conclave.config import ModelSpec

BASE_URL = "https://openrouter.ai/api/v1"
TIMEOUT = httpx.Timeout(300.0, connect=15.0)

# Applied when a model's `max_tokens` isn't set in models.toml. Without an
# explicit value, some OpenRouter routes fall back to a provider-specific
# default that can be surprisingly small — always send something explicit.
DEFAULT_MAX_TOKENS = 8000


class OpenRouterError(Exception):
    """A non-retryable or exhausted-retry failure from OpenRouter."""


def _extract_text(body: dict) -> str:
    choice = body["choices"][0]["message"]
    text = choice.get("content") or ""
    if not text.strip():
        # some reasoning models put their answer only in the reasoning field
        text = choice.get("reasoning") or ""
    return text


async def _call_with_retry(
    api_key: str, model_id: str, prompt: str, system_prompt: str, max_tokens: int
) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/conclave-mcp/conclave",
        "X-Title": "Conclave",
    }
    payload = {
        "model": model_id,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await post_with_retry(client, f"{BASE_URL}/chat/completions", headers, payload)
        except httpx.TransportError as e:
            raise OpenRouterError(f"network error calling {model_id}: {e}") from e

    if r.status_code != 200:
        raise OpenRouterError(f"{model_id} returned HTTP {r.status_code}:\n{r.text[:600]}")

    body = r.json()
    if "error" in body:
        raise OpenRouterError(f"{model_id} returned an error: {body['error']}")

    text = _extract_text(body)
    usage = body.get("usage") or {}
    tokens = usage.get("total_tokens", "?")
    return f"{text}\n\n---\n{model_id} · {tokens} tokens"


async def ask(
    api_key: str,
    spec: ModelSpec,
    catalogue: dict[str, ModelSpec],
    prompt: str,
    system_prompt: str,
    *,
    _visited: frozenset[str] = frozenset(),
) -> str:
    """Call `spec`'s model; on exhausted retries, fall through to its fallback if set."""
    max_tokens = spec.max_tokens or DEFAULT_MAX_TOKENS
    try:
        return await _call_with_retry(api_key, spec.id, prompt, system_prompt, max_tokens)
    except OpenRouterError as e:
        if spec.fallback is None or spec.fallback in _visited:
            raise
        fallback_spec = catalogue[spec.fallback]
        note = f"[{spec.alias} failed ({e}); falling back to {spec.fallback}]\n\n"
        result = await ask(
            api_key,
            fallback_spec,
            catalogue,
            prompt,
            system_prompt,
            _visited=_visited | {spec.alias},
        )
        return note + result
