"""The registered overview calendar read serves its filing-year envelope beside every calendar.

A range the envelope does not serve reads as unsupported, so a frontend never
shows it as a calendar in which nothing is due; a range it serves keeps its
deadline rows. Each case reads the calendar through the registered operation.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ...application.overview.calendar_envelope import OverviewCalendarSupportState
from ...application.overview.calendar_models import OverviewCalendarEntrySource
from ...application.overview.read_calendar_projection import OverviewCalendarSnapshot
from ...application.overview.read_payload import OverviewCalendarRead
from ...application.overview.read_request import OVERVIEW_READ_DEFINITION_IDS, OverviewReadKind, OverviewReadRequest
from ...application.overview.read_result import OverviewReadProjection
from ...core.external_constants import OutputLanguage
from ..cli.overview_rendering import overview_calendar_output
from .persona_materialisation import PersonaWorld, ReplayScope, materialised_persona, run_operation

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PERSONA = "autonomo-fontanero"


def _calendar(world: PersonaWorld, year: int) -> OverviewCalendarSnapshot:
    request = OverviewReadRequest(
        profile_id=world.profile_id,
        kind=OverviewReadKind.CALENDAR,
        output_language=OutputLanguage.ES,
        from_date=date(year, 1, 1),
        to_date=date(year, 12, 31),
    )
    payload = run_operation(world, OVERVIEW_READ_DEFINITION_IDS[request.kind], request, OverviewReadProjection).payload
    assert isinstance(payload, OverviewCalendarRead)
    assert payload.calendar is not None
    return payload.calendar


def _registry_rows(calendar: OverviewCalendarSnapshot) -> int:
    return sum(row.source is OverviewCalendarEntrySource.REGISTRY_DEADLINE for row in calendar.entries)


def test_the_calendar_read_serves_the_envelope_and_marks_a_year_below_it_unsupported(tmp_path: Path) -> None:
    with materialised_persona(_PERSONA, tmp_path, ReplayScope.PROFILE, reuse=True) as replayed:
        world = replayed.world
        envelope = world.operation.supported_filing_years()
        floor = _calendar(world, envelope.floor)
        horizon = _calendar(world, envelope.horizon)
        below = _calendar(world, envelope.floor - 1)

    for served in (floor, horizon, below):
        assert (served.support.floor, served.support.horizon, served.support.hard_ceiling) == (
            envelope.floor,
            envelope.horizon,
            envelope.hard_ceiling,
        )
    assert floor.support.state is OverviewCalendarSupportState.SUPPORTED
    assert horizon.support.state is OverviewCalendarSupportState.SUPPORTED
    assert _registry_rows(floor)
    assert _registry_rows(horizon)
    assert below.support.state is OverviewCalendarSupportState.BELOW_FLOOR
    assert below.support.unsupported
    assert _registry_rows(below) == 0


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
    with materialised_persona(_PERSONA, tmp_path, ReplayScope.PROFILE, reuse=True) as replayed:
        world = replayed.world
        envelope = world.operation.supported_filing_years()
        assert envelope.admits_coordinate(envelope.horizon + 1)
        supported = _calendar(world, envelope.horizon)
        projected = _calendar(world, envelope.horizon + 1)
        below = _calendar(world, envelope.floor - 1)
    floor = str(envelope.floor)

    assert _cli_support(supported) == (["supported", floor], [])
    assert _cli_support(projected) == (["projected", floor], ["overview.calendar.support.projected"])
    assert _cli_support(below) == (["below_floor", floor], ["overview.calendar.support.below_floor"])
    assert _registry_rows(projected)
