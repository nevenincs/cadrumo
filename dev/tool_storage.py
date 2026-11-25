"""Development tool storage: where external tools keep their caches, configuration and logs.

These locations belong to the repository's developer tooling, never to the product. The
product places every location beneath its one storage root; a developer's pip, npm, Cargo,
Ruff or Homebrew cache may be moved by its own variable, and this module resolves that variable
beneath the same root when it is relative.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from cadrumo.core.storage_environment import resolve_storage_path

TOOL_STORAGE_LOCATIONS: Mapping[str, tuple[str, str]] = {
    "PIP_CACHE_DIR": ("CADRUMO_PIP_CACHE_DIR", "development/cache/pip"),
    "npm_config_cache": ("CADRUMO_NPM_CACHE_DIR", "development/cache/npm"),
    "CARGO_HOME": ("CADRUMO_CARGO_HOME", "development/cache/cargo"),
    "CARGO_TARGET_DIR": ("CADRUMO_CARGO_TARGET_DIR", "development/build/cargo"),
    "PYTHONPYCACHEPREFIX": ("CADRUMO_PYTHON_CACHE_DIR", "development/cache/pycache"),
    "XDG_CACHE_HOME": ("CADRUMO_TOOL_CACHE_DIR", "development/cache/tools"),
    "XDG_CONFIG_HOME": ("CADRUMO_TOOL_CONFIG_DIR", "development/config/tools"),
    "XDG_DATA_HOME": ("CADRUMO_TOOL_DATA_DIR", "development/data/tools"),
    "XDG_STATE_HOME": ("CADRUMO_TOOL_STATE_DIR", "development/state/tools"),
    "RUFF_CACHE_DIR": ("CADRUMO_RUFF_CACHE_DIR", "development/cache/ruff"),
    "HOMEBREW_CACHE": ("CADRUMO_HOMEBREW_CACHE_DIR", "development/cache/homebrew"),
    "HOMEBREW_LOGS": ("CADRUMO_HOMEBREW_LOGS_DIR", "development/logs/homebrew"),
    "HOMEBREW_TEMP": ("CADRUMO_HOMEBREW_TEMP_DIR", "tmp/homebrew"),
}


def storage_directory(environment_variable: str, default: str, *, root: Path | None = None) -> Path:
    """Resolve one tool-location override; blank values use the default beneath the storage root."""
    return resolve_storage_path(os.environ.get(environment_variable, "").strip() or default, root=root)


def tool_storage_environment() -> dict[str, str]:
    """Bind external tool caches and bytecode to shared, overrideable storage."""
    return {
        native: str(storage_directory(variable, default))
        for native, (variable, default) in TOOL_STORAGE_LOCATIONS.items()
    }
