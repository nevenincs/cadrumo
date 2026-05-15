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


class CasillaConstraintViolationError(RegistryError):
    """Raised when a computed casilla value falls outside its declared
    `casilla.constraints` (sign, min_value, max_value).

    The error envelope carries `casilla_id`, the offending `value`, the
    offended constraint clause, and the casilla's `legal_refs` so the
    operator sees the BOE permalink that justifies the rule.
    """
