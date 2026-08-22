import threading
import time

import pytest

from rate_limiter import RateLimiter


class ManualClock:
    """A controllable fake clock for deterministic timing tests."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


# -- Construction / validation --------------------------------------------


def test_invalid_rate_raises():
    with pytest.raises(ValueError):
        RateLimiter(rate=0)
    with pytest.raises(ValueError):
        RateLimiter(rate=-1)


def test_invalid_burst_raises():
    with pytest.raises(ValueError):
        RateLimiter(rate=1, burst=0)
    with pytest.raises(ValueError):
        RateLimiter(rate=1, burst=-5)


def test_default_burst_equals_rate():
    clock = ManualClock()
    limiter = RateLimiter(rate=5, clock=clock)
    assert limiter.capacity == 5
    assert limiter.available_tokens == 5


def test_try_acquire_invalid_token_amount_raises():
    limiter = RateLimiter(rate=1, clock=ManualClock())
    with pytest.raises(ValueError):
        limiter.try_acquire(0)
    with pytest.raises(ValueError):
        limiter.try_acquire(-1)


# -- Burst behavior ---------------------------------------------------------


def test_burst_allows_capacity_requests_up_front():
    clock = ManualClock()
    limiter = RateLimiter(rate=1, burst=5, clock=clock)

    for _ in range(5):
        assert limiter.try_acquire() is True

    # Bucket is now empty; the 6th immediate request must fail.
    assert limiter.try_acquire() is False


def test_burst_caps_token_accumulation():
    clock = ManualClock()
    limiter = RateLimiter(rate=1, burst=3, clock=clock)

    clock.advance(1000)  # far more time than needed to overflow the bucket
    assert limiter.available_tokens == 3

    # Only 3 tokens should be spendable, not an unbounded amount.
    assert limiter.try_acquire(3) is True
    assert limiter.try_acquire(1) is False


def test_try_acquire_multiple_tokens_at_once():
    clock = ManualClock()
    limiter = RateLimiter(rate=1, burst=5, clock=clock)

    assert limiter.try_acquire(3) is True
    assert limiter.available_tokens == 2
    assert limiter.try_acquire(3) is False  # only 2 left
    assert limiter.try_acquire(2) is True
    assert limiter.available_tokens == 0


# -- Refill timing ----------------------------------------------------------


def test_refill_grants_tokens_proportional_to_elapsed_time():
    clock = ManualClock()
    limiter = RateLimiter(rate=2, burst=2, clock=clock)  # 2 tokens/sec

    assert limiter.try_acquire(2) is True
    assert limiter.try_acquire() is False

    clock.advance(0.4)  # 0.4s * 2/s = 0.8 tokens -> not enough
    assert limiter.try_acquire() is False

    clock.advance(0.1)  # total 0.5s * 2/s = 1.0 token -> enough
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False


def test_refill_does_not_exceed_capacity():
    clock = ManualClock()
    limiter = RateLimiter(rate=10, burst=4, clock=clock)

    limiter.try_acquire(4)
    clock.advance(10)  # would be 100 tokens without the cap
    assert limiter.available_tokens == 4


def test_no_refill_when_time_does_not_advance():
    clock = ManualClock()
    limiter = RateLimiter(rate=1, burst=1, clock=clock)

    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False  # same instant, no new tokens


def test_partial_refill_is_retained_between_calls():
    clock = ManualClock()
    limiter = RateLimiter(rate=1, burst=1, clock=clock)

    limiter.try_acquire()  # empty the bucket
    clock.advance(0.3)
    limiter.try_acquire()  # fails, but the 0.3 tokens worth of elapsed time...
    clock.advance(0.3)
    limiter.try_acquire()  # ...should combine with this to reach 0.6, still < 1
    assert limiter.available_tokens == pytest.approx(0.6)
    clock.advance(0.4)
    assert limiter.try_acquire() is True  # now at 1.0


# -- Real clock integration --------------------------------------------------


def test_real_clock_default_wiring_end_to_end():
    # Uses the real time.monotonic default to sanity-check the wiring,
    # with a generous rate/tolerance to avoid flakiness under CI jitter.
    limiter = RateLimiter(rate=100, burst=1)  # 1 token refills in 10ms
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False

    time.sleep(0.05)
    assert limiter.try_acquire() is True


# -- Thread safety ------------------------------------------------------------


def test_thread_safety_never_grants_more_than_capacity():
    clock = ManualClock()
    limiter = RateLimiter(rate=1, burst=20, clock=clock)
    successes = []
    lock = threading.Lock()

    def worker():
        ok = limiter.try_acquire()
        if ok:
            with lock:
                successes.append(1)

    threads = [threading.Thread(target=worker) for _ in range(100)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Only the initial burst of 20 tokens should ever be handed out,
    # regardless of how many threads race for them concurrently.
    assert len(successes) == 20
    assert limiter.available_tokens == 0
