"""Date-boundary helpers for filing-period registry tokens.

``aeat.core.Period`` is the backend filing-period authority: a filing
year plus registry token, constructed with ``Period.from_year_and_code``.
This module provides registry-token date-boundary helpers.

Do not treat this module as canonical period storage. Prefer typed
``aeat.core.Period`` at domain boundaries.

The ``nP`` tokens are the Impuesto sobre Sociedades pago-fraccionado
instalment claves (Modelo 202). Per the AEAT Modelo 202 instructions,
``1P`` is the payment made in the first twenty days of April, ``2P``
the equivalent October payment, and ``3P`` the December payment; the
period-boundary helpers map each instalment to its payment month.

Callers wrap :class:`ValueError` into their own domain error type
(e.g. ``ModeloBuilderError``, ``RegistrySnapshotError``) at the boundary
they own.
"""

from __future__ import annotations

from datetime import date

from ..core.errors import AeatError


class PeriodError(AeatError):
    """Base class for period-related errors."""


class PeriodValidationError(PeriodError, ValueError):
    """Raised when a period token is malformed. Inherits from ValueError for Pydantic."""


def period_start_date(filing_year: int, registry_period: str) -> date:
    """Return the inclusive start-of-period date for a registry token.

    Args:
        filing_year: The filing year carried by the typed period scope.
        registry_period: One of ``"1T"`` … ``"4T"``, ``"01"`` … ``"12"``,
            ``"0A"``.

    Returns:
        The first day of the period the token covers (e.g. ``"1T"`` →
        ``YYYY-01-01``, ``"4T"`` → ``YYYY-10-01``, ``"0A"`` →
        ``YYYY-01-01``, ``"03"`` → ``YYYY-03-01``, ``"1P"`` →
        ``YYYY-04-01``, ``"2P"`` → ``YYYY-10-01``, ``"3P"`` →
        ``YYYY-12-01``).

    Raises:
        PeriodValidationError: When ``registry_period`` is not a recognised shape.
    """
    if registry_period == "1T":
        return date(filing_year, 1, 1)
    if registry_period == "2T":
        return date(filing_year, 4, 1)
    if registry_period == "3T":
        return date(filing_year, 7, 1)
    if registry_period == "4T":
        return date(filing_year, 10, 1)
    if registry_period == "0A":
        return date(filing_year, 1, 1)
    if registry_period == "1P":
        return date(filing_year, 4, 1)
    if registry_period == "2P":
        return date(filing_year, 10, 1)
    if registry_period == "3P":
        return date(filing_year, 12, 1)
    try:
        return date(filing_year, int(registry_period), 1)
    except ValueError as exc:
        raise PeriodValidationError(f"invalid registry period {registry_period!r}") from exc


def period_end_date(filing_year: int, registry_period: str) -> date:
    """Return the inclusive end-of-period date for a registry token.

    Args:
        filing_year: The filing year carried by the typed period scope.
        registry_period: One of ``"1T"`` … ``"4T"``, ``"01"`` … ``"12"``,
            ``"0A"``.

    Returns:
        The last day of the period the token covers (e.g. ``"1T"`` →
        ``YYYY-03-31``, ``"0A"`` and ``"4T"`` → ``YYYY-12-31``, ``"03"``
        → ``YYYY-03-01`` for the monthly-as-first-of-month convention
        the application layer already uses, ``"1P"`` → ``YYYY-04-30``,
        ``"2P"`` → ``YYYY-10-31``, ``"3P"`` → ``YYYY-12-31``).

    Raises:
        PeriodValidationError: When ``registry_period`` is not a recognised shape.
    """
    if registry_period == "1T":
        return date(filing_year, 3, 31)
    if registry_period == "2T":
        return date(filing_year, 6, 30)
    if registry_period == "3T":
        return date(filing_year, 9, 30)
    if registry_period in {"4T", "0A"}:
        return date(filing_year, 12, 31)
    if registry_period == "1P":
        return date(filing_year, 4, 30)
    if registry_period == "2P":
        return date(filing_year, 10, 31)
    if registry_period == "3P":
        return date(filing_year, 12, 31)
    try:
        return date(filing_year, int(registry_period), 1)
    except ValueError as exc:
        raise PeriodValidationError(f"invalid registry period {registry_period!r}") from exc


__all__ = [
    "PeriodError",
    "PeriodValidationError",
    "period_end_date",
    "period_start_date",
]
