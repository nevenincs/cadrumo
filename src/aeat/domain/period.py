"""Date-boundary helpers for filing-period registry tokens.

:class:`~aeat.core.Period` is the backend filing-period authority: a filing
year plus registry token, constructed with ``Period.from_year_and_code``.
This module provides only date-boundary helpers for bare registry tokens.

Do not treat this module as canonical period storage. Prefer typed
:class:`~aeat.core.Period` at domain boundaries and decompose to
``filing_year`` plus ``registry_token`` only at registry/helper seams.

The ``nP`` tokens are the Impuesto sobre Sociedades pago-fraccionado
instalment claves (Modelo 202). Per the AEAT Modelo 202 instructions,
``1P`` is the payment made in the first twenty days of April, ``2P``
the equivalent October payment, and ``3P`` the December payment; the
period-boundary helpers map each instalment to its payment month.

These helpers are not a display parser, not a ledger date-span authority, and
not a replacement for registry period validation. They accept the bare tokens
already selected by an owning caller and raise typed domain period errors when
the token cannot be mapped.

Callers wrap :class:`ValueError` into their own domain error type
(e.g. ``ModeloBuilderError``, ``RegistrySnapshotError``) at the boundary
they own.
"""

from __future__ import annotations

from datetime import date

from ..core.errors import AeatError


class PeriodError(AeatError):
    """Base class for errors raised by this registry-token helper module."""


class PeriodValidationError(PeriodError, ValueError):
    """Raised when a bare registry token cannot be mapped to helper dates."""


def period_start_date(filing_year: int, registry_period: str) -> date:
    """Return the inclusive start-of-period date for a registry token.

    Args:
        filing_year: The filing year carried by the typed period scope.
        registry_period: Bare registry token such as ``"1T"`` ... ``"4T"``,
            ``"01"`` ... ``"12"``, ``"0A"``, or Modelo 202 instalments
            ``"1P"`` ... ``"3P"``.

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
        registry_period: Bare registry token such as ``"1T"`` ... ``"4T"``,
            ``"01"`` ... ``"12"``, ``"0A"``, or Modelo 202 instalments
            ``"1P"`` ... ``"3P"``.

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
