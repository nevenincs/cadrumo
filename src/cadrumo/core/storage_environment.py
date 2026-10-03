"""Import-light storage paths shared by application and development bootstrap."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


def project_root() -> Path:
    """Return the authored repository, or the caller's project for installed code."""
    source = Path(__file__).resolve()
    root = source.parents[3]
    if source == root / "src" / "cadrumo" / "core" / "storage_environment.py" and (root / "pyproject.toml").is_file():
        return root
    return Path.cwd().resolve()


def configured_storage_root(*, environ: Mapping[str, str] | None = None, repository_root: Path | None = None) -> Path:
    """Resolve the storage root, with the local backend refinement taking precedence."""
    environment = os.environ if environ is None else environ
    raw = (
        environment.get("CADRUMO_LOCAL_STORAGE_ROOT", "").strip() or environment.get("CADRUMO_STORAGE_ROOT", "").strip()
    )
    anchor = project_root() if repository_root is None else repository_root
    candidate = Path(raw).expanduser() if raw else Path("var/storage")
    return (candidate if candidate.is_absolute() else anchor / candidate).resolve()


def resolve_storage_path(value: str | Path, *, root: Path | None = None) -> Path:
    """Anchor relative storage members beneath the configured root."""
    candidate = Path(value).expanduser()
    anchor = configured_storage_root() if root is None else root
    return (candidate if candidate.is_absolute() else anchor / candidate).resolve()


def storage_directory(environment_variable: str, default: str, *, root: Path | None = None) -> Path:
    """Resolve one category override; blank values use the category default."""
    return resolve_storage_path(os.environ.get(environment_variable, "").strip() or default, root=root)


def prepare_temporary_directory() -> Path:
    """Create the controlled scratch base for callers of tempfile APIs."""
    root = storage_directory("CADRUMO_TEMP_DIR", "tmp")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


TOOL_STORAGE_LOCATIONS: Mapping[str, tuple[str, str]] = {
    "UV_CACHE_DIR": ("CADRUMO_UV_CACHE_DIR", "development/cache/uv"),
    "UV_PYTHON_INSTALL_DIR": ("CADRUMO_UV_PYTHON_DIR", "development/python"),
    "UV_TOOL_DIR": ("CADRUMO_UV_TOOL_DIR", "development/tools/uv"),
    "UV_TOOL_BIN_DIR": ("CADRUMO_UV_TOOL_BIN_DIR", "development/tools/bin"),
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


def tool_storage_environment() -> dict[str, str]:
    """Bind external tool caches and bytecode to shared, overrideable storage."""
    return {
        native: str(storage_directory(variable, default))
        for native, (variable, default) in TOOL_STORAGE_LOCATIONS.items()
    }
