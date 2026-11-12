"""Domain errors for the :mod:`cadrumo.domain.renta` subpackage."""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError


class RentaError(CadrumoError):
    """Base error for every :mod:`cadrumo.domain.renta` failure mode."""


class RentaValidationError(RentaError):
    """Raised on invalid Renta field values."""


class RentaDateRequiredError(RentaValidationError):
    """Raised when a dated tax fact has no date to be read at.

    A calculation that reads a fact in force on a date refuses rather than
    reading it on the run date; the context names the command that supplies it.
    """


__all__ = [
    "RentaDateRequiredError",
    "RentaError",
    "RentaValidationError",
]
