"""Transport-boundary tests for the modelo work deadline posture."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from .._modelo_payloads import WorkDeadlinePosturePayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DATES = {
    "closes_on": date(2026, 4, 20),
    "nominal_closes_on": date(2026, 4, 18),
    "holiday_coverage": DeadlineHolidayCoverage.NATIONAL_ONLY,
}


def test_deadline_posture_payload_roundtrips_the_application_date_contract() -> None:
    payload = WorkDeadlinePosturePayload(
        closes_on=date(2026, 4, 20),
        nominal_closes_on=date(2026, 4, 18),
        holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
        days_remaining=0,
    )

    restored = WorkDeadlinePosturePayload.model_validate_json(payload.model_dump_json())

    assert restored == payload
    dumped = payload.model_dump(mode="json")
    assert dumped["closes_on"] == "2026-04-20"
    assert dumped["nominal_closes_on"] == "2026-04-18"
    assert dumped["holiday_coverage"] == "national_only"


@pytest.mark.parametrize(
    "raw",
    (
        {**_DATES, "closes_on": "not-a-date", "days_remaining": 0},
        {**_DATES, "days_remaining": None, "days_overdue": None},
        {**_DATES, "days_remaining": 0, "days_overdue": 1},
        {**_DATES, "days_remaining": -1},
        {**_DATES, "days_overdue": -1},
        {**_DATES, "nominal_closes_on": date(2026, 4, 21), "days_remaining": 0},
        {
            "closes_on": date(2026, 4, 20),
            "holiday_coverage": DeadlineHolidayCoverage.NATIONAL_ONLY,
            "days_remaining": 0,
        },
        {"closes_on": date(2026, 4, 20), "nominal_closes_on": date(2026, 4, 20), "days_remaining": 0},
    ),
    ids=[
        "malformed-date",
        "no-posture",
        "both-postures",
        "negative-remaining",
        "negative-overdue",
        "effective-before-nominal",
        "nominal-missing",
        "coverage-missing",
    ],
)
def test_deadline_posture_payload_refuses_malformed_or_impossible_states(raw: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        WorkDeadlinePosturePayload.model_validate(raw)
