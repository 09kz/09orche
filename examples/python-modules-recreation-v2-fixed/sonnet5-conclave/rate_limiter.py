import threading
import time


class TokenBucket:
    """Token-bucket rate limiter.

    Args:
        rate: Tokens added per second.
        burst: Maximum bucket capacity (burst size).
    """

    def __init__(self, rate: float, burst: float):
        if rate <= 0:
            raise ValueError("rate must be positive")
        if burst <= 0:
            raise ValueError("burst must be positive")
        self.rate = float(rate)
        self.burst = float(burst)
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """Try to acquire `tokens` without blocking.

        Returns True on success, False if not enough tokens are available.
        """
        if tokens > self.burst:
            raise ValueError("requested tokens exceed burst capacity")

        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_refill = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    @property
    def available_tokens(self) -> float:
        """Current number of tokens (refilled lazily)."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            return min(self.burst, self._tokens + elapsed * self.rate)


# test_rate_limiter.py (generated independently, in parallel, with no visibility
# into this file) expects the class to be named RateLimiter -- the two parallel
# subagent calls disagreed on naming despite an identical prompt spec. Alias
# rather than rename, to keep this file exactly as the subagent produced it.
RateLimiter = TokenBucket