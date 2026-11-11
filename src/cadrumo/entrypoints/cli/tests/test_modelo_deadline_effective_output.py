"""The calculate output shows the effective deadline beside the nominal one, with its holiday coverage."""

from __future__ import annotations

from datetime import date

import pytest

from ....application.modelo.work_plazo import ModeloWorkDeadlinePosture
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ..modelo_rendering import work_deadline_output_from_posture, work_plazo_lines_from_posture

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ENVELOPE = filing_year_envelope()
_NOMINAL = date(_ENVELOPE.horizon, 4, 20)
_MOVED = date(_ENVELOPE.horizon, 4, 21)
# A nominal deadline moved to the next day, observed on that day.
_ON_THE_MOVED_DAY = ModeloWorkDeadlinePosture(
    closes_on=_MOVED,
    nominal_closes_on=_NOMINAL,
    holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
    days_remaining=0,
)
# A year without a published holiday calendar keeps the nominal date, unverified.
_UNPUBLISHED_DAY = date(_ENVELOPE.horizon + 1, 2, 1)
_UNVERIFIED_AND_PASSED = ModeloWorkDeadlinePosture(
    closes_on=_UNPUBLISHED_DAY,
    nominal_closes_on=_UNPUBLISHED_DAY,
    holiday_coverage=DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE,
    days_overdue=1,
)


def test_text_lines_name_both_dates_and_the_coverage() -> None:
    lines = work_plazo_lines_from_posture(_ON_THE_MOVED_DAY)

    assert lines[:3] == [
        f"plazo_closes_on\t{_MOVED.isoformat()}",
        f"plazo_nominal_closes_on\t{_NOMINAL.isoformat()}",
        "plazo_holiday_coverage\tnational_only",
    ]
    assert not any(line.startswith("days_overdue") for line in lines)


def test_json_payload_and_notice_carry_both_dates_and_the_coverage() -> None:
    payload, notices = work_deadline_output_from_posture(_ON_THE_MOVED_DAY, fallback_legal_ref=None)

    assert payload is not None
    dumped = payload.model_dump(mode="json")
    assert dumped["closes_on"] == _MOVED.isoformat()
    assert dumped["nominal_closes_on"] == _NOMINAL.isoformat()
    assert dumped["holiday_coverage"] == "national_only"
    assert dumped["days_remaining"] == 0
    assert notices == []


def test_an_overdue_notice_states_an_unverified_effective_date_as_such() -> None:
    payload, notices = work_deadline_output_from_posture(
        _UNVERIFIED_AND_PASSED, fallback_legal_ref="ley-58-2003:art-27"
    )

    assert payload is not None
    assert payload.holiday_coverage is DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE
    assert len(notices) == 1
    context = notices[0].context
    assert context is not None
    assert context["closes_on"] == _UNPUBLISHED_DAY.isoformat()
    assert context["nominal_closes_on"] == _UNPUBLISHED_DAY.isoformat()
    assert context["holiday_coverage"] == "calendar_unavailable"
    assert context["days_overdue"] == "1"
