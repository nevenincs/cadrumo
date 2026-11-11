"""Each persona's calendar renders its unanswered facts as undetermined obligations, never as a refusal.

The installed journey refused ``overview calendar`` for every catalogue persona
because each leaves some payer or threshold fact unanswered. Such a fact decides
only the obligations that depend on it: the coverage contract reports those as
undetermined, the rows its answered facts establish stay on the calendar, and
the fact itself arrives as a warning. Each case reads the calendar through the
registered overview operation.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ...application.overview.coverage import CoverageAdviceReason
from ...application.overview.read_payload import OverviewCalendarRead
from ...application.overview.read_request import OVERVIEW_READ_DEFINITION_IDS, OverviewReadKind, OverviewReadRequest
from ...application.overview.read_result import OverviewReadProjection
from ...core.external_constants import OutputLanguage
from ...tests.personas import persona_ids
from .persona_materialisation import ReplayScope, materialised_persona, run_operation

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("persona_id", persona_ids())
def test_a_persona_calendar_shows_undetermined_obligations_beside_its_rows(tmp_path: Path, persona_id: str) -> None:
    with materialised_persona(persona_id, tmp_path, ReplayScope.PROFILE, reuse=True) as replayed:
        world = replayed.world
        year = replayed.persona.fiscal_year.resolve(world.envelope)
        request = OverviewReadRequest(
            profile_id=world.profile_id,
            kind=OverviewReadKind.CALENDAR,
            output_language=OutputLanguage.ES,
            from_date=date(year, 1, 1),
            to_date=date(year + 1, 12, 31),
        )
        payload = run_operation(
            world, OVERVIEW_READ_DEFINITION_IDS[request.kind], request, OverviewReadProjection
        ).payload

    assert isinstance(payload, OverviewCalendarRead)
    assert payload.calendar is not None
    calendar = payload.calendar.to_calendar()
    assert calendar.taxpayer_model_declared
    # The facts the journey's refusal named are still reported, now as warnings.
    assert calendar.warnings
    # Only an undeclared taxpayer model leaves the CLI anything to refuse with.
    assert payload.refusal_requirements == ()

    rows = {entry.modelo for entry in calendar.entries}
    # The obligations the answered facts establish are still rows.
    assert rows
    undetermined = {
        item.modelo
        for item in calendar.coverage.advised
        if item.reason is CoverageAdviceReason.APPLICABILITY_UNDETERMINED
    }
    assert not undetermined & rows, (undetermined, rows)
