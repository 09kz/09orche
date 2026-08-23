"""Named, reusable subagent personas — a base model plus a fixed system prompt.

A profile bundles a base model alias (from the loaded models.toml catalogue)
with a persona and, optionally, a reasoning level or agent tier override.
Once saved, the orchestrator can call it by name instead of restating the
persona on every call. Storage mirrors config.py's models.toml handling —
same TOML table-of-tables shape, same env-var-then-cwd path resolution — but
a missing file means zero profiles exist yet, not an error, since profiles
are created at runtime rather than shipped.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from orche.config import AGENT_TIERS, ConfigError, validate_alias_name
from orche.reasoning import VALID_EFFORTS


@dataclass(frozen=True)
class Profile:
    name: str
    base_alias: str
    system_prompt: str
    reasoning_effort: str | None = None
    agent_tools: str | None = None  # overrides the base model's tier, if set


def _resolve_path() -> Path:
    env_path = os.environ.get("ORCHE_PROFILES_PATH")
    if env_path:
        return Path(env_path)
    return Path.cwd() / "profiles.toml"


def load_profiles(path: Path | None = None) -> dict[str, Profile]:
    """Load and validate saved profiles. A missing file means no profiles yet."""
    resolved = path if path is not None else _resolve_path()
    if not resolved.is_file():
        return {}

    try:
        data = resolved.read_bytes()
    except OSError as e:
        raise ConfigError(f"could not read {resolved}: {e}") from e

    try:
        raw = tomllib.loads(data.decode("utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"invalid TOML in {resolved}: {e}") from e

    profiles_section = raw.get("profiles", {})
    if not isinstance(profiles_section, dict):
        raise ConfigError(f"{resolved}: [profiles] must be a table")

    profiles: dict[str, Profile] = {}
    for name, entry in profiles_section.items():
        validate_alias_name(name)
        if not isinstance(entry, dict):
            raise ConfigError(f"profiles.{name} must be a table")
        if "base_alias" not in entry or not isinstance(entry["base_alias"], str):
            raise ConfigError(f"profiles.{name} is missing a string 'base_alias'")
        if "system_prompt" not in entry or not isinstance(entry["system_prompt"], str):
            raise ConfigError(f"profiles.{name} is missing a string 'system_prompt'")

        reasoning_effort = entry.get("reasoning_effort")
        if reasoning_effort is not None and reasoning_effort not in VALID_EFFORTS:
            raise ConfigError(
                f"profiles.{name}.reasoning_effort must be one of {VALID_EFFORTS} "
                f"(got {reasoning_effort!r})"
            )

        agent_tools = entry.get("agent_tools")
        if agent_tools is not None and agent_tools not in AGENT_TIERS:
            raise ConfigError(
                f"profiles.{name}.agent_tools must be one of {AGENT_TIERS} "
                f"(got {agent_tools!r})"
            )

        profiles[name] = Profile(
            name=name,
            base_alias=entry["base_alias"],
            system_prompt=entry["system_prompt"].strip(),
            reasoning_effort=reasoning_effort,
            agent_tools=agent_tools,
        )

    return profiles


def _toml_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _render(profiles: dict[str, Profile]) -> str:
    lines = []
    for profile in profiles.values():
        lines.append(f"[profiles.{profile.name}]")
        lines.append(f'base_alias = "{_toml_escape(profile.base_alias)}"')
        lines.append(f'system_prompt = "{_toml_escape(profile.system_prompt)}"')
        if profile.reasoning_effort is not None:
            lines.append(f'reasoning_effort = "{profile.reasoning_effort}"')
        if profile.agent_tools is not None:
            lines.append(f'agent_tools = "{profile.agent_tools}"')
        lines.append("")
    return "\n".join(lines)


def save_profile(profile: Profile, path: Path | None = None) -> None:
    """Upsert `profile` into the profiles file, creating it if needed."""
    resolved = path if path is not None else _resolve_path()
    existing = load_profiles(resolved)
    existing[profile.name] = profile
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(_render(existing), encoding="utf-8")
