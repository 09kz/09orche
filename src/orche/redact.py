"""Best-effort secret redaction before text leaves this machine for OpenRouter.

Idea borrowed from Wally-Ahmed's openrouter-subagents
(https://github.com/Wally-Ahmed/openrouter-subagents), which redacts likely
secrets from outgoing requests. This is a safety net for recognizable secret
shapes — not a guarantee, and not a substitute for keeping real secrets out of
prompts and agent-mode workspaces in the first place.
"""

import re

_PATTERNS = [
    re.compile(r"sk-or-v1-[a-f0-9]{40,}"),  # OpenRouter API keys
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),  # Anthropic API keys
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # generic OpenAI-style secret keys
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),  # GitHub tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key IDs
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),  # Slack tokens
    re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
        r"[\s\S]+?"
        r"-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    ),
]

_REDACTED = "[REDACTED]"


def redact(text: str) -> str:
    """Replace recognizable secret shapes in `text` with a placeholder."""
    for pattern in _PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text
