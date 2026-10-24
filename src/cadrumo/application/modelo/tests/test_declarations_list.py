"""The filing list preserves local drafts alongside unlinked AEAT completions."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.period import Period
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.deadlines.models import ObligationStatus
from ....domain.modelos.work_unit import WorkUnitState
from ...overview.calendar import holiday_coverage_statement
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
from ..declaration_targets import DeclarationTarget
from ..declarations_calendar import (
    DeclarationsCalendarEntryRefV1,
    DeclarationsCalendarProjectionV1,
    DeclarationsCalendarSource,
    DeclarationsCalendarSourceStateV1,
)
from ..declarations_list import (
    DECLARATION_GROUP_LOCALE_KEYS,
    DeclarationListGroup,
    DeclarationListNextStep,
    calendar_sources,
    deadline_note_words,
    declaration_list_rows,
    group_words,
    source_notices,
    worded_creation_targets,
    worded_declaration_list,
    zone_states,
)
from ..declarations_list_operation import (
    ModeloDeclarationsListProjectionV1,
    ModeloDeclarationsListRequest,
    project_declarations_list,
)
from ..declarations_workspace_contracts import (
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceSource,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneStateV1,
)
from ..work_form_header import ModeloFormDeadlineTone

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


def test_each_row_names_its_step_and_keeps_the_aeats_facts_beside_its_own() -> None:
    blocked = _local(DeclarationSummaryState.BLOCKED).model_copy(
        update={"summary": DeclarationSummary(state=DeclarationSummaryState.BLOCKED, blocking_count=2)}
    )
    checked = _local(DeclarationSummaryState.CHECKED, work="b" * 64).model_copy(
        update={"period": Period.from_year_and_code(2025, "2T")}
    )
    later = _entry(external=False, period=Period.from_year_and_code(2025, "3T"), close=date(2025, 10, 20))
    filed_elsewhere = _entry(external=True, period=Period.from_year_and_code(2025, "4T"), close=date(2026, 1, 30))

    rows = {
        row.key: row
        for row in worded_declaration_list(
            _workspace(blocked, checked), _calendar(later, filed_elsewhere), OutputLanguage.EN
        )
    }

    fix = rows["a" * 64]
    assert (fix.next_step, fix.blocking_count, fix.opens_local_work) == (DeclarationListNextStep.FIX, 2, False)
    assert fix.work_unit_id == "a" * 64
    assert fix.state_words.startswith("▲ ")
    ready = rows["b" * 64]
    assert (ready.next_step, ready.opens_local_work, ready.group) == (
        DeclarationListNextStep.CREATE_FILE,
        True,
        DeclarationListGroup.READY,
    )
    due = next(row for row in rows.values() if row.key.startswith("due:"))
    assert (due.next_step, due.opens_local_work, due.work_unit_id) == (DeclarationListNextStep.START, False, None)
    assert due.deadline == date(2025, 10, 20)
    unlinked = next(row for row in rows.values() if row.key.startswith("aeat:"))
    # A return the AEAT holds with no local work shows the AEAT's date, never a deadline or a local result.
    assert (unlinked.deadline, unlinked.result_words, unlinked.next_step) == (None, None, None)
    assert unlinked.aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    assert unlinked.aeat_submitted_at == datetime(2025, 4, 15, 9, 30, tzinfo=UTC)
    assert all(row.modelo_title.startswith("Modelo 303") for row in rows.values())


def test_rows_are_said_in_the_language_asked_for() -> None:
    workspace = _workspace(_local(DeclarationSummaryState.DRAFT))
    english, spanish = (
        worded_declaration_list(workspace, None, language)[0] for language in (OutputLanguage.EN, OutputLanguage.ES)
    )

    assert (english.period_words, spanish.period_words) == ("1st quarter 2025", "1.er trimestre 2025")
    assert english.state_words != spanish.state_words
    assert english.next_step is spanish.next_step is DeclarationListNextStep.CONTINUE


def _zone_stale(workspace: DeclarationsWorkspaceProjectionV1) -> DeclarationsWorkspaceProjectionV1:
    zones = tuple(
        zone.model_copy(
            update={
                "availability": DeclarationsWorkspaceAvailability.STALE,
                "reason_code": "workbench.declarations.partial_read",
            }
        )
        if zone.zone is DeclarationsWorkspaceZone.FILING_HISTORY
        else zone
        for zone in workspace.zones
    )
    return workspace.model_copy(update={"zones": zones})


def test_an_open_deadline_counts_its_days_at_the_headers_thresholds_and_a_closed_row_has_none() -> None:
    soon = _entry(external=False, period=Period.from_year_and_code(2025, "2T"), close=date(2025, 5, 5))
    overdue = _entry(external=False)
    third = Period.from_year_and_code(2025, "3T")
    recorded = _local(DeclarationSummaryState.RECORDED, work="c" * 64).model_copy(update={"period": third})
    recorded_deadline = _entry(external=False, period=third, close=date(2025, 5, 2))

    rows = {
        row.key: row
        for row in worded_declaration_list(
            _workspace(recorded), _calendar(soon, overdue, recorded_deadline), OutputLanguage.EN
        )
    }

    due_soon = next(row for row in rows.values() if row.period_code == "2T")
    assert (due_soon.days_remaining, due_soon.days_overdue, due_soon.due_tone) == (5, None, ModeloFormDeadlineTone.SOON)
    assert due_soon.due_words == tr("workspace.modelo.header.deadline", date="05/05/2025", days=5, locale="en")
    late = next(row for row in rows.values() if row.key.startswith("due:") and row.period_code == "1T")
    assert (late.days_remaining, late.days_overdue, late.due_tone) == (None, 9, ModeloFormDeadlineTone.URGENT)
    closed = rows["c" * 64]
    assert closed.deadline is not None, closed
    assert (closed.days_remaining, closed.days_overdue, closed.due_words, closed.due_tone) == (None, None, None, None)


def test_every_row_names_its_group_and_a_row_with_no_step_says_why() -> None:
    unlinked = _entry(external=True)
    advice = (AdvisedObligation(modelo="100", reason=CoverageAdviceReason.APPLICABILITY_UNDETERMINED),)

    rows = worded_declaration_list(_workspace(), _calendar(unlinked, advised=advice), OutputLanguage.EN)

    assert set(DECLARATION_GROUP_LOCALE_KEYS) == set(DeclarationListGroup)
    for row in rows:
        assert row.group_words == group_words(row.group, OutputLanguage.EN) != row.group.value
    filed = next(row for row in rows if row.state == "aeat_unlinked")
    assert filed.opens_aeat_filing and filed.next_step is None
    assert filed.help_words == tr("workspace.declarations.list.aeat_unlinked.help.confirmed", locale="en")
    maybe = next(row for row in rows if row.state == "maybe")
    assert not maybe.opens_aeat_filing and maybe.help_words == tr("workspace.declarations.list.maybe.help", locale="en")


def test_the_new_declaration_dialog_offers_the_admitted_addresses_with_the_due_one_first() -> None:
    draft = _local(DeclarationSummaryState.DRAFT)
    later = _entry(external=False, period=Period.from_year_and_code(2025, "2T"), close=date(2025, 7, 21))
    rows = declaration_list_rows(_workspace(draft), _calendar(later))
    admitted = (
        DeclarationTarget("303", _PERIOD),
        DeclarationTarget("303", later.period),
        DeclarationTarget("390", Period.from_year_and_code(2025, "0A")),
    )

    targets = {
        (target.modelo, target.period_code): target
        for target in worded_creation_targets(rows, admitted, OutputLanguage.EN)
    }

    assert set(targets) == {("303", "1T"), ("303", "2T"), ("390", "0A")}
    existing = targets["303", "1T"].existing
    assert existing is not None and existing.work_unit_id == "a" * 64 and existing.state_words
    suggested = targets["303", "2T"]
    assert suggested.suggested and suggested.expected and suggested.existing is None
    assert suggested.deadline == date(2025, 7, 21) and suggested.deadline_text == "21/07/2025"
    assert not targets["390", "0A"].expected and not targets["390", "0A"].suggested
    assert [target.suggested for target in targets.values()].count(True) == 1
    # With nothing admitted, the returns due are what the dialog offers.
    offered = [(item.modelo, item.period_code) for item in worded_creation_targets(rows, (), OutputLanguage.EN)]
    assert offered == [("303", "2T")]


def test_the_list_says_what_it_could_read_and_never_passes_a_partial_read_for_everything() -> None:
    workspace = _zone_stale(_workspace())
    calendar = _calendar(_entry(external=False))
    never = calendar.model_copy(
        update={
            "sources": tuple(
                source.model_copy(
                    update={
                        "availability": HomeAvailability.NEVER_CAPTURED,
                        "observed_at": None,
                        "item_count": None,
                        "reason_code": "home.aeat.never_captured",
                    }
                )
                if source.source is DeclarationsCalendarSource.AEAT_EVIDENCE
                else source
                for source in calendar.sources
            )
        }
    )

    zones = zone_states(workspace, OutputLanguage.EN)
    sources = calendar_sources(never, OutputLanguage.EN)
    notices = source_notices(workspace, never, OutputLanguage.EN)

    assert [zone.zone for zone in zones] == list(DeclarationsWorkspaceZone)
    stale = next(zone for zone in zones if zone.zone is DeclarationsWorkspaceZone.FILING_HISTORY)
    assert stale.availability is DeclarationsWorkspaceAvailability.STALE
    assert stale.words == tr("workspace.declarations.availability.stale", locale="en")
    aeat = next(source for source in sources if source.source is DeclarationsCalendarSource.AEAT_EVIDENCE)
    assert aeat.observed_at is None and tr("workspace.declarations.calendar.never_observed", locale="en") in aeat.words
    assert notices == (aeat.words, tr("workspace.declarations.refusal.source", locale="en"))
    schedule = next(source for source in sources if source.source is DeclarationsCalendarSource.SCHEDULE)
    assert "30/04/2025 12:00 UTC" in schedule.words, schedule.words
    fresh = calendar_sources(calendar, OutputLanguage.EN)
    aeat_read = next(item.words for item in fresh if item.source is DeclarationsCalendarSource.AEAT_EVIDENCE)
    assert source_notices(_workspace(), calendar, OutputLanguage.EN) == (aeat_read,)


def test_a_deadline_short_of_the_regional_holidays_is_noted_and_a_final_one_is_not() -> None:
    national = _entry(external=False)
    regional = national.model_copy(update={"holiday_coverage": DeadlineHolidayCoverage.NATIONAL_AND_TERRITORY})

    noted = deadline_note_words(declaration_list_rows(_workspace(), _calendar(national)), OutputLanguage.ES)
    final = deadline_note_words(declaration_list_rows(_workspace(), _calendar(regional)), OutputLanguage.ES)

    assert noted == holiday_coverage_statement(DeadlineHolidayCoverage.NATIONAL_ONLY, None, OutputLanguage.ES)
    assert noted != holiday_coverage_statement(DeadlineHolidayCoverage.NATIONAL_ONLY, None, OutputLanguage.EN)
    assert final is None


def test_the_public_list_carries_what_it_could_read_and_the_dialogs_addresses_and_round_trips() -> None:
    workspace = _zone_stale(_workspace(_local(DeclarationSummaryState.DRAFT))).model_copy(
        update={"creation_targets": (DeclarationTarget("303", Period.from_year_and_code(2025, "2T")),)}
    )
    request = ModeloDeclarationsListRequest(
        profile_id=UUID("13000000-0000-4000-8000-000000000450"), output_language=OutputLanguage.EN
    )

    projection = project_declarations_list(request, workspace, _calendar(_entry(external=False)))

    assert [zone.zone for zone in projection.zones] == list(DeclarationsWorkspaceZone)
    assert {source.source for source in projection.sources} == set(DeclarationsCalendarSource)
    assert tr("workspace.declarations.refusal.source", locale="en") in projection.notices
    assert projection.deadline_note_words is not None
    assert [(target.modelo, target.period_code) for target in projection.creation_targets] == [("303", "2T")]
    assert all(row.group_words for row in projection.rows)
    restored = ModeloDeclarationsListProjectionV1.model_validate_json(projection.model_dump_json())
    assert restored == projection


def test_a_return_the_aeat_holds_opens_its_notes_in_the_rows_language_and_no_other_row_does() -> None:
    request = ModeloDeclarationsListRequest(
        profile_id=UUID("13000000-0000-4000-8000-000000000450"), output_language=OutputLanguage.ES
    )
    later = _entry(external=False, period=Period.from_year_and_code(2025, "2T"), close=date(2025, 7, 21))

    projection = project_declarations_list(
        request, _workspace(_local(DeclarationSummaryState.DRAFT)), _calendar(_entry(external=True), later)
    )

    keys = ("confirmed", "no_refile", "unavailable")
    for row in projection.rows:
        if row.opens_aeat_filing:
            assert row.aeat_filing is not None
            assert row.aeat_filing.notes == tuple(
                tr(f"workspace.declarations.list.aeat_unlinked.help.{key}", locale="es") for key in keys
            )
        else:
            assert row.aeat_filing is None, row.key
    assert any(row.opens_aeat_filing for row in projection.rows)
    assert not any(hasattr(row.aeat_filing, "reference_id") for row in projection.rows)
