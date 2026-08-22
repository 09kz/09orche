# Solo orchestrator vs. orchestrator + subagents: four experiments

The question behind all four: when does delegating to `ask_ox_alpha` /
`agent_ox_alpha` actually make an orchestrator *faster*, not just cheaper?
Parallel dispatch alone doesn't guarantee it — these experiments look for
where the real crossover point is.

| # | Experiment | Result | Winner |
|---|---|---|---|
| 1 | [python-modules-recreation](python-modules-recreation) | Two real, separate Claude Code Desktop sessions (not automated). Solo: 5 min, 514 lines, 26/26 tests verified. Delegated: ~15 min, 413 lines, couldn't verify (broken `pytest` on PATH), needed manual bug fixes, one failed retry round-trip. | **Solo**, decisively |
| 2 | [parallel-summarization](parallel-summarization) | Fan-out summarization of 4 real README files, chosen to favor parallelism (large content, low verification stakes). Solo: ~20s. Delegated (4-way parallel): 41s, dominated by one slow call. | **Solo**, ~2x |
| 3a | [python-modules-recreation-v2-fixed](python-modules-recreation-v2-fixed) | Retry of #1's task with the known `reasoning_effort` fix applied, split 4 ways (impl and tests as separate parallel calls). 111s wall clock, but 19/19 tests failed — the independently-generated impl and test files disagreed on the API. | **Neither** — broken output |
| 3b | [python-modules-recreation-v3-bundled](python-modules-recreation-v3-bundled) | Same task, `reasoning_effort` fix kept, but module+tests bundled into one call per module (2-way parallel across genuinely independent modules). **88.6s, 12/12 tests passed, zero manual fixes.** | **Delegated, ~3.4x faster** than #1's solo baseline |

## The actual crossover condition

Three failed attempts before finding a real win narrows it down further than
"parallelize independent work" — that framing alone produced two losses
(#2, #3a) before #3b's specific combination worked:

1. **Each piece has to be substantial enough that a free-tier round trip
   (10–110s, wildly variable) beats Sonnet just doing it directly.** #2's
   pieces (short README summaries) never cleared that bar — solo was faster
   even with real parallelism, because per-call network/queue variance
   dominated actual content-length-driven work.
2. **Set `reasoning_effort` explicitly for code generation.** Without it
   (test #1), a reasoning-capable free model can burn its entire token
   budget on visible chain-of-thought and return no code at all.
3. **Never split an implementation from its own tests across independent
   calls.** #3a proved this concretely: matching, explicit prompts for both
   halves still weren't enough to keep two isolated model calls converging
   on the same class name, constructor signature, or injected dependencies.
   Bundle anything that shares an API surface into one call; only
   parallelize across pieces that are genuinely independent of each other.

None of this generalizes from a handful of runs into a hard rule — free-tier
model latency in particular varied by an order of magnitude between calls in
these same experiments (`rate_limiter`'s generation took 8.5s once and 111s
another time, same prompt, same model). Treat the *shape* of the finding as
reliable, the exact numbers as one data point.
