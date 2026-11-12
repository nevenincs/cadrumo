"""The header says the grade the year reaches, and, when the form serves them, why the year cannot be filed yet.

The grade words are always served and always drawn. The projection words are
served for a year carried from another edition and for a year its own edition
authors below filing grade; a year at filing grade serves none and the line is
not shown. The years are the synthetic form's own, never literals.
"""

from __future__ import annotations

import pytest
from textual.widgets import Static

from ......application.modelo.work_form_declaration_facts import ModeloFormYearProjection
from ......application.modelo.work_form_models import ModeloWorkForm
from ......core.authority_grade import RegistryAuthorityGrade
from ......core.config import override_settings
from ......core.i18n.render import tr
from ......domain.calculations.registry.schema_references import TemporalProjectionDirection
from ....components.host import ScreenHostApp
from ....tests.settling import settle
from ..screen import ModeloWorkbenchScreen
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_GRADE_WORDS = "Synthetic grade words"


def _projected(form: ModeloWorkForm, words: str) -> ModeloFormYearProjection:
    return ModeloFormYearProjection(
        direction=TemporalProjectionDirection.FORWARD,
        authored_filing_year=form.filing_year - 1,
        reachable_grade=RegistryAuthorityGrade.CALCULATION,
        reachable_grade_words=_GRADE_WORDS,
        words=words,
    )


def _below_filing_grade(form: ModeloWorkForm, words: str) -> ModeloFormYearProjection:
    return ModeloFormYearProjection(
        direction=TemporalProjectionDirection.AUTHORED,
        authored_filing_year=form.filing_year,
        reachable_grade=RegistryAuthorityGrade.CALCULATION,
        reachable_grade_words=_GRADE_WORDS,
        words=words,
    )


def _at_filing_grade(form: ModeloWorkForm) -> ModeloFormYearProjection:
    return ModeloFormYearProjection(
        direction=TemporalProjectionDirection.AUTHORED,
        authored_filing_year=form.filing_year,
        reachable_grade=RegistryAuthorityGrade.FILING,
        reachable_grade_words=_GRADE_WORDS,
    )


async def _lines(projection: ModeloFormYearProjection) -> tuple[bool, str, bool, str]:
    form = synthetic_form().model_copy(update={"year_projection": projection})
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            grade = screen.query_one("#wb-grade", Static)
            line = screen.query_one("#wb-projection", Static)
            return bool(grade.display), str(grade.render()), bool(line.display), str(line.render())


@pytest.mark.asyncio
async def test_a_projected_year_shows_its_grade_and_the_served_words() -> None:
    form = synthetic_form()
    with override_settings(cadrumo_output_language="en"):
        words = tr(
            "application.modelo.findings.registry_filing_year_projected",
            modelo=form.modelo,
            filing_year=form.filing_year,
            period=form.period.registry_token,
            authored_filing_year=form.filing_year - 1,
        )
    grade_shown, grade_text, shown, text = await _lines(_projected(form, words))
    assert grade_shown
    assert grade_text == _GRADE_WORDS
    assert shown
    assert text == words


@pytest.mark.asyncio
async def test_an_authored_year_below_filing_grade_shows_the_served_words() -> None:
    form = synthetic_form()
    with override_settings(cadrumo_output_language="en"):
        words = tr(
            "application.modelo.findings.registry_authority_grade_insufficient",
            modelo=form.modelo,
            filing_year=form.filing_year,
            period=form.period.registry_token,
        )
    grade_shown, grade_text, shown, text = await _lines(_below_filing_grade(form, words))
    assert grade_shown
    assert grade_text == _GRADE_WORDS
    assert shown
    assert text == words


@pytest.mark.asyncio
async def test_a_year_at_filing_grade_shows_no_projection_line() -> None:
    _, _, shown, text = await _lines(_at_filing_grade(synthetic_form()))
    assert not shown
    assert text == ""


@pytest.mark.asyncio
async def test_the_grade_words_are_shown_whether_or_not_the_form_serves_projection_words() -> None:
    form = synthetic_form()
    for projection in (
        _projected(form, "Carried from another edition."),
        _below_filing_grade(form, "Not yet checked closely enough to file."),
        _at_filing_grade(form),
    ):
        grade_shown, grade_text, _, _ = await _lines(projection)
        assert grade_shown
        assert grade_text == projection.reachable_grade_words
