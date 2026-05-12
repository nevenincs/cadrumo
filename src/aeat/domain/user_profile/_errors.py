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
