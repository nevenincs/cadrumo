"""Canonical typed exception hierarchy for the per-bucket directory model.

Each class carries a structured payload (active bucket id, holding PID,
conflicting bucket id, recovery context) so callers can render typed
diagnostics without re-parsing the message string. Every class inherits
from :class:`core.errors.CadrumoError`; the project error registry's
``__init_subclass__`` hook binds each subclass to its declared
:class:`core.errors.ErrorCode` row at import time.
"""

from __future__ import annotations

from collections.abc import Mapping

from ..errors import SecureStorageError


class BucketError(SecureStorageError):
    """Base class for every per-bucket lifecycle error."""


class BucketValidationError(BucketError):
    """Raised when a bucket parameter fails validation."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
    ) -> None:
        """Build a bucket validation failure with structured context."""
        super().__init__(
            message,
            context=context,
            translated_message="errors.integrity.integrity_storage_bucket_validation",
        )


class BucketBusyError(BucketError):
    """Raised when a second process attempts to unlock a held bucket.

    Carries the holding PID so the caller can render the diagnostic
    without re-parsing the lockfile.
    """

    def __init__(self, *, bucket_id: str, holding_pid: int) -> None:
        """Build a busy-bucket failure naming the lock holder."""
        super().__init__(
            context={"bucket_id": bucket_id, "holding_pid": holding_pid},
            translated_message="errors.locked.locked_storage_bucket_busy",
        )
        self.bucket_id = bucket_id
        self.holding_pid = holding_pid


class BucketAlreadyPresentError(BucketError):
    """Raised when provisioning would collide with an existing bucket id.

    Carries the conflicting bucket id.
    """

    def __init__(self, *, bucket_id: str) -> None:
        """Build an existing-bucket collision failure."""
        super().__init__(
            context={"bucket_id": bucket_id},
            translated_message="errors.refused.refused_storage_bucket_already_present",
        )
        self.bucket_id = bucket_id


class BucketPathTooLongError(BucketError):
    """Raised when provisioning a bucket directory exceeds the Windows ``MAX_PATH`` ceiling.

    Classified via
    :func:`core.paths.is_windows_long_path_error` from a caught
    ``WinError 3`` / ``WinError 206`` on legacy (non long-path-aware)
    Windows workstations. Distinct from :class:`BucketValidationError` so
    the CLI names the actual cause (the resolved bucket directory tree is
    too deep for ``MAX_PATH``) instead of a generic validation failure.
    """

    def __init__(self, *, bucket_id: str, path: str) -> None:
        """Build a path-length failure with the resolved path."""
        super().__init__(
            context={"bucket_id": bucket_id, "path": path},
            translated_message="errors.error.error_storage_bucket_path_too_long",
        )
        self.bucket_id = bucket_id
        self.path = path


class BucketLockedError(BucketError):
    """Raised when an operation requires an unlocked :class:`BucketSession`.

    Carries the storage identity and the failed unlocked-state observation.
    Recovery policy belongs to the boundary because a bucket id is not a
    verified public profile-action argument.
    """

    def __init__(self, *, bucket_id: str) -> None:
        """Build a locked-bucket failure."""
        super().__init__(
            context={"bucket_id": bucket_id, "bucket_session_unlocked": False},
            translated_message="errors.locked.locked_storage_bucket_session",
        )
        self.bucket_id = bucket_id


__all__ = [
    "BucketAlreadyPresentError",
    "BucketBusyError",
    "BucketError",
    "BucketLockedError",
    "BucketPathTooLongError",
    "BucketValidationError",
]
