"""Storage-layer exceptions.

All storage errors inherit from :class:`aeat.errors.AeatError` so callers can
catch domain-wide failures with a single base class.
"""

from __future__ import annotations

from aeat.errors import AeatError


class StorageError(AeatError):
    """Base class for every error raised by :mod:`aeat.storage`."""


class MigrationError(StorageError):
    """Raised when an Alembic migration operation fails."""


class RepositoryError(StorageError):
    """Raised when a repository operation fails (not-found, integrity, etc.)."""
