"""Collector of the coverage audit: reads each persona's overview calendar at the registry's own horizon.

This module is not a test of the suite. ``python -m dev.acceptance.persona_table coverage``
names it explicitly to pytest, which collects it in spite of its name; the
suite never does. Each case materialises one persona as the obligation tests do
(its return history replayed when it holds one), reads the overview calendar
with suppressed obligations shown from the envelope's floor to the year after
its horizon, and appends one JSON line per return of an envelope year to the
file ``PERSONA_COVERAGE_OUT`` names: a window row as ``applicable``, a
suppressed row with its verdict. A refused read is one line naming the refusal.
"""

from __future__ import annotations

import os
from datetime import date
from functools import cache
from pathlib import Path

import pytest

from cadrumo.application.overview.read_calendar_projection import OverviewCalendarSnapshot
from cadrumo.application.overview.read_payload import OverviewCalendarRead
from cadrumo.application.overview.read_request import (
    OVERVIEW_READ_DEFINITION_IDS,
    OverviewReadKind,
    OverviewReadRequest,
)
from cadrumo.application.overview.read_result import OverviewReadProjection
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.tests.persona_materialisation import (
    PersonaMaterialisationError,
    PersonaWorld,
    ReplayScope,
    materialised_persona,
    run_operation,
    year_envelope,
)
from cadrumo.tests.personas import Persona, PersonaCatalogueError, YearEnvelope, persona_ids, read_persona

from .coverage import APPLICABLE, OUT_ENV, PERSONAS_ENV, CalendarObservation, CalendarRefusal

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@cache
def _envelope() -> YearEnvelope:
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation)


def _wanted() -> tuple[str, ...]:
    return tuple(item.strip() for item in os.environ.get(PERSONAS_ENV, "").split(",") if item.strip())


def _scope(persona: Persona) -> ReplayScope:
    """The history scope when the persona holds returns or observations of earlier years, else the full ledger.

    The obligation tests read the calendar of the same replay.
    """
    if persona.filed_returns or persona.calculated_returns or persona.local_observations or persona.aeat_filings:
        return ReplayScope.HISTORY
    return ReplayScope.FULL


def _split(period: str) -> tuple[int | None, str]:
    """The year and the registry code of a calendar period written as ``<year> <code>``."""
    head, _, code = period.rpartition(" ")
    year = head.rsplit(" ", 1)[-1]
    return (int(year) if year.isdigit() else None), code


def _observations(
    persona_id: str, calendar: OverviewCalendarSnapshot, envelope: YearEnvelope
) -> list[CalendarObservation]:
    found: list[CalendarObservation] = []
    for entry in calendar.entries:
        stated, code = _split(entry.period)
        year = int(entry.filing_year) if entry.filing_year is not None else stated
        if year is not None and envelope.floor <= year <= envelope.horizon:
            found.append(CalendarObservation(persona_id, entry.modelo, year, code, APPLICABLE))
    for row in calendar.suppressed_entries:
        year, code = _split(row.period)
        if year is not None and envelope.floor <= year <= envelope.horizon:
            found.append(CalendarObservation(persona_id, row.modelo, year, code, str(row.verdict), row.reason))
    return found


def calendar_observations(
    world: PersonaWorld, persona_id: str, envelope: YearEnvelope, *, from_date: date, to_date: date
) -> list[CalendarObservation]:
    """The returns of ``envelope``'s years the overview calendar of ``world`` projects, suppressed ones shown.

    A refused read, or one that returns no calendar, raises ``PersonaMaterialisationError``.
    """
    request = OverviewReadRequest(
        profile_id=world.profile_id,
        kind=OverviewReadKind.CALENDAR,
        output_language=OutputLanguage.ES,
        from_date=from_date,
        to_date=to_date,
        show_suppressed=True,
    )
    payload = run_operation(world, OVERVIEW_READ_DEFINITION_IDS[request.kind], request, OverviewReadProjection).payload
    if not isinstance(payload, OverviewCalendarRead) or payload.calendar is None:
        raise PersonaMaterialisationError(f"the calendar read returned {type(payload).__name__} without a calendar")
    return _observations(persona_id, payload.calendar, envelope)


@pytest.mark.parametrize("persona_id", [p for p in persona_ids() if not _wanted() or p in _wanted()])
def test_persona_calendar(tmp_path: Path, persona_id: str) -> None:
    """Materialise one persona at the registry's horizon and append its calendar projection."""
    out = Path(os.environ[OUT_ENV])
    envelope = _envelope()
    persona = read_persona(persona_id, envelope=envelope)
    try:
        with materialised_persona(persona_id, tmp_path, _scope(persona), reuse=True) as materialised:
            observations = calendar_observations(
                materialised.world,
                persona_id,
                envelope,
                from_date=date(envelope.floor, 1, 1),
                to_date=date(envelope.horizon + 1, 12, 31),
            )
        lines = [observation.to_json() for observation in observations]
    except (PersonaMaterialisationError, PersonaCatalogueError) as error:
        lines = [CalendarRefusal(persona_id, f"{type(error).__name__}: {error}"[:900]).to_json()]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as handle:
        handle.write("".join(line + "\n" for line in lines))
