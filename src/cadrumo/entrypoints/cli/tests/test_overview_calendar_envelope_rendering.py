"""The CLI calendar renders the served filing-year support and never an empty unsupported year.

Each case reads the calendar through the registered operation and renders it through the command line's calendar output.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....application.overview.read_calendar_projection import OverviewCalendarSnapshot
from ...tests.overview_calendar_envelope_support import PERSONA, overview_calendar, registry_deadline_rows
from ...tests.persona_materialisation import materialised_persona
from ...tests.persona_world import ReplayScope
from ..overview_rendering import overview_calendar_output

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _cli_support(read: OverviewCalendarSnapshot) -> tuple[list[str], list[str]]:
    """Render ``read`` through the CLI calendar and return its support fields and support notice codes."""
    calendar = read.to_calendar()
    result, lines, notices = overview_calendar_output(
        calendar, calendar.range, support=read.support, evidence_notices=()
    )
    assert result.support == read.support
    support_line = next(line for line in lines if line.startswith("support	"))
    return support_line.split("	")[1:3], [
        notice.code for notice in notices if notice.code.startswith("overview.calendar.support")
    ]


def test_the_cli_calendar_renders_the_served_support_and_never_an_empty_unsupported_year(tmp_path: Path) -> None:
    with materialised_persona(PERSONA, tmp_path, ReplayScope.PROFILE, reuse=True) as replayed:
        world = replayed.world
        envelope = world.operation.supported_filing_years()
        assert envelope.admits_coordinate(envelope.horizon + 1)
        supported = overview_calendar(world, envelope.horizon)
        projected = overview_calendar(world, envelope.horizon + 1)
        below = overview_calendar(world, envelope.floor - 1)
    floor = str(envelope.floor)

    assert _cli_support(supported) == (["supported", floor], [])
    assert _cli_support(projected) == (["projected", floor], ["overview.calendar.support.projected"])
    assert _cli_support(below) == (["below_floor", floor], ["overview.calendar.support.below_floor"])
    assert registry_deadline_rows(projected)
