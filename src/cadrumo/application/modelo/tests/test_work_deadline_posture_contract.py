"""Contract tests for validated modelo work deadline postures."""

from __future__ import annotations

from datetime import date
from operator import methodcaller

import pytest

from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ..work_plazo import ModeloWorkDeadlinePosture

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("days_remaining", "days_overdue"),
    ((None, None), (0, 1), (-1, None), (None, -1)),
)
def test_deadline_posture_refuses_contradictory_or_negative_day_counts(
    days_remaining: int | None,
    days_overdue: int | None,
) -> None:
    with pytest.raises(ValueError):
        ModeloWorkDeadlinePosture(
            closes_on=date(2026, 4, 20),
            nominal_closes_on=date(2026, 4, 20),
            holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
            days_remaining=days_remaining,
            days_overdue=days_overdue,
        )


@pytest.mark.parametrize("field", ["closes_on", "nominal_closes_on"])
def test_deadline_posture_requires_concrete_dates(field: str) -> None:
    values: dict[str, object] = {
        "closes_on": date(2026, 4, 20),
        "nominal_closes_on": date(2026, 4, 20),
        "holiday_coverage": DeadlineHolidayCoverage.NATIONAL_ONLY,
        "days_remaining": 0,
    }
    values[field] = "not-a-date"
    with pytest.raises(ValueError, match=field):
        methodcaller("__call__", **values)(ModeloWorkDeadlinePosture)


def test_deadline_posture_refuses_an_effective_date_before_the_nominal_one() -> None:
    """The business-day shift only ever moves a deadline later."""
    with pytest.raises(ValueError, match="nominal"):
        ModeloWorkDeadlinePosture(
            closes_on=date(2026, 4, 17),
            nominal_closes_on=date(2026, 4, 18),
            holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
            days_remaining=0,
        )


def test_deadline_posture_requires_a_holiday_coverage() -> None:
    with pytest.raises(ValueError, match="holiday_coverage"):
        methodcaller(
            "__call__",
            closes_on=date(2026, 4, 20),
            nominal_closes_on=date(2026, 4, 20),
            holiday_coverage="national_only",
            days_remaining=0,
        )(ModeloWorkDeadlinePosture)
