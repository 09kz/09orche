# Test 2: parallel document summarization

**Hypothesis going in:** fan-out summarization of independent documents should
favor parallel delegation — large per-branch generation cost, low
verification stakes (a mediocre summary is still useful, unlike buggy code).

**Setup:** 4 real, independently-sourced READMEs (444–2099 words) from
competitor MCP servers found earlier in this project's own research
(th3nolo/openrouter-mcp, Wally-Ahmed/openrouter-subagents,
physics91/openrouter-mcp, stabgan/openrouter-mcp-multimodal). Same task both
arms: a ~100–150 word structured brief per document (what it does, tools,
notable details, license).

**Solo** (`sonnet5/`): read and summarized all 4 sequentially, no delegation.
**~20.4s** wall clock (18:17:33.667 → 18:17:54.046).

**Delegated** (`sonnet5-orche/`): 4 parallel `ask_ox_alpha` calls
(`reasoning_effort="low"`, avoiding the truncation failure mode found in
test 1), one per document, via `asyncio.gather`.
**41.26s** wall clock — dominated by one call (doc1, ironically the
*shortest* document) that alone took 41.26s while the other three finished
in 8.5–10.6s. Sequential delegation would have taken ~70.6s (sum of all
four), so parallelism *did* work — ~1.7x faster than it would have been
serial — but that's still ~2x slower than just doing it myself.

## Result: solo won, ~2x

Not what the hypothesis predicted. The reason: **per-call latency variance on
free-tier OpenRouter dominates for short-to-medium tasks.** A 444-word README
took longer to summarize than a 2099-word one — content length wasn't the
bottleneck, network/queue variance was. Parallel execution helps only to the
extent it hides that variance behind the *slowest* call; it can't make the
slowest call itself faster.

**Takeaway:** fan-out delegation needs each individual piece of work to be
*substantial* enough that Sonnet doing it directly would take longer than a
free-tier round trip (which can itself be 10–40+ seconds, unpredictably).
Four ~500-word summaries don't clear that bar. See test 3b for a case that
does.
