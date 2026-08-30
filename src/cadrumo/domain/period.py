"""Date-boundary helpers for filing-period registry tokens.

:class:`~cadrumo.core.Period` is the backend filing-period authority: a filing
year plus registry token, constructed with ``Period.from_year_and_code``.
This module provides only date-boundary helpers for bare registry tokens.

Do not treat this module as canonical period storage. Prefer typed
:class:`~cadrumo.core.Period` at domain boundaries and decompose to
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

from ..core.period import Period
from ..core.period import PeriodError as CorePeriodError
from ..core.errors.hierarchy import CadrumoError


class RegistryPeriodError(CadrumoError):
    """Base class for errors raised by this bare registry-token helper module."""


class PeriodValidationError(RegistryPeriodError, ValueError):
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
    period = _period_from_registry_token(filing_year, registry_period)
    if period.has_date_span():
        return period.start_date
    if registry_period == "1P":
        return date(filing_year, 4, 1)
    if registry_period == "2P":
        return date(filing_year, 10, 1)
    if registry_period == "3P":
        return date(filing_year, 12, 1)
    raise PeriodValidationError(f"invalid registry period {registry_period!r}")


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
        → ``YYYY-03-31``, ``"1P"`` → ``YYYY-04-30``,
        ``"2P"`` → ``YYYY-10-31``, ``"3P"`` → ``YYYY-12-31``).

    Raises:
        PeriodValidationError: When ``registry_period`` is not a recognised shape.
    """
    period = _period_from_registry_token(filing_year, registry_period)
    if period.has_date_span():
        return period.end_date
    if registry_period == "1P":
        return date(filing_year, 4, 30)
    if registry_period == "2P":
        return date(filing_year, 10, 31)
    if registry_period == "3P":
        return date(filing_year, 12, 31)
    raise PeriodValidationError(f"invalid registry period {registry_period!r}")


def calculation_filing_date(period: Period) -> date:
    """Resolve the deterministic filing date used by a calculation context.

    This is deliberately distinct from :func:`period_end_date`.  The latter
    is a strict bare-token range helper and continues to refuse tokens that
    do not represent a ledger date span.  A calculation already owns a typed
    :class:`Period`, however, and needs a date for every accepted code so
    temporal registry parameters resolve consistently across calculation,
    verification, filing replay, and calculation-sheet paths.

    Args:
        period: The typed filing-period scope of the calculation.

    Returns:
        The inclusive end date for contiguous periods; the corresponding
        ordinary quarter end for ``EXT-nT``; Modelo 202 payment-month ends for
        ``1P`` through ``3P``; and 31 December for ``4P``, ``AD-HOC``, and
        ``EVENT-N``.
    """
    if period.has_date_span():
        return period.end_date

    code = period.registry_token
    if code.startswith("EXT-"):
        return Period.from_year_and_code(period.filing_year, code.removeprefix("EXT-")).end_date
    if code == "1P":
        return date(period.filing_year, 4, 30)
    if code == "2P":
        return date(period.filing_year, 10, 31)
    if code == "3P":
        return date(period.filing_year, 12, 31)
    if code == "4P" or code == "AD-HOC" or code.startswith("EVENT-"):
        return date(period.filing_year, 12, 31)
    raise PeriodValidationError(f"calculation filing date is undefined for registry period {code!r}")


def _period_from_registry_token(filing_year: int, registry_period: str) -> Period:
    """Construct the canonical typed period or preserve this module's public error contract."""
    try:
        return Period.from_year_and_code(filing_year, registry_period)
    except CorePeriodError as exc:
        raise PeriodValidationError(f"invalid registry period {registry_period!r}") from exc


__all__ = [
    "PeriodValidationError",
    "RegistryPeriodError",
    "calculation_filing_date",
    "period_end_date",
    "period_start_date",
]
