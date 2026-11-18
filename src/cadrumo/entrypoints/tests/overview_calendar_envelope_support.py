"""Shared reads for the overview calendar envelope tests: the persona and the calendar read through the registered operation."""

from __future__ import annotations

from datetime import date

from ...application.overview.calendar_models import OverviewCalendarEntrySource
from ...application.overview.read_calendar_projection import OverviewCalendarSnapshot
from ...application.overview.read_payload import OverviewCalendarRead
from ...application.overview.read_request import OVERVIEW_READ_DEFINITION_IDS, OverviewReadKind, OverviewReadRequest
from ...application.overview.read_result import OverviewReadProjection
from ...core.external_constants import OutputLanguage
from .persona_operations import run_operation
from .persona_world import PersonaWorld

PERSONA = "autonomo-fontanero"


def overview_calendar(world: PersonaWorld, year: int) -> OverviewCalendarSnapshot:
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


def registry_deadline_rows(calendar: OverviewCalendarSnapshot) -> int:
    return sum(row.source is OverviewCalendarEntrySource.REGISTRY_DEADLINE for row in calendar.entries)
