"""Tests for rate_limiter.TokenBucketRateLimiter."""

import threading
import time

import pytest

from rate_limiter import TokenBucketRateLimiter


class FakeClock:
    """Deterministic monotonic clock controlled manually."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture()
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(time, "monotonic", fake)
    return fake


def test_initial_bucket_is_full():
    limiter = TokenBucketRateLimiter(rate=1.0, capacity=5.0)
    assert limiter.available_tokens == 5.0


def test_basic_acquire_success_and_failure(clock):
    limiter = TokenBucketRateLimiter(rate=1.0, capacity=2.0)
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False
    assert limiter.available_tokens == 0.0


def test_refill_capped_at_capacity_after_long_idle(clock):
    limiter = TokenBucketRateLimiter(rate=1.0, capacity=3.0)
    assert limiter.try_acquire(3.0) is True
    assert limiter.available_tokens == 0.0

    # Advance far beyond what is needed to refill the bucket.
    clock.advance(10_000)
    assert limiter.available_tokens == 3.0
    assert limiter.try_acquire(3.0) is True
    assert limiter.try_acquire() is False


def test_refill_over_time_deterministic(clock):
    limiter = TokenBucketRateLimiter(rate=2.0, capacity=4.0)

    assert limiter.try_acquire(4.0) is True
    assert limiter.available_tokens == 0.0

    clock.advance(1.0)
    assert limiter.available_tokens == pytest.approx(2.0)
    assert limiter.try_acquire(2.0) is True
    assert limiter.try_acquire() is False

    clock.advance(0.25)
    assert limiter.available_tokens == pytest.approx(0.5)


def test_try_acquire_multiple_tokens_no_partial_consumption(clock):
    limiter = TokenBucketRateLimiter(rate=1.0, capacity=5.0)
    assert limiter.try_acquire(3.0) is True
    assert limiter.available_tokens == pytest.approx(2.0)

    # Requesting more than available must fail without deducting anything.
    before = limiter.available_tokens
    assert limiter.try_acquire(3.0) is False
    assert limiter.available_tokens == before


def test_invalid_constructor_args():
    for bad_rate in (0, -1.0):
        with pytest.raises(ValueError):
            TokenBucketRateLimiter(rate=bad_rate, capacity=1.0)
    for bad_capacity in (0, -2.5):
        with pytest.raises(ValueError):
            TokenBucketRateLimiter(rate=1.0, capacity=bad_capacity)


def test_concurrent_acquires_never_exceed_capacity(clock):
    capacity = 10
    threads_count = 50
    # Time is frozen by the `clock` fixture, so no refill occurs during the
    # test regardless of `rate` — accounting is purely deductive.
    limiter = TokenBucketRateLimiter(rate=1.0, capacity=capacity)

    successes = []
    successes_lock = threading.Lock()

    def worker():
        result = limiter.try_acquire(1)
        with successes_lock:
            successes.append(result)

    threads = [threading.Thread(target=worker) for _ in range(threads_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    total_successes = sum(successes)
    assert len(successes) == threads_count
    assert total_successes == capacity
    assert limiter.available_tokens == 0.0
