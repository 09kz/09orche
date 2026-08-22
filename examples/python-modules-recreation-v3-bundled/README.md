# Test 3b: same task, bundled module+tests per call — the case that actually wins

Same underlying task as the original test and test 3a (LRU cache + token-
bucket rate limiter, each with tests), one more variable changed: each
parallel call now generates a module **and its own tests together**, so
there's no cross-call API drift. Two independent, genuinely unrelated
modules run in parallel — that's the axis this project's tool can actually
help with; splitting a module from its own tests (test 3a) is not.

`reasoning_effort="low"` kept from test 3a.

## Result: 88.61s wall clock, 12/12 tests passed, zero manual fixes

```
============================= test session starts =============================
collected 12 items

test_lru_cache.py ......                                                 [ 50%]
test_rate_limiter.py ......                                              [100%]

============================== 12 passed in 0.12s ==============================
```

`lru_cache` (with tests) took 22.83s; `rate_limiter` (with tests) took
88.45s — again the slower of the two, consistent with test 3a's outlier
call being on the same task. `asyncio.gather` waits for the slower one, so
total wall clock ≈ the rate limiter call's time, not the sum of both.

## Compared to the original, real, human-run baseline

| | Solo Sonnet 5 (original test, real Desktop session) | Delegated, bundled (this test) |
|---|---|---|
| Wall clock | ~300s (~5 min) | **88.61s (~1.5 min)** |
| Verified? | Yes — 26/26 pytest, real run | Yes — 12/12 pytest, real run |
| Manual fixes needed | 0 | 0 |

**This is the real use case the project was looking for:** two genuinely
independent modules, each generated together with its own tests in a single
call (no cross-call API drift), dispatched in parallel with a correctly-set
`reasoning_effort`. ~3.4x faster than solo, and it actually passed on the
first try.

**What made this the winning configuration, that the earlier attempts
didn't have:**
1. `reasoning_effort="low"` set explicitly (test 1 didn't have this at all).
2. Bundling a module with its own tests in one call, instead of splitting
   them into separate parallel calls (test 3a had this exact split and
   failed integration).
3. The two parallel branches (LRU cache, rate limiter) are genuinely
   unrelated — no shared state or API between them to drift apart.

This is a narrower use case than "any parallelizable task" — it needs pieces
that are both substantial (large enough that a free-tier round trip beats
Sonnet doing it directly — see `../parallel-summarization` for a case where
the pieces were too small for that to hold) and self-contained (no shared
API surface between them, or all of that surface generated together in one
call).
