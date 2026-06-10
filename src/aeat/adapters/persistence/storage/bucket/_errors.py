"""Typed exception hierarchy for the per-bucket directory model.

Each class carries a structured payload (active bucket id, holding PID,
conflicting bucket id, recovery context) so callers can render typed
diagnostics without re-parsing the message string. Every class inherits
from :class:`aeat.core.errors.AeatError`; the project error registry's
``__init_subclass__`` hook binds each subclass to its declared
:class:`aeat.core.errors.ErrorCode` row at import time.
"""

from __future__ import annotations

from collections.abc import Mapping

from ..errors import SecureStorageError


class BucketError(SecureStorageError):
    """Base class for every per-bucket lifecycle error."""


class BucketValidationError(BucketError):
    """Raised when a bucket parameter or manifest field fails validation."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(
            message,
            context=context,
            translated_message="errors.integrity.integrity_storage_bucket_validation",
        )


class NoActiveBucketError(BucketError):
    """Raised when no active bucket can be resolved.

    The precedence chain is exhausted (no ``--bucket`` flag, no
    ``AEAT_ACTIVE_BUCKET`` env, no pointer file), and the process
    refuses to proceed.
    """

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(translated_message="errors.refused.refused_storage_bucket_no_active")
        self._detail = detail


class BucketBusyError(BucketError):
    """Raised when a second process attempts to unlock a held bucket.

    Carries the holding PID so the caller can render the diagnostic
    without re-parsing the lockfile.
    """

    def __init__(self, *, bucket_id: str, holding_pid: int) -> None:
        super().__init__(
            context={"bucket_id": bucket_id, "holding_pid": holding_pid},
            translated_message="errors.locked.locked_storage_bucket_busy",
        )
        self.bucket_id = bucket_id
        self.holding_pid = holding_pid


class BucketAlreadyPresentError(BucketError):
    """Raised when an import would collide with an existing bucket id.

    Carries the conflicting bucket id.
    """

    def __init__(self, *, bucket_id: str) -> None:
        super().__init__(
            context={"bucket_id": bucket_id},
            translated_message="errors.refused.refused_storage_bucket_already_present",
        )
        self.bucket_id = bucket_id


class BucketLockedError(BucketError):
    """Raised when an operation requires an unlocked :class:`BucketSession`.

    Carries the locked bucket id so the diagnostic can point the
    operator at ``aeat config switch NAME``.
    """

    def __init__(self, *, bucket_id: str) -> None:
        super().__init__(
            context={"bucket_id": bucket_id},
            translated_message="errors.locked.locked_storage_bucket_session",
        )
        self.bucket_id = bucket_id


class RecoveryUnavailableError(BucketError):
    """Raised when the recovery wrap cannot be loaded for the active bucket.

    Distinguishes "recovery never enrolled" (the bucket's manifest has
    ``recovery_enrolled = false``) from a torn or tampered envelope; the
    typed payload carries the active bucket id.
    """

    def __init__(self, *, bucket_id: str) -> None:
        super().__init__(
            context={"bucket_id": bucket_id},
            translated_message="errors.fail.fail_storage_bucket_recovery_unavailable",
        )
        self.bucket_id = bucket_id


class RecoveryVerificationError(BucketError):
    """Raised when the operator-typed recovery code does not decode.

    Fired by ``aeat config recover`` when the 24-word entry does not
    unwrap the bucket's recovery envelope.
    """

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(translated_message="errors.auth.auth_storage_bucket_recovery_verification")
        self._detail = detail


__all__ = [
    "BucketAlreadyPresentError",
    "BucketBusyError",
    "BucketError",
    "BucketLockedError",
    "BucketValidationError",
    "NoActiveBucketError",
    "RecoveryUnavailableError",
    "RecoveryVerificationError",
]
