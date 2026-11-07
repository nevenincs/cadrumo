"""Filing windows projected from the governed filing-window rule where none is authored.

A revision may author a deadline window for a modelo, filing year and period.
That authored window is an explicit statement of the published dates and always
wins. Where none is authored, the window is projected from two governed mapping
facts, resolved through canonical governed-fact temporal selection:

* ``deadlines.filing-window-clause``: per modelo and period, the day the window
  opens and the month and day it nominally closes (RD 1624/1992 art. 71.4,
  Orden EHA/3786/2008 art. 7, Orden EHA/3111/2009 art. 8).
* ``deadlines.filing-close-inhabil-shift``: the extension of a nominal close
  that falls on an inhábil day to the next día hábil (Ley 39/2015 art. 30.5,
  reached through its DA 1ª.2 and Ley 58/2003 art. 7.2), counted on the national
  calendar, the only calendar that moves an electronic filing close (art. 31.3).

A window is projected only where the law-selected revision's filing schedule
declares the period: the schedule decides that an obligation exists, the clause
only supplies its dates. A projected window is a dated window like an authored
one, and every consumer judges it the same way. When its shift needs a holiday
calendar the registry has not published, it keeps its nominal close with
``CALENDAR_UNAVAILABLE`` coverage -- the same state an authored window whose
shift calendar is unpublished reaches -- so its close is unknown, never
computed against a holiday-free calendar nor reported as absent.

Window matching stays with :func:`~cadrumo.domain.deadlines.plazo.resolve_filing_window`;
this module projects one coordinate and enumerates a year's unauthored ones.
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Final, Literal

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period, PeriodError
from ..calculations.registry.errors import (
    FilingYearOutsideSupportEnvelopeError,
    GovernedFactNotApplicableError,
    NoRevisionForPeriodError,
    RegistryValidationError,
)
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.facts.variants import FactSelector
from ..calculations.registry.schema_base import DateAxis
from ..calculations.registry.schema_deadlines import DeadlineWindowDefinition
from ..calculations.registry.schema_references import TemporalProjectionDirection
from .errors import DeadlineValidationError
from .festivos import (
    CALENDAR_UNAVAILABLE_SHIFT_REASON,
    DeadlineHolidayCoverage,
    HolidayCalendar,
    load_holiday_calendar,
    shift_deadline,
)

if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation
    from ..calculations.registry.schema_deadlines import ModeloScheduleDefinition
    from ..calculations.registry.temporal import RevisionSelectionMetadata

FILING_WINDOW_CLAUSE_FACT_ID: Final = "deadlines.filing-window-clause"
FILING_CLOSE_SHIFT_FACT_ID: Final = "deadlines.filing-close-inhabil-shift"

_MODELO_SELECTOR: Final = "modelo"
_MONTH_END: Final = "month_end"
_MAX_DAY_OF_MONTH: Final = 31
_MAX_MONTH_OFFSET: Final = 12
_CLAUSE_KEYS: Final = frozenset({"opens", "deadline_month_offset", "filing_last_day"})
_SHIFT_KEYS: Final = frozenset({"rule", "calendar_scope", "inhabil_basis"})


class FilingWindowSource(StrEnum):
    """Where a filing window's dates come from."""

    AUTHORED = "authored"
    PROJECTED = "projected"


class FilingWindowOpening(StrEnum):
    """When a projected window opens."""

    DAY_AFTER_PERIOD_END = "day_after_period_end"


class FilingCloseShiftRule(StrEnum):
    """How an inhábil nominal close is extended."""

    NEXT_BUSINESS_DAY = "next_business_day"


class FilingCloseCalendarScope(StrEnum):
    """Which holiday calendar decides that a nominal close is inhábil."""

    NATIONAL = "national"


class FilingCloseInhabilBasis(StrEnum):
    """What grounds the calendar scope of the shift."""

    AEAT_PUBLISHED_PRACTICE = "aeat_published_practice"


# ---------------------------------------------------------------------------
# Typed rule parts read from the governed facts.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FilingWindowClause:
    """One filing-window clause: when the window opens and when it nominally closes.

    ``filing_last_day`` of ``None`` means the last day of the deadline month.
    """

    opening: FilingWindowOpening
    deadline_month_offset: int
    filing_last_day: int | None

    def deadline_month(self, period_end: date) -> tuple[int, int]:
        """Return the year and month in which the window nominally closes."""
        month_index = period_end.year * 12 + (period_end.month - 1) + self.deadline_month_offset
        return month_index // 12, month_index % 12 + 1

    def opens_on(self, period_end: date) -> date:
        """Return the first day of the window."""
        return period_end + timedelta(days=1)

    def nominal_close(self, period_end: date) -> date:
        """Return the nominal last day of the window, before any extension for an inhábil day."""
        year, month = self.deadline_month(period_end)
        last = calendar.monthrange(year, month)[1]
        day = last if self.filing_last_day is None else self.filing_last_day
        if day > last:
            raise DeadlineValidationError(f"filing-window clause day {day} does not exist in {year}-{month:02d}")
        return date(year, month, day)


@dataclass(frozen=True, slots=True)
class FilingCloseShiftProcedure:
    """The inhábil-day extension in force on a nominal close."""

    rule: FilingCloseShiftRule
    calendar_scope: FilingCloseCalendarScope
    inhabil_basis: FilingCloseInhabilBasis


def _subject(resolved: ResolvedMappingFact) -> str:
    return f"governed fact {resolved.fact_id!r} variant {resolved.variant_id!r}"


def _entries(resolved: ResolvedMappingFact, *, keys: frozenset[str]) -> dict[str, object]:
    entries: dict[str, object] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str):
            raise RegistryValidationError(f"{_subject(resolved)} has a non-text key")
        entries[entry.key] = entry.value
    if entries.keys() != keys:
        raise RegistryValidationError(
            f"{_subject(resolved)} entries must declare exactly {sorted(keys)!r}; got {sorted(entries)!r}",
        )
    return entries


def _integer(value: object, *, key: str, minimum: int, maximum: int, subject: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise RegistryValidationError(f"{subject} {key!r} must be a whole number from {minimum} to {maximum}")
    return value


def _member[E: StrEnum](enum: type[E], value: object, *, key: str, subject: str) -> E:
    if not isinstance(value, str) or value not in {member.value for member in enum}:
        raise RegistryValidationError(f"{subject} {key!r} must be one of {sorted(member.value for member in enum)!r}")
    return enum(value)


def filing_window_clause_from_fact(resolved: ResolvedMappingFact) -> FilingWindowClause:
    """Read one resolved filing-window clause, refusing unknown keys and out-of-range days."""
    subject = _subject(resolved)
    entries = _entries(resolved, keys=_CLAUSE_KEYS)
    raw_day = entries["filing_last_day"]
    return FilingWindowClause(
        opening=_member(FilingWindowOpening, entries["opens"], key="opens", subject=subject),
        deadline_month_offset=_integer(
            entries["deadline_month_offset"],
            key="deadline_month_offset",
            minimum=0,
            maximum=_MAX_MONTH_OFFSET,
            subject=subject,
        ),
        filing_last_day=(
            None
            if raw_day == _MONTH_END
            else _integer(raw_day, key="filing_last_day", minimum=1, maximum=_MAX_DAY_OF_MONTH, subject=subject)
        ),
    )


def filing_close_shift_from_fact(resolved: ResolvedMappingFact) -> FilingCloseShiftProcedure:
    """Read one resolved inhábil-day shift procedure, refusing unknown keys and tokens."""
    subject = _subject(resolved)
    entries = _entries(resolved, keys=_SHIFT_KEYS)
    return FilingCloseShiftProcedure(
        rule=_member(FilingCloseShiftRule, entries["rule"], key="rule", subject=subject),
        calendar_scope=_member(
            FilingCloseCalendarScope, entries["calendar_scope"], key="calendar_scope", subject=subject
        ),
        inhabil_basis=_member(FilingCloseInhabilBasis, entries["inhabil_basis"], key="inhabil_basis", subject=subject),
    )


class FilingWindowRuleEvidence(BaseModel):
    """The governed-fact variant one part of a projection resolved to."""

    model_config = STRICT_FROZEN_CONFIG

    fact_id: str = Field(min_length=1)
    variant_id: str = Field(min_length=1)
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    review_status: str = Field(min_length=1)
    projection_direction: TemporalProjectionDirection
    projected_from_date: date | None = None

    @classmethod
    def from_fact(cls, resolved: ResolvedMappingFact) -> FilingWindowRuleEvidence:
        """Retain the identity, evidence and projection of one resolved fact."""
        return cls(
            fact_id=resolved.fact_id,
            variant_id=resolved.variant_id,
            legal_refs=tuple(resolved.legal_refs),
            source_refs=tuple(resolved.source_refs),
            review_status=resolved.review_status.value,
            projection_direction=resolved.projection_direction,
            projected_from_date=resolved.projected_from_date,
        )


def resolve_mapping_fact(operation: PinnedAuthorityOperation, query: MappingFactQuery) -> ResolvedMappingFact | None:
    try:
        resolved = operation.resolve_governed_fact(query)
    except GovernedFactNotApplicableError:
        return None
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError(f"governed fact {query.fact_id!r} must resolve to a mapping fact")
    return resolved


def resolve_filing_window_clause(
    operation: PinnedAuthorityOperation,
    *,
    modelo: str,
    period: Period,
) -> tuple[FilingWindowClause, ResolvedMappingFact] | None:
    """Resolve the filing-window clause of one dated period, or ``None`` when none is declared.

    The coordinate is the end of the period on the filing-period axis, the same
    coordinate every period-keyed deadline clause is selected by. A filing year
    the support envelope gates addresses no clause, and neither does a period
    whose window would run past the last date the calendar can write.
    """
    if not period.has_date_span() or not operation.supported_filing_years().admits_coordinate(period.filing_year):
        return None
    if period.end_date.year >= date.max.year:
        return None
    resolved = resolve_mapping_fact(
        operation,
        MappingFactQuery(
            fact_id=FILING_WINDOW_CLAUSE_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=period.end_date,
            selectors=(FactSelector(name=_MODELO_SELECTOR, value=modelo),),
            filing_year=period.filing_year,
            period=period.registry_token,
        ),
    )
    if resolved is None:
        return None
    return filing_window_clause_from_fact(resolved), resolved


# ---------------------------------------------------------------------------
# Resolution union.
# ---------------------------------------------------------------------------


class AuthoredFilingWindow(BaseModel):
    """A window a revision authors; it wins over the rule."""

    model_config = STRICT_FROZEN_CONFIG

    source: Literal[FilingWindowSource.AUTHORED] = FilingWindowSource.AUTHORED
    window: DeadlineWindowDefinition

    @property
    def dated_window(self) -> DeadlineWindowDefinition:
        """The window with a known close."""
        return self.window

    @property
    def window_id(self) -> str:
        """The authored window identity."""
        return self.window.id

    @property
    def period(self) -> Period:
        """The filing period the window covers."""
        return self.window.period

    @property
    def opens_on(self) -> date:
        """The first day of the window."""
        return self.window.opens_on

    @property
    def closes_on(self) -> date:
        """The published close of the window."""
        return self.window.closes_on


class ProjectedFilingWindow(BaseModel):
    """A window projected from the governed rule, with its provenance.

    ``window`` is the projection materialised as a deadline window so every
    consumer reads it as it reads an authored one; it never authors a payment
    cutoff, which the domiciliación resolver derives. Its ``closes_on`` is the
    close after the national inhábil-day shift, or the nominal close when the
    shift's holiday calendar is unpublished (``holiday_coverage`` is then
    ``CALENDAR_UNAVAILABLE``).
    """

    model_config = STRICT_FROZEN_CONFIG

    source: Literal[FilingWindowSource.PROJECTED] = FilingWindowSource.PROJECTED
    window: DeadlineWindowDefinition
    nominal_closes_on: date
    shift_reason: str = Field(min_length=1)
    holiday_refs: tuple[str, ...] = ()
    holiday_coverage: DeadlineHolidayCoverage
    clause: FilingWindowRuleEvidence
    shift: FilingWindowRuleEvidence
    inhabil_basis: FilingCloseInhabilBasis

    @property
    def dated_window(self) -> DeadlineWindowDefinition:
        """The projected window with its known close."""
        return self.window

    @property
    def window_id(self) -> str:
        """The deterministic projected window identity."""
        return self.window.id

    @property
    def period(self) -> Period:
        """The filing period the window covers."""
        return self.window.period

    @property
    def opens_on(self) -> date:
        """The first day of the window."""
        return self.window.opens_on

    @property
    def closes_on(self) -> date:
        """The close after the national inhábil-day shift."""
        return self.window.closes_on

    @property
    def projection_direction(self) -> TemporalProjectionDirection:
        """How the clause variant reached this coordinate."""
        return self.clause.projection_direction


FilingWindowResolution = Annotated[
    AuthoredFilingWindow | ProjectedFilingWindow,
    Field(discriminator="source"),
]


# ---------------------------------------------------------------------------
# Projection.
# ---------------------------------------------------------------------------


def projected_window_id(modelo: str, period: Period) -> str:
    """Return the deterministic identity of a projected window; it cannot collide with an authored id."""
    return f"projected-{modelo}-{period.filing_year}-{period.registry_token.lower()}"


def _calendar_available(
    year: int,
    *,
    calendars: tuple[HolidayCalendar, ...],
    operation: PinnedAuthorityOperation,
) -> bool:
    """Return whether ``year`` is supplied or published, so the shift can classify its days."""
    if any(holiday_calendar.year == year for holiday_calendar in calendars):
        return True
    try:
        load_holiday_calendar(year, operation=operation)
    except DeadlineValidationError:
        return False
    return True


def project_scheduled_window(
    operation: PinnedAuthorityOperation,
    *,
    modelo: str,
    period: Period,
    schedule: ModeloScheduleDefinition,
    calendars: tuple[HolidayCalendar, ...],
) -> ProjectedFilingWindow | None:
    """Project the filing window of a scheduled modelo period from its registry clause."""
    clause_resolution = resolve_filing_window_clause(operation, modelo=modelo, period=period)
    if clause_resolution is None:
        return None
    clause, clause_fact = clause_resolution
    period_end = period.end_date
    opens_on = clause.opens_on(period_end)
    nominal = clause.nominal_close(period_end)
    shift_fact = resolve_mapping_fact(
        operation,
        MappingFactQuery(
            fact_id=FILING_CLOSE_SHIFT_FACT_ID, date_axis=DateAxis.SUBMISSION_DATE, effective_date=nominal
        ),
    )
    if shift_fact is None:
        return None
    procedure = filing_close_shift_from_fact(shift_fact)
    clause_evidence = FilingWindowRuleEvidence.from_fact(clause_fact)
    shift_evidence = FilingWindowRuleEvidence.from_fact(shift_fact)
    closes_on, holiday_coverage, shift_reason, holiday_refs = _shifted_close(
        nominal, modelo=modelo, calendars=calendars, operation=operation
    )
    window = DeadlineWindowDefinition(
        id=projected_window_id(modelo, period),
        filing_year=period.filing_year,
        period=period,
        period_kind=schedule.period_kind,
        opens_on=opens_on,
        closes_on=closes_on,
        legal_refs=tuple(dict.fromkeys((*clause_evidence.legal_refs, *shift_evidence.legal_refs))),
        source_refs=tuple(dict.fromkeys((*clause_evidence.source_refs, *shift_evidence.source_refs))),
    )
    return ProjectedFilingWindow(
        window=window,
        nominal_closes_on=nominal,
        shift_reason=shift_reason,
        holiday_refs=holiday_refs,
        holiday_coverage=holiday_coverage,
        clause=clause_evidence,
        shift=shift_evidence,
        inhabil_basis=procedure.inhabil_basis,
    )


def _shifted_close(
    nominal: date,
    *,
    modelo: str,
    calendars: tuple[HolidayCalendar, ...],
    operation: PinnedAuthorityOperation,
) -> tuple[date, DeadlineHolidayCoverage, str, tuple[str, ...]]:
    """Return the close after the inhábil-day shift, its coverage, reason and moving holidays.

    A close whose year, or the following year the walk enters, has no
    published holiday calendar keeps its nominal date with
    ``CALENDAR_UNAVAILABLE`` coverage: the close is unknown, and the nominal
    date is only its lower bound.
    """
    unavailable = (nominal, DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE, CALENDAR_UNAVAILABLE_SHIFT_REASON, ())
    if not _calendar_available(nominal.year, calendars=calendars, operation=operation):
        return unavailable
    try:
        shift = shift_deadline(nominal, modelo=modelo, calendars=calendars, operation=operation)
    except DeadlineValidationError:
        # The close year classifies, so a refusal here is the walk entering the
        # following year; that is a calendar gap only when the year is unpublished.
        if _calendar_available(nominal.year + 1, calendars=calendars, operation=operation):
            raise
        return unavailable
    return shift.adjusted_close_date, shift.coverage, shift.shift_reason, shift.holiday_refs


def scheduled_coordinate(
    operation: PinnedAuthorityOperation,
    *,
    modelo: str,
    filing_year: int,
    token: str,
) -> tuple[RevisionSelectionMetadata, ModeloScheduleDefinition] | None:
    """Return the law-selected revision and the schedule declaring the period, or ``None``."""
    from ..calculations.registry.temporal import select_revision_metadata

    try:
        metadata = select_revision_metadata(operation.modelo_directory(modelo), filing_year=filing_year, period=token)
    except (FilingYearOutsideSupportEnvelopeError, NoRevisionForPeriodError):
        return None
    schedule = next((item for item in metadata.filing_schedules if token in item.periods), None)
    if schedule is None:
        return None
    return metadata, schedule


@dataclass(frozen=True, slots=True)
class ProjectedWindowRow:
    """One unauthored coordinate's projection with the revision that owns its schedule."""

    modelo: str
    revision: RevisionSelectionMetadata
    resolution: ProjectedFilingWindow


def _clause_modelos(operation: PinnedAuthorityOperation) -> tuple[str, ...]:
    """Return the modelos the clause declares; only they can have a projected window."""
    fact = operation.governed_fact(FILING_WINDOW_CLAUSE_FACT_ID)
    return tuple(
        sorted(
            {
                selector.value
                for variant in fact.variants
                for selector in variant.selectors
                if selector.name == _MODELO_SELECTOR and isinstance(selector.value, str)
            },
        ),
    )


def _unauthored_row(
    operation: PinnedAuthorityOperation,
    *,
    modelo: str,
    filing_year: int,
    token: str,
) -> ProjectedWindowRow | None:
    """Project one scheduled coordinate into a row, or ``None`` when it cannot be projected."""
    try:
        period = Period.from_year_and_code(filing_year, token)
    except PeriodError:
        return None
    if not period.has_date_span():
        return None
    scheduled = scheduled_coordinate(operation, modelo=modelo, filing_year=filing_year, token=token)
    if scheduled is None:
        return None
    metadata, schedule = scheduled
    resolution = project_scheduled_window(operation, modelo=modelo, period=period, schedule=schedule, calendars=())
    if resolution is None:
        return None
    return ProjectedWindowRow(modelo=modelo, revision=metadata, resolution=resolution)


def _unauthored_modelo_rows(
    operation: PinnedAuthorityOperation,
    modelo: str,
    filing_year: int,
    covered: frozenset[str],
) -> list[ProjectedWindowRow]:
    """Project one modelo's scheduled coordinates that no authored window covers."""
    directory = operation.modelo_directory(modelo)
    tokens = sorted(
        {
            token
            for metadata in directory.revisions
            for schedule in metadata.filing_schedules
            for token in schedule.periods
        },
    )
    rows: list[ProjectedWindowRow] = []
    for token in tokens:
        if token in covered:
            continue
        row = _unauthored_row(operation, modelo=modelo, filing_year=filing_year, token=token)
        if row is not None:
            rows.append(row)
    return rows


def project_unauthored_filing_windows(
    operation: PinnedAuthorityOperation,
    filing_year: int,
    *,
    authored: Mapping[str, frozenset[str]],
) -> tuple[ProjectedWindowRow, ...]:
    """Project every scheduled coordinate of ``filing_year`` that no window authors.

    ``authored`` maps a modelo to the period tokens its authored windows already
    cover for the year; those coordinates are never projected, so an authored
    window always wins. Coordinates are enumerated from the filing schedules of
    the modelos the clause declares, and each is resolved through the canonical
    revision selector and governed-fact resolution.
    """
    rows: list[ProjectedWindowRow] = []
    registered = frozenset(operation.modelo_ids())
    for modelo in _clause_modelos(operation):
        if modelo not in registered:
            continue
        rows.extend(_unauthored_modelo_rows(operation, modelo, filing_year, authored.get(modelo, frozenset())))
    return tuple(rows)


__all__ = (
    "FILING_CLOSE_SHIFT_FACT_ID",
    "FILING_WINDOW_CLAUSE_FACT_ID",
    "AuthoredFilingWindow",
    "FilingCloseCalendarScope",
    "FilingCloseInhabilBasis",
    "FilingCloseShiftProcedure",
    "FilingCloseShiftRule",
    "FilingWindowClause",
    "FilingWindowOpening",
    "FilingWindowResolution",
    "FilingWindowRuleEvidence",
    "FilingWindowSource",
    "ProjectedFilingWindow",
    "ProjectedWindowRow",
    "filing_close_shift_from_fact",
    "filing_window_clause_from_fact",
    "project_unauthored_filing_windows",
    "projected_window_id",
    "resolve_filing_window_clause",
)
