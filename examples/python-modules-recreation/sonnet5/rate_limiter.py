"""A thread-safe token-bucket rate limiter.

Pure standard-library implementation: tokens accumulate at a fixed rate
up to a configurable burst capacity, and callers spend tokens via
``try_acquire``. A single lock makes every public method safe to call
from multiple threads concurrently.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional


class RateLimiter:
    """Token-bucket rate limiter.

    Args:
        rate: Tokens added per second (must be positive).
        burst: Maximum number of tokens the bucket can hold, i.e. the
            largest instantaneous burst allowed. Defaults to ``rate``
            (one second's worth of tokens) if not given.
        clock: Zero-argument callable returning the current time in
            seconds. Defaults to ``time.monotonic``; overridable for
            deterministic testing.
    """

    def __init__(
        self,
        rate: float,
        burst: Optional[float] = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        capacity = rate if burst is None else burst
        if capacity <= 0:
            raise ValueError("burst must be positive")

        self._rate = float(rate)
        self._capacity = float(capacity)
        self._tokens = float(capacity)
        self._clock = clock
        self._last_refill = clock()
        self._lock = threading.Lock()

    @property
    def rate(self) -> float:
        return self._rate

    @property
    def capacity(self) -> float:
        return self._capacity

    def _refill(self, now: float) -> None:
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """Attempt to spend ``tokens``. Returns whether it succeeded.

        On success the tokens are deducted immediately. On failure the
        bucket is left untouched (aside from the refill that always
        happens first).
        """
        if tokens <= 0:
            raise ValueError("tokens must be positive")
        with self._lock:
            self._refill(self._clock())
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    @property
    def available_tokens(self) -> float:
        """Current token count, after applying any pending refill."""
        with self._lock:
            self._refill(self._clock())
            return self._tokens

    def __repr__(self) -> str:
        return f"RateLimiter(rate={self._rate}, capacity={self._capacity})"
