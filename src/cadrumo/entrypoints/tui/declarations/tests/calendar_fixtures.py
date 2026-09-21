"""Synthetic declarations-calendar projections and controllers for tests.

The calendar screens are exercised from this package and, at the whole-TUI
level, from ``entrypoints.tui.tests``. The fixtures live here, beside the
calendar they describe, so every suite builds the same projection instead of
reaching into another suite's module internals.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from .....application.modelo.declarations_calendar import (
    DeclarationsCalendarEntryRefV1,
    DeclarationsCalendarProjectionV1,
    DeclarationsCalendarSource,
    DeclarationsCalendarSourceStateV1,
)
from .....application.overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendarEntrySource,
    OverviewCalendarRange,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from .....application.overview.home import HomeAvailability
from .....core.period import Period
from .....domain.deadlines.models import ObligationStatus
from ...navigation import TuiScreenContextV1
from ..controller import DeclarationsCalendarController
from ..models import CalendarEntryHandoffV1, CalendarRecoveryHandoffV1

#: The observation instant every synthetic calendar projection is built at.
CALENDAR_NOW = datetime(2026, 9, 3, 10, tzinfo=UTC)


def calendar_row(
    modelo: str,
    period_code: str,
    closes: date,
    legal: ObligationStatus,
    user: OverviewPeriodState,
    *,
    local: OverviewLocalFilingState | None = OverviewLocalFilingState.READY_TO_FILE,
    aeat: OverviewAeatSubmissionState | None = OverviewAeatSubmissionState.NOT_OBSERVED,
) -> DeclarationsCalendarEntryRefV1:
    """Build one calendar entry reference."""
    return DeclarationsCalendarEntryRefV1(
        modelo=modelo,
        filing_year=2026,
        period=Period.from_year_and_code(2026, period_code),
        opens_on=closes.replace(day=1),
        closes_on=closes,
        adjusted_closes_on=closes,
        shift_reason="fixture",
        payment_cutoff_on=closes.replace(day=max(1, closes.day - 5)),
        evaluated_on=date(2026, 9, 3),
        days_overdue=(date(2026, 9, 3) - closes).days if legal is ObligationStatus.OVERDUE else None,
        legal_status=legal,
        user_state=user,
        local_filing_state=local,
        aeat_submission_state=aeat,
        justificante_verified=None if aeat is None else False,
        evidence_conflicted=False,
        source=OverviewCalendarEntrySource.REGISTRY_DEADLINE,
    )


def calendar_projection(*, evidence_unobservable: bool = False) -> DeclarationsCalendarProjectionV1:
    """Build a three-entry calendar projection, optionally without AEAT evidence."""
    rows = (
        calendar_row("130", "1T", date(2026, 4, 20), ObligationStatus.OVERDUE, OverviewPeriodState.LATE),
        calendar_row(
            "303",
            "2T",
            date(2026, 7, 20),
            ObligationStatus.FILED,
            OverviewPeriodState.FILED,
            local=OverviewLocalFilingState.EXTERNAL_BASELINE_IMPORTED,
        ),
        calendar_row("111", "3T", date(2026, 10, 20), ObligationStatus.UPCOMING, OverviewPeriodState.DUE),
    )
    if evidence_unobservable:
        rows = tuple(
            row.model_copy(update={"aeat_submission_state": None, "justificante_verified": None}) for row in rows
        )
    return DeclarationsCalendarProjectionV1(
        as_of=date(2026, 9, 3),
        generated_at=CALENDAR_NOW,
        query_range=OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31)),
        sources=(
            DeclarationsCalendarSourceStateV1(
                source=DeclarationsCalendarSource.SCHEDULE,
                availability=HomeAvailability.AVAILABLE,
                observed_at=CALENDAR_NOW,
                item_count=3,
            ),
            DeclarationsCalendarSourceStateV1(
                source=DeclarationsCalendarSource.LOCAL_FILING,
                availability=HomeAvailability.AVAILABLE,
                observed_at=CALENDAR_NOW,
                item_count=2,
            ),
            DeclarationsCalendarSourceStateV1(
                source=DeclarationsCalendarSource.AEAT_EVIDENCE,
                availability=(HomeAvailability.NEVER_CAPTURED if evidence_unobservable else HomeAvailability.AVAILABLE),
                observed_at=None if evidence_unobservable else CALENDAR_NOW,
                reason_code="calendar.aeat.never" if evidence_unobservable else None,
                item_count=None if evidence_unobservable else 0,
            ),
        ),
        entries=rows,
    )


def calendar_controller(
    projection: DeclarationsCalendarProjectionV1,
    *,
    handoff: CalendarEntryHandoffV1 | None = None,
    recovery_handoff: CalendarRecoveryHandoffV1 | None = None,
    context: TuiScreenContextV1 | None = None,
) -> DeclarationsCalendarController:
    """Build a calendar controller over *projection*."""
    return DeclarationsCalendarController(
        context or TuiScreenContextV1(destination="workbench.declarations"),
        projection,
        entry_handoff=handoff,
        recovery_handoff=recovery_handoff,
    )
