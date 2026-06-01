"""Domain errors for the :mod:`aeat.domain.renta` subpackage."""

from __future__ import annotations

from ...core.errors import AeatError


class RentaError(AeatError):
    """Base error for every :mod:`aeat.domain.renta` failure mode."""


class RentaValidationError(RentaError, ValueError):
    """Raised on invalid Renta field values. Inherits from ValueError for Pydantic."""


__all__ = [
    "RentaError",
    "RentaValidationError",
]
