"""Transport-boundary tests for the modelo work deadline posture."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from .._modelo_payloads import WorkDeadlinePosturePayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_deadline_posture_payload_roundtrips_the_application_date_contract() -> None:
    payload = WorkDeadlinePosturePayload(closes_on=date(2026, 4, 20), days_remaining=0)

    restored = WorkDeadlinePosturePayload.model_validate_json(payload.model_dump_json())

    assert restored == payload
    assert payload.model_dump(mode="json")["closes_on"] == "2026-04-20"


@pytest.mark.parametrize(
    "raw",
    (
        {"closes_on": "not-a-date", "days_remaining": 0},
        {"closes_on": date(2026, 4, 20), "days_remaining": None, "days_overdue": None},
        {"closes_on": date(2026, 4, 20), "days_remaining": 0, "days_overdue": 1},
        {"closes_on": date(2026, 4, 20), "days_remaining": -1},
        {"closes_on": date(2026, 4, 20), "days_overdue": -1},
    ),
)
def test_deadline_posture_payload_refuses_malformed_or_impossible_states(raw: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        WorkDeadlinePosturePayload.model_validate(raw)
