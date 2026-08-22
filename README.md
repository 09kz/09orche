# Conclave

Expose OpenRouter models as tools inside Claude Code, so your orchestrator can
delegate work to them without leaving your Anthropic subscription.

## The problem this solves

Claude Code talks to exactly one API endpoint. Pointing `ANTHROPIC_BASE_URL` at
OpenRouter reroutes *everything* — including the orchestrator itself — so there's
no way to run "Sonnet plans, a free model executes" through configuration alone.

Conclave takes a different route: it doesn't touch the endpoint. It's an MCP
server that wraps OpenRouter's chat completions API as a set of tools
(`ask_ox_alpha`, `ask_glm`, …). Claude Code keeps talking to Anthropic as usual,
and calls out to Conclave's tools whenever it — or you — decides that's useful.

This isn't the same as a native Claude Code subagent: these tools don't see your
files or your repo. They take a prompt, return text. That covers most of what
people actually want from a second model: a second opinion, boilerplate
generation, working through a long document, a different eye on a piece of code.

## Install

```bash
uvx conclave-mcp
```

or add it straight to Claude Code:

```bash
claude mcp add conclave -s user \
  -e "OPENROUTER_API_KEY=your-key-here" \
  -- uvx conclave-mcp
```

Get a key at [openrouter.ai/settings/keys](https://openrouter.ai/settings/keys).
The bundled model catalogue is entirely free-tier — no OpenRouter spend required
to use it as shipped.

Restart Claude Code (or run `claude mcp list` to confirm the server shows
`Connected`) and the tools are available.

## Usage

Ask directly:

> Use ask_ox_alpha to review this function for edge cases.

Or let Claude decide — each tool's description tells it what the model is good
for, so it can pick on its own when a request calls for it.

`list_models` is always available and reports the current catalogue: aliases,
OpenRouter ids, and configured fallbacks.

## Configuring your own models

The bundled catalogue lives in `models.toml`. Override it by placing your own
`models.toml` in your working directory, or by pointing an environment variable
at any file:

```bash
export CONCLAVE_MODELS_PATH=/path/to/your/models.toml
```

Each entry becomes a tool named `ask_<alias>`:

```toml
[models.my_model]
id = "some-provider/some-model"
description = "What this model is good for — Claude reads this to decide when to use it."
fallback = "another_alias"  # optional: retried if this model's calls exhaust retries
```

Verify a model id against
[openrouter.ai/api/v1/models](https://openrouter.ai/api/v1/models) before adding
it — OpenRouter's catalogue changes.

## Reliability

Free-tier models share upstream rate limits, so a 429 is an expected outcome, not
a bug. Conclave retries transient failures (429, 5xx) with exponential backoff,
and falls through to a model's configured `fallback` once retries are exhausted.

## Development

```bash
git clone https://github.com/09kz/conclave
cd conclave
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
pytest
ruff check src tests
mypy src
```

### Why the dependency pins

`mcp` is pinned to `1.9.4` and `pydantic-settings` to `<2.7`. Newer
`pydantic-settings` raises an `IncompleteFieldDefinitionWarning` at import time
that FastMCP turns into a silent startup failure — it shows up only as
`CONNECTION_CLOSED` in `claude mcp list`, with nothing on stderr. `mcp` 2.x
negotiates protocol `2025-11-25`, which Claude Code does not yet accept. Don't
bump either without confirming Claude Code speaks the newer protocol first.

## License

MIT — see [LICENSE](LICENSE).
