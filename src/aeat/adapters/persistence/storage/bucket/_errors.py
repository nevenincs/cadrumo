"""Typed exception hierarchy for the per-bucket directory model.

Each class carries a structured payload (active bucket id, holding PID,
conflicting bucket id, recovery context) so callers can render typed
diagnostics without re-parsing the message string. Every class inherits
from :class:`aeat.core.errors.AeatError`; the project error registry's
``__init_subclass__`` hook binds each subclass to its declared
:class:`aeat.core.errors.ErrorCode` row at import time.
"""

from __future__ import annotations

from .....core.errors import AeatError


class BucketError(AeatError):
    """Base class for every per-bucket lifecycle error."""


class NoActiveBucketError(BucketError):
    """Raised when no active bucket can be resolved.

    The precedence chain is exhausted (no ``--bucket`` flag, no
    ``AEAT_ACTIVE_BUCKET`` env, no pointer file), and the process
    refuses to proceed.
    """


class BucketBusyError(BucketError):
    """Raised when a second process attempts to unlock a held bucket.

    Carries the holding PID so the caller can render the diagnostic
    without re-parsing the lockfile.
    """

    def __init__(self, *, bucket_id: str, holding_pid: int) -> None:
        message = f"bucket {bucket_id!r} is held by pid {holding_pid}"
        super().__init__(message, context={"bucket_id": bucket_id, "holding_pid": holding_pid})
        self.bucket_id = bucket_id
        self.holding_pid = holding_pid


class BucketAlreadyPresentError(BucketError):
    """Raised when an import would collide with an existing bucket id.

    Carries the conflicting bucket id.
    """

    def __init__(self, *, bucket_id: str) -> None:
        message = f"bucket {bucket_id!r} already exists"
        super().__init__(message, context={"bucket_id": bucket_id})
        self.bucket_id = bucket_id


class BucketLockedError(BucketError):
    """Raised when an operation requires an unlocked :class:`BucketSession`.

    Carries the locked bucket id so the diagnostic can point the
    operator at ``aeat config unlock``.
    """

    def __init__(self, *, bucket_id: str) -> None:
        message = f"bucket {bucket_id!r} is locked"
        super().__init__(message, context={"bucket_id": bucket_id})
        self.bucket_id = bucket_id


class RecoveryUnavailableError(BucketError):
    """Raised when the recovery wrap cannot be loaded for the active bucket.

    Distinguishes "recovery never enrolled" (the bucket's manifest has
    ``recovery_enrolled = false``) from a torn or tampered envelope; the
    typed payload carries the active bucket id.
    """

    def __init__(self, *, bucket_id: str) -> None:
        message = f"recovery wrap unavailable for bucket {bucket_id!r}"
        super().__init__(message, context={"bucket_id": bucket_id})
        self.bucket_id = bucket_id


class RecoveryVerificationError(BucketError):
    """Raised when the operator-typed recovery code does not decode.

    Fired by ``aeat config verify-recovery`` when the 24-word entry
    does not unwrap the bucket's recovery envelope.
    """


__all__ = [
    "BucketAlreadyPresentError",
    "BucketBusyError",
    "BucketError",
    "BucketLockedError",
    "NoActiveBucketError",
    "RecoveryUnavailableError",
    "RecoveryVerificationError",
]
