"""Exact authenticated active AEAT evidence completes an obligation without completing local drafts."""

from __future__ import annotations

from datetime import date

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.deadlines.models import ObligationStatus
from ..calendar import build_overview_calendar
from ..calendar_evidence import calendar_filing_evidence_from_sources
from ..calendar_models import (
    OverviewAeatEvidenceConcern,
    OverviewAeatSubmissionState,
    OverviewCalendarRange,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from .calendar_test_support import filed_declaration_observation, profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERIOD = Period.from_year_and_code(2025, "1T")
_RANGE = OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30))
_AS_OF = date(2025, 4, 30)


def _row(operation: PinnedAuthorityOperation, observations, *, coordinate_change: dict[str, object] | None = None):
    evidence = calendar_filing_evidence_from_sources(
        filed_declaration_observations=observations,
        expected_tax_id="X1234567L",
    )
    if coordinate_change:
        evidence = tuple(item.model_copy(update=coordinate_change) for item in evidence)
    calendar = build_overview_calendar(profile(), _RANGE, operation=operation, today=_AS_OF, filing_evidence=evidence)
    return next(item for item in calendar.entries if item.modelo == "303" and item.period == _PERIOD)


def test_an_exact_alta_is_filed_without_local_link_or_overdue_recovery(operation: PinnedAuthorityOperation) -> None:
    observed = filed_declaration_observation(artefacts=())

    row = _row(operation, (observed,))

    assert row.status is ObligationStatus.FILED
    assert row.user_state is OverviewPeriodState.FILED
    assert row.recovery is None
    assert row.days_overdue is None
    assert row.filing_evidence.local_filing_state is OverviewLocalFilingState.NOT_READY_TO_FILE
    assert row.filing_evidence.aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    assert row.filing_evidence.aeat_submitted_at == observed.presented_at
    assert row.filing_evidence.justificante_verified is False
    assert row.filing_evidence.aeat_reference_id == observed.expediente_id
    assert row.filing_evidence.aeat_evidence_concerns == ()


@pytest.mark.parametrize(
    "change",
    [
        {"authenticated_identity": "Y7654321G"},
        {"status": "BAJA"},
        {"period": Period.from_year_and_code(2025, "2T")},
        {"modelo": "130"},
    ],
)
def test_wrong_identity_inactive_status_and_other_coordinates_do_not_complete_this_period(
    operation: PinnedAuthorityOperation,
    change: dict[str, object],
) -> None:
    observation_change = {
        key: value
        for key, value in change.items()
        if key in {"authenticated_identity", "status"} and isinstance(value, str)
    }
    coordinate_change = {key: value for key, value in change.items() if key in {"period", "modelo"}}
    observed = filed_declaration_observation(artefacts=()).model_copy(update=observation_change)

    row = _row(operation, (observed,), coordinate_change=coordinate_change)

    assert row.status is ObligationStatus.OVERDUE
    assert row.user_state is OverviewPeriodState.LATE
    assert row.recovery is not None
    assert row.days_overdue is not None and row.days_overdue > 0
    assert row.filing_evidence.aeat_submission_state is OverviewAeatSubmissionState.NOT_OBSERVED
    assert row.filing_evidence.aeat_evidence_concerns == (
        (OverviewAeatEvidenceConcern.INACTIVE_REGISTER,) if change.get("status") == "BAJA" else ()
    )


@pytest.mark.parametrize(
    ("status", "concern"),
    [
        ("BAJA", OverviewAeatEvidenceConcern.INACTIVE_REGISTER),
        ("UNKNOWN", OverviewAeatEvidenceConcern.UNKNOWN_REGISTER),
    ],
)
def test_inactive_and_unknown_register_rows_stay_visible_as_concerns_without_completion(
    operation: PinnedAuthorityOperation, status: str, concern: OverviewAeatEvidenceConcern
) -> None:
    observation = filed_declaration_observation(artefacts=()).model_copy(update={"status": status})
    row = _row(operation, (observation,))
    assert row.status is ObligationStatus.OVERDUE
    assert row.filing_evidence.aeat_evidence_concerns == (concern,)
    assert row.filing_evidence.aeat_submission_state is OverviewAeatSubmissionState.NOT_OBSERVED
    assert row.filing_evidence.aeat_submitted_at is None
    assert not row.filing_evidence.justificante_verified


def test_identity_mismatch_does_not_even_expose_a_register_concern(operation: PinnedAuthorityOperation) -> None:
    observation = filed_declaration_observation(artefacts=()).model_copy(
        update={"status": "BAJA", "authenticated_identity": "Y7654321G"}
    )
    row = _row(operation, (observation,))
    assert row.filing_evidence.aeat_evidence_concerns == ()
    assert row.filing_evidence.aeat_reference_id is None


def test_a_status_concern_cannot_be_erased_by_an_alta_for_the_same_period(operation: PinnedAuthorityOperation) -> None:
    active = filed_declaration_observation(artefacts=(), expediente_id="12345678901234567890")
    inactive = filed_declaration_observation(artefacts=(), expediente_id="12345678901234567891").model_copy(
        update={"status": "BAJA"}
    )
    row = _row(operation, (active, inactive))
    assert row.filing_evidence.aeat_evidence_concerns == (OverviewAeatEvidenceConcern.INACTIVE_REGISTER,)
    assert not row.filing_evidence.aeat_filed
    assert row.status is ObligationStatus.OVERDUE and row.recovery is not None


def test_conflicting_alta_references_keep_the_obligation_open_for_checking(operation: PinnedAuthorityOperation) -> None:
    first = filed_declaration_observation(artefacts=(), expediente_id="12345678901234567890")
    second = filed_declaration_observation(artefacts=(), expediente_id="12345678901234567891")

    row = _row(operation, (first, second))

    assert row.filing_evidence.aeat_evidence_conflict_reference_ids
    assert row.status is ObligationStatus.OVERDUE
    assert row.user_state is OverviewPeriodState.LATE
    assert row.recovery is not None
