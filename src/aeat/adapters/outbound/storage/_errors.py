"""Typed exception hierarchy for the storage provider abstraction.

Provider and remote-mirror failures raised by
:class:`aeat.adapters.outbound.storage.StorageProvider` implementations use
subclasses of :class:`OutboundStorageError` so the application layer's sync
coordinator can dispatch on the concrete failure mode without parsing upstream
error strings. Each public leaf binds to a stable
:class:`aeat.core.errors.ErrorCode` through :mod:`aeat.core.errors.registry`
so the CLI taxonomy stays explicit.

:class:`StorageCorruptionError` is the deliberate exception: it derives from
:class:`CoreError` because it represents structurally invalid sidecar metadata,
not a remote-provider transport, quota, permission, or mirror failure.

The `Outbound` prefix disambiguates this hierarchy from the persistence
side :class:`aeat.adapters.persistence.storage.errors.StorageError`, which
covers at-rest persistence and has a different parent chain.
"""

from __future__ import annotations

from ....core.errors import AeatError, CoreError


class OutboundStorageError(AeatError):
    """Base class for every outbound storage-provider failure."""


class OutboundStorageValidationError(OutboundStorageError, ValueError):
    """Raised when storage operation parameters fail validation.

    Inherits from :class:`ValueError` to remain compatible with pydantic
    validators while staying catchable as :class:`OutboundStorageError`.
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
    """Raised when fetched provider data fails integrity checks.

    The shared hash comparison path is
    :func:`aeat.adapters.outbound.storage._integrity.verify_content_hash`.
    """


class OutboundStorageUnavailableError(OutboundStorageError):
    """Raised when the backend is reachable but signals temporary unavailability."""


class StorageCorruptionError(CoreError):
    """Raised when a sidecar file contains structurally invalid field types.

    As a :class:`CoreError`, this indicates on-disk data corruption: the
    sidecar JSON parses successfully but a required field (e.g.
    ``byte_length``) carries a type that the runtime cannot coerce to the
    expected primitive. Unlike :class:`OutboundStorageIntegrityError`, which
    covers payload-byte hash mismatches from
    :func:`aeat.adapters.outbound.storage._integrity.verify_content_hash`, this
    error surfaces schema-level violations in the sidecar metadata file itself.
    """


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
    "StorageCorruptionError",
]
