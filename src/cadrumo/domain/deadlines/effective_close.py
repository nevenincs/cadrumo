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
accounts for. :meth:`EffectiveFilingDeadline.posture_on` is the one place a
reference date is judged against that close -- upcoming, due soon, due today
or overdue, and in plazo or extemporánea for a presentation -- and every
surface reads its answer instead of comparing dates itself. The judgement
depends only on the close, its holiday coverage and the reference date; it
never depends on which filing year is asked, on whether the window is
authored or projected from the governed rule, or on which surface asks.

A holiday calendar the registry does not publish for a year the shift
consults leaves the close unknown. That is the one unknown state: the nominal
date is kept only as a lower bound, a presentation up to it is in plazo, and
nothing is judged after it. The ``CALENDAR_UNAVAILABLE`` coverage on the
result is the structured finding a surface reports for it.

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
from ..calculations.registry.errors import RegistryError
from ..modelos.filing_record import FilingDeclarationKind, declaration_kind_is_timed_against_the_plazo
from .errors import DeadlineValidationError
from .festivos import (
    CALENDAR_UNAVAILABLE_SHIFT_REASON,
    DeadlineHolidayCoverage,
    HolidayJurisdiction,
    shift_deadline,
)
from .models import ObligationStatus
from .plazo import resolve_filing_window

if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation

_LOG = get_logger(__name__)

#: Days before the effective close for which an open obligation is ``DUE_SOON``.
DEFAULT_DUE_SOON_DAYS: Final = 14


def _classify_obligation_status(closes_on: date, today: date, due_soon_days: int) -> ObligationStatus:
    """Map a KNOWN effective close date to an :class:`ObligationStatus`.

    The OVERDUE / DUE_TODAY / DUE_SOON / UPCOMING boundaries. Surfaces reach
    them through :meth:`EffectiveFilingDeadline.posture_on`, which first decides
    whether the close is known at all. The date passed is the effective close,
    after the business-day shift (Ley 39/2015 art. 30.5 through Ley 58/2003
    art. 7.2), never the nominal one: a window ending on a Sunday is not
    overdue on the Monday the filer may still file.
    """
    if today > closes_on:
        return ObligationStatus.OVERDUE
    if today == closes_on:
        return ObligationStatus.DUE_TODAY
    if (closes_on - today).days <= due_soon_days:
        return ObligationStatus.DUE_SOON
    return ObligationStatus.UPCOMING


@dataclass(frozen=True, slots=True)
class DeadlinePosture:
    """Where one reference date stands against a declaration's effective close.

    Attributes:
        status: ``UPCOMING``, ``DUE_SOON``, ``DUE_TODAY`` or ``OVERDUE`` against
            a known close; ``UNKNOWN`` when the close is unknown.
        days_remaining: Days left until the close, or ``None`` once it has
            passed. For an unknown close it counts to the nominal close, a
            lower bound, and is ``None`` past it.
        days_overdue: Days since a known close, or ``None`` while it has not
            passed or is unknown.
    """

    status: ObligationStatus
    days_remaining: int | None
    days_overdue: int | None

    @property
    def timeliness(self) -> FilingTimeliness:
        """The posture a presentation on the reference date takes against the plazo voluntario."""
        if self.days_overdue is not None:
            return FilingTimeliness.EXTEMPORANEA
        if self.days_remaining is not None:
            return FilingTimeliness.EN_PLAZO
        return FilingTimeliness.UNKNOWN


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
        if not self.close_known and self.closes_on != self.nominal_closes_on:
            raise ValueError("an unknown close keeps only the nominal date")

    @property
    def close_known(self) -> bool:
        """Whether the effective close is established; ``False`` when its shift calendar is unpublished."""
        return self.holiday_coverage is not DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE

    def _days_remaining_on(self, reference_on: date) -> int | None:
        """Days left until the effective close date, or ``None`` once it has passed.

        For an unknown close this counts to the nominal close, which the close
        is never earlier than.
        """
        return (self.closes_on - reference_on).days if reference_on <= self.closes_on else None

    def _days_overdue_on(self, reference_on: date) -> int | None:
        """Days since the effective close date, or ``None`` while it has not passed or is unknown."""
        if not self.close_known:
            return None
        return (reference_on - self.closes_on).days if reference_on > self.closes_on else None

    def posture_on(self, reference_on: date, *, due_soon_days: int = DEFAULT_DUE_SOON_DAYS) -> DeadlinePosture:
        """Judge one reference date against this close: the single posture every surface reads.

        A known close classifies the date by the canonical boundaries. An
        unknown close is ``UNKNOWN``: its nominal date is only a lower bound,
        so the date is in plazo up to it and nothing is judged after it.
        """
        days_remaining = self._days_remaining_on(reference_on)
        if not self.close_known:
            return DeadlinePosture(ObligationStatus.UNKNOWN, days_remaining, None)
        return DeadlinePosture(
            _classify_obligation_status(self.closes_on, reference_on, due_soon_days),
            days_remaining,
            self._days_overdue_on(reference_on),
        )

    def timeliness_on(self, presented_on: date) -> FilingTimeliness:
        """Say whether a presentation on this date is inside the plazo voluntario, or late.

        The posture of :meth:`posture_on` read for a presentation date, so a
        filing receipt cannot call a filing late that the schedule, the
        calendar or the editor calls in time. This is a calendar posture, never
        an Article 27 assessment; see
        :class:`~cadrumo.core.filing_timeliness.FilingTimeliness`.
        """
        return self.posture_on(presented_on).timeliness


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

    An authored window and a window projected from the governed rule resolve
    through the same shift. A close whose shift calendar is unpublished
    resolves with ``close_known`` false; it is never ``None``, because an
    unknown close is not an absent one.

    Raises:
        RegistryError: The registry could not be read, so the deadline is
            unknown rather than absent.
        DeadlineValidationError: More than one window matches the declaration.
    """
    resolution = resolve_filing_window(modelo, filing_year, period, authority=operation)
    if resolution is None:
        return None
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
    declaration_kind: FilingDeclarationKind = FilingDeclarationKind.ORIGINAL,
) -> FilingTimeliness:
    """Decide the posture to KEEP on a filing being recorded now.

    ``declaration_kind`` selects whether the period's own plazo decides this
    declaration's lateness at all; a kind no official text times against that
    window keeps an unknown posture (see
    :func:`~cadrumo.domain.modelos.filing_record.declaration_kind_is_timed_against_the_plazo`).

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
    if not declaration_kind_is_timed_against_the_plazo(declaration_kind):
        return FilingTimeliness.UNKNOWN
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
    "DEFAULT_DUE_SOON_DAYS",
    "DeadlinePosture",
    "EffectiveFilingDeadline",
    "decide_filing_timeliness",
    "effective_filing_deadline",
    "resolve_effective_filing_deadline",
    "resolve_filing_timeliness",
]
