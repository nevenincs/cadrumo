"""Pin the M136 fourth-quarter effective-close boundary through the application path.

The fourth-quarter filing window closes on 20 January of the following year and
rolls to the next working day when that date is a weekend. The expectation is
worked out here from the calendar for every supported exercise, so a year whose
nominal close falls on a Saturday or a Sunday proves the roll and the other
years prove the window is not moved.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import supported_authored_exercises
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..work_plazo import modelo_work_deadline_posture

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "d" * 64
_SATURDAY = 5


def _next_working_day(day: date) -> date:
    while day.weekday() >= _SATURDAY:
        day += timedelta(days=1)
    return day


@pytest.mark.parametrize("exercise", supported_authored_exercises("136"))
def test_m136_q4_posture_uses_the_effective_close_after_a_weekend(
    operation: PinnedAuthorityOperation,
    exercise: int,
) -> None:
    period = Period.from_year_and_code(exercise, "4T")
    selected_revision = operation.revision_for_context("136", filing_year=exercise, period=period.registry_token)
    revision_id = selected_revision.id
    created_at = datetime(exercise, 1, 1, tzinfo=UTC)
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="136",
            filing_year=exercise,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("136"),
        filing_year=exercise,
        period=period,
        revision_id=revision_id,
        name=f"136-{exercise}-4T",
        created_at=created_at,
        updated_at=created_at,
    )
    nominal_close = date(exercise + 1, 1, 20)
    effective_close = _next_working_day(nominal_close)

    before_effective_close = modelo_work_deadline_posture(
        work_unit,
        reference_on=effective_close - timedelta(days=1),
        operation=operation,
    )
    on_effective_close = modelo_work_deadline_posture(
        work_unit,
        reference_on=effective_close,
        operation=operation,
    )
    after_effective_close = modelo_work_deadline_posture(
        work_unit,
        reference_on=effective_close + timedelta(days=1),
        operation=operation,
    )

    assert before_effective_close is not None
    assert before_effective_close.nominal_closes_on == nominal_close
    assert before_effective_close.closes_on == effective_close
    assert before_effective_close.days_remaining == 1
    assert before_effective_close.days_overdue is None
    assert before_effective_close.conditional_recargo_preview is None

    assert on_effective_close is not None
    assert on_effective_close.nominal_closes_on == nominal_close
    assert on_effective_close.closes_on == effective_close
    assert on_effective_close.days_remaining == 0
    assert on_effective_close.days_overdue is None
    assert on_effective_close.conditional_recargo_preview is None

    assert after_effective_close is not None
    assert after_effective_close.nominal_closes_on == nominal_close
    assert after_effective_close.closes_on == effective_close
    assert after_effective_close.days_remaining is None
    assert after_effective_close.days_overdue == 1
