"""Typed exception hierarchy for the storage provider abstraction.

Every storage backend (local filesystem, Google Drive, in-memory test)
raises subclasses of `StorageError` so the application layer's sync
coordinator can dispatch on the concrete failure mode without parsing
upstream error strings. Each leaf binds to a stable `ErrorCode` in
`aeat.core.errors.registry._adapters` so the public CLI taxonomy stays
explicit.
"""

from __future__ import annotations

from ....core.errors import AeatError


class StorageError(AeatError):
    """Base class for every storage-provider failure."""


class StorageValidationError(StorageError, ValueError):
    """Raised when storage operation parameters fail validation.

    Inherits from `ValueError` to remain compatible with pydantic
    validators while staying catchable under the unified hierarchy.
    """


class StorageNotFoundError(StorageError):
    """Raised when a requested object or namespace does not exist."""


class StorageConflictError(StorageError):
    """Raised when a put / move / rename collides with an existing object."""


class StoragePermissionError(StorageError):
    """Raised when the active credentials lack the required scope or grant."""


class StorageQuotaError(StorageError):
    """Raised when the backend rejects an operation due to quota exhaustion."""


class StorageNetworkError(StorageError):
    """Raised when the backend endpoint is unreachable (DNS/TLS/timeout)."""


class StorageIntegrityError(StorageError):
    """Raised when a fetched payload fails integrity checks (hash/size/etag)."""


class StorageUnavailableError(StorageError):
    """Raised when the backend is reachable but signals temporary unavailability."""


__all__ = [
    "StorageConflictError",
    "StorageError",
    "StorageIntegrityError",
    "StorageNetworkError",
    "StorageNotFoundError",
    "StoragePermissionError",
    "StorageQuotaError",
    "StorageUnavailableError",
    "StorageValidationError",
]
