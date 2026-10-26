"""Typed errors for the inventory application service."""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError


class InventoryServiceInputError(CadrumoError):
    """Raised when a CLI-supplied input violates the typed inventory contract."""


class InventoryActividadNotFoundError(CadrumoError):
    """Raised when an inventory lookup targets a missing actividad / year."""


class InventoryActividadConflictError(CadrumoError):
    """Raised when a create attempt collides with an existing actividad / year."""


class InventoryClosingAuthorityConflictError(CadrumoError):
    """Raised when a different immutable closing authority already exists.

    This is an application repository capability error, translated by
    :class:`InventoryService` into the registered operator-facing input error.
    It deliberately is not a CLI error code of its own.
    """


__all__ = [
    "InventoryActividadConflictError",
    "InventoryActividadNotFoundError",
    "InventoryClosingAuthorityConflictError",
    "InventoryServiceInputError",
]
