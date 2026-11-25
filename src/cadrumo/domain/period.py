"""Date-boundary helpers for filing-period registry tokens.

:class:`~cadrumo.core.period.Period` is the backend filing-period authority: a filing
year plus registry token, constructed with ``Period.from_year_and_code``.
This module provides only date-boundary helpers for bare registry tokens.

Do not treat this module as canonical period storage. Prefer typed
:class:`~cadrumo.core.period.Period` at domain boundaries and decompose to
``filing_year`` plus ``registry_token`` only at registry/helper seams.

The ``nP`` tokens are the Impuesto sobre Sociedades pago-fraccionado
instalment claves. The ``modelo-202-instalment-payment-months`` fact declares the
month of each payment (LIS art. 40.1), and the period-boundary helpers map each
instalment to that month.

These helpers are not a display parser, not a ledger date-span authority, and
not a replacement for registry period validation. They accept the bare tokens
already selected by an owning caller and raise typed domain period errors when
the token cannot be mapped.

Callers wrap :class:`ValueError` into their own domain error type
(e.g. ``ModeloBuilderError``, ``RegistrySnapshotError``) at the boundary
they own.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import TYPE_CHECKING, Final

from ..core.errors.hierarchy import CadrumoError
from ..core.period import Period
from ..core.period import PeriodError as CorePeriodError
from .calculations.registry.form_codes import resolve_form_codes

if TYPE_CHECKING:
    from .calculations.registry.governed_fact_scope import GovernedFactSource

_INSTALMENT_MONTHS_FACT: Final = "modelo-202-instalment-payment-months"
_FEBRUARY: Final = 2
_LEAP_FEBRUARY_DAYS: Final = 29
_THIRTY_DAY_MONTHS: Final = frozenset({4, 6, 9, 11})
_THIRTY_DAYS: Final = 30
_THIRTY_ONE_DAYS: Final = 31


class RegistryPeriodError(CadrumoError):
    """Base class for errors raised by this bare registry-token helper module."""


class PeriodValidationError(RegistryPeriodError):
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
    period = _periodfrom_registry_token(filing_year, registry_period)
    if period.has_date_span():
        return period.start_date
    month = _instalment_month(registry_period)
    if month is None:
        raise PeriodValidationError(f"invalid registry period {registry_period!r}")
    return date(filing_year, month, 1)


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
    period = _periodfrom_registry_token(filing_year, registry_period)
    if period.has_date_span():
        return period.end_date
    month = _instalment_month(registry_period)
    if month is None:
        raise PeriodValidationError(f"invalid registry period {registry_period!r}")
    return _last_day_of_month(filing_year, month)


def calculation_filing_date(period: Period, *, authority: GovernedFactSource | None = None) -> date:
    """Resolve the deterministic filing date used by a calculation context.

    This is deliberately distinct from :func:`period_end_date`.  The latter
    is a strict bare-token range helper and continues to refuse tokens that
    do not represent a ledger date span.  A calculation already owns a typed
    :class:`Period`, however, and needs a date for every accepted code so
    temporal registry parameters resolve consistently across calculation,
    verification, filing replay, and calculation-sheet paths.

    Args:
        period: The typed filing-period scope of the calculation.
        authority: The pinned registry generation that declares the instalment payment months;
            ``None`` reads the governed-fact scope in progress.

    Returns:
        The inclusive end date for contiguous periods; the corresponding
        ordinary quarter end for ``EXT-nT``; Modelo 202 payment-month ends for
        ``1P`` through ``3P``; and 31 December for ``4P`` and ``EVENT-N``.
    """
    if period.has_date_span():
        return period.end_date

    code = period.registry_token
    if (scheme_quarter := period.scheme_quarter) is not None:
        return Period.from_year_and_code(period.filing_year, scheme_quarter.value).end_date
    month = _instalment_month(code, authority=authority)
    if month is not None:
        return _last_day_of_month(period.filing_year, month)
    if code == "4P" or code.startswith("EVENT-"):
        return date(period.filing_year, 12, 31)
    raise PeriodValidationError(f"calculation filing date is undefined for registry period {code!r}")


def instalment_period_in_progress_date(period: Period, *, authority: GovernedFactSource | None = None) -> date | None:
    """Return the day whose período impositivo an instalment is paid on account of.

    LIS art. 40 makes each pago fraccionado of a contribuyente whose período
    impositivo is not the calendar year "a cuenta de la liquidación
    correspondiente al período impositivo que esté en curso el día anterior al
    inicio de cada uno de los citados períodos de pago". That is the day before
    the first day of the payment month the ``modelo-202-instalment-payment-months``
    fact declares. ``None`` when the period is not such an instalment.
    """
    month = _instalment_month(period.registry_token, authority=authority)
    if month is None:
        return None
    return date(period.filing_year, month, 1) - timedelta(days=1)


def periodo_impositivo_start(*, on: date, closing_day: int, closing_month: int, constitution: date) -> date | None:
    """Return the first day of the período impositivo in progress on ``on``.

    The período impositivo is the entity's ejercicio económico (LIS art. 27.1),
    so it starts the day after the latest ejercicio closing strictly before
    ``on``, and never before the entity was constituted. A closing on 29
    February closes on the last day of February in a common year.

    Returns:
        The start date, or ``None`` when the entity was constituted after ``on``
        and so had no período impositivo in progress that day.
    """
    if constitution > on:
        return None
    closing = _ejercicio_closing(on.year, closing_month, closing_day)
    if closing >= on:
        closing = _ejercicio_closing(on.year - 1, closing_month, closing_day)
    return max(closing + timedelta(days=1), constitution)


def ejercicio_closing_is_valid(*, closing_day: int, closing_month: int) -> bool:
    """Whether a stated day and month name a day some year has, 29 February included."""
    if not 1 <= closing_month <= 12:
        return False
    if closing_month == _FEBRUARY:
        longest = _LEAP_FEBRUARY_DAYS
    else:
        longest = _THIRTY_DAYS if closing_month in _THIRTY_DAY_MONTHS else _THIRTY_ONE_DAYS
    return 1 <= closing_day <= longest


def _ejercicio_closing(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _instalment_month(token: str, *, authority: GovernedFactSource | None = None) -> int | None:
    """Return the payment month the registry declares for an instalment token, if it is one."""
    declared = resolve_form_codes(_INSTALMENT_MONTHS_FACT, authority=authority)
    return declared.integer(token) if token in declared.entries else None


def _last_day_of_month(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _periodfrom_registry_token(filing_year: int, registry_period: str) -> Period:
    """Construct the canonical typed period or preserve this module's public error contract."""
    try:
        return Period.from_year_and_code(filing_year, registry_period)
    except CorePeriodError as exc:
        raise PeriodValidationError(f"invalid registry period {registry_period!r}") from exc


__all__ = [
    "PeriodValidationError",
    "RegistryPeriodError",
    "calculation_filing_date",
    "ejercicio_closing_is_valid",
    "instalment_period_in_progress_date",
    "period_end_date",
    "period_start_date",
    "periodo_impositivo_start",
]
