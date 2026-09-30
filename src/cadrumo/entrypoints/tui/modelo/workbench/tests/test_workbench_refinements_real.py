"""A real Modelo 303 reads cleanly: each heading once, and a help band that does not repeat itself.

The declaration is seeded in real encrypted storage and read through the
production reader against the bundled registry. Its third page prints "Result"
and "Corrective return" in two parts each; the navigator names each once. The
help band of a box filled from a source says where its value comes from in the
row's words, without a "Source" line that says the same again and without a
description that opens by naming the box.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from rich.cells import cell_len
from rich.console import Console
from rich.text import Text
from textual.pilot import Pilot
from textual.widgets import OptionList, Static

from ......application.modelo.work_form_models import ModeloFormCasillaAddressV1, ModeloFormField, ModeloWorkForm
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import lookup_translation, tr
from ....components.host import ScreenHostApp
from ....tests.modelo_workbench_session import real_workbench
from ..casilla_list import CasillaList, description_text
from ..installed import InstalledModeloWorkbench
from ..navigator import heading_groups
from ..screen import ModeloWorkbenchScreen
from ..vocabulary import SOURCE_WORDED_ORIGINS, origin_text

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_GUTTERS = 4
"""The help band's padding, a gutter on each side."""


@pytest.fixture(scope="module")
def workbench(tmp_path_factory: pytest.TempPathFactory) -> Iterator[InstalledModeloWorkbench]:
    """One real first-quarter Modelo 303, read only for every assertion in this module."""
    root: Path = tmp_path_factory.mktemp("refinements-real")
    with real_workbench(root, modelo="303", filing_year=2026, period_code="1T") as installed:
        yield installed


async def _opened(pilot: Pilot[None], screen: ModeloWorkbenchScreen) -> ModeloWorkForm:
    for _ in range(200):
        await pilot.pause()
        if screen.form is not None:
            return screen.form
    raise AssertionError("the workbench never finished reading its declaration")


def _navigator(screen: ModeloWorkbenchScreen) -> list[str]:
    navigator = screen.query_one("#wb-sections", OptionList)
    return [str(navigator.get_option_at_index(index).prompt) for index in range(navigator.option_count)]


@pytest.mark.asyncio
async def test_a_heading_the_real_layout_prints_twice_is_listed_once(workbench: InstalledModeloWorkbench) -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(workbench, actions=workbench)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(160, 48)) as pilot:
            await _opened(pilot, screen)
            repeated = next(
                (
                    (index, [group[0].heading.text for group in heading_groups(page) if len(group) > 1])
                    for index, page in enumerate(screen.pages_shown)
                    if len(heading_groups(page)) < len(page.sections)
                ),
                None,
            )
            assert repeated is not None, "the real layout no longer prints a heading twice; pick another witness"
            index, headings = repeated
            for _ in range(index):
                await pilot.press("right_square_bracket")
            await pilot.pause()
            rows = _navigator(screen)
            app.exit(None)

    assert headings == ["Result", "Corrective return"]
    for heading in headings:
        # A section row leads with its mark, whichever level it shows; the heading follows it.
        listed = [row for row in rows if row.strip().partition(" ")[2].startswith(heading)]
        assert len(listed) == 1, f"{heading!r} is listed {len(listed)} times: {rows}"


def _sourced(form: ModeloWorkForm) -> ModeloFormField:
    return next(
        field
        for field in form.fields()
        if field.box
        and field.origin in SOURCE_WORDED_ORIGINS
        and field.source is not None
        and any(binding.policy.family is field.source.family for binding in field.bindings)
    )


@pytest.mark.asyncio
async def test_a_real_boxs_help_band_says_its_source_once_in_the_rows_words(
    workbench: InstalledModeloWorkbench,
) -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(workbench, actions=workbench)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(160, 48)) as pilot:
            form = await _opened(pilot, screen)
            field = _sourced(form)
            await pilot.press("g", *(field.box or ""), "enter")
            for _ in range(100):
                await pilot.pause()
                band = str(screen.query_one("#wb-help", Static).render()).splitlines()
                entry = screen.query_one(CasillaList).highlighted
                if entry is not None and entry.field.box == field.box and len(band) > 3:
                    break
            words = origin_text(field)
            said = {
                lookup_translation(binding.policy.origin_sentence_key, locale="en")
                for binding in field.bindings
                if field.source is not None and binding.policy.family is field.source.family
            }
            app.exit(None)

    assert isinstance(field.address, ModeloFormCasillaAddressV1)
    card = workbench.help_card(field.address.casilla_id, OutputLanguage.EN)
    assert said & set(card.origins), "the witness box's card must repeat its origin words for this to prove anything"
    assert band[1].startswith(f"{words} · ")
    assert "Imported" not in band[1]
    description = description_text(field)
    if description is not None:
        assert band[2] == description
        assert not band[2].lower().startswith(("box ", "casilla "))
    assert not any(line.removeprefix("Source: ") in said for line in band if line.startswith("Source: "))


_ART_71 = "rd-1624-1992:art-71"
_ART_71_TEXT = "art.\u00a071"
"""How the band cites that article: "art." held to its number by a no-break space."""
_NO_BREAK = "\u00a0"


@pytest.fixture(scope="module")
def annual_vat(tmp_path_factory: pytest.TempPathFactory) -> Iterator[InstalledModeloWorkbench]:
    """One real annual VAT summary (Modelo 390), whose boxes cite the VAT regulation by article."""
    root: Path = tmp_path_factory.mktemp("refinements-real-390")
    with real_workbench(root, modelo="390", filing_year=2025, period_code="0A") as installed:
        yield installed


def _splits_the_citation(line: str, width: int) -> bool:
    """Whether the terminal's own wrapping, left alone, would break the line between "art." and its number."""
    wrapped = [part.plain for part in Text(line).wrap(Console(width=width), width)]
    return any(first.rstrip().endswith("art.") for first in wrapped[:-1])


@pytest.mark.asyncio
async def test_the_help_band_never_breaks_a_citation_between_art_and_its_number(
    annual_vat: InstalledModeloWorkbench,
) -> None:
    with override_settings(cadrumo_output_language="en"):
        load = annual_vat.load(OutputLanguage.EN)
        field = next(
            field
            for field in load.form.fields()
            if field.box
            and _ART_71 in {str(ref) for ref in field.legal_refs}
            and isinstance(field.address, ModeloFormCasillaAddressV1)
        )
        assert isinstance(field.address, ModeloFormCasillaAddressV1)
        card = annual_vat.help_card(field.address.casilla_id, OutputLanguage.EN)
        assert any(item.text.endswith(_ART_71_TEXT) for item in card.legal_basis)
        line = tr("tui.modelo.workbench.help.legal", citations="; ".join(item.text for item in card.legal_basis))
        width = next(width for width in range(76, 200) if _splits_the_citation(line, width))
        screen = ModeloWorkbenchScreen(annual_vat, actions=annual_vat)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(width + _GUTTERS, 48)) as pilot:
            await _opened(pilot, screen)
            await pilot.press("g", *(field.box or ""), "enter")
            band: list[str] = []
            for _ in range(100):
                await pilot.pause()
                band = str(screen.query_one("#wb-help", Static).render()).splitlines()
                if any(item.startswith("Legal basis:") for item in band):
                    break
            await pilot.press("question_mark")
            for _ in range(5):
                await pilot.pause()
            widget = screen.query_one("#wb-help", Static)
            band_width = widget.content_region.width
            painted = [widget.render_line(row).text for row in range(widget.size.height)]
            app.exit(None)

    assert band_width == width, "the band must be exactly as wide as the width the terminal would have split"
    assert any(_ART_71_TEXT in item for item in band)
    assert any(_ART_71_TEXT in item for item in painted), painted
    assert not any(item.rstrip().endswith("art.") for item in painted), painted
    assert all(cell_len(item) <= width for item in band if _NO_BREAK in item)
