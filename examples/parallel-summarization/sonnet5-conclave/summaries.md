# Delegated summaries (4 parallel ask_ox_alpha calls, reasoning_effort=low)

Total wall clock: 41.26s

## doc1 (41.26s — the slowest call, ironically the shortest doc)

**OpenRouter MCP Server** — A Model Context Protocol server exposing
OpenRouter's 400+ AI models (GPT-4, Claude, Gemini, Llama, etc.) through
Claude Desktop and Claude Code.

**Key tools:** `list_models` (with pricing), `chat_with_model` (model,
message, max_tokens, temperature, system_prompt), `compare_models`
(side-by-side multi-model responses), `get_model_info` (context
limits/capabilities).

**Resources:** model listings, pricing data, and usage statistics via
`openrouter://` URIs.

**Technical details:** TypeScript/Node.js; install via npm/yarn with a build
step. Requires an OpenRouter API key stored in `.env`; optional env vars for
base URL, site URL, and app name attribution headers. Integrates via
`claude mcp add` or manual Claude Desktop JSON config. Includes dev scripts
for tests, linting, and type checking. API keys kept out of version control.

**License:** MIT

## doc2 (10.51s)

**openrouter-subagents** — an MCP server and CLI exposing a model-agnostic
"subagent" tool backed by OpenRouter (one API key, any model). Defaults to
`openrouter/fusion`, which runs a panel of models in parallel and has a
judge model synthesize a single answer.

**Key tools/features:**
- `ask_openrouter`: query any OpenRouter model; Fusion-only params for panel
  (`analysis_models`, 1-8) and judge. Full reasoning controls:
  `reasoning_effort` (none->max), exact token budgets, enable/disable,
  exclude reasoning from output, temperature.
- `list_patterns` / `get_pattern`: Markdown orchestration playbooks read at
  call time (e.g., `two-layer-cross-model-expert`, `worker-orchestrator`).
- CLI mirrors the MCP tool with raw-text stdout output; supports piped
  stdin/context files for token-cheap delegation.

**Technical details:** Node 18+, OpenAI-compatible Chat Completions endpoint
with Bearer auth; Fusion config precedence is per-call arg > `.env` default >
OpenRouter preset; ~280s timeout. Agents are instructed to retry failed
calls unchanged rather than downgrade settings. Security: gitignored `.env`,
best-effort secret redaction on outbound text; Fusion fans input to multiple
third-party providers.

**License:** MIT

## doc3 (8.54s)

**OpenRouter MCP Server** (`@physics91/openrouter-mcp`) — an MCP server
exposing OpenRouter models to MCP-compatible clients (Claude Desktop, Claude
Code, VS Code) via local stdio.

**Features**
- MCP tools: chat, vision chat, model listing, usage stats, free-model
  tools/metrics
- Benchmarking and performance comparison suite
- Collective-intelligence tools: consensus, ensemble reasoning, adaptive
  routing, cross-model validation
- Secure API key storage (OS keychain, encrypted file, or .env) with audit
  logging; streaming, caching

**Setup**: `npx @physics91/openrouter-mcp init` then `start`. Requires
Node.js 16+, Python 3.10+ in PATH, and an OpenRouter API key. CLI includes
credential rotation, deletion, security audit, encryption migration, and
one-command client installers (`install-claude`, `install-claude-code`).

**DevOps**: Quality gates use ruff/black/isort plus a Python "assurance"
test runner followed by npm security tests. Publishing is manual via
`npm publish --access public`; pre-commit hooks enforce Conventional
Commits and smoke tests. Vision tools accept base64/URL images only.

**License**: MIT

## doc4 (10.58s)

**OpenRouter MCP Multimodal** — a production-grade Model Context Protocol
(MCP) server (Node.js/TypeScript, stdio) that connects AI coding agents
(Cursor, Claude Desktop, VS Code, Windsurf, Cline) to OpenRouter's unified
LLM API.

**What it does:** Exposes 14 tools covering the full multimodal surface —
chat (`chat_completion` with 300+ models, provider routing, web search,
caching), vision (image analysis/generation), audio (transcription/TTS/
music), video (analysis plus async generation via Veo/Sora/Seedance/Wan
with progress notifications and resumable jobs), and catalog utilities
(model search/validation, document reranking, health check).

**Key technical details:**
- Listed on the official MCP Registry; protocol MCP 2025-06-18; Node >= 20
- Security: input/output path sandboxes, SSRF guards on URL fetches,
  untrusted-content tagging, structured error taxonomy (`_meta.code`); path
  traversal advisory fixed in v4.5.2
- Installable via npx, uvx/pipx (thin Python launcher wrapping npx), npm
  global, Docker Hub/GHCR, Smithery, one-click deeplinks, Claude Code CLI
- Testing: 650+ automated tests (unit/mock/regression) plus live
  integration scenarios; free OpenRouter models work for CI

**License:** Apache 2.0.
