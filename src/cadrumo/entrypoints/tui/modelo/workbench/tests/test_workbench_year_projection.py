"""A year worked out from another year's edition says so under the header, in the words the form serves.

The form states the projection before any check; an authored year serves no
words and the line is not shown.
"""

from __future__ import annotations

import pytest
from textual.widgets import Static

from ......application.modelo.work_form_declaration_facts import ModeloFormYearProjection
from ......core.authority_grade import RegistryAuthorityGrade
from ......core.config import override_settings
from ......core.i18n.render import tr
from ......domain.calculations.registry.schema_references import TemporalProjectionDirection
from ....components.host import ScreenHostApp
from ....tests.settling import settle
from ..screen import ModeloWorkbenchScreen
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


async def _projection_line(form_words: str | None) -> tuple[bool, str]:
    form = synthetic_form()
    if form_words is not None:
        form = form.model_copy(
            update={
                "year_projection": ModeloFormYearProjection(
                    direction=TemporalProjectionDirection.FORWARD,
                    authored_filing_year=form.year_projection.authored_filing_year - 1,
                    reachable_grade=RegistryAuthorityGrade.CALCULATION,
                    words=form_words,
                )
            }
        )
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            line = screen.query_one("#wb-projection", Static)
            return bool(line.display), str(line.render())


@pytest.mark.asyncio
async def test_a_projected_year_shows_the_served_words() -> None:
    with override_settings(cadrumo_output_language="en"):
        words = tr(
            "application.modelo.findings.registry_filing_year_projected",
            modelo="130",
            filing_year=2027,
            period="1T",
            authored_filing_year=2026,
        )
    shown, text = await _projection_line(words)
    assert shown
    assert text == words


@pytest.mark.asyncio
async def test_an_authored_year_shows_no_projection_line() -> None:
    shown, text = await _projection_line(None)
    assert not shown
    assert text == ""
