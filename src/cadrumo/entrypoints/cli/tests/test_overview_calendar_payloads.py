"""Refusal coverage for overview calendar JSON projections."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..overview_results import (
    OverviewCalendarEventPayload,
    OverviewCalendarFilingEvidencePayload,
    OverviewCalendarRangePayload,
)

_YEAR = filing_year_envelope().horizon


pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_calendar_range_payload_refuses_unordered_or_malformed_dates() -> None:
    for payload in (
        {"from_date": date(_YEAR, 5, 2).isoformat(), "to_date": date(_YEAR, 5, 1).isoformat()},
        {"from_date": "not-a-date", "to_date": date(_YEAR, 5, 1).isoformat()},
    ):
        with pytest.raises(ValidationError):
            OverviewCalendarRangePayload.model_validate(payload)


def test_calendar_evidence_payload_enforces_closed_state_and_csv_pairing() -> None:
    valid = {
        "local_filing_state": "ready_to_file",
        "aeat_submission_state": "justificante_verified",
        "justificante_required": True,
        "justificante_verified": True,
        "verified_justificante_csv": "CSV20260000001",
    }
    assert OverviewCalendarFilingEvidencePayload.model_validate(valid).justificante_verified is True
    for field, value in (("aeat_submission_state", "bogus"), ("verified_justificante_csv", None)):
        with pytest.raises(ValidationError):
            OverviewCalendarFilingEvidencePayload.model_validate({**valid, field: value})


def test_calendar_event_payload_enforces_verified_csv_pairing_and_csv_normalization() -> None:
    event = {
        "event_type": "filing",
        "event_date": date(_YEAR, 5, 1).isoformat(),
        "source": "aeat",
        "summary": "Filed",
        "reference_id": "ref-1",
        "aeat_submission_state": "justificante_verified",
        "justificante_verified": True,
        "verified_justificante_csv": "CSV20260000001",
    }
    assert OverviewCalendarEventPayload.model_validate(event).event_type == "filing"
    normalized = OverviewCalendarEventPayload.model_validate(
        {**event, "verified_justificante_csv": event["verified_justificante_csv"].lower()},
    )
    assert normalized.verified_justificante_csv == event["verified_justificante_csv"]
    with pytest.raises(ValidationError):
        OverviewCalendarEventPayload.model_validate({**event, "verified_justificante_csv": None})
    with pytest.raises(ValidationError):
        OverviewCalendarEventPayload.model_validate(
            {**event, "verified_justificante_csv": "-".join(event["verified_justificante_csv"])},
        )
