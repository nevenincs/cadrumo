"""Errors raised by the user-profile domain."""

from __future__ import annotations

from ...core.errors import AeatError


class UserProfileError(AeatError):
    """Base error for every :mod:`aeat.domain.user_profile` failure mode."""


class UserProfileSchemaLoadError(UserProfileError):
    """Raised when the committed user-profile schema cannot be loaded."""


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
