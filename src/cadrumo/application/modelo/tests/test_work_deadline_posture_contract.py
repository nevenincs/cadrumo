"""Contract tests for validated modelo work deadline postures."""

from __future__ import annotations

from datetime import date
from typing import cast

import pytest

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
            days_remaining=days_remaining,
            days_overdue=days_overdue,
        )


def test_deadline_posture_requires_a_concrete_date() -> None:
    with pytest.raises(ValueError, match="closes_on"):
        ModeloWorkDeadlinePosture(
            closes_on=cast(date, "not-a-date"),
            days_remaining=0,
        )
