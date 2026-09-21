"""Offline CLI/TUI parity over independent synthetic calendar stores."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest

from cadrumo.application.modelo.declarations_calendar import (
    DeclarationsCalendarSource,
    DeclarationsCalendarSourceObservationV1,
    project_declarations_calendar,
)
from cadrumo.application.overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendar,
    OverviewCalendarEntry,
    OverviewCalendarEntrySource,
    OverviewCalendarFilingEvidence,
    OverviewCalendarRange,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from cadrumo.application.overview.evidence import CalendarEvidenceProjection
from cadrumo.application.overview.home import HomeAvailability, HomeZoneState
from cadrumo.core.period import Period
from cadrumo.domain.deadlines.models import ObligationStatus
from cadrumo.entrypoints.cli._overview_rendering import overview_calendar_output
from cadrumo.entrypoints.tui.declarations.controller import DeclarationsCalendarController
from cadrumo.entrypoints.tui.declarations.models import DeclarationsCalendarScopeV1
from cadrumo.entrypoints.tui.navigation import TuiScreenContextV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

LIVE_CAPABILITIES = "NOT_EXERCISED"
_AS_OF = date(2026, 5, 30)
_GENERATED = datetime(2026, 5, 30, 10, tzinfo=UTC)
_RANGE = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
_PERIOD = Period.from_year_and_code(2026, "1T")


@dataclass(frozen=True, slots=True)
class SyntheticCalendarStore:
    """One isolated, immutable source used by exactly one frontend lane."""

    calendar: OverviewCalendar
    evidence: CalendarEvidenceProjection

    @classmethod
    def seeded(cls) -> SyntheticCalendarStore:
        filing = OverviewCalendarFilingEvidence(
            modelo="303",
            filing_year=2026,
            period=_PERIOD,
            local_filing_state=OverviewLocalFilingState.READY_TO_FILE,
            aeat_submission_state=OverviewAeatSubmissionState.NOT_OBSERVED,
            justificante_verified=False,
        )
        entry = OverviewCalendarEntry(
            modelo="303",
            period=_PERIOD,
            opens_on=date(2026, 4, 1),
            closes_on=date(2026, 4, 20),
            adjusted_closes_on=date(2026, 4, 20),
            shift_reason="none",
            payment_cutoff_on=date(2026, 4, 15),
            evaluated_on=_AS_OF,
            days_overdue=40,
            status=ObligationStatus.OVERDUE,
            user_state=OverviewPeriodState.LATE,
            filing_year=2026,
            filing_evidence=filing,
            source=OverviewCalendarEntrySource.REGISTRY_DEADLINE,
        )
        available = HomeZoneState(availability=HomeAvailability.AVAILABLE, observed_at=_GENERATED)
        return cls(
            calendar=OverviewCalendar(
                range=_RANGE,
                evaluated_on=_AS_OF,
                entries=(entry,),
                generated_at=_GENERATED,
            ),
            evidence=CalendarEvidenceProjection(
                local_state=available,
                aeat_state=available,
                evidence=(filing,),
            ),
        )


def test_cli_and_tui_preserve_the_same_calendar_meaning_offline() -> None:
    cli_store = SyntheticCalendarStore.seeded()
    tui_store = SyntheticCalendarStore.seeded()
    assert cli_store is not tui_store
    assert cli_store.calendar is not tui_store.calendar

    cli, _, _ = overview_calendar_output(cli_store.calendar, _RANGE, evidence_notices=())
    tui_projection = project_declarations_calendar(
        calendar=tui_store.calendar,
        evidence=tui_store.evidence,
        as_of=_AS_OF,
        schedule_observation=DeclarationsCalendarSourceObservationV1(
            source=DeclarationsCalendarSource.SCHEDULE,
            availability=HomeAvailability.AVAILABLE,
            observed_at=_GENERATED,
        ),
    )
    tui = DeclarationsCalendarController(
        TuiScreenContextV1(destination="workbench.declarations"),
        tui_projection,
    ).visible_entries(DeclarationsCalendarScopeV1.ALL, "")[0]
    cli_row = cli.entries[0]

    assert cli.as_of == tui.evaluated_on.isoformat() == _AS_OF.isoformat()
    assert (cli_row.modelo, cli_row.period) == (str(tui.modelo), str(tui.period))
    assert cli_row.closes_on == tui.closes_on.isoformat()
    assert cli_row.adjusted_closes_on == tui.adjusted_closes_on.isoformat()
    assert cli_row.payment_cutoff_on == tui.payment_cutoff_on.isoformat()
    assert cli_row.days_overdue == tui.days_overdue == 40
    assert cli_row.user_state == tui.user_state.value
    assert cli_row.local_filing_state == tui.local_filing_state.value
    assert cli_row.aeat_submission_state == tui.aeat_submission_state
    assert cli_row.justificante_verified is tui.justificante_verified is False
    assert LIVE_CAPABILITIES == "NOT_EXERCISED"
