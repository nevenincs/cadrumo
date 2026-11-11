"""Transport-boundary tests for the modelo work deadline posture."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ..modelo_results import WorkDeadlinePosturePayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon
_EFFECTIVE = date(_YEAR, 4, 20)
_NOMINAL = date(_YEAR, 4, 18)
_DATES = {
    "closes_on": _EFFECTIVE,
    "nominal_closes_on": _NOMINAL,
    "holiday_coverage": DeadlineHolidayCoverage.NATIONAL_ONLY,
}


def test_deadline_posture_payload_roundtrips_the_application_date_contract() -> None:
    payload = WorkDeadlinePosturePayload(
        closes_on=_EFFECTIVE,
        nominal_closes_on=_NOMINAL,
        holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
        days_remaining=0,
    )

    restored = WorkDeadlinePosturePayload.model_validate_json(payload.model_dump_json())

    assert restored == payload
    dumped = payload.model_dump(mode="json")
    assert dumped["closes_on"] == _EFFECTIVE.isoformat()
    assert dumped["nominal_closes_on"] == _NOMINAL.isoformat()
    assert dumped["holiday_coverage"] == "national_only"


@pytest.mark.parametrize(
    "raw",
    (
        {**_DATES, "closes_on": "not-a-date", "days_remaining": 0},
        {**_DATES, "days_remaining": None, "days_overdue": None},
        {**_DATES, "days_remaining": 0, "days_overdue": 1},
        {**_DATES, "days_remaining": -1},
        {**_DATES, "days_overdue": -1},
        {**_DATES, "nominal_closes_on": _EFFECTIVE + timedelta(days=1), "days_remaining": 0},
        {
            "closes_on": _EFFECTIVE,
            "holiday_coverage": DeadlineHolidayCoverage.NATIONAL_ONLY,
            "days_remaining": 0,
        },
        {"closes_on": _EFFECTIVE, "nominal_closes_on": _EFFECTIVE, "days_remaining": 0},
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
