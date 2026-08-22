"""Shared retry/backoff for calls to OpenRouter, used by client.py and agent.py."""

from __future__ import annotations

import asyncio
import os
import random

import httpx

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
BASE_DELAY = 1.5

# httpx.Timeout's "read" value is the max gap between successive chunks of
# an in-progress response, not a hard cap on total response time — a model
# that keeps actively streaming tokens won't hit this even if the whole
# call takes much longer. It only fires if the provider goes fully silent
# for this long. 900s is generous headroom for the largest max_tokens caps
# in the bundled catalogue.
DEFAULT_TIMEOUT_S = 900.0


def get_timeout() -> httpx.Timeout:
    """CONCLAVE_TIMEOUT_S overrides the default read/write/pool timeout.

    Assumes the value was already validated at startup (see
    `conclave.server.build_server`) — falls back to the default on a bad
    value rather than crashing an in-flight call.
    """
    raw = os.environ.get("CONCLAVE_TIMEOUT_S")
    try:
        seconds = float(raw) if raw else DEFAULT_TIMEOUT_S
    except ValueError:
        seconds = DEFAULT_TIMEOUT_S
    return httpx.Timeout(seconds, connect=15.0)


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
