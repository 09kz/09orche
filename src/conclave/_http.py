"""Shared retry/backoff for calls to OpenRouter, used by client.py and agent.py."""

from __future__ import annotations

import asyncio
import random

import httpx

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
BASE_DELAY = 1.5


async def backoff(attempt: int) -> None:
    delay = BASE_DELAY * (2**attempt) + random.uniform(0, 0.5)
    await asyncio.sleep(delay)


async def post_with_retry(
    client: httpx.AsyncClient, url: str, headers: dict, json_payload: dict
) -> httpx.Response:
    """POST with retry on 429/5xx and transport errors.

    Returns the final response once retries are exhausted, whatever its
    status — the caller decides what a non-200 result means. Raises only if
    every attempt hits a transport-level error (no response at all).
    """
    last_error: httpx.TransportError | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = await client.post(url, headers=headers, json=json_payload)
        except httpx.TransportError as e:
            last_error = e
            if attempt == MAX_RETRIES:
                raise
            await backoff(attempt)
            continue

        if r.status_code in RETRYABLE_STATUS and attempt < MAX_RETRIES:
            await backoff(attempt)
            continue
        return r

    # Unreachable: the loop above always returns or raises.
    raise last_error  # type: ignore[misc]
