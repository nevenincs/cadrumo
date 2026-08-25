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
    """Raised when a bucket parameter or manifest field fails validation."""

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


class NoActiveBucketError(BucketError):
    """Raised when no active bucket can be resolved.

    The precedence chain is exhausted (no ``--profile`` flag and no
    pointer file), and the process refuses to proceed. The adapter records
    that selection fact only; a boundary with a verified public profile label
    owns any action projection.
    """

    def __init__(self, detail: str | None = None) -> None:
        """Build a no-active-bucket failure."""
        del detail
        super().__init__(
            context={"active_bucket_selected": False},
            translated_message="errors.refused.refused_storage_bucket_no_active",
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
    """Raised when an import would collide with an existing bucket id.

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


class RecoveryUnavailableError(BucketError):
    """The refusal reserved for a recovery wrap that cannot be loaded.

    The prose that stood here was destroyed by an edit and is NOT reconstructed
    below, because its meaning did not survive either. It distinguished
    "recovery never enrolled" from a torn or tampered envelope by reading a
    ``recovery_enrolled`` flag off the bucket manifest, and that field has since
    been removed: the manifest now REFUSES a payload carrying it, which
    ``test_rejects_the_removed_manifest_recovery_mirror`` pins. So the
    distinction has no basis left in the record, and restoring the sentence
    would reinstate a claim the tree contradicts.

    What is established by measurement, and nothing beyond it: the class exists
    and is exported, it carries the active bucket id in its typed payload, and
    it has no raise sites anywhere in the tree. Whoever reinstates a recovery
    lifecycle owns re-deciding what this refusal distinguishes, on whatever
    signal the manifest carries then.
    """

    def __init__(self, *, bucket_id: str) -> None:
        """Build a recovery-unavailable failure."""
        super().__init__(
            context={"bucket_id": bucket_id},
            translated_message="errors.fail.fail_storage_bucket_recovery_unavailable",
        )
        self.bucket_id = bucket_id


class RecoveryVerificationError(BucketError):
    """The refusal reserved for an operator-typed recovery code that fails to decode.

    Not raised anywhere. The command-line verb this once named no longer
    resolves, and the citation is removed rather than repointed because there
    is no replacement verb to point at: a dead operator instruction in a
    docstring is worse than none, since a reader will try it.

    The shape it describes is still the intended one -- a 24-word entry that
    does not unwrap the bucket's recovery envelope -- but nothing today accepts
    such an entry.
    """

    def __init__(self, detail: str | None = None) -> None:
        """Build a recovery-verification failure."""
        super().__init__(translated_message="errors.auth.auth_storage_bucket_recovery_verification")
        self._detail = detail


__all__ = [
    "BucketAlreadyPresentError",
    "BucketBusyError",
    "BucketError",
    "BucketLockedError",
    "BucketPathTooLongError",
    "BucketValidationError",
    "NoActiveBucketError",
    "RecoveryUnavailableError",
    "RecoveryVerificationError",
]
