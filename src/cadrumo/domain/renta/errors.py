"""Domain errors for the :mod:`cadrumo.domain.renta` subpackage."""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError


class RentaError(CadrumoError):
    """Base error for every :mod:`cadrumo.domain.renta` failure mode."""


class RentaValidationError(RentaError, ValueError):
    """Raised on invalid Renta field values. Inherits from ValueError for Pydantic."""


__all__ = [
    "RentaError",
    "RentaValidationError",
]
