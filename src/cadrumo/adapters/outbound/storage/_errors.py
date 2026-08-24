"""Typed exception hierarchy for the storage provider abstraction.

Provider and remote-mirror failures raised by
:class:`adapters.outbound.storage.StorageProvider` implementations use
subclasses of :class:`OutboundStorageError` so the application layer's sync
coordinator can dispatch on the concrete failure mode without parsing upstream
error strings. Each public leaf binds to a stable
:class:`core.errors.ErrorCode` through
:mod:`core.errors.registry` so the CLI taxonomy stays explicit.

:class:`StorageCorruptionError` is the deliberate exception: it derives from
:class:`core.errors.CoreError` because it represents structurally invalid
sidecar metadata, not a remote-provider transport, quota, permission, or mirror
failure.

The `Outbound` prefix disambiguates this hierarchy from the persistence
side :class:`adapters.persistence.storage.StorageError`, which
covers at-rest persistence and has a different parent chain.

See Also:
    :class:`adapters.outbound.storage.StorageProvider`
        Provider Protocol whose implementations raise this hierarchy.
    :class:`adapters.outbound.storage.ProviderObjectMetadata`
        Boundary record paired with integrity and corruption checks.
"""

from __future__ import annotations

from ....core.errors import CadrumoError, CoreError, TerminalPreconditionErrorMixin


class OutboundStorageError(TerminalPreconditionErrorMixin, CadrumoError):
    """Base class for every outbound storage-provider failure."""


class OutboundStorageValidationError(OutboundStorageError, ValueError):
    """Raised when storage operation parameters fail validation.

    Inherits from :class:`ValueError` to remain compatible with pydantic
    validators while staying catchable as :class:`OutboundStorageError`.
    """

    def __init__(self, message: str | None = None, *, context=None, translated_message=None, precondition_verdict=None):
        super().__init__(
            message,
            context=context,
            translated_message=translated_message,
            precondition_verdict=precondition_verdict,
        )


class OutboundStorageNotFoundError(OutboundStorageError):
    """Raised when a requested object or namespace does not exist."""


class OutboundStorageConflictError(OutboundStorageError):
    """Raised when a put / move / rename collides with an existing object."""


class OutboundStoragePermissionError(OutboundStorageError):
    """Raised when the active credentials lack the required scope or grant."""


class OutboundStoragePathTooLongError(OutboundStorageError):
    """Raised when a resolved on-disk path exceeds the platform's path-length ceiling.

    Classified via
    :func:`core.paths.is_windows_long_path_error` from a caught
    ``WinError 3`` / ``WinError 206`` on legacy (non long-path-aware)
    Windows workstations. Distinct from
    :class:`OutboundStorageConflictError` so the CLI surfaces the actual
    cause (a storage root too deep for the ``MAX_PATH`` ceiling) instead of
    a generic write-conflict message.
    """


class OutboundStorageQuotaError(OutboundStorageError):
    """Raised when the backend rejects an operation due to quota exhaustion."""


class OutboundStorageNetworkError(OutboundStorageError):
    """Raised when the backend endpoint is unreachable (DNS/TLS/timeout)."""


class OutboundStorageIntegrityError(OutboundStorageError):
    """Raised when fetched provider data fails integrity checks.

    The shared hash comparison path is
    :func:`adapters.outbound.storage._integrity.verify_content_hash`.
    """


class OutboundStorageUnavailableError(OutboundStorageError):
    """Raised when the backend is reachable but signals temporary unavailability."""


class StorageCorruptionError(TerminalPreconditionErrorMixin, CoreError):
    """Raised when a sidecar file contains structurally invalid field types.

    As a :class:`core.errors.CoreError`, this indicates on-disk data
    corruption: the sidecar JSON parses successfully but a required field (e.g.
    ``byte_length``) carries a type that the runtime cannot coerce to the
    expected primitive. Unlike :class:`OutboundStorageIntegrityError`, which
    covers payload-byte hash mismatches from
    :func:`adapters.outbound.storage._integrity.verify_content_hash`, this
    error surfaces schema-level violations in the sidecar metadata file itself.
    """

    def __init__(self, message=None, *, context=None, translated_message=None, precondition_verdict=None):
        super().__init__(
            message,
            context=context,
            translated_message=translated_message,
            precondition_verdict=precondition_verdict,
        )


__all__ = [
    "OutboundStorageConflictError",
    "OutboundStorageError",
    "OutboundStorageIntegrityError",
    "OutboundStorageNetworkError",
    "OutboundStorageNotFoundError",
    "OutboundStoragePathTooLongError",
    "OutboundStoragePermissionError",
    "OutboundStorageQuotaError",
    "OutboundStorageUnavailableError",
    "OutboundStorageValidationError",
    "StorageCorruptionError",
]
