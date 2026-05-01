"""Shared path-normalization and containment helpers."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_SAFE_FILE_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def resolve_project_path(value: str | Path) -> Path:
    """Resolve a repo-relative path against ``PROJECT_ROOT``."""

    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (PROJECT_ROOT / candidate).resolve()


def normalize_project_relative_path(value: Path | None) -> Path | None:
    """Normalize optional path settings to absolute repo-root-relative paths."""

    if value is None:
        return None
    return resolve_project_path(value)


def normalize_project_relative_str(value: str) -> str:
    """Normalize optional string-backed path settings to absolute strings."""

    if not value:
        return value
    return str(resolve_project_path(value))


def resolve_relative_subpath(root: Path, relative_path: str, *, context: str) -> Path:
    """Resolve ``relative_path`` under ``root`` and enforce containment."""

    if "\\" in relative_path:
        raise ValueError(f"{context} must use forward slashes only")
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError(f"{context} must stay within the owning root")

    resolved_root = root.resolve()
    resolved = (resolved_root / Path(*pure.parts)).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"{context} escapes the owning root") from exc
    return resolved


def resolve_record_json_path(root: Path, record_id: str, *, context: str) -> Path:
    """Resolve a file-backed record id to ``<root>/<record_id>.json`` safely."""

    if not _SAFE_FILE_TOKEN_RE.fullmatch(record_id):
        raise ValueError(f"{context} must be a simple filename token")
    resolved_root = root.resolve()
    resolved = (resolved_root / f"{record_id}.json").resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"{context} escapes the owning root") from exc
    return resolved
