"""Focused tests for pure Home projection composition."""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from cadrumo.application.ledger.models import LedgerStatusReport
from cadrumo.application.operator_actions.models import ActionReference, DeclaredNextAction
from cadrumo.application.overview.calendar_models import (
    CalendarCompleteness,
    OverviewAeatSubmissionState,
    OverviewCalendarEntry,
    OverviewCalendarFilingEvidence,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from cadrumo.core.period import Period
from cadrumo.domain.deadlines.models import ObligationStatus
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id

from ..agenda import OverviewAgenda
from ..home import HomeProjectionInput, compose_home_projection
from ..home_projection import (
    HomeAccountSession,
    HomeAvailability,
    HomeNextAction,
    HomeSessionPosture,
    HomeZoneState,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)
_AVAILABLE = HomeZoneState(availability=HomeAvailability.AVAILABLE, observed_at=_NOW)
_ACCOUNT = HomeAccountSession(posture=HomeSessionPosture.ACTIVE, profile_label="Local profile")


def _work_unit(label: str, *, updated_hour: int, calculated: bool = False) -> WorkUnit:
    period = Period.from_year_and_code(2026, "3T")
    work_unit_id = derive_work_unit_id(
        bucket_id="a" * 64,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="2026-v1",
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id="a" * 64,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="2026-v1",
        name=label,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        updated_at=datetime(2026, 9, 3, updated_hour, tzinfo=UTC),
        current_calculation_revision_id="b" * 64 if calculated else None,
    )


def _calendar_entry(modelo: str, due_on: date, period_code: str) -> OverviewCalendarEntry:
    period = Period.from_year_and_code(2026, period_code)
    return OverviewCalendarEntry(
        modelo=modelo,
        period=period,
        opens_on=due_on,
        closes_on=due_on,
        adjusted_closes_on=due_on,
        shift_reason="none",
        status=ObligationStatus.DUE_SOON,
        user_state=OverviewPeriodState.DUE,
        filing_year=2026,
        filing_evidence=OverviewCalendarFilingEvidence(
            local_filing_state=OverviewLocalFilingState.READY_TO_FILE,
            aeat_submission_state=OverviewAeatSubmissionState.ACCEPTED,
        ),
    )


def _input(**updates: object) -> HomeProjectionInput:
    values: dict[str, object] = {
        "generated_at": _NOW,
        "account": _ACCOUNT,
        "actions_state": _AVAILABLE,
        "declarations_state": _AVAILABLE,
        "ledger_state": _AVAILABLE,
        "ledger_status": LedgerStatusReport(
            bucket_id="a" * 64,
            total_count=5,
            active_count=4,
            archived_count=1,
            stashed_count=0,
            pending_review_count=2,
            reviewed_count=2,
            skipped_count=0,
            readiness_issue_count=1,
        ),
        "agenda_state": _AVAILABLE,
        "agenda_evidence_state": _AVAILABLE,
        "overview_agenda": OverviewAgenda(
            as_of=date(2026, 9, 3),
            horizon_days=60,
            generated_at=_NOW,
            completeness=CalendarCompleteness(),
        ),
        "messages_state": _AVAILABLE,
        "messages_requiring_attention": 0,
    }
    values.update(updates)
    return HomeProjectionInput.model_validate(values)


def test_composes_work_units_and_ledger_without_adapter_resolution() -> None:
    older = _work_unit("older", updated_hour=8)
    newer = _work_unit("newer", updated_hour=9, calculated=True)

    projection = compose_home_projection(_input(work_units=(older, newer)))

    assert [item.name for item in projection.declarations] == ["newer", "older"]
    assert [item.state.value for item in projection.declarations] == ["needs_review", "draft"]
    assert projection.ledger is not None
    assert projection.ledger.model_dump() == {
        "entries": 4,
        "requiring_review": 2,
        "unclassified": 2,
        "missing_evidence": 1,
    }


def test_actions_are_deterministically_sorted_trimmed_and_reranked() -> None:
    actions = tuple(
        HomeNextAction(
            rank=rank,
            action=DeclaredNextAction(action=ActionReference(action_id=f"home.action_{suffix}")),
            reason_code=f"reason.{suffix}",
        )
        for rank, suffix in ((8, "d"), (1, "b"), (1, "a"), (4, "c"))
    )

    projection = compose_home_projection(_input(actions=actions))

    assert [item.action.action.action_id for item in projection.actions] == [
        "home.action_a",
        "home.action_b",
        "home.action_c",
    ]
    assert [item.rank for item in projection.actions] == [0, 1, 2]


def test_agenda_uses_legal_due_date_top_three_and_masks_unobservable_aeat_evidence() -> None:
    entries = (
        _calendar_entry("390", date(2026, 10, 23), "0A"),
        _calendar_entry("303", date(2026, 10, 20), "3T"),
        _calendar_entry("130", date(2026, 10, 20), "3T"),
        _calendar_entry("111", date(2026, 10, 21), "3T"),
    )
    agenda = OverviewAgenda(
        as_of=date(2026, 9, 3),
        horizon_days=60,
        due_soon=entries,
        generated_at=_NOW,
        completeness=CalendarCompleteness(),
    )
    never_captured = HomeZoneState(
        availability=HomeAvailability.NEVER_CAPTURED,
        reason_code="aeat.never_captured",
    )

    projection = compose_home_projection(
        _input(overview_agenda=agenda, agenda_evidence_state=never_captured),
    )

    assert [(item.due_on, item.modelo) for item in projection.agenda] == [
        (date(2026, 10, 20), "130"),
        (date(2026, 10, 20), "303"),
        (date(2026, 10, 21), "111"),
    ]
    assert all(item.aeat_submission_state is OverviewAeatSubmissionState.NOT_OBSERVED for item in projection.agenda)


def test_non_available_reader_result_is_refused_instead_of_becoming_a_false_empty_state() -> None:
    locked = HomeZoneState(availability=HomeAvailability.LOCKED, reason_code="profile.locked")

    with pytest.raises(ValidationError, match="non-available Ledger zone"):
        compose_home_projection(_input(ledger_state=locked))
