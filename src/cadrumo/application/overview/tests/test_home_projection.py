"""Contract tests for the immutable Home projection."""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from cadrumo.application.operator_actions.models import DeclaredNextAction
from cadrumo.application.overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from cadrumo.core.period import Period

from ..home import (
    HomeAccountSession,
    HomeAgendaEntry,
    HomeAvailability,
    HomeDeclarationState,
    HomeLedgerReadiness,
    HomeNextAction,
    HomeProjectionV1,
    HomeSessionPosture,
    HomeZoneState,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 9, 2, 10, 0, tzinfo=UTC)
_AVAILABLE = HomeZoneState(availability=HomeAvailability.AVAILABLE, observed_at=_NOW)
_LOCKED = HomeZoneState(availability=HomeAvailability.LOCKED, reason_code="profile.locked")


def test_available_empty_projection_preserves_proven_zero_counts() -> None:
    projection = HomeProjectionV1(
        generated_at=_NOW,
        account=HomeAccountSession(posture=HomeSessionPosture.ACTIVE, profile_label="Example profile"),
        actions_state=_AVAILABLE,
        declarations_state=_AVAILABLE,
        ledger_state=_AVAILABLE,
        ledger=HomeLedgerReadiness(entries=0, requiring_review=0, unclassified=0, missing_evidence=0),
        agenda_state=_AVAILABLE,
        agenda_evidence_state=HomeZoneState(
            availability=HomeAvailability.NEVER_CAPTURED,
            reason_code="aeat.never_captured",
        ),
        messages_state=_AVAILABLE,
        messages_requiring_attention=0,
    )

    assert projection.ledger is not None
    assert projection.ledger.entries == 0
    assert projection.messages_requiring_attention == 0
    with pytest.raises(ValidationError):
        projection.ledger.entries = 1


def test_locked_projection_cannot_claim_zero_ledger_or_messages() -> None:
    with pytest.raises(ValidationError, match="non-available Ledger zone"):
        HomeProjectionV1(
            generated_at=_NOW,
            account=HomeAccountSession(posture=HomeSessionPosture.LOCKED, profile_label="Example profile"),
            actions_state=_LOCKED,
            declarations_state=_LOCKED,
            ledger_state=_LOCKED,
            ledger=HomeLedgerReadiness(entries=0, requiring_review=0, unclassified=0, missing_evidence=0),
            agenda_state=_LOCKED,
            agenda_evidence_state=_LOCKED,
            messages_state=_LOCKED,
        )


def test_never_captured_zone_refuses_a_false_observation_time() -> None:
    with pytest.raises(ValidationError, match="never-captured"):
        HomeZoneState(
            availability=HomeAvailability.NEVER_CAPTURED,
            observed_at=_NOW,
            reason_code="messages.never_captured",
        )


def test_stale_zone_requires_the_last_observation_time() -> None:
    with pytest.raises(ValidationError, match="last observation"):
        HomeZoneState(availability=HomeAvailability.STALE, reason_code="calendar.stale")


def test_ledger_issue_counts_cannot_exceed_entries() -> None:
    with pytest.raises(ValidationError, match="cannot exceed"):
        HomeLedgerReadiness(entries=1, requiring_review=2, unclassified=0, missing_evidence=0)


def test_selected_profile_posture_requires_a_label() -> None:
    with pytest.raises(ValidationError, match="requires a profile label"):
        HomeAccountSession(posture=HomeSessionPosture.ACTIVE)


def test_local_agenda_survives_when_aeat_evidence_was_never_captured() -> None:
    agenda = HomeAgendaEntry(
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "3T"),
        due_on=date(2026, 10, 20),
        period_state=OverviewPeriodState.DUE,
        local_filing_state=OverviewLocalFilingState.READY_TO_FILE,
        aeat_submission_state=OverviewAeatSubmissionState.NOT_OBSERVED,
    )
    projection = HomeProjectionV1(
        generated_at=_NOW,
        account=HomeAccountSession(posture=HomeSessionPosture.ACTIVE, profile_label="Example profile"),
        actions_state=_AVAILABLE,
        declarations_state=_AVAILABLE,
        ledger_state=_AVAILABLE,
        ledger=HomeLedgerReadiness(entries=0, requiring_review=0, unclassified=0, missing_evidence=0),
        agenda_state=_AVAILABLE,
        agenda_evidence_state=HomeZoneState(
            availability=HomeAvailability.NEVER_CAPTURED,
            reason_code="aeat.never_captured",
        ),
        agenda=(agenda,),
        messages_state=_AVAILABLE,
        messages_requiring_attention=0,
    )

    assert projection.agenda == (agenda,)
    assert projection.agenda_evidence_state.availability is HomeAvailability.NEVER_CAPTURED


def test_agenda_requires_chronological_order_and_preview_bound() -> None:
    def entry(due_on: date) -> HomeAgendaEntry:
        return HomeAgendaEntry(
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "3T"),
            due_on=due_on,
            period_state=OverviewPeriodState.DUE,
            local_filing_state=OverviewLocalFilingState.NOT_READY_TO_FILE,
            aeat_submission_state=OverviewAeatSubmissionState.NOT_OBSERVED,
        )

    with pytest.raises(ValidationError, match="chronological"):
        HomeProjectionV1(
            generated_at=_NOW,
            account=HomeAccountSession(posture=HomeSessionPosture.ACTIVE, profile_label="Example profile"),
            actions_state=_AVAILABLE,
            declarations_state=_AVAILABLE,
            ledger_state=_AVAILABLE,
            ledger=HomeLedgerReadiness(entries=0, requiring_review=0, unclassified=0, missing_evidence=0),
            agenda_state=_AVAILABLE,
            agenda_evidence_state=_AVAILABLE,
            agenda=(entry(date(2026, 10, 21)), entry(date(2026, 10, 20))),
            messages_state=_AVAILABLE,
            messages_requiring_attention=0,
        )


def test_declaration_state_is_closed_and_period_year_must_match() -> None:
    assert HomeDeclarationState.NEEDS_REVIEW.value == "needs_review"
    with pytest.raises(ValidationError, match="filing_year must match"):
        from cadrumo.application.overview.home_projection import HomeDeclarationResume

        HomeDeclarationResume(
            work_unit_id="a" * 64,
            modelo="303",
            filing_year=2025,
            period=Period.from_year_and_code(2026, "3T"),
            name="IVA third quarter",
            state=HomeDeclarationState.NEEDS_REVIEW,
        )


def test_never_captured_aeat_evidence_refuses_an_observed_submission() -> None:
    agenda = HomeAgendaEntry(
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "3T"),
        due_on=date(2026, 10, 20),
        period_state=OverviewPeriodState.DUE,
        local_filing_state=OverviewLocalFilingState.READY_TO_FILE,
        aeat_submission_state=OverviewAeatSubmissionState.ACCEPTED,
    )
    with pytest.raises(ValidationError, match="cannot claim AEAT submission"):
        HomeProjectionV1(
            generated_at=_NOW,
            account=HomeAccountSession(posture=HomeSessionPosture.ACTIVE, profile_label="Example profile"),
            actions_state=_AVAILABLE,
            declarations_state=_AVAILABLE,
            ledger_state=_AVAILABLE,
            ledger=HomeLedgerReadiness(entries=0, requiring_review=0, unclassified=0, missing_evidence=0),
            agenda_state=_AVAILABLE,
            agenda_evidence_state=HomeZoneState(
                availability=HomeAvailability.NEVER_CAPTURED,
                reason_code="aeat.never_captured",
            ),
            agenda=(agenda,),
            messages_state=_AVAILABLE,
            messages_requiring_attention=0,
        )


def test_non_available_messages_cannot_claim_a_zero_count() -> None:
    with pytest.raises(ValidationError, match="non-available Messages zone"):
        HomeProjectionV1(
            generated_at=_NOW,
            account=HomeAccountSession(posture=HomeSessionPosture.LOCKED, profile_label="Example profile"),
            actions_state=_LOCKED,
            declarations_state=_LOCKED,
            ledger_state=_LOCKED,
            agenda_state=_LOCKED,
            agenda_evidence_state=_LOCKED,
            messages_state=_LOCKED,
            messages_requiring_attention=0,
        )


def test_action_preview_requires_contiguous_ranks_and_complete_address() -> None:
    declared = DeclaredNextAction.model_construct()
    with pytest.raises(ValidationError, match="complete or absent"):
        HomeNextAction(rank=0, action=declared, reason_code="declaration.review", modelo="303")

    actions = tuple(HomeNextAction(rank=index + 1, action=declared, reason_code="review") for index in range(2))
    with pytest.raises(ValidationError, match="contiguous ranks"):
        HomeProjectionV1(
            generated_at=_NOW,
            account=HomeAccountSession(posture=HomeSessionPosture.ACTIVE, profile_label="Example profile"),
            actions_state=_AVAILABLE,
            actions=actions,
            declarations_state=_AVAILABLE,
            ledger_state=_AVAILABLE,
            ledger=HomeLedgerReadiness(entries=0, requiring_review=0, unclassified=0, missing_evidence=0),
            agenda_state=_AVAILABLE,
            agenda_evidence_state=_AVAILABLE,
            messages_state=_AVAILABLE,
            messages_requiring_attention=0,
        )
