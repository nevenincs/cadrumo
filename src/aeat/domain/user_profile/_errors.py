"""Errors raised by the user-profile domain."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from ...core.errors import AeatError


class UserProfileError(AeatError):
    """Base error for every :mod:`aeat.domain.user_profile` failure mode."""


class UserProfileSchemaLoadError(UserProfileError):
    """Raised when the committed user-profile schema cannot be loaded."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
    ) -> None:
        """Initialise a localized user-profile schema load failure."""
        super().__init__(
            message,
            context=context,
            translated_message="errors.fail.fail_user_profile_schema_load",
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
    current :class:`~aeat.domain.user_profile.UserProfileRecord` schema.
    The original :exc:`pydantic.ValidationError` is preserved on
    :attr:`original_exception` so callers can inspect the typed field
    errors without losing the deserialization detail.

    The CLI boundary catches this typed error and routes it to
    :exc:`~aeat.entrypoints.cli._errors.CliStoredDataValidationBoundaryError`
    (distinct from the input-time
    :exc:`~aeat.entrypoints.cli._errors.CliValidationBoundaryError`) so
    operators see a repair-oriented message rather than a generic refusal.

    Attributes:
        profile_id: Identifier of the profile whose record drifted.
        original_exception: The underlying :exc:`pydantic.ValidationError`.
    """

    def __init__(self, profile_id: str, error: ValidationError) -> None:
        """Initialise the drift error with profile identity and the validation failure.

        Args:
            profile_id: Identifier of the profile whose record failed validation.
            error: The underlying :exc:`pydantic.ValidationError` from deserialization.
        """
        super().__init__(
            translated_message="errors.storage.stored_data_validation_boundary",
            context={"profile_id": profile_id, "recovery": "aeat config repair --help"},
            suggestion="aeat config repair --help",
        )
        self.profile_id: str = profile_id
        self.original_exception: ValidationError = error
