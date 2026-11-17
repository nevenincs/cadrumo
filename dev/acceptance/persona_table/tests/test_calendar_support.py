"""The calendar support state of a replayed year is recorded as the calendar read served it."""

from __future__ import annotations

import json
from datetime import date

import pytest

from cadrumo.application.overview.calendar_envelope import OverviewCalendarSupport, OverviewCalendarSupportState
from cadrumo.application.overview.calendar_models import OverviewCalendarRange
from cadrumo.application.overview.read_calendar_projection import OverviewCalendarSnapshot
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema_references import TemporalSupportEnvelope
from cadrumo.entrypoints.tests.persona_world import year_envelope

from ..calendar_sweep import SUPPORT_FILE, support_line

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _bounds() -> tuple[int, int]:
    with bundled_indexed_authority().operation() as operation:
        envelope = year_envelope(operation)
    return envelope.floor, envelope.horizon


_FLOOR, _HORIZON = _bounds()


def _snapshot(year: int) -> OverviewCalendarSnapshot:
    envelope = TemporalSupportEnvelope(floor=_FLOOR, horizon=_HORIZON, hard_ceiling=None)
    served = OverviewCalendarRange(from_date=date(year, 1, 1), to_date=date(year + 1, 12, 31))
    return OverviewCalendarSnapshot.model_construct(support=OverviewCalendarSupport.for_range(served, envelope))


def test_a_supported_year_is_recorded_with_the_bounds_the_read_was_served_under() -> None:
    line = json.loads(support_line("persona", _HORIZON, _HORIZON - 2, _snapshot(_HORIZON - 2)))
    assert line["state"] == str(OverviewCalendarSupportState.SUPPORTED)
    assert (line["floor"], line["horizon"], line["hard_ceiling"]) == (_FLOOR, _HORIZON, None)
    assert line["range"] == [f"{_HORIZON - 2}-01-01", f"{_HORIZON - 1}-12-31"]
    assert (line["persona"], line["case_horizon"], line["year"]) == ("persona", _HORIZON, _HORIZON - 2)


@pytest.mark.parametrize(
    ("year", "state"),
    [
        (_HORIZON, OverviewCalendarSupportState.PROJECTED),
        (_FLOOR - 4, OverviewCalendarSupportState.BELOW_FLOOR),
        (_FLOOR - 1, OverviewCalendarSupportState.PARTIAL),
    ],
)
def test_each_support_state_is_recorded_as_the_read_computed_it(year: int, state: OverviewCalendarSupportState) -> None:
    assert json.loads(support_line("persona", _HORIZON, year, _snapshot(year)))["state"] == str(state)


def test_a_refused_read_and_a_calendar_without_support_are_recorded_apart() -> None:
    refused = json.loads(support_line("persona", _HORIZON, _HORIZON, None, "refused words"))
    assert (refused["state"], refused["refusal"]) == ("refused", "refused words")
    assert "floor" not in refused
    bare = json.loads(support_line("persona", _HORIZON, _HORIZON, OverviewCalendarSnapshot.model_construct()))
    assert bare["state"] == "not-served"


def test_the_sidecar_sits_beside_the_rows() -> None:
    assert SUPPORT_FILE == "calendar-support.jsonl"
