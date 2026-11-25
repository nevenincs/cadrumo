"""The registered overview calendar read serves its filing-year envelope beside every calendar.

A range the envelope does not serve reads as unsupported, so a frontend never
shows it as a calendar in which nothing is due; a range it serves keeps its
deadline rows. Each case reads the calendar through the registered operation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...application.overview.calendar_envelope import OverviewCalendarSupportState
from .overview_calendar_envelope_support import PERSONA, overview_calendar, registry_deadline_rows
from .persona_materialisation import materialised_persona
from .persona_world import ReplayScope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_the_calendar_read_serves_the_envelope_and_marks_a_year_below_it_unsupported(tmp_path: Path) -> None:
    with materialised_persona(PERSONA, tmp_path, ReplayScope.PROFILE, reuse=True) as replayed:
        world = replayed.world
        envelope = world.operation.supported_filing_years()
        floor = overview_calendar(world, envelope.floor)
        horizon = overview_calendar(world, envelope.horizon)
        below = overview_calendar(world, envelope.floor - 1)

    for served in (floor, horizon, below):
        assert (served.support.floor, served.support.horizon, served.support.hard_ceiling) == (
            envelope.floor,
            envelope.horizon,
            envelope.hard_ceiling,
        )
    assert floor.support.state is OverviewCalendarSupportState.SUPPORTED
    assert horizon.support.state is OverviewCalendarSupportState.SUPPORTED
    assert registry_deadline_rows(floor)
    assert registry_deadline_rows(horizon)
    assert below.support.state is OverviewCalendarSupportState.BELOW_FLOOR
    assert below.support.unsupported
    assert registry_deadline_rows(below) == 0
