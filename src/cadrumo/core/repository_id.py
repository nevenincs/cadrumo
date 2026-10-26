"""Shape rule for the free-string ids persistence repositories are keyed by.

An id that is empty, carries a path separator, or is a dot token could compose
into a filename that escapes a store directory or collides with a hidden file.
This module owns the single predicate; each layer that enforces it keeps its
own error type and message, because those belong to the layer's boundary.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["RepositoryIdViolation", "repository_id_violation"]


class RepositoryIdViolation(StrEnum):
    """Why a repository id was refused; the values are stable diagnostic identifiers."""

    EMPTY = "empty_repository_id"
    SEPARATOR = "repository_id_separator"
    LEADING_DOT = "repository_id_dot_token"

    @property
    def requirement(self) -> str:
        """The rule broken, phrased to follow the id's context label in a message."""
        return _REQUIREMENTS[self]


_REQUIREMENTS = {
    RepositoryIdViolation.EMPTY: "must be non-empty",
    RepositoryIdViolation.SEPARATOR: "must not contain path separators",
    RepositoryIdViolation.LEADING_DOT: "must not be a relative-path token",
}


def repository_id_violation(token: str) -> RepositoryIdViolation | None:
    """Return the first shape rule ``token`` breaks, or ``None`` when it is admissible.

    The rule is deliberately minimal: non-empty, no path separator, and not
    ``.``, ``..`` or any dot-prefixed value. It names no id alphabet, so one
    predicate serves every repository regardless of its identifier domain.
    """
    if not token:
        return RepositoryIdViolation.EMPTY
    if "/" in token or "\\" in token:
        return RepositoryIdViolation.SEPARATOR
    if token.startswith("."):
        return RepositoryIdViolation.LEADING_DOT
    return None
