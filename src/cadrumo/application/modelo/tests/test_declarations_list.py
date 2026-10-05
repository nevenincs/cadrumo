"""The filing list preserves local drafts alongside unlinked AEAT completions."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ....core.period import Period
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.deadlines.models import ObligationStatus
from ....domain.modelos.work_unit import WorkUnitState
from ...overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendarEntrySource,
    OverviewCalendarRange,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from ...overview.coverage import AdvisedObligation, CoverageAdviceReason, ObligationCoverageReport
from ...overview.home import HomeAvailability
from ..declaration_summary import DeclarationSummary, DeclarationSummaryState
from ..declarations_calendar import (
    DeclarationsCalendarEntryRefV1,
    DeclarationsCalendarProjectionV1,
    DeclarationsCalendarSource,
    DeclarationsCalendarSourceStateV1,
)
from ..declarations_list import DeclarationListGroup, declaration_list_rows
from ..declarations_workspace_contracts import (
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceSource,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneStateV1,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_AS_OF = date(2025, 4, 30)
_NOW = datetime(2025, 4, 30, 12, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "1T")


def _workspace(*declarations: DeclarationsWorkspaceDeclarationRefV1):
    return DeclarationsWorkspaceProjectionV1(
        bucket_id="13000000-0000-4000-8000-000000000450",
        zones=tuple(
            DeclarationsWorkspaceZoneStateV1(
                zone=zone,
                availability=DeclarationsWorkspaceAvailability.AVAILABLE,
                observed_at=_NOW,
                sources=tuple(DeclarationsWorkspaceSource),
                item_count=len(declarations) if zone is DeclarationsWorkspaceZone.DECLARATIONS else 0,
            )
            for zone in DeclarationsWorkspaceZone
        ),
        declarations=declarations,
        calculation_revisions=(),
        filings=(),
        lifecycle=(),
    )


def _local(state: DeclarationSummaryState, *, work: str = "a" * 64):
    return DeclarationsWorkspaceDeclarationRefV1(
        work_unit_id=work,
        modelo="303",
        filing_year=2025,
        period=_PERIOD,
        state=WorkUnitState.BORRADOR,
        has_current_calculation=state is not DeclarationSummaryState.DRAFT,
        has_current_filing=state is DeclarationSummaryState.RECORDED,
        summary=DeclarationSummary(state=state),
    )


def _entry(*, external: bool, conflicted: bool = False, period: Period = _PERIOD, close: date = date(2025, 4, 21)):
    filed = external and not conflicted
    return DeclarationsCalendarEntryRefV1(
        modelo="303",
        filing_year=2025,
        period=period,
        opens_on=date(2025, 4, 1),
        closes_on=close,
        adjusted_closes_on=close,
        shift_reason="unchanged",
        holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
        evaluated_on=_AS_OF,
        days_overdue=None if filed else (_AS_OF - close).days if close < _AS_OF else None,
        legal_status=ObligationStatus.FILED
        if filed
        else ObligationStatus.OVERDUE
        if close < _AS_OF
        else ObligationStatus.UPCOMING,
        user_state=OverviewPeriodState.FILED
        if filed
        else OverviewPeriodState.LATE
        if close < _AS_OF
        else OverviewPeriodState.DUE,
        local_filing_state=OverviewLocalFilingState.NOT_READY_TO_FILE,
        aeat_submission_state=OverviewAeatSubmissionState.SUBMITTED_OBSERVED
        if external
        else OverviewAeatSubmissionState.NOT_OBSERVED,
        justificante_verified=False,
        evidence_conflicted=conflicted,
        aeat_submitted_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC) if external else None,
        source=OverviewCalendarEntrySource.REGISTRY_DEADLINE,
    )


def _calendar(*entries: DeclarationsCalendarEntryRefV1, advised: tuple[AdvisedObligation, ...] = ()):
    return DeclarationsCalendarProjectionV1(
        as_of=_AS_OF,
        generated_at=_NOW,
        query_range=OverviewCalendarRange(from_date=date(2025, 1, 1), to_date=date(2025, 12, 31)),
        sources=tuple(
            DeclarationsCalendarSourceStateV1(
                source=source,
                availability=HomeAvailability.AVAILABLE,
                observed_at=_NOW,
                item_count=len(entries),
            )
            for source in DeclarationsCalendarSource
        ),
        entries=entries,
        coverage=ObligationCoverageReport(advised=advised),
    )


def test_an_unlinked_external_filing_is_a_completed_row_with_its_own_date() -> None:
    calendar = _entry(external=True)

    rows = declaration_list_rows(_workspace(), _calendar(calendar))

    assert len(rows) == 1
    row = rows[0]
    assert row.group is DeclarationListGroup.AEAT_UNLINKED and row.state == "aeat_unlinked"
    assert row.declaration is None and row.calendar is calendar
    assert row.calendar.aeat_submitted_at == datetime(2025, 4, 15, 9, 30, tzinfo=UTC)
    assert row.deadline == date(2025, 4, 21)


def test_a_local_draft_stays_in_progress_when_that_period_is_already_filed_at_aeat() -> None:
    draft = _local(DeclarationSummaryState.DRAFT)
    calendar = _entry(external=True)

    rows = declaration_list_rows(_workspace(draft), _calendar(calendar))

    assert len(rows) == 2
    local = next(row for row in rows if row.declaration is draft)
    external = next(row for row in rows if row.declaration is None)
    assert local.state == "draft" and local.group is DeclarationListGroup.IN_PROGRESS
    assert local.declaration is not None and local.declaration.summary is not None
    assert local.declaration.summary.result is None
    assert external.state == "aeat_unlinked" and external.group is DeclarationListGroup.AEAT_UNLINKED


@pytest.mark.parametrize(
    "state", [DeclarationSummaryState.DRAFT, DeclarationSummaryState.CALCULATED, DeclarationSummaryState.CHECKED]
)
def test_an_external_completion_removes_original_draft_urgency_but_preserves_correction_urgency(
    state: DeclarationSummaryState,
) -> None:
    calendar = _entry(external=True)
    original = _local(state)
    correction = original.model_copy(update={"summary": DeclarationSummary(state=state, is_correction=True)})
    original_row = next(
        row for row in declaration_list_rows(_workspace(original), _calendar(calendar)) if row.declaration
    )
    correction_row = next(
        row for row in declaration_list_rows(_workspace(correction), _calendar(calendar)) if row.declaration
    )
    assert original_row.group is (
        DeclarationListGroup.READY if state is DeclarationSummaryState.CHECKED else DeclarationListGroup.IN_PROGRESS
    )
    assert correction_row.group is DeclarationListGroup.ATTENTION
    assert original_row.state == correction_row.state == state.value


def test_a_register_status_concern_is_visible_and_keeps_due_work_uncompleted() -> None:
    concern = _entry(external=False).model_copy(update={"aeat_needs_check": True})
    rows = declaration_list_rows(_workspace(), _calendar(concern))
    assert len(rows) == 1
    assert rows[0].state == "aeat_needs_check"
    assert rows[0].group is DeclarationListGroup.ATTENTION
    assert not any(row.state == "aeat_unlinked" for row in rows)


@pytest.mark.parametrize(
    ("state", "group"),
    [
        (DeclarationSummaryState.BLOCKED, DeclarationListGroup.ATTENTION),
        (DeclarationSummaryState.UNREADABLE, DeclarationListGroup.ATTENTION),
        (DeclarationSummaryState.CHECKED, DeclarationListGroup.READY),
        (DeclarationSummaryState.CALCULATED, DeclarationListGroup.IN_PROGRESS),
        (DeclarationSummaryState.RECORDED, DeclarationListGroup.RECORDED),
        (DeclarationSummaryState.SUPERSEDED, DeclarationListGroup.RECORDED),
    ],
)
def test_local_states_are_grouped_without_building_a_form(
    state: DeclarationSummaryState, group: DeclarationListGroup
) -> None:
    rows = declaration_list_rows(_workspace(_local(state)), None)

    assert len(rows) == 1 and rows[0].state == state.value and rows[0].group is group


def test_an_overdue_unstarted_period_and_a_conflicted_submission_both_need_attention() -> None:
    for entry in (_entry(external=False), _entry(external=True, conflicted=True)):
        rows = declaration_list_rows(_workspace(), _calendar(entry))
        assert len(rows) == 1 and rows[0].group is DeclarationListGroup.ATTENTION
        assert rows[0].state == ("aeat_needs_check" if entry.evidence_conflicted else "not_started")


def test_a_later_period_is_not_hidden_by_this_periods_local_draft() -> None:
    later = _entry(external=False, period=Period.from_year_and_code(2025, "2T"), close=date(2025, 7, 21))

    rows = declaration_list_rows(_workspace(_local(DeclarationSummaryState.DRAFT)), _calendar(later))

    assert len(rows) == 2
    unstarted = next(row for row in rows if row.declaration is None)
    assert unstarted.period == later.period and unstarted.group is DeclarationListGroup.NOT_STARTED


def test_undetermined_and_window_missing_modelos_remain_visible_as_advice() -> None:
    advice = (
        AdvisedObligation(modelo="100", reason=CoverageAdviceReason.APPLICABILITY_UNDETERMINED),
        AdvisedObligation(modelo="349", reason=CoverageAdviceReason.APPLICABLE_WINDOW_MISSING),
    )

    rows = declaration_list_rows(_workspace(), _calendar(advised=advice))

    assert {row.modelo for row in rows} == {"100", "349"}
    assert all(row.group is DeclarationListGroup.MAYBE and row.period is None for row in rows)
    assert {row.advice for row in rows} == {item.reason for item in advice}
