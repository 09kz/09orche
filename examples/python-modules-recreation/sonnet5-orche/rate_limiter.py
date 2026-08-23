"""Token-bucket rate limiter.

A thread-safe, lazily-refilled token bucket implementation using only the
Python standard library. Tokens accumulate at a fixed rate up to a maximum
capacity (burst size) and are consumed by :meth:`TokenBucketRateLimiter.try_acquire`.
"""

from __future__ import annotations

import threading
import time


class TokenBucketRateLimiter:
    """Thread-safe token-bucket rate limiter with lazy refill.

    Args:
        rate: Token refill rate in tokens per second. Must be > 0.
        capacity: Maximum number of tokens the bucket can hold (burst size).
            Must be > 0.

    Raises:
        ValueError: If ``rate`` or ``capacity`` is not strictly positive.
    """

    def __init__(self, rate: float, capacity: float) -> None:
        if not isinstance(rate, (int, float)) or isinstance(rate, bool) or rate <= 0:
            raise ValueError("rate must be a positive number")
        if not isinstance(capacity, (int, float)) or isinstance(capacity, bool) or capacity <= 0:
            raise ValueError("capacity must be a positive number")

        self._rate = float(rate)
        self._capacity = float(capacity)
        self._tokens = self._capacity
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    @property
    def available_tokens(self) -> float:
        """Current number of available tokens, computed without mutating state."""
        with self._lock:
            return min(self._capacity, self._tokens + self._elapsed_refill(time.monotonic()))

    @property
    def rate(self) -> float:
        """Token refill rate in tokens per second."""
        return self._rate

    @property
    def capacity(self) -> float:
        """Maximum burst size of the bucket."""
        return self._capacity

    def _elapsed_refill(self, now: float) -> float:
        """Return tokens accrued since ``self._last_refill`` given time ``now``.

        Caller must hold the lock.
        """
        elapsed = max(0.0, now - self._last_refill)
        return elapsed * self._rate

    def try_acquire(self, tokens: float = 1) -> bool:
        """Attempt to consume ``tokens`` from the bucket without blocking.

        The bucket is refilled lazily based on elapsed time before the check.
        On success the requested tokens are deducted atomically; on failure no
        partial consumption occurs.

        Args:
            tokens: Number of tokens to consume. Defaults to 1.

        Returns:
            True if the tokens were acquired, False otherwise.
        """
        if tokens < 0:
            raise ValueError("tokens must be non-negative")

        with self._lock:
            now = time.monotonic()
            self._tokens = min(self._capacity, self._tokens + self._elapsed_refill(now))
            self._last_refill = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False
