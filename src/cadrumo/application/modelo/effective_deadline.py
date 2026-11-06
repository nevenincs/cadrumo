"""The last day a filer actually has for a declaration, beside the date the registry declares.

A deadline window's close is the date AEAT publishes, already moved past
weekends and national inhábil days; a window projected from the governed rule
is moved the same way. When that day is still not a business day the deadline
moves to the next one (Ley 39/2015 art. 30.5, applied to tax procedure through
Ley 58/2003 art. 7.2). An electronic filing counts days on the State's calendar
of días inhábiles (art. 31.3, which excludes art. 30.6), so only weekends and
national inhábiles move a close, and the effective date is the same for every
filer whatever their territory.
Every surface that says whether a declaration is on time or late
-- the calculate command, the declaration editor, the filing calendar and the
local filing record's timeliness -- reads that effective date here, so none of
them can judge lateness against the nominal date while another judges it
against the moved one.

The result keeps both dates and says which holidays the effective date
accounts for. A year whose holiday calendar is not published keeps the
nominal date and reports the calendar as unavailable, so an unverified date is
never shown as final. A projected window whose own close is unknown keeps its
nominal close only as a lower bound: the filer is on time up to it, and no
lateness is judged after it.

See Also:
    :func:`cadrumo.domain.deadlines.festivos.shift_deadline`:
        The business-day rule and its modelo exceptions.
    :func:`cadrumo.domain.deadlines.plazo.resolve_filing_window`:
        The single matching authority for a declaration's deadline window.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Final

from ...core.filing_timeliness import FilingTimeliness
from ...core.logging import get_logger
from ...core.period import Period
from ...core.time.clock import MADRID_TZ
from ...domain.calculations.registry.errors import RegistryError
from ...domain.deadlines.errors import DeadlineValidationError
from ...domain.deadlines.festivos import (
    DeadlineHolidayCoverage,
    HolidayJurisdiction,
    shift_deadline,
)
from ...domain.deadlines.filing_window_projection import ProjectedFilingWindowCloseUnavailable
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
        close_known: ``False`` for a projected window whose close is unknown;
            ``closes_on`` is then the nominal close as a lower bound, and no
            lateness is judged after it.
    """

    nominal_closes_on: date
    closes_on: date
    holiday_coverage: DeadlineHolidayCoverage
    shift_reason: str
    jurisdictions: tuple[HolidayJurisdiction, ...] = ()
    holiday_refs: tuple[str, ...] = ()
    close_known: bool = True

    def __post_init__(self) -> None:
        """Refuse an effective date earlier than the nominal one; the shift only moves forward."""
        if self.closes_on < self.nominal_closes_on:
            raise ValueError("the effective close date cannot precede the nominal close date")
        if not self.close_known and (
            self.closes_on != self.nominal_closes_on
            or self.holiday_coverage is not DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE
        ):
            raise ValueError("an unknown close keeps only the nominal date, with the calendar unavailable")

    def days_remaining_on(self, reference_on: date) -> int | None:
        """Days left until the effective close date, or ``None`` once it has passed.

        For an unknown close this counts to the nominal close, which the close
        is never earlier than.
        """
        return (self.closes_on - reference_on).days if reference_on <= self.closes_on else None

    def days_overdue_on(self, reference_on: date) -> int | None:
        """Days since the effective close date, or ``None`` while it has not passed or is unknown."""
        if not self.close_known:
            return None
        return (reference_on - self.closes_on).days if reference_on > self.closes_on else None

    def timeliness_on(self, presented_on: date) -> FilingTimeliness:
        """Say whether a presentation on this date is inside the plazo voluntario, or late.

        Derived from the same one-sided day counts the deadline posture uses, so
        a surface cannot call a filing late that the posture calls in time. An
        unknown close keeps its nominal date as a lower bound only: a
        presentation up to it is still in time, and nothing past it is judged.

        This is a calendar posture, never an Article 27 assessment; see
        :class:`~cadrumo.core.filing_timeliness.FilingTimeliness`.
        """
        if self.days_overdue_on(presented_on) is not None:
            return FilingTimeliness.EXTEMPORANEA
        if self.days_remaining_on(presented_on) is not None:
            return FilingTimeliness.EN_PLAZO
        return FilingTimeliness.UNKNOWN


def effective_filing_deadline(
    nominal_closes_on: date,
    *,
    modelo: str,
    operation: PinnedAuthorityOperation,
) -> EffectiveFilingDeadline:
    """Apply the national business-day rule to one nominal close date.

    A holiday calendar the pinned authority cannot resolve keeps the nominal date with
    ``CALENDAR_UNAVAILABLE`` coverage rather than failing the read.
    """
    try:
        shift = shift_deadline(nominal_closes_on, modelo=modelo, operation=operation)
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
    operation: PinnedAuthorityOperation,
) -> EffectiveFilingDeadline | None:
    """Resolve a declaration's deadline window and its effective close date, or ``None`` without a window.

    A projected window whose close is unknown resolves with ``close_known``
    false; it is never ``None``, because an unknown close is not an absent one.

    Raises:
        RegistryError: The registry could not be read, so the deadline is
            unknown rather than absent.
        DeadlineValidationError: More than one window matches the declaration.
    """
    resolution = resolve_filing_window(modelo, filing_year, period, authority=operation)
    if resolution is None:
        return None
    if isinstance(resolution, ProjectedFilingWindowCloseUnavailable):
        return EffectiveFilingDeadline(
            nominal_closes_on=resolution.nominal_closes_on,
            closes_on=resolution.nominal_closes_on,
            holiday_coverage=DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE,
            shift_reason=CALENDAR_UNAVAILABLE_SHIFT_REASON,
            close_known=False,
        )
    return effective_filing_deadline(resolution.closes_on, modelo=modelo, operation=operation)


def resolve_filing_timeliness(
    modelo: str,
    filing_year: int,
    period: Period,
    *,
    presented_on: date,
    operation: PinnedAuthorityOperation,
) -> FilingTimeliness:
    """Judge one presentation date against the declaration's plazo voluntario.

    A declaration whose axis the registry declares no window for is
    :attr:`~cadrumo.core.filing_timeliness.FilingTimeliness.UNKNOWN`: an absent
    window says nothing about punctuality.

    Raises:
        RegistryError: The registry could not be read, so timeliness is unknown
            rather than decided. A caller that must not lose a committed fact to
            a projection failure degrades it to ``UNKNOWN`` itself.
        DeadlineValidationError: More than one window matches the declaration.
    """
    deadline = resolve_effective_filing_deadline(modelo, filing_year, period, operation=operation)
    if deadline is None:
        return FilingTimeliness.UNKNOWN
    return deadline.timeliness_on(presented_on)


def decide_filing_timeliness(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    filed_at: datetime,
    operation: PinnedAuthorityOperation,
) -> FilingTimeliness:
    """Decide the posture to KEEP on a filing being recorded now.

    The presentation date is the Europe/Madrid civil date of ``filed_at``. A
    filing plazo is a Spanish-calendar boundary (Ley 39/2015 art. 31), and the
    UTC date reports the previous Spanish day for up to two hours every night.

    This is the writer's decision point, so it must yield a value rather than
    raise: the filing is being committed, and a deadline window that cannot be
    read is recorded as
    :attr:`~cadrumo.core.filing_timeliness.FilingTimeliness.UNKNOWN` instead of
    discarding the filing or passing an unreadable registry off as punctuality.
    Readers report the kept value; none of them judges it again, because a
    window amended later must not change what a past filing's posture was.
    """
    try:
        return resolve_filing_timeliness(
            modelo,
            filing_year,
            period,
            presented_on=filed_at.astimezone(MADRID_TZ).date(),
            operation=operation,
        )
    except (RegistryError, DeadlineValidationError):
        _LOG.debug(
            "filing timeliness undecidable; recording it as unknown",
            extra={
                "modelo": modelo,
                "filing_year": filing_year,
                "period": period.registry_token,
            },
            exc_info=True,
        )
        return FilingTimeliness.UNKNOWN


__all__ = [
    "CALENDAR_UNAVAILABLE_SHIFT_REASON",
    "EffectiveFilingDeadline",
    "decide_filing_timeliness",
    "effective_filing_deadline",
    "resolve_effective_filing_deadline",
    "resolve_filing_timeliness",
]
