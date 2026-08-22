"""Load and validate the model catalogue from models.toml."""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, replace
from importlib import resources
from pathlib import Path

ALIAS_RE_MSG = "aliases must match [a-z][a-z0-9_]* (got {alias!r})"
AGENT_TIERS = ("read", "read_write", "full")


@dataclass(frozen=True)
class ModelSpec:
    alias: str
    id: str
    description: str
    fallback: str | None = None
    max_tokens: int | None = None
    agent_tools: str | None = None  # one of AGENT_TIERS, or None = agent mode off


class ConfigError(Exception):
    """Raised when models.toml is missing or malformed."""


def _candidate_paths() -> list[Path]:
    candidates = []
    if env_path := os.environ.get("CONCLAVE_MODELS_PATH"):
        candidates.append(Path(env_path))
    candidates.append(Path.cwd() / "models.toml")
    return candidates


def _find_config_path() -> Path | None:
    for path in _candidate_paths():
        if path.is_file():
            return path
    return None


def _load_raw(path: Path | None) -> dict:
    if path is not None:
        try:
            data = path.read_bytes()
        except OSError as e:
            raise ConfigError(f"could not read {path}: {e}") from e
    else:
        # fall back to the bundled default catalogue
        ref = resources.files("conclave").joinpath("models.toml")
        data = ref.read_bytes()

    try:
        return tomllib.loads(data.decode("utf-8"))
    except tomllib.TOMLDecodeError as e:
        source = path if path is not None else "bundled models.toml"
        raise ConfigError(f"invalid TOML in {source}: {e}") from e


def _validate_alias(alias: str) -> None:
    if not alias or not alias.replace("_", "a").isalnum() or not alias[0].isalpha():
        raise ConfigError(ALIAS_RE_MSG.format(alias=alias))
    if not alias.islower():
        raise ConfigError(ALIAS_RE_MSG.format(alias=alias))


def load_models(path: Path | None = None) -> dict[str, ModelSpec]:
    """Load and validate the model catalogue.

    Resolution order when `path` is not given explicitly:
    1. `CONCLAVE_MODELS_PATH` env var
    2. `./models.toml` in the current working directory
    3. the catalogue bundled with the package

    If `CONCLAVE_AGENT_MODE` is set (to "read", "read_write", or "full"), it
    turns on agent mode at that tier for every model that doesn't already set
    its own `agent_tools` — a one-variable way to make the whole catalogue
    agent-capable without editing models.toml.
    """
    resolved = path if path is not None else _find_config_path()
    raw = _load_raw(resolved)

    models_section = raw.get("models")
    if not isinstance(models_section, dict) or not models_section:
        source = resolved if resolved is not None else "bundled models.toml"
        raise ConfigError(f"{source} has no [models.*] entries")

    specs: dict[str, ModelSpec] = {}
    for alias, entry in models_section.items():
        _validate_alias(alias)
        if not isinstance(entry, dict):
            raise ConfigError(f"models.{alias} must be a table")
        if "id" not in entry or not isinstance(entry["id"], str):
            raise ConfigError(f"models.{alias} is missing a string 'id'")
        if "description" not in entry or not isinstance(entry["description"], str):
            raise ConfigError(f"models.{alias} is missing a string 'description'")
        fallback = entry.get("fallback")
        if fallback is not None and not isinstance(fallback, str):
            raise ConfigError(f"models.{alias}.fallback must be a string alias")

        max_tokens = entry.get("max_tokens")
        if max_tokens is not None and (not isinstance(max_tokens, int) or max_tokens <= 0):
            raise ConfigError(f"models.{alias}.max_tokens must be a positive integer")

        agent_tools = entry.get("agent_tools")
        if agent_tools is not None and agent_tools not in AGENT_TIERS:
            raise ConfigError(
                f"models.{alias}.agent_tools must be one of {AGENT_TIERS} (got {agent_tools!r})"
            )

        specs[alias] = ModelSpec(
            alias=alias,
            id=entry["id"],
            description=entry["description"].strip(),
            fallback=fallback,
            max_tokens=max_tokens,
            agent_tools=agent_tools,
        )

    for spec in specs.values():
        if spec.fallback is not None and spec.fallback not in specs:
            raise ConfigError(
                f"models.{spec.alias}.fallback references unknown alias {spec.fallback!r}"
            )
        if spec.fallback == spec.alias:
            raise ConfigError(f"models.{spec.alias}.fallback cannot reference itself")

    specs = _apply_agent_mode_override(specs)
    return specs


def _apply_agent_mode_override(specs: dict[str, ModelSpec]) -> dict[str, ModelSpec]:
    """CONCLAVE_AGENT_MODE, if set, turns on agent mode at that tier for every
    model that doesn't already set its own `agent_tools` in models.toml. A
    per-model setting always wins over the blanket flag.
    """
    override = os.environ.get("CONCLAVE_AGENT_MODE")
    if override is None:
        return specs
    if override not in AGENT_TIERS:
        raise ConfigError(
            f"CONCLAVE_AGENT_MODE must be one of {AGENT_TIERS} (got {override!r})"
        )
    return {
        alias: spec if spec.agent_tools is not None else replace(spec, agent_tools=override)
        for alias, spec in specs.items()
    }


def load_models_or_exit() -> dict[str, ModelSpec]:
    try:
        return load_models()
    except ConfigError as e:
        print(f"conclave: configuration error: {e}", file=sys.stderr)
        raise SystemExit(1) from e
