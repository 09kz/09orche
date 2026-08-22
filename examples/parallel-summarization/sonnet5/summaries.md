# Solo Sonnet 5 summaries (no delegation)

Wall clock: ~20.4s (18:17:33.667 -> 18:17:54.046)

## doc1 — th3nolo/openrouter-mcp

Node.js/TypeScript MCP server giving access to 400+ OpenRouter models. Four
tools: `list_models`, `chat_with_model`, `compare_models`, `get_model_info` —
pure pass-through, no file/shell access, no agent mode. Three MCP resources
expose the model list, pricing, and usage stats. Standard `npm install`+
`build` setup, key in `.env`. MIT.

## doc2 — Wally-Ahmed/openrouter-subagents

MCP server + CLI with a single `ask_openrouter` tool, defaulting to
`openrouter/fusion` (a model panel plus a synthesizing judge). Full
`reasoning` control (levels `none`->`max`, token budgets), best-effort secret
redaction before requests leave the machine. Ships a CLI mode that bypasses
JSON-RPC for cheaper shell-based delegation. Ready-made orchestration
playbooks (`two-layer-cross-model-expert`, `worker-orchestrator`) read from
disk at call time. No file/shell access for the model itself. MIT.

## doc3 — physics91/openrouter-mcp

Node.js MCP server with secure key storage (OS keychain / encrypted file),
"collective intelligence" tools (consensus, ensemble reasoning, adaptive
routing), and a heavy DevOps pipeline (ruff/black/isort, pytest, pre-commit
hooks enforcing Conventional Commits). Requires both Node and Python on
PATH. No mention of file/shell access for the model. License not stated
directly in the README (points to a LICENSE file).

## doc4 — stabgan/openrouter-mcp-multimodal

The most built-out of the four — 14 tools, full multimodal support
(text/image/audio/video, both analysis and generation: Veo, Sora, Seedance).
Input/output path sandboxing (`OPENROUTER_INPUT_DIR`/`OUTPUT_DIR`), SSRF
protection, 650+ tests. Distributed via npm, pip/uvx, Docker, GHCR, and
Smithery — the widest distribution of the four. Apache 2.0.
