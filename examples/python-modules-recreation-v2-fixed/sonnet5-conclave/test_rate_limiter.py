import time
from unittest.mock import patch

import pytest

from rate_limiter import RateLimiter


class ManualClock:
    """Injectable clock for deterministic time control."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock():
    return ManualClock()


class TestBurstCapacity:
    def test_initial_burst_available(self, clock):
        rl = RateLimiter(rate=1.0, burst=5, clock=clock)
        for _ in range(5):
            assert rl.try_acquire() is True

    def test_burst_exhausted_blocks_immediately(self, clock):
        rl = RateLimiter(rate=1.0, burst=3, clock=clock)
        for _ in range(3):
            assert rl.try_acquire() is True
        assert rl.try_acquire() is False

    def test_zero_burst_never_allows(self, clock):
        rl = RateLimiter(rate=10.0, burst=0, clock=clock)
        assert rl.try_acquire() is False

    def test_single_token_burst(self, clock):
        rl = RateLimiter(rate=2.0, burst=1, clock=clock)
        assert rl.try_acquire() is True
        assert rl.try_acquire() is False


class TestRefillTiming:
    def test_refill_after_elapsed_time(self, clock):
        rl = RateLimiter(rate=2.0, burst=2, clock=clock)  # 2 tokens/sec
        assert rl.try_acquire() is True
        assert rl.try_acquire() is True
        assert rl.try_acquire() is False

        clock.advance(0.5)  # one token refilled
        assert rl.try_acquire() is True
        assert rl.try_acquire() is False

    def test_partial_refill_not_granted_early(self, clock):
        rl = RateLimiter(rate=1.0, burst=1, clock=clock)
        assert rl.try_acquire() is True
        clock.advance(0.4)  # less than 1 full token
        assert rl.try_acquire() is False
        clock.advance(0.6)  # now a full token has accrued
        assert rl.try_acquire() is True

    def test_fractional_rate(self, clock):
        rl = RateLimiter(rate=0.5, burst=1, clock=clock)  # 1 token per 2s
        assert rl.try_acquire() is True
        clock.advance(1.0)
        assert rl.try_acquire() is False
        clock.advance(1.0)
        assert rl.try_acquire() is True

    def test_tokens_accumulate_while_idle(self, clock):
        rl = RateLimiter(rate=1.0, burst=3, clock=clock)
        assert rl.try_acquire() is True
        clock.advance(5.0)  # enough time to fully refill the bucket
        for _ in range(3):
            assert rl.try_acquire() is True
        assert rl.try_acquire() is False


class TestCapacityCapping:
    def test_no_accumulation_above_burst(self, clock):
        rl = RateLimiter(rate=10.0, burst=2, clock=clock)
        clock.advance(100.0)  # would generate far more than 2 tokens
        acquired = sum(rl.try_acquire() for _ in range(10))
        assert acquired == 2

    def test_long_idle_then_full_burst_only(self, clock):
        rl = RateLimiter(rate=0.1, burst=4, clock=clock)
        clock.advance(1000.0)
        acquired = sum(rl.try_acquire() for _ in range(20))
        assert acquired == 4

    def test_capping_preserves_future_refill(self, clock):
        rl = RateLimiter(rate=1.0, burst=2, clock=clock)
        clock.advance(50.0)  # capped at 2 tokens
        assert rl.try_acquire() is True
        assert rl.try_acquire() is True
        # Bucket was at cap; next token should arrive after exactly 1s,
        # not instantly from leftover "overflow".
        clock.advance(0.9)
        assert rl.try_acquire() is False
        clock.advance(0.1)
        assert rl.try_acquire() is True


class TestDefaultClock:
    @patch("rate_limiter.time.monotonic", side_effect=[0.0, 0.0, 1.0])
    def test_works_with_default_clock(self, mock_time):
        rl = RateLimiter(rate=1.0, burst=1)
        assert rl.try_acquire() is True
        assert rl.try_acquire() is False
        assert rl.try_acquire() is True