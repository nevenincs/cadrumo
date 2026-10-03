"""Filing evidence survives the public calendar projection without losing an axis."""

from __future__ import annotations

from datetime import date

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.calendar_ccaa_catalogue import resolve_calendar_ccaa_catalogue
from ....domain.deadlines.models import ModeloDeadline, ObligationStatus
from ..calendar import _calendar_entry_from_obligation
from ..calendar_models import (
    OverviewAeatEvidenceConcern,
    OverviewAeatSubmissionState,
    OverviewCalendarFilingEvidence,
)
from ..read_calendar_item_projection import OverviewCalendarEntrySnapshot, OverviewFilingEvidenceSnapshot

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


def test_a_resident_s_holiday_territory_survives_the_snapshot_round_trip(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    closes_on = date(2025, 9, 11)
    obligation = ModeloDeadline(
        modelo="303",
        period=Period.from_year_and_code(2025, "3T"),
        opens_on=closes_on.replace(day=1),
        closes_on=closes_on,
        payment_cutoff_on=None,
        status=ObligationStatus.UPCOMING,
        applies_because="synthetic resident obligation",
        boe_references=(),
        recovery=None,
    )
    territory = resolve_calendar_ccaa_catalogue(effective_date=closes_on, authority=authority_operation).require(
        "ES-CT"
    )
    entry = _calendar_entry_from_obligation(
        obligation,
        holiday_territory=territory,
        filing_evidence=(),
        live_censo_verified_profile_keys=None,
        today=date(2025, 8, 1),
        due_soon_days=14,
        operation=authority_operation,
    )
    assert entry.holiday_territory is not None

    snapshot = OverviewCalendarEntrySnapshot.from_entry(entry)
    restored = OverviewCalendarEntrySnapshot.model_validate_json(snapshot.model_dump_json(), strict=True).to_entry()

    assert restored == entry
