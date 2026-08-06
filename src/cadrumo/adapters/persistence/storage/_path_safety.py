"""Typed path-containment helpers for the persistence substrate.

The wider project ships :func:`core.paths.resolve_relative_subpath`, which
raises a plain :class:`ValueError` on traversal violations. New persistence
code uses the typed wrappers in this module instead so:

- the failure carries the registered ``PathContainmentError`` code
  (``INTEGRITY_STORAGE_PATH_CONTAINMENT``) and lands in the standard
  CLI error envelope;
- callers can write narrow ``except PathContainmentError`` clauses
  rather than broad ``except ValueError``;
- :class:`PathContainmentError` still inherits from :class:`ValueError`
  so callers that handle Python path-shape errors remain correct.
"""

from __future__ import annotations

from pathlib import Path

from ....core.paths import resolve_relative_subpath
from .errors import PathContainmentError


def _containment_error(message: str, *, context: str, violation: str) -> PathContainmentError:
    return PathContainmentError(
        message,
        context={
            "path_context": context,
            "violation": violation,
        },
    )


def safe_subpath(root: Path, relative_path: str, *, context: str) -> Path:
    """Resolve ``relative_path`` under ``root`` and enforce containment.

    Wraps :func:`core.paths.resolve_relative_subpath`. Any
    :class:`ValueError` raised by the wrapped helper is re-raised as a
    localized :class:`PathContainmentError` with the same diagnostic
    ``args`` message and ``__cause__``.

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
        raise _containment_error(
            str(exc),
            context=context,
            violation="relative_subpath",
        ) from exc


def safe_repository_id(token: str, *, context: str) -> str:
    """Reject repository-id tokens that would compose into an unsafe filename.

    A token containing a path separator, a dot-prefix, or one of the
    relative-path tokens (``"."`` / ``".."``) would either escape a store
    directory or collide with a hidden file, so this helper rejects the
    token's SHAPE at the public-method boundary.

    It is the early-rejection half of the substrate's two-layer path
    contract, and which layer follows depends on the backend. The
    secure-object substrate is SQL-backed: it keys rows by
    ``(namespace, identifier)`` and composes only ``db://`` logical markers
    for diagnostics, so no filesystem path is derived from the token and
    shape rejection is the whole of it. Where a token does become a real
    filename -- the rotation entry's ``target_filename`` -- the second layer
    is :func:`safe_subpath`, which re-resolves it against the real
    filesystem at enumeration and is the only layer that can catch a
    symlinked store directory. Neither layer subsumes the other.

    The validation is intentionally minimal — non-empty, no path
    separator, no dot-token. It does not claim knowledge of any
    domain-specific id alphabet (UUIDs, AEAT CSVs, modelo numerics,
    etc.) so a single helper covers every governance repository.

    Args:
        token: The free-string id supplied by the repository caller.
        context: Stable label (``"submission_id"`` / ``"draft_id"`` /
            etc.) embedded in the error message. Lets the failure
            message remain byte-identical to the per-domain
            validators it replaces.

    Returns:
        ``token`` unchanged. Returning the validated value lets the
        helper appear inline (``safe_repository_id(record_id, ...)``
        as both check and pass-through).

    Raises:
        PathContainmentError: When ``token`` is empty, contains a path
            separator, is the bare ``.`` / ``..`` token, or starts
            with a dot.
    """
    if not token:
        raise _containment_error(
            f"{context} must be non-empty",
            context=context,
            violation="empty_repository_id",
        )
    if "/" in token or "\\" in token:
        raise _containment_error(
            f"{context} must not contain path separators",
            context=context,
            violation="repository_id_separator",
        )
    if token in {".", ".."} or token.startswith("."):
        raise _containment_error(
            f"{context} must not be a relative-path token",
            context=context,
            violation="repository_id_dot_token",
        )
    return token


__all__ = [
    "safe_repository_id",
    "safe_subpath",
]
