"""Refusal coverage for overview calendar JSON projections."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._overview_payloads import (
    OverviewCalendarEventPayload,
    OverviewCalendarFilingEvidencePayload,
    OverviewCalendarRangePayload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_calendar_range_payload_refuses_unordered_or_malformed_dates() -> None:
    for payload in (
        {"from_date": "2026-05-02", "to_date": "2026-05-01"},
        {"from_date": "not-a-date", "to_date": "2026-05-01"},
    ):
        with pytest.raises(ValidationError):
            OverviewCalendarRangePayload.model_validate(payload)


def test_calendar_evidence_payload_enforces_closed_state_and_csv_pairing() -> None:
    valid = {
        "local_filing_state": "ready_to_file",
        "aeat_submission_state": "justificante_verified",
        "justificante_required": True,
        "justificante_verified": True,
        "verified_justificante_csv": "CSV-2026-001",
    }
    assert OverviewCalendarFilingEvidencePayload.model_validate(valid).justificante_verified is True
    for field, value in (("aeat_submission_state", "bogus"), ("verified_justificante_csv", None)):
        with pytest.raises(ValidationError):
            OverviewCalendarFilingEvidencePayload.model_validate({**valid, field: value})


def test_calendar_event_payload_enforces_verified_csv_pairing() -> None:
    event = {
        "event_type": "filing",
        "event_date": "2026-05-01",
        "source": "aeat",
        "summary": "Filed",
        "reference_id": "ref-1",
        "aeat_submission_state": "justificante_verified",
        "justificante_verified": True,
        "verified_justificante_csv": "CSV-2026-001",
    }
    assert OverviewCalendarEventPayload.model_validate(event).event_type == "filing"
    with pytest.raises(ValidationError):
        OverviewCalendarEventPayload.model_validate({**event, "verified_justificante_csv": None})
