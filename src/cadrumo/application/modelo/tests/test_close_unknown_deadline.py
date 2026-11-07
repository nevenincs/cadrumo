"""A projected window whose close is unknown bounds the deadline below and judges no lateness.

Modelo 303 for 2028 has no authored window and the 2028 holiday calendar is not
published. The nominal close of the first quarter, 20 April 2028 (RD 1624/1992
art. 71.4), is a lower bound: before it the filer has at least the days to it;
after it neither a remaining nor an overdue count can be stated.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.deadlines.effective_close import resolve_effective_filing_deadline
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..work_form_service import modelo_form_deadline
from ..work_plazo import modelo_work_deadline_posture

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = 2028
_PERIOD = Period.from_year_and_code(_YEAR, "1T")
_NOMINAL_CLOSE = date(_YEAR, 4, 20)
_BEFORE = date(_YEAR, 4, 10)
_AFTER = date(_YEAR, 6, 1)


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _work_unit() -> WorkUnit:
    revision_id = "close-unknown"
    created_at = datetime(_YEAR, 4, 2, tzinfo=UTC)
    bucket_id = "c" * 64
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id, modelo="303", filing_year=_YEAR, period=_PERIOD, revision_id=revision_id
        ),
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=_YEAR,
        period=_PERIOD,
        revision_id=revision_id,
        name="close-unknown-303",
        created_at=created_at,
        updated_at=created_at,
    )


def test_the_effective_deadline_keeps_only_the_nominal_lower_bound(operation: PinnedAuthorityOperation) -> None:
    deadline = resolve_effective_filing_deadline("303", _YEAR, _PERIOD, operation=operation)

    assert deadline is not None
    assert deadline.close_known is False
    assert deadline.nominal_closes_on == _NOMINAL_CLOSE
    assert deadline.closes_on == _NOMINAL_CLOSE
    assert deadline.holiday_coverage is DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE
    assert deadline.days_remaining_on(_BEFORE) == 10
    assert deadline.days_overdue_on(_AFTER) is None
    assert deadline.days_remaining_on(_AFTER) is None


def test_the_work_posture_counts_down_to_the_bound_and_then_states_nothing(
    operation: PinnedAuthorityOperation,
) -> None:
    before = modelo_work_deadline_posture(_work_unit(), reference_on=_BEFORE, operation=operation)
    after = modelo_work_deadline_posture(_work_unit(), reference_on=_AFTER, operation=operation)

    assert before is not None
    assert before.days_remaining == 10
    assert before.days_overdue is None
    assert before.conditional_recargo_preview is None
    assert after is None


def test_the_form_header_states_no_deadline_once_the_bound_passes(operation: PinnedAuthorityOperation) -> None:
    before = modelo_form_deadline(operation, ModeloCode("303"), _PERIOD, reference_on=_BEFORE)
    after = modelo_form_deadline(operation, ModeloCode("303"), _PERIOD, reference_on=_AFTER)

    assert before is not None
    assert before.days_remaining == 10
    assert after is None
