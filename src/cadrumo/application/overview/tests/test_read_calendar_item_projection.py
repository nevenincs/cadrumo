"""Filing evidence survives the public calendar projection without losing an axis."""

from __future__ import annotations

from datetime import date

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.deadlines.effective_close import effective_filing_deadline
from ....domain.deadlines.models import ModeloDeadline, ObligationStatus
from ..calendar import calendar_entry_from_obligation
from ..calendar_models import (
    OverviewAeatEvidenceConcern,
    OverviewAeatSubmissionState,
    OverviewCalendarFilingEvidence,
)
from ..read_calendar_item_projection import OverviewCalendarEntrySnapshot, OverviewFilingEvidenceSnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon


def test_the_snapshot_carries_every_filing_evidence_field() -> None:
    assert set(OverviewFilingEvidenceSnapshot.model_fields) == set(OverviewCalendarFilingEvidence.model_fields)


def test_register_concerns_round_trip_and_keep_the_filing_open() -> None:
    evidence = OverviewCalendarFilingEvidence(
        modelo="303",
        period=Period.from_year_and_code(_YEAR, "1T"),
        aeat_submission_state=OverviewAeatSubmissionState.SUBMITTED_OBSERVED,
        aeat_evidence_concerns=(OverviewAeatEvidenceConcern.INACTIVE_REGISTER,),
    )

    restored = OverviewFilingEvidenceSnapshot.from_evidence(evidence).to_evidence()

    assert restored == evidence
    assert not restored.aeat_filed


def test_a_regional_holiday_close_survives_the_snapshot_round_trip(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    closes_on = date(_YEAR, 9, 11)
    effective = effective_filing_deadline(closes_on, modelo="303", operation=authority_operation)
    obligation = ModeloDeadline(
        modelo="303",
        period=Period.from_year_and_code(_YEAR, "3T"),
        opens_on=closes_on.replace(day=1),
        closes_on=closes_on,
        adjusted_closes_on=effective.closes_on,
        holiday_coverage=effective.holiday_coverage,
        shift_reason=effective.shift_reason,
        shift_jurisdictions=effective.jurisdictions,
        shift_holiday_refs=effective.holiday_refs,
        payment_cutoff_on=None,
        status=ObligationStatus.UPCOMING,
        boe_references=(),
        recovery=None,
    )
    entry = calendar_entry_from_obligation(
        obligation,
        filing_evidence=(),
        live_censo_verified_profile_keys=None,
        today=date(_YEAR, 8, 1),
        due_soon_days=14,
        operation=authority_operation,
    )
    assert entry.adjusted_closes_on == closes_on

    snapshot = OverviewCalendarEntrySnapshot.from_entry(entry)
    restored = OverviewCalendarEntrySnapshot.model_validate_json(snapshot.model_dump_json(), strict=True).to_entry()

    assert restored == entry
