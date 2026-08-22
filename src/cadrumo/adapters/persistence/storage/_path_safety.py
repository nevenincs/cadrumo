"""Typed path-containment helpers for the persistence substrate.

Shape rejection for the free-string ids persistence repositories are keyed by.
The failure carries the registered ``PathContainmentError`` code
(``INTEGRITY_STORAGE_PATH_CONTAINMENT``) so it lands in the standard CLI error
envelope, callers can write a narrow ``except PathContainmentError`` rather
than a broad ``except ValueError``, and the error still inherits from
:class:`ValueError` so existing path-shape handlers remain correct.

This module once also wrapped :func:`core.paths.resolve_relative_subpath` as
``safe_subpath``, the containment half of a two-layer contract. Nothing called
it, and the one field it was written for -- a rotation entry's
``target_filename`` -- is no longer in the tree, so the wrapper was removed
rather than left standing as the second layer of a contract with one layer.
The core primitive it wrapped is unaffected and still has a live consumer; a
filesystem-backed store that needs containment again wraps it in one line.
"""

from __future__ import annotations

from .errors import PathContainmentError


def _containment_error(message: str, *, context: str, violation: str) -> PathContainmentError:
    return PathContainmentError(
        message,
        context={
            "path_context": context,
            "violation": violation,
        },
    )


def safe_repository_id(token: str, *, context: str) -> str:
    """Reject repository-id tokens that would compose into an unsafe filename.

    A token containing a path separator, a dot-prefix, or one of the
    relative-path tokens (``"."`` / ``".."``) would either escape a store
    directory or collide with a hidden file, so this helper rejects the
    token's SHAPE at the public-method boundary.

    Shape rejection is currently the WHOLE contract, which it was not always
    described as. The substrate behind every caller is SQL-backed: rows are
    keyed by ``(namespace, identifier)`` and only ``db://`` logical markers are
    composed for diagnostics, so no filesystem path is derived from a token.

    This once documented a second layer -- ``safe_subpath``, re-resolving a
    token against the real filesystem, said to be the only layer that could
    catch a symlinked store directory. That layer had no callers, and the one
    field named as needing it, a rotation entry's ``target_filename``, is no
    longer in the tree. It has been removed. A reader who needs that guarantee
    should know it is absent rather than believe it is somewhere else: if a
    token ever does become a real filename, containment has to be added back
    at that join, and this check will not supply it.

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


__all__ = ["safe_repository_id"]
