---
name: subagent-orchestration
description: Delegate work to 09orche tools, decide when a reusable profile is worth creating, and verify subagent output without a rigid mandatory pipeline. Use when the user asks to delegate a task to another model, create a subagent persona, or set up a multi-model workflow.
---

# Orchestrating subagents with 09orche

You are the orchestrator. This project's MCP tools (`ask_<alias>`,
`agent_<alias>`, and the profile tools below) give you access to other
models as subagents — text in, text out for `ask_*`; real sandboxed file and
shell access, scoped to one workspace directory, for `agent_*`. This skill is
about *when* and *how* to use them well, not what the tools do — see the
project README for that.

## One-off delegation vs. a saved profile

For a single task, just call the tool directly with an inline `system_prompt`:

```
ask_ox_alpha(prompt="...", system_prompt="You are a terse code reviewer. Flag only real bugs.")
```

Reach for a **profile** when you'll want the same persona again — across
several calls in this session, or in future sessions on the same project.
Creating one is one call:

```
save_profile(
  name="reviewer",
  base_alias="ox_alpha",
  system_prompt="You are a terse code reviewer. Flag only real bugs, no style nits.",
  agent_tools="read",          # optional: only if this profile needs agent mode
)
```

After that, `ask_profile("reviewer", prompt)` or
`agent_profile("reviewer", prompt, workspace)` reuses the persona without
restating it. Check `list_profiles()` before creating one — it may already
exist from an earlier session.

Don't create a profile for a task you'll only run once. A profile that never
gets reused is just an extra file to maintain.

## Verification is your judgment call, not a mandatory step

This project deliberately does not force every delegated task through an
automatic verifier — that would be slower and often redundant with what you'd
naturally check anyway. Pick the right level for the task:

**Default: review it yourself.** For most delegated work, read the subagent's
output (or its `agent_*` diff/changes) the way you'd review a colleague's
pull request. This is usually enough, and it's cheap. A worked example: two
subagents built a small Conway's Game of Life implementation in a shared
workspace — one wrote the core logic, the other wrote a CLI and tests on top
of it. The second subagent's own tests initially looked fine to a
skim, but running them (as the orchestrator, not trusting the subagent's
self-report) found a real bug: a test assumed a class was iterable when it
wasn't. Actually running the check, not just reading the code, is what caught
it.

**Prefer mechanical verification over another model's opinion, wherever the
task allows it.** If there's a command that can confirm the claim — run the
tests, diff the file against what was asked for, check the exit code — run
it yourself rather than asking a model whether it thinks the work is correct.
An LLM's confidence is not evidence. (This mirrors the trust-gate approach in
[Kayaba-Attribution/claude-cheap-agents](https://github.com/Kayaba-Attribution/claude-cheap-agents):
subagents there must conclude with `EVIDENCE: <command>`, which gets
independently re-run and checked — not taken on the subagent's word.)

**Reach for a dedicated verifier profile when self-review isn't practical** —
the task is large, spans many files, or you want a second, independent read
before committing to it. Two things make a verifier profile actually useful
instead of theater:

- Back it with a **different base model** than the one that did the work.
  Same-model self-review shares the same blind spots; a different model is
  more likely to catch what the first one missed.
- Give it a narrow, specific brief — "check whether this change actually
  does X, list concrete problems with file:line references" — not "is this
  good?". A vague verification prompt gets a vague, unhelpful answer.

```
save_profile(
  name="skeptic",
  base_alias="glm",                     # different model than the one that built it
  system_prompt="You verify other models' work. Be skeptical. Point to specific "
                 "evidence — a failing test, a line of code, a command's actual "
                 "output — not general impressions. If you can't verify a claim, say so.",
  agent_tools="read",
)
```

## When delegating is actually faster (and when it isn't)

Four measured experiments in `examples/` — not speculation — settled this.
Full detail and driver scripts are there; the short version:

- **Solo won twice, ~2-3x, when the delegated pieces were small.** Free-tier
  OpenRouter latency per call ranges roughly 8-110 seconds on the *same*
  model and prompt — wildly variable, and dominated by queueing/network, not
  by how much work the piece actually is. A handful of short README
  summaries lost to solo Sonnet doing them directly, even dispatched in
  parallel, because the round-trip overhead alone exceeded just doing the
  work. **Don't delegate a piece of work small enough that you'd finish it
  yourself before a free-tier call would even return.**
- **Splitting an implementation from its own tests across independent
  parallel calls produced 19 of 19 tests failing** — class names,
  constructor signatures, and injected dependencies drifted apart between
  the two calls despite matching, explicit prompts for both. There is no
  shared source of truth between two isolated model calls; don't assume
  matching instructions are enough.
- **The one case that won decisively (~3.4x, fully verified, zero manual
  fixes): two genuinely independent modules, each generated together with
  its own tests in a single call, dispatched in parallel.** That's the
  actual shape to aim for — substantial, self-contained, independent pieces,
  not just "anything that can theoretically run in parallel."
- `reasoning_effort` set explicitly (see the tool's own description) was the
  difference between a call returning working code and a call burning its
  entire budget on invisible chain-of-thought and returning nothing.

## A minimal end-to-end pattern

1. Decompose the task into pieces that are each substantial and
   self-contained — see above for why small or API-coupled pieces don't
   parallelize well. Anything sharing an API surface (an implementation and
   its own tests, two modules that call into each other) goes in one call,
   not split across several.
2. For each piece, decide: one-off (`ask_*`/`agent_*` with an inline
   `system_prompt`) or a saved profile (recurring role — check
   `list_profiles()` first).
3. Delegate. If pieces genuinely depend on each other (subagent B needs to
   see what subagent A produced), run them in a shared workspace and have B
   start by reading A's output — don't assume B knows the API/shape without
   checking.
4. Verify at the level the task warrants: read it yourself, run a mechanical
   check, or call a dedicated verifier profile — pick one, don't default to
   skipping this step because the subagent said it was done.
5. Integrate and report what you actually found, including anything the
   subagent got wrong. Silently fixing a subagent's mistake without
   mentioning it hides information the user might want.
