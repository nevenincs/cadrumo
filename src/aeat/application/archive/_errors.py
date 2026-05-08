"""Typed errors raised by the archive subsystem."""

from __future__ import annotations

from ...core.errors import AeatError


class ArchiveError(AeatError):
    """Base class for every archive export/import failure."""


class ArchiveAdapterMissingError(ArchiveError):
    """Raised when an archive operation references an unregistered namespace."""


class ArchiveBundleSchemaError(ArchiveError):
    """Raised when a bundle's wire schema is unsupported by this consumer."""


class ArchiveConflictError(ArchiveError):
    """Raised when restoring a record would overwrite an existing object.

    Surfaces only under :attr:`ConflictPolicy.FAIL`. Carries the
    namespace and natural object key on the standard message so
    operators can resolve manually.
    """


__all__ = [
    "ArchiveAdapterMissingError",
    "ArchiveBundleSchemaError",
    "ArchiveConflictError",
    "ArchiveError",
]
