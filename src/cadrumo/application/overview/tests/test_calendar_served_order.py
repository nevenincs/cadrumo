"""The calendar serves its rows in one decided list order and names their attention order."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.deadlines.models import ObligationStatus
from ..calendar import build_overview_calendar
from ..calendar_models import (
    OverviewCalendarRange,
    OverviewPeriodState,
    calendar_attention_order_key,
    calendar_list_order_key,
)
from ..read_calendar_projection import OverviewCalendarSnapshot
from .calendar_test_support import profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_STATE = OverviewPeriodState
_YEAR = filing_year_envelope().horizon


def _listed(close: date, status: ObligationStatus, modelo: str = "303") -> tuple[int, int, bool, date, str, str, str]:
    return calendar_list_order_key(
        adjusted_closes_on=close, status=status, modelo=modelo, period="3T", local_work_unit_id=None
    )


def _attended(
    close: date, status: ObligationStatus, state: OverviewPeriodState
) -> tuple[int, bool, date, str, str, str]:
    return calendar_attention_order_key(
        adjusted_closes_on=close, status=status, user_state=state, modelo="303", period="3T", local_work_unit_id=None
    )


def test_the_list_groups_by_close_month_with_known_closes_before_unknown_ones() -> None:
    month_start = date(_YEAR, 10, 1)
    early_unknown = _listed(month_start, ObligationStatus.UNKNOWN)
    late_known = _listed(month_start + timedelta(days=19), ObligationStatus.DUE_SOON)
    next_month = _listed(month_start + timedelta(days=31), ObligationStatus.UPCOMING)

    assert sorted([next_month, early_unknown, late_known]) == [late_known, early_unknown, next_month]


def test_the_list_breaks_a_same_day_tie_by_modelo() -> None:
    close = date(_YEAR, 10, 20)
    first = _listed(close, ObligationStatus.DUE_SOON, modelo="111")
    second = _listed(close, ObligationStatus.DUE_SOON, modelo="303")

    assert sorted([second, first]) == [first, second]


def test_attention_puts_late_then_due_then_unknown_then_filed_whatever_the_date() -> None:
    close = date(_YEAR, 10, 20)
    filed = _attended(close - timedelta(days=60), ObligationStatus.FILED, _STATE.FILED)
    unknown = _attended(close - timedelta(days=30), ObligationStatus.UNKNOWN, _STATE.UNKNOWN)
    due = _attended(close + timedelta(days=30), ObligationStatus.UPCOMING, _STATE.DUE)
    late = _attended(close + timedelta(days=60), ObligationStatus.OVERDUE, _STATE.LATE)

    assert sorted([filed, unknown, due, late]) == [late, due, unknown, filed]


def _snapshot(operation: PinnedAuthorityOperation) -> OverviewCalendarSnapshot:
    envelope = operation.supported_filing_years()
    year = envelope.horizon
    calendar = build_overview_calendar(
        profile(),
        OverviewCalendarRange(from_date=date(year, 1, 1), to_date=date(year, 12, 31)),
        operation=operation,
        today=date(year, 6, 1),
        raw_values={},
    )
    return OverviewCalendarSnapshot.from_calendar(calendar, envelope=envelope)


def test_a_served_calendar_keeps_both_orders(authority_operation: PinnedAuthorityOperation) -> None:
    snapshot = _snapshot(authority_operation)
    entries = snapshot.entries
    assert len(entries) > 1

    closes = [row.adjusted_closes_on for row in entries]
    assert [(day.year, day.month) for day in closes] == sorted((day.year, day.month) for day in closes)
    assert sorted(snapshot.attention_order) == list(range(len(entries)))
    attended = [entries[index].user_state for index in snapshot.attention_order]
    ranks = [[_STATE.LATE, _STATE.DUE, _STATE.UNKNOWN, _STATE.FILED].index(state) for state in attended]
    assert ranks == sorted(ranks)


def test_a_served_calendar_refuses_rows_out_of_its_order(authority_operation: PinnedAuthorityOperation) -> None:
    payload = json.loads(_snapshot(authority_operation).model_dump_json())
    payload["entries"] = list(reversed(payload["entries"]))

    with pytest.raises(ValidationError, match="list order"):
        OverviewCalendarSnapshot.model_validate_json(json.dumps(payload))


def test_a_served_calendar_refuses_an_attention_order_it_does_not_decide(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    payload = json.loads(_snapshot(authority_operation).model_dump_json())
    payload["attention_order"] = list(reversed(payload["attention_order"]))

    with pytest.raises(ValidationError, match="attention_order"):
        OverviewCalendarSnapshot.model_validate_json(json.dumps(payload))
