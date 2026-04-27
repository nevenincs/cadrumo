"""Typed path-containment helpers for the persistence substrate.

The wider project ships :func:`aeat._paths.resolve_relative_subpath` and
:func:`aeat._paths.resolve_record_json_path` which raise plain
:class:`ValueError` on traversal violations. New persistence code uses
the typed wrappers in this module instead so:

- the failure carries the registered ``PathContainmentError`` code
  (``INTEGRITY_STORAGE_PATH_CONTAINMENT``) and lands in the standard
  CLI error envelope;
- callers can write narrow ``except PathContainmentError`` clauses
  rather than broad ``except ValueError``;
- back-compat is preserved because :class:`PathContainmentError`
  inherits from :class:`ValueError` (any existing ``except ValueError``
  catches the new typed shape too).
"""

from __future__ import annotations

from pathlib import Path

from .._paths import resolve_record_json_path, resolve_relative_subpath
from .errors import PathContainmentError


def safe_subpath(root: Path, relative_path: str, *, context: str) -> Path:
    """Resolve ``relative_path`` under ``root`` and enforce containment.

    Wraps :func:`aeat._paths.resolve_relative_subpath`. Any
    :class:`ValueError` raised by the wrapped helper is re-raised as a
    :class:`PathContainmentError` with the same message and ``__cause__``.

    Args:
        root: Configured root directory the path must stay under.
        relative_path: Forward-slash-separated relative path.
        context: Stable label embedded in the error message; used for
            log diagnostics.

    Returns:
        The resolved absolute :class:`Path` known to live under ``root``.

    Raises:
        PathContainmentError: On any traversal or shape violation.
    """
    try:
        return resolve_relative_subpath(root, relative_path, context=context)
    except ValueError as exc:
        raise PathContainmentError(str(exc)) from exc


def safe_record_path(root: Path, record_id: str, *, context: str) -> Path:
    """Resolve a record-id-keyed JSON file under ``root``.

    Wraps :func:`aeat._paths.resolve_record_json_path` and re-raises
    its :class:`ValueError` as :class:`PathContainmentError`.

    Args:
        root: Configured root directory.
        record_id: Simple filename token; the helper enforces a strict
            allow-list of characters so traversal sequences cannot
            slip through.
        context: Stable label embedded in the error message.

    Returns:
        The resolved absolute :class:`Path` of ``<root>/<record_id>.json``.

    Raises:
        PathContainmentError: When ``record_id`` is not a safe token
            or when the resolved path escapes ``root``.
    """
    try:
        return resolve_record_json_path(root, record_id, context=context)
    except ValueError as exc:
        raise PathContainmentError(str(exc)) from exc


__all__ = [
    "safe_record_path",
    "safe_subpath",
]
