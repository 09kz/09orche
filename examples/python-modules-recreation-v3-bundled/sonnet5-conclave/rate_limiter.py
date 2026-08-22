import time


class RateLimiter:
    """Token-bucket rate limiter.

    Args:
        rate: Tokens added per second.
        burst: Maximum bucket capacity (initial tokens).
        clock: Callable returning current time in seconds (defaults to time.monotonic).
    """

    def __init__(self, rate, burst, clock=time.monotonic):
        if rate <= 0:
            raise ValueError("rate must be positive")
        if burst <= 0:
            raise ValueError("burst must be positive")
        self.rate = float(rate)
        self.burst = float(burst)
        self._clock = clock
        self._tokens = float(burst)
        self._last = clock()

    def try_acquire(self):
        """Try to take one token. Returns True on success, False otherwise."""
        now = self._clock()
        elapsed = now - self._last
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last = now
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False
