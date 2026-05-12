"""Shared path normalization and containment helpers.

Centralises the small set of filesystem primitives that every other
``aeat`` module needs: resolving repo-relative paths against the
project root, normalising user-provided settings to absolute paths,
and safely resolving caller-provided sub-paths under a fixed root
without allowing path-traversal escapes.

The containment helpers (:func:`resolve_relative_subpath`,
:func:`resolve_record_json_path`) refuse backslashes, parent
references, absolute components, and any resolved path that escapes
the owning root. They are the load-bearing defence against
caller-controlled identifier injection on the on-disk store paths.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from .errors import CoreValidationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
"""Absolute filesystem path to the repository root."""

_SAFE_FILE_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def resolve_project_path(value: str | Path) -> Path:
    """Resolve a repo-relative path against :data:`PROJECT_ROOT`.

    Args:
        value: An absolute or repo-relative path; user-style ``~``
            references are expanded.

    Returns:
        The fully resolved absolute :class:`pathlib.Path`.
    """

    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (PROJECT_ROOT / candidate).resolve()


def normalize_project_relative_path(value: Path | None) -> Path | None:
    """Normalise an optional path setting to an absolute repo-rooted path.

    Args:
        value: Optional configured path, or ``None``.

    Returns:
        ``None`` when ``value`` is ``None``; otherwise the resolved
        absolute path produced by :func:`resolve_project_path`.
    """

    if value is None:
        return None
    return resolve_project_path(value)


def normalize_project_relative_str(value: str) -> str:
    """Normalise an optional string-backed path setting to an absolute string.

    Args:
        value: Configured path string; an empty string is passed
            through unchanged so that callers can model "unset" with
            an empty string.

    Returns:
        The resolved absolute path as a string, or the original empty
        string.
    """

    if not value:
        return value
    return str(resolve_project_path(value))


def resolve_relative_subpath(root: Path, relative_path: str, *, context: str) -> Path:
    """Resolve ``relative_path`` under ``root`` and enforce containment.

    Args:
        root: The fixed parent directory that the result must live
            under.
        relative_path: A POSIX-style sub-path supplied by an
            untrusted-ish caller. Backslashes, absolute components,
            empty parts, ``.`` and ``..`` parts are all rejected.
        context: Short human-readable label used in raised error
            messages so the caller can attribute the failure.

    Returns:
        The resolved absolute path inside ``root``.

    Raises:
        ValueError: When ``relative_path`` is malformed or when the
            resolved path escapes ``root``.
    """

    if "\\" in relative_path:
        raise CoreValidationError(f"{context} must use forward slashes only")
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise CoreValidationError(f"{context} must stay within the owning root")

    resolved_root = root.resolve()
    resolved = (resolved_root / Path(*pure.parts)).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise CoreValidationError(f"{context} escapes the owning root") from exc
    return resolved


def resolve_record_json_path(root: Path, record_id: str, *, context: str) -> Path:
    """Resolve a file-backed record id to ``<root>/<record_id>.json`` safely.

    Args:
        root: The directory that owns the JSON sidecar files.
        record_id: A simple filename token. Must match a strict
            ``[A-Za-z0-9][A-Za-z0-9._-]{0,127}`` shape so the
            resolved path cannot escape ``root`` via path separators
            or parent references.
        context: Short human-readable label used in raised error
            messages.

    Returns:
        The resolved absolute path of the JSON sidecar.

    Raises:
        ValueError: When ``record_id`` is not a simple filename token
            or the resolved path escapes ``root``.
    """

    if not _SAFE_FILE_TOKEN_RE.fullmatch(record_id):
        raise CoreValidationError(f"{context} must be a simple filename token")
    resolved_root = root.resolve()
    resolved = (resolved_root / f"{record_id}.json").resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:  # pragma: no cover - defensive
        raise CoreValidationError(f"{context} escapes the owning root") from exc
    return resolved
