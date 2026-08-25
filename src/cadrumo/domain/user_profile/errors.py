"""Errors raised by the user-profile domain."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from pydantic import ValidationError

from ...core.errors import CadrumoError

#: Registered operator text for a user-profile schema that cannot be loaded.
#: Stated once so the refusal and the gate that pins it read the same spelling,
#: and held equal to the code registry's own ``message_key`` by a test.
SCHEMA_LOAD_MESSAGE_KEY: Final[str] = "errors.fail.fail_user_profile_schema_load"

#: Registered operator text for a persisted profile record that no longer
#: validates. Shared with the transactions drift refusal, which reports the
#: same condition over a different record.
STORED_PROFILE_DRIFT_MESSAGE_KEY: Final[str] = "errors.storage.stored_data_validation_boundary"


class UserProfileError(CadrumoError):
    """Base error for every :mod:`domain.user_profile` failure mode."""


class UserProfileSchemaLoadError(UserProfileError):
    """Raised when the committed user-profile schema cannot be loaded.

    Constructed with facts only. The class supplies its registered key as the
    sole rendered text, and the keyword-only signature is what makes that
    structural rather than conventional: there is no positional slot an
    authored sentence could occupy, so ``str(exc)`` is the key in every locale
    and in every traceback and log line that renders the exception directly.

    Attributes:
        context: Locale-neutral machine facts naming the failed precondition,
            the schema file and the stage of the load that refused.
    """

    def __init__(self, *, context: Mapping[str, object] | None = None) -> None:
        """Initialise a localized user-profile schema load failure from facts."""
        super().__init__(
            context=context,
            translated_message=SCHEMA_LOAD_MESSAGE_KEY,
        )


class UserProfileValidationError(UserProfileError, ValueError):
    """Raised on invalid user profile values. Inherits from ValueError for Pydantic."""


class UserProfileNotFoundError(UserProfileError, KeyError):
    """Raised when a requested user profile section or field is missing."""


class ProfileNotFoundError(UserProfileError):
    """Raised when a profile lookup targets an unknown ``profile_id``."""


class ProfileAlreadyExistsError(UserProfileError):
    """Raised when a register / duplicate command collides with an existing profile."""


class ProfileSchemaValidationError(UserProfileError):
    """Raised when a lifecycle command's facts violate the schema contract."""


class ProfilePreflightMissingError(UserProfileError):
    """Raised when modelo/revision preflight cannot find a required profile selector."""


class ProfileSnapshotHashMismatchError(UserProfileError):
    """Raised when the recorded snapshot hash differs from the current projection."""


class ProfileSnapshotNotFoundError(UserProfileError):
    """Raised when a snapshot id has no persisted record in the secure backend."""


class ProfileSnapshotClassificationError(UserProfileError):
    """Raised when a stored snapshot's classification violates its contract."""


class ProfileSnapshotVersionError(UserProfileError):
    """Raised when a stored snapshot's schema version is unsupported."""


class ProfileBucketMismatchError(UserProfileError):
    """Raised when a payload's profile identity is not the bound bucket's own.

    A profile bucket is an isolated store holding exactly one profile
    identity. This refuses the cross-profile read or write that the
    key-derivation habit alone did not prevent.
    """


class ProfileExportError(UserProfileError):
    """Base error for profile-archive export failures (serialization, write)."""


class ProfileImportError(UserProfileError):
    """Base error for profile-archive import failures (parse, signature, collision)."""


class ProfileImportSignatureError(ProfileImportError):
    """Raised when a profile archive fails its signature/integrity check."""


class ProfileImportCollisionError(ProfileImportError):
    """Raised when an imported profile_id collides with an existing profile."""


class StoredProfileDriftError(UserProfileError):
    """Raised when a persisted profile record fails schema validation on load.

    The record was valid when it was written; schema evolution or an
    out-of-band edit caused the on-disk representation to drift from the
    current :class:`~domain.user_profile.values.UserProfileRecord` schema.
    The original :exc:`pydantic.ValidationError` is preserved on
    ``original_exception`` so callers can inspect the typed field
    errors without losing the deserialization detail.

    The CLI boundary catches this typed error and routes it to
    :exc:`~entrypoints.cli.errors.CliStoredDataValidationBoundaryError`
    (distinct from the input-time
    :exc:`~entrypoints.cli.errors.CliValidationBoundaryError`) so
    operators see a repair-oriented message rather than a generic refusal.

    The refusal carries facts, not a way out. Which command repairs a drifted
    record is a decision about the operator surface, and this layer cannot see
    that surface: it names the contract that diverged and leaves the outcome to
    the CLI boundary, which classifies the wrapped refusal as a stored-data
    precondition and emits the typed no-recovery outcome for it. A command
    string carried here would be a second action authority competing with that
    one, unread by every consumer and wrong the moment the verb is renamed.

    The facts name WHICH contract diverged and HOW MANY of its constraints
    failed, never the values that failed them. A violation's location path
    reproduces mapping KEYS as well as field names, so a record keyed by a tax
    identifier would put that identifier in the fact; the redaction-aware
    projection that can tell those apart belongs to the boundary that owns the
    record type, and re-deriving it here would be a second, unredacted copy.
    ``original_exception`` carries the full typed detail to whoever is entitled
    to project it.

    Attributes:
        profile_id: Generated profile identity (a UUIDv4, never a tax
            identifier) whose record drifted.
        original_exception: The underlying :exc:`pydantic.ValidationError`.
    """

    def __init__(self, *, profile_id: str, error: ValidationError) -> None:
        """Initialise the drift error with profile identity and the validation failure.

        Args:
            profile_id: Identifier of the profile whose record failed validation.
            error: The underlying :exc:`pydantic.ValidationError` from deserialization.
        """
        super().__init__(
            translated_message=STORED_PROFILE_DRIFT_MESSAGE_KEY,
            context={
                "profile_id": profile_id,
                "failing_record": error.title,
                "violation_count": len(error.errors()),
            },
        )
        self.profile_id: str = profile_id
        self.original_exception: ValidationError = error
