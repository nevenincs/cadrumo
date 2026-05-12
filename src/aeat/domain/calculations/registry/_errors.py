"""Registry error types for AEAT legal calculation definitions."""

from __future__ import annotations

from ....core.errors import AeatError


class RegistryError(AeatError, ValueError):
    """Base error for registry loading, resolution, and validation."""


class RegistryLoadError(RegistryError):
    """Raised when registry files cannot be parsed into strict schema objects."""


class RegistryValidationError(RegistryError):
    """Raised when registry definitions are incomplete or contradictory."""


class RegistrySnapshotError(RegistryError):
    """Raised when a filing-grade snapshot cannot be selected."""
