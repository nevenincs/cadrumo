"""Errors raised by the user-profile schema loader."""

from __future__ import annotations


class UserProfileSchemaLoadError(ValueError):
    """Raised when the committed user-profile schema cannot be loaded."""
