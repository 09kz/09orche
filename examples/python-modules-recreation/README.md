# Test 1: the original comparison (two real Claude Code Desktop sessions)

The first test in this series, run manually — not automated — in two
separate Claude Code Desktop windows with Sonnet 5, given the exact same
task: write `lru_cache.py` (thread-safe LRU cache) and `rate_limiter.py`
(token-bucket rate limiter), each with pytest tests.

`sonnet5/` — solo, no delegation. `sonnet5-orche/` — delegated both
modules to `ask_ox_alpha` in a single parallel batch (two tool calls, one
message).

## Result: solo won, ~3x

| | Solo (`sonnet5/`) | Delegated (`sonnet5-orche/`) |
|---|---|---|
| Wall clock | ~5 min | ~15 min |
| Lines produced | 514 | 413 |
| Verified? | Yes — 26/26 pytest, real run | No — environment had no working `python` on PATH; hand-traced instead |
| Manual fixes needed | 0 | 2 (a leftover nonsense expression, a bogus test assertion) |

Where the ~10 extra minutes actually went (from the session transcripts, not
guessed): the first `ask_ox_alpha` attempt failed outright — the model spent
its whole reply on visible chain-of-thought and got cut off before emitting
any code, for both parallel calls at once. The retry (with
`reasoning_effort="low"` and a stricter "code only" instruction) succeeded,
but that first attempt was a fully wasted round trip. On top of that, the
orchestrator had to review and fix two real bugs in what came back —
verification cost that's easy to forget about when reasoning abstractly
about "parallel dispatch should be faster."

See `../python-modules-recreation-v2-fixed` (retries with the
`reasoning_effort` fix applied from the start, but the same impl/test
task-split as here) and `../python-modules-recreation-v3-bundled` (the
configuration that actually won).
