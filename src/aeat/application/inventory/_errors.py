"""Typed errors for the inventory application service."""

from __future__ import annotations

from ...core.errors import AeatError


class InventoryServiceInputError(AeatError):
    """Raised when a CLI-supplied input violates the typed inventory contract."""


class InventoryActividadNotFoundError(AeatError):
    """Raised when an inventory lookup targets a missing actividad / year."""


class InventoryActividadConflictError(AeatError):
    """Raised when a create attempt collides with an existing actividad / year."""


__all__ = [
    "InventoryActividadConflictError",
    "InventoryActividadNotFoundError",
    "InventoryServiceInputError",
]
