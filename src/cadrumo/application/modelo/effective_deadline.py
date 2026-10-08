"""The last day a filer actually has for a declaration, beside the date the registry declares.

Deadline windows store the nominal statutory close date. When that day is not
a business day the deadline moves to the next one (Ley 39/2015 art. 30.5,
applied to tax procedure through Ley 58/2003 art. 7.2), and whether a day is a
business day depends on the holiday calendar and on the filer's territory
(art. 30.6). Every surface that says whether a declaration is on time or late
-- the calculate command, the declaration editor and the filing calendar --
reads that effective date here, so none of them can judge lateness against the
nominal date while another judges it against the moved one.

The result keeps both dates and says which holidays the effective date
accounts for. A year whose holiday calendar is not published keeps the
nominal date and reports the calendar as unavailable, so an unverified date is
never shown as final.

See Also:
    :func:`cadrumo.domain.deadlines.festivos.shift_deadline`:
        The business-day rule and its modelo exceptions.
    :func:`cadrumo.domain.deadlines.plazo.resolve_filing_window`:
        The single matching authority for a declaration's deadline window.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final

from ...core.logging import get_logger
from ...core.period import Period
from ...domain.deadlines.errors import DeadlineValidationError
from ...domain.deadlines.festivos import (
    CalendarCCAA,
    DeadlineHolidayCoverage,
    HolidayJurisdiction,
    shift_deadline,
)
from ...domain.deadlines.plazo import resolve_filing_window

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

_LOG = get_logger(__name__)

#: Shift reason recorded when the holiday calendar could not be resolved.
CALENDAR_UNAVAILABLE_SHIFT_REASON: Final = "calendar_unavailable"


@dataclass(frozen=True, slots=True)
class EffectiveFilingDeadline:
    """A declaration's nominal close date and the business-day date the filer actually has.

    Attributes:
        nominal_closes_on: The close date the deadline window declares.
        closes_on: The effective close date after the business-day shift; on
            time means filed on or before this day.
        holiday_coverage: Which holidays ``closes_on`` accounts for.
            ``CALENDAR_UNAVAILABLE`` means it is the unverified nominal date.
        shift_reason: Stable token for why the date moved, or did not.
        jurisdictions: The holiday jurisdictions that moved the date.
        holiday_refs: The holidays that moved the date.
    """

    nominal_closes_on: date
    closes_on: date
    holiday_coverage: DeadlineHolidayCoverage
    shift_reason: str
    jurisdictions: tuple[HolidayJurisdiction, ...] = ()
    holiday_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Refuse an effective date earlier than the nominal one; the shift only moves forward."""
        if self.closes_on < self.nominal_closes_on:
            raise ValueError("the effective close date cannot precede the nominal close date")

    def days_remaining_on(self, reference_on: date) -> int | None:
        """Days left until the effective close date, or ``None`` once it has passed."""
        return (self.closes_on - reference_on).days if reference_on <= self.closes_on else None

    def days_overdue_on(self, reference_on: date) -> int | None:
        """Days since the effective close date, or ``None`` while it has not passed."""
        return (reference_on - self.closes_on).days if reference_on > self.closes_on else None


def effective_filing_deadline(
    nominal_closes_on: date,
    *,
    modelo: str,
    holiday_territory: CalendarCCAA | None,
    operation: PinnedAuthorityOperation,
) -> EffectiveFilingDeadline:
    """Apply the business-day rule to one nominal close date.

    ``holiday_territory`` is the filer's autonomous community; ``None`` checks
    national holidays only and the coverage says so. A holiday calendar the
    pinned authority cannot resolve keeps the nominal date with
    ``CALENDAR_UNAVAILABLE`` coverage rather than failing the read.
    """
    try:
        shift = shift_deadline(nominal_closes_on, modelo=modelo, ccaa_code=holiday_territory, operation=operation)
    except DeadlineValidationError as exc:
        _LOG.debug(
            "deadline business-day shift unavailable; keeping the nominal close date",
            extra={
                "modelo": modelo,
                "nominal_closes_on": nominal_closes_on.isoformat(),
                "error_type": type(exc).__name__,
            },
        )
        return EffectiveFilingDeadline(
            nominal_closes_on=nominal_closes_on,
            closes_on=nominal_closes_on,
            holiday_coverage=DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE,
            shift_reason=CALENDAR_UNAVAILABLE_SHIFT_REASON,
        )
    return EffectiveFilingDeadline(
        nominal_closes_on=nominal_closes_on,
        closes_on=shift.adjusted_close_date,
        holiday_coverage=shift.coverage,
        shift_reason=shift.shift_reason,
        jurisdictions=shift.jurisdictions,
        holiday_refs=shift.holiday_refs,
    )


def resolve_effective_filing_deadline(
    modelo: str,
    filing_year: int,
    period: Period,
    *,
    holiday_territory: CalendarCCAA | None,
    operation: PinnedAuthorityOperation,
) -> EffectiveFilingDeadline | None:
    """Resolve a declaration's deadline window and its effective close date, or ``None`` without a window.

    Raises:
        RegistryError: The registry could not be read, so the deadline is
            unknown rather than absent.
        DeadlineValidationError: More than one window matches the declaration.
    """
    window = resolve_filing_window(modelo, filing_year, period, authority=operation)
    if window is None:
        return None
    return effective_filing_deadline(
        window.closes_on, modelo=modelo, holiday_territory=holiday_territory, operation=operation
    )


__all__ = [
    "CALENDAR_UNAVAILABLE_SHIFT_REASON",
    "EffectiveFilingDeadline",
    "effective_filing_deadline",
    "resolve_effective_filing_deadline",
]
