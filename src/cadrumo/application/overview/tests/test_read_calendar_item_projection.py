"""Filing evidence survives the public calendar projection without losing an axis."""

from __future__ import annotations

import pytest

from ....core.period import Period
from ..calendar_models import (
    OverviewAeatEvidenceConcern,
    OverviewAeatSubmissionState,
    OverviewCalendarFilingEvidence,
)
from ..read_calendar_item_projection import OverviewFilingEvidenceSnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_the_snapshot_carries_every_filing_evidence_field() -> None:
    assert set(OverviewFilingEvidenceSnapshot.model_fields) == set(OverviewCalendarFilingEvidence.model_fields)


def test_register_concerns_round_trip_and_keep_the_filing_open() -> None:
    evidence = OverviewCalendarFilingEvidence(
        modelo="303",
        period=Period.from_year_and_code(2023, "1T"),
        aeat_submission_state=OverviewAeatSubmissionState.SUBMITTED_OBSERVED,
        aeat_evidence_concerns=(OverviewAeatEvidenceConcern.INACTIVE_REGISTER,),
    )

    restored = OverviewFilingEvidenceSnapshot.from_evidence(evidence).to_evidence()

    assert restored == evidence
    assert not restored.aeat_filed
