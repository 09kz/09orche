from rate_limiter import RateLimiter


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def test_burst_capacity_allows_initial_burst():
    clock = FakeClock()
    rl = RateLimiter(rate=10, burst=5, clock=clock)
    acquired = [rl.try_acquire() for _ in range(5)]
    assert all(acquired)
    assert not rl.try_acquire()


def test_empty_bucket_rejects_immediately():
    clock = FakeClock()
    rl = RateLimiter(rate=10, burst=1, clock=clock)
    assert rl.try_acquire()
    assert not rl.try_acquire()


def test_refill_over_time():
    clock = FakeClock()
    rl = RateLimiter(rate=2, burst=2, clock=clock)  # 1 token per 0.5s
    assert rl.try_acquire()
    assert rl.try_acquire()
    assert not rl.try_acquire()

    clock.advance(0.25)
    assert not rl.try_acquire()  # only half a token accrued

    clock.advance(0.25)
    assert rl.try_acquire()      # one full token now
    assert not rl.try_acquire()


def test_capacity_capping_no_unbounded_accumulation():
    clock = FakeClock()
    rl = RateLimiter(rate=10, burst=3, clock=clock)
    # Drain the bucket
    for _ in range(3):
        assert rl.try_acquire()

    # Wait far longer than needed to refill; tokens must cap at burst
    clock.advance(1000)

    acquired = [rl.try_acquire() for _ in range(10)]
    assert acquired == [True, True, True] + [False] * 7


def test_partial_refill_does_not_leak_across_calls():
    clock = FakeClock()
    rl = RateLimiter(rate=1, burst=1, clock=clock)
    assert rl.try_acquire()
    clock.advance(0.4)
    assert not rl.try_acquire()   # rejected call must not consume partial token
    clock.advance(0.6)
    assert rl.try_acquire()       # full second elapsed -> exactly one token
