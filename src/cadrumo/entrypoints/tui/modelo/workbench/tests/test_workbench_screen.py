"""The workbench opens on what the filer must do, and explains every box it shows.

Driven through the standalone screen host with a synthetic form: the screen
reads its declaration off the event loop, lands on the first box that needs the
filer, names the modelo, the period in words and the result in its header,
shows where the filing stands and what to do next, moves between official
pages, filters what it shows, and explains the box under the cursor with the
help it fetched for that box alone.
"""

from __future__ import annotations

import pytest
from textual.widgets import Static

from ......core.config import override_settings
from ....components.host import ScreenHostApp
from ..casilla_list import CasillaList
from ..screen import ModeloWorkbenchScreen
from .workbench_fixture import FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _text(screen: ModeloWorkbenchScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


def _list_text(screen: ModeloWorkbenchScreen) -> str:
    widget = screen.query_one(CasillaList)
    return "\n".join(widget.render_line(y).text for y in range(widget.size.height))


@pytest.mark.asyncio
async def test_the_workbench_opens_on_the_first_box_that_needs_the_filer() -> None:
    reader = FakeReader()
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(reader)
        async with ScreenHostApp(screen).run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            highlighted = screen.query_one(CasillaList).highlighted
            header = _text(screen, "#wb-header")
            result = _text(screen, "#wb-result")
            stepper = _text(screen, "#wb-stepper")
            next_line = _text(screen, "#wb-next")
            page = _text(screen, "#wb-page")

    assert reader.loads == 1
    assert highlighted is not None and highlighted.key == ("casilla", "06")
    assert "Modelo 130" in header
    assert "1.er trimestre 2026" in header
    assert result == "Resultado  1.300,00\u00a0€  [19]"
    assert "▸ Rellenar" in stepper
    assert "Completa las casillas marcadas (pendientes: 1) [n]" in next_line
    assert "Resultado" in page
    assert "página 2 de 3" in page
    assert "ordenadas automáticamente" in page


@pytest.mark.asyncio
async def test_official_grids_and_design_constants_read_as_the_printed_row() -> None:
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader())
        async with ScreenHostApp(screen).run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            await pilot.press("left_square_bracket")
            await pilot.pause()
            listing = _list_text(screen)

    assert "Régimen general 21 %" in listing
    assert "Tipo %: 21,00 · lo fija el diseño oficial" in listing
    assert "[07] Base imponible" in listing


@pytest.mark.asyncio
async def test_the_attention_filter_leaves_only_what_needs_the_filer() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader())
        async with ScreenHostApp(screen).run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            await pilot.press("f")
            await pilot.pause()
            listing = _list_text(screen)
            page = _text(screen, "#wb-page")

    assert "only what needs attention" in page
    assert "Retenciones" in listing
    assert "Resultado de la autoliquidaci" not in listing


@pytest.mark.asyncio
async def test_the_help_band_explains_the_box_and_adds_its_formula_once_fetched() -> None:
    reader = FakeReader()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(reader)
        async with ScreenHostApp(screen).run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            await pilot.press("down")
            for _ in range(5):
                await pilot.pause()
            band = _text(screen, "#wb-help")

    assert "[19] Resultado de la autoliquidación" in band
    assert "Calculated" in band
    assert "Cadrumo calculates it from other boxes." in band
    assert "Calculation: [19] = [01] − [02]" in band
    assert "19" in reader.cards


@pytest.mark.asyncio
async def test_a_narrow_terminal_folds_the_navigator_away() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader())
        async with ScreenHostApp(screen).run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await pilot.pause()
            narrow = screen.has_class("-narrow")
            navigator_shown = screen.query_one("#wb-sections").display

    assert narrow
    assert not navigator_shown


@pytest.mark.asyncio
async def test_a_complete_declaration_offers_the_next_lifecycle_step() -> None:
    reader = FakeReader(form=synthetic_form(needs_input=False))
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(reader)
        async with ScreenHostApp(screen).run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            stepper = _text(screen, "#wb-stepper")
            next_line = _text(screen, "#wb-next")

    assert "✓ Fill in" in stepper
    assert "✓ Calculate" in stepper
    assert "▸ Check" in stepper
    assert next_line == "Next: Check the declaration [F8]"


@pytest.mark.asyncio
async def test_leaving_dismisses_the_workbench() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            gone = app.screen is not screen

    assert gone
