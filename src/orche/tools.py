"""Sandboxed tools an agent-mode model may call, scoped to one workspace root."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

MAX_READ_BYTES = 200_000
MAX_GREP_MATCHES = 200
MAX_SHELL_OUTPUT = 20_000
SHELL_TIMEOUT_S = 60

DENY_NAMES = {".env", ".git", "id_rsa", "id_ed25519", ".ssh"}

TIERS = ("read", "read_write", "full")


class SandboxError(Exception):
    """A tool call tried to escape the workspace, or hit a denied path."""


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: str


def _resolve_in_workspace(workspace: Path, relative: str) -> Path:
    candidate = (workspace / relative).resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError as e:
        raise SandboxError(f"path {relative!r} escapes the workspace root") from e
    if any(part in DENY_NAMES for part in candidate.parts):
        raise SandboxError(f"path {relative!r} touches a denied name")
    return candidate


def read_file(workspace: Path, path: str) -> ToolResult:
    target = _resolve_in_workspace(workspace, path)
    if not target.is_file():
        return ToolResult(False, f"not a file: {path}")
    data = target.read_bytes()
    truncated = len(data) > MAX_READ_BYTES
    text = data[:MAX_READ_BYTES].decode("utf-8", errors="replace")
    if truncated:
        text += f"\n\n[truncated, file is {len(data)} bytes]"
    return ToolResult(True, text)


def list_dir(workspace: Path, path: str = ".") -> ToolResult:
    target = _resolve_in_workspace(workspace, path)
    if not target.is_dir():
        return ToolResult(False, f"not a directory: {path}")
    entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name))
    lines = [f"{'d' if e.is_dir() else 'f'}  {e.name}" for e in entries]
    return ToolResult(True, "\n".join(lines) or "(empty)")


def grep(workspace: Path, pattern: str, path: str = ".") -> ToolResult:
    import re

    target = _resolve_in_workspace(workspace, path)
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return ToolResult(False, f"invalid regex: {e}")

    files = [target] if target.is_file() else list(target.rglob("*"))
    matches: list[str] = []
    for f in files:
        if len(matches) >= MAX_GREP_MATCHES:
            break
        if not f.is_file() or any(part in DENY_NAMES for part in f.parts):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if rx.search(line):
                rel = f.relative_to(workspace)
                matches.append(f"{rel}:{i}: {line.strip()[:200]}")
                if len(matches) >= MAX_GREP_MATCHES:
                    break

    if not matches:
        return ToolResult(True, "(no matches)")
    return ToolResult(True, "\n".join(matches))


def write_file(workspace: Path, path: str, content: str) -> ToolResult:
    target = _resolve_in_workspace(workspace, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return ToolResult(True, f"wrote {len(content)} chars to {path}")


def run_shell(workspace: Path, command: str) -> ToolResult:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=SHELL_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(False, f"command timed out after {SHELL_TIMEOUT_S}s")

    out = (proc.stdout or "") + (proc.stderr or "")
    if len(out) > MAX_SHELL_OUTPUT:
        out = out[:MAX_SHELL_OUTPUT] + "\n[truncated]"
    return ToolResult(proc.returncode == 0, out or f"(exit {proc.returncode}, no output)")


# JSON-schema tool definitions, keyed by the tier that unlocks them.
_READ_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file relative to the workspace root.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List entries in a directory relative to the workspace root.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "default": "."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search for a regex pattern across files under a path in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                },
                "required": ["pattern"],
            },
        },
    },
]

_WRITE_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Overwrite a file relative to the workspace root with given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
]

_SHELL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a shell command with the workspace root as the working directory.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]

_HANDLERS: dict[str, Callable[..., ToolResult]] = {
    "read_file": read_file,
    "list_dir": list_dir,
    "grep": grep,
    "write_file": write_file,
    "run_shell": run_shell,
}

# Which tools each tier is actually permitted to run — enforced in dispatch(),
# independently of which schemas were advertised to the model. Advertising
# controls what the model is told about; this controls what can happen if it
# calls something else anyway.
_TIER_TOOLS = {
    "read": {"read_file", "list_dir", "grep"},
    "read_write": {"read_file", "list_dir", "grep", "write_file"},
    "full": {"read_file", "list_dir", "grep", "write_file", "run_shell"},
}


def schemas_for_tier(tier: str) -> list[dict]:
    if tier not in TIERS:
        raise ValueError(f"unknown tier {tier!r}, must be one of {TIERS}")
    schemas = list(_READ_SCHEMAS)
    if tier in ("read_write", "full"):
        schemas += _WRITE_SCHEMAS
    if tier == "full":
        schemas += _SHELL_SCHEMAS
    return schemas


def dispatch(workspace: Path, tier: str, name: str, arguments: dict) -> ToolResult:
    if tier not in TIERS:
        raise ValueError(f"unknown tier {tier!r}, must be one of {TIERS}")
    if name not in _TIER_TOOLS[tier]:
        return ToolResult(False, f"tool {name!r} is not permitted at tier {tier!r}")
    handler = _HANDLERS[name]
    try:
        return handler(workspace, **arguments)
    except SandboxError as e:
        return ToolResult(False, str(e))
    except TypeError as e:
        return ToolResult(False, f"bad arguments for {name}: {e}")
