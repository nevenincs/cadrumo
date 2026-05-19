"""Typed exception hierarchy for the storage provider abstraction.

Every storage backend (local filesystem, Google Drive, in-memory test)
raises subclasses of `OutboundStorageError` so the application layer's
sync coordinator can dispatch on the concrete failure mode without
parsing upstream error strings. Each leaf binds to a stable `ErrorCode`
in `aeat.core.errors.registry._adapters` so the public CLI taxonomy
stays explicit.

The `Outbound` prefix disambiguates this hierarchy from the persistence
side `StorageError` in `aeat.adapters.persistence.storage.errors`, which
covers at-rest persistence and has a different parent chain.
"""

from __future__ import annotations

from ....core.errors import AeatError


class OutboundStorageError(AeatError):
    """Base class for every storage-provider failure."""


class OutboundStorageValidationError(OutboundStorageError, ValueError):
    """Raised when storage operation parameters fail validation.

    Inherits from `ValueError` to remain compatible with pydantic
    validators while staying catchable under the unified hierarchy.
    """


class OutboundStorageNotFoundError(OutboundStorageError):
    """Raised when a requested object or namespace does not exist."""


class OutboundStorageConflictError(OutboundStorageError):
    """Raised when a put / move / rename collides with an existing object."""


class OutboundStoragePermissionError(OutboundStorageError):
    """Raised when the active credentials lack the required scope or grant."""


class OutboundStorageQuotaError(OutboundStorageError):
    """Raised when the backend rejects an operation due to quota exhaustion."""


class OutboundStorageNetworkError(OutboundStorageError):
    """Raised when the backend endpoint is unreachable (DNS/TLS/timeout)."""


class OutboundStorageIntegrityError(OutboundStorageError):
    """Raised when a fetched payload fails integrity checks (hash/size/etag)."""


class OutboundStorageUnavailableError(OutboundStorageError):
    """Raised when the backend is reachable but signals temporary unavailability."""


__all__ = [
    "OutboundStorageConflictError",
    "OutboundStorageError",
    "OutboundStorageIntegrityError",
    "OutboundStorageNetworkError",
    "OutboundStorageNotFoundError",
    "OutboundStoragePermissionError",
    "OutboundStorageQuotaError",
    "OutboundStorageUnavailableError",
    "OutboundStorageValidationError",
]
