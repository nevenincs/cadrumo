"""Official headings on real declarations: every headed part reads in the filer's language, never as a name.

Each declaration is seeded in real encrypted storage and read through the
production reader against the published registry authority, in each of the
four languages. A section the layout heads with official words shows the
catalogue's translation of them in the navigator and in the list, the Spanish
form shows the official words themselves, and no headed part falls back to the
official Spanish, a box range, a page position or a technical name.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ......application.modelo.work_form_models import (
    ModeloFormRepeatingBlock,
    ModeloFormSection,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
)
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ....components.host import ScreenHostApp
from ....tests.modelo_workbench_session import real_workbench
from ..casilla_list import CasillaListHeading
from ..installed import InstalledModeloWorkbench
from ..navigator import looks_like_identifier, presented_form
from ..page_items import page_items, section_nav_text, workbench_pages
from ..screen import ModeloWorkbenchScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_ADDRESSES = [
    pytest.param({"modelo": "100", "filing_year": 2024, "period_code": "0A"}, id="renta"),
    pytest.param({"modelo": "349", "filing_year": 2026, "period_code": "1T"}, id="intra-community"),
]
_NAVIGATOR_WIDTH = 400


@pytest.fixture(scope="module", params=_ADDRESSES)
def workbench(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Iterator[object]:
    """One real declaration per address, read only for every assertion in this module."""
    root: Path = tmp_path_factory.mktemp("official-headings-real")
    with real_workbench(root, **request.param) as installed:
        yield installed


def _headed(form: ModeloWorkForm) -> dict[tuple[str, str], ModeloFormSection]:
    """Every section the layout heads with official words, by page and section id."""
    return {
        (page.id, section.id): section for page in form.pages for section in page.sections if section.official_heading
    }


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_every_headed_section_reads_in_the_filers_language_in_the_navigator_and_the_list(
    language: OutputLanguage, workbench: InstalledModeloWorkbench
) -> None:
    with override_settings(cadrumo_output_language=language.value):
        form = workbench.load(language).form
        headed = _headed(form)
        assert headed, "the declaration carries no official heading, so this check would pass on anything"
        not_localized = [
            (place, section.heading.disclosure)
            for place, section in headed.items()
            if section.heading.disclosure is not ModeloFormTextDisclosure.LOCALIZED
        ]
        if language is OutputLanguage.ES:
            wrong = [place for place, section in headed.items() if section.heading.text != section.official_heading]
        else:
            wrong = [place for place, section in headed.items() if section.heading.text == section.official_heading]
        pages = workbench_pages(presented_form(form))
        shown = {(page.id, section.id): section.heading.text for page in pages for section in page.sections}
        navigator = [section_nav_text(section, _NAVIGATOR_WIDTH) for page in pages for section in page.sections]
        listed = [
            item.text for page in pages for item in page_items(page, staged={}) if isinstance(item, CasillaListHeading)
        ]

    assert not_localized == []
    assert wrong == []
    assert {place: shown[place] for place in headed} == {
        place: section.heading.text for place, section in headed.items()
    }
    assert not [place for place, section in headed.items() if looks_like_identifier(section.heading.text)]
    assert not [place for place, section in headed.items() if not any(section.heading.text in row for row in navigator)]
    assert not [place for place, section in headed.items() if not any(section.heading.text in line for line in listed)]


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_every_headed_repeating_column_reads_in_the_filers_language(
    language: OutputLanguage, workbench: InstalledModeloWorkbench
) -> None:
    with override_settings(cadrumo_output_language=language.value):
        form = workbench.load(language).form
    columns = [
        column
        for section in _headed(form).values()
        for block in section.blocks
        if isinstance(block, ModeloFormRepeatingBlock)
        for column in block.columns
    ]
    if form.modelo == "349":
        assert columns, "the 349 record tables lost their columns, so this check would pass on anything"
    assert not [column.key for column in columns if column.heading.disclosure is not ModeloFormTextDisclosure.LOCALIZED]
    assert not [column.key for column in columns if looks_like_identifier(column.heading.text)]


@pytest.mark.asyncio
async def test_the_mounted_workbench_shows_the_translated_headings(workbench: InstalledModeloWorkbench) -> None:
    with override_settings(cadrumo_output_language="en"):
        headed = _headed(workbench.load(OutputLanguage.EN).form)
        expected = {place: section.heading.text for place, section in headed.items()}
        screen = ModeloWorkbenchScreen(workbench, actions=workbench)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(160, 48)) as pilot:
            for _ in range(200):
                await pilot.pause()
                if screen.form is not None:
                    break
            shown = {
                (page.id, section.id): section.heading.text for page in screen.pages_shown for section in page.sections
            }
            app.exit(None)

    assert expected
    assert {key: shown.get(key) for key in expected} == expected
