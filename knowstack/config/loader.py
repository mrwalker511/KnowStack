"""Locate and load knowstack.toml configuration, merging CLI overrides."""
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from .schema import KnowStackConfig

_CONFIG_FILENAMES = ("knowstack.toml", ".knowstack.toml")


def _find_config_file(start: Path) -> Path | None:
    """Walk upward from start until a config file is found."""
    current = start.resolve()
    for _ in range(10):  # max 10 levels up
        for name in _CONFIG_FILENAMES:
            candidate = current / name
            if candidate.is_file():
                return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def load_config(
    repo_path: Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> KnowStackConfig:
    """Load configuration from file + apply overrides.

    Priority (highest first): CLI overrides → knowstack.toml → defaults.
    """
    start = (repo_path or Path(".")).resolve()
    config_file = _find_config_file(start)

    raw: dict[str, Any] = {}
    if config_file is not None:
        with open(config_file, "rb") as fh:
            raw = tomllib.load(fh)

    if overrides:
        raw.update({k: v for k, v in overrides.items() if v is not None})

    config = KnowStackConfig(**raw)
    return config.resolve_paths(start)
