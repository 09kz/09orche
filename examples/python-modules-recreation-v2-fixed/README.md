# Test 3a: same code task, but with the known reasoning_effort fix — split 4 ways

Re-run of `../python-modules-recreation`'s task (LRU cache + rate limiter,
each with tests), this time with `reasoning_effort="low"` set from the start
to avoid the truncation failure diagnosed in the original test (ox_alpha
burning its whole reply on visible chain-of-thought before emitting code).

**Split:** 4 fully independent parallel `ask_ox_alpha` calls — one for
`lru_cache.py`, one for `test_lru_cache.py`, one for `rate_limiter.py`, one
for `test_rate_limiter.py`. Each call saw only its own task description, not
the other three calls' output.

**Result: 111.21s wall clock, but 19/19 tests failed on first run.**

One call (`rate_limiter.py`) alone took 111.04s — a massive outlier next to
the other three (8.5–40.6s), most likely an upstream 429/retry on ox_alpha's
free tier. Since `asyncio.gather` waits for the slowest call, that one
request set the floor for the whole batch.

Worse than the timing: the four independently-generated files didn't agree
with each other. `rate_limiter.py` defined a class named `TokenBucket`;
`test_rate_limiter.py` (generated in the same batch, with no visibility into
what the implementation call had actually produced) imported `RateLimiter`
and expected an injectable `clock` constructor argument that the
implementation never got. `lru_cache.py`'s constructor didn't match what
`test_lru_cache.py` expected either. A single alias fix
(`RateLimiter = TokenBucket`) was not enough — the two files had genuinely
diverged on API shape, not just naming.

**Takeaway:** splitting an implementation from its own tests into two
context-isolated parallel calls is fragile. Even an explicit, matching
prompt for both doesn't guarantee the two models converge on the same API —
there's no shared source of truth between them. See `../python-modules-recreation-v3-bundled`
for the fix: bundle a module and its tests into one call.
