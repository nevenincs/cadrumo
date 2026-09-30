"""The help band speaks the row's words, a filed declaration says it is filed, and the footer and next step fit.

The help band names where a value comes from with the same words as its row,
never the bare "Imported"; gives the box's description without an opening that
only repeats its number; and drops a source's sentence the origin words
already say. On a declaration recorded as filed it says so for every box, asks
the filer for nothing, and the footer offers no key that would change it. At
80, 120 and 200 columns the footer never runs under the palette key and keeps
the next step, and the next-action line never takes more than one line.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import override

import pytest
from rich.cells import cell_len
from textual.pilot import Pilot
from textual.widgets import Footer, OptionList, Static

from ......application.modelo.casilla_help import ModeloCasillaHelpCardV1
from ......application.modelo.source_policy import SourceSurface
from ......application.modelo.work_form_models import (
    ModeloFormGridBlock,
    ModeloFormGridCell,
    ModeloFormOrigin,
    ModeloWorkForm,
)
from ......core.casilla_id import CasillaId
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import lookup_translation
from ......domain.calculations.registry.schema_form_layouts import FormCellKind
from ....components.host import ScreenHostApp
from ....navigation import TuiNavigationTargetV1
from ..casilla_list import CasillaList
from ..editor import CasillaEditorScreen
from ..issues import WorkbenchIssuesScreen
from ..progress import fit_next_line
from ..screen import ModeloWorkbenchScreen
from ..sources import OpenSourceSurface, surface_target
from ..wording import wrap_words
from .declaration_states import recorded_as_filed
from .sectioned_form import sectioned_form
from .workbench_fixture import FakeActions, FakeReader, form_field, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WIDTHS = [80, 120, 200]
_RECORDED_REASON = "No. This declaration is recorded as filed."
_CHANGE_KEY_WORDS = ("Review changes", "Next step", "Calculate", "Confirm assumed values", "Next to do")


def _sentence(key: str) -> str:
    return lookup_translation(f"docs.casilla.binding_source.{key}", locale="en") or key


@dataclass
class _SourcedReader(FakeReader):
    """A reader whose help cards name the sources that feed each box, as the registry does."""

    @override
    def help_card(self, casilla_id: CasillaId, language: OutputLanguage) -> ModeloCasillaHelpCardV1:
        """Return the fixture's card with the source sentences of the box's own bindings."""
        card = super().help_card(casilla_id, language)
        field = next(item for item in self.form.fields() if item.box == str(casilla_id))
        origins = tuple(_sentence(binding.policy.source_kind.value) for binding in field.bindings)
        return card.model_copy(update={"origins": origins})


async def _settle(pilot: Pilot[None], times: int = 4) -> None:
    for _ in range(times):
        await pilot.pause()


async def _band_on(pilot: Pilot[None], screen: ModeloWorkbenchScreen, box: str) -> list[str]:
    await pilot.press("g", *box, "enter")
    await _settle(pilot, 6)
    entry = screen.query_one(CasillaList).highlighted
    assert entry is not None and entry.field.box == box
    return str(screen.query_one("#wb-help", Static).render()).splitlines()


@pytest.mark.asyncio
async def test_the_help_band_uses_the_rows_words_and_says_a_source_only_once() -> None:
    reader = _SourcedReader(form=sectioned_form())
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(reader, actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            band = await _band_on(pilot, screen, "01")
            app.exit(None)

    assert band[1].startswith("↓ From your records · ")
    assert "Imported" not in "\n".join(band)
    assert band[2] == "Income from the activity in the quarter."
    assert not any(line.startswith("Source:") for line in band), "the origin words already say the records"


@pytest.mark.asyncio
async def test_a_source_the_origin_words_do_not_name_is_still_said() -> None:
    reader = _SourcedReader(form=synthetic_form())
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(reader, actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            band = await _band_on(pilot, screen, "06")
            app.exit(None)

    sources = [line for line in band if line.startswith("Source:")]
    assert sources == [
        f"Source: {_sentence('retenciones_aggregation')}",
        f"Source: {_sentence('withholding')}",
    ]


def _filed() -> ModeloWorkForm:
    return recorded_as_filed(sectioned_form())


def _footer(screen: ModeloWorkbenchScreen) -> tuple[list[tuple[str, int, int]], tuple[int, int] | None]:
    """The footer's keys as (words, left, right), and where the palette key starts and ends, if it shows."""
    footer = screen.query_one(Footer)
    keys: list[tuple[str, int, int]] = []
    palette: tuple[int, int] | None = None
    for child in footer.query("FooterKey"):
        if child.has_class("-command-palette"):
            palette = (child.region.x, child.region.right)
        else:
            keys.append((str(child.render()), child.region.x, child.region.right))
    return keys, palette


@pytest.mark.asyncio
@pytest.mark.parametrize("width", _WIDTHS)
async def test_a_filed_declaration_says_so_for_every_box_and_offers_no_change(width: int) -> None:
    reader = FakeReader(form=_filed(), verified=True, filed=True)
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(reader, actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(width, 30)) as pilot:
            await _settle(pilot)
            assumed = await _band_on(pilot, screen, "05")
            sourced = await _band_on(pilot, screen, "01")
            chips = str(screen.query_one("#wb-chips", Static).render())
            keys, _ = _footer(screen)
            app.exit(None)

    assert assumed[1] == _RECORDED_REASON, "an assumed box on a filed declaration asks for nothing"
    assert "◐" not in "\n".join(assumed)
    assert sourced[1] == f"↓ From your records · {_RECORDED_REASON}"
    assert chips == ""
    words = " ".join(text for text, _, _ in keys)
    assert not any(word in words for word in _CHANGE_KEY_WORDS)
    assert "Help" in words


@pytest.mark.asyncio
@pytest.mark.parametrize("width", _WIDTHS)
async def test_the_footer_keeps_the_next_step_clear_of_the_palette_key(width: int) -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=sectioned_form()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(width, 30)) as pilot:
            await _settle(pilot)
            keys, palette = _footer(screen)
            app.exit(None)

    assert any(text == "f8 Next step" for text, _, _ in keys)
    edge = width if palette is None else palette[0]
    assert all(right <= edge for _, _, right in keys), f"a key runs under the palette key at {width} columns: {keys}"


@pytest.mark.asyncio
@pytest.mark.parametrize("width", _WIDTHS)
async def test_the_next_step_never_takes_more_than_one_line(width: int) -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=sectioned_form()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(width, 30)) as pilot:
            await _settle(pilot)
            next_step = screen.query_one("#wb-next", Static)
            stepper = screen.query_one("#wb-stepper", Static)
            text = str(next_step.render())
            region, stepper_row = next_step.region, stepper.region.y
            app.exit(None)

    assert text == "Next: Confirm the assumed values (to confirm: 4) [n]"
    assert region.height == 1
    assert cell_len(text) <= region.width
    if width >= 120:
        assert region.y == stepper_row, "with room the next step sits beside the stepper"
    else:
        assert region.y == stepper_row + 1, "without room the next step takes its own line"


@pytest.mark.parametrize("width", [8, 20, 30, 60])
def test_a_next_step_too_long_for_its_line_keeps_its_key_and_shortens_its_words(width: int) -> None:
    with override_settings(cadrumo_output_language="en"):
        line = fit_next_line("Confirm the assumed values (to confirm: 4)", "n", width, then="Record filing [F8]")

    assert cell_len(line) <= max(width, cell_len("Next: … [n]"))
    assert line.endswith("[n]")
    assert line.startswith("Next: ")
    if width < 60:
        assert "…" in line


@pytest.mark.parametrize("width", [10, 16, 24, 40])
def test_the_band_breaks_a_line_only_where_a_breakable_space_stands(width: int) -> None:
    held = "art.\u00a071"
    text = f"Legal basis: Ley 37/1992, {held}; Real Decreto 1624/1992, {held}"

    lines = wrap_words(text, width)

    assert all(cell_len(line) <= width for line in lines)
    assert not any(line.endswith("art.") for line in lines)
    assert " ".join(lines).count(held) == 2 or width < cell_len(held)


def _with_unrated_row() -> ModeloWorkForm:
    """The fixture whose grid row prints a rate box that holds no value and no grounded rate."""
    form = synthetic_form()
    page = form.pages[0]
    grid_section = page.sections[1]
    grid = grid_section.blocks[0]
    assert isinstance(grid, ModeloFormGridBlock)
    rate = form_field("08", "Tipo", ModeloFormOrigin.OPTIONAL_EMPTY).model_copy(update={"data_type": "ratio"})
    row = grid.rows[0]
    cells = (row.cells[0], ModeloFormGridCell(kind=FormCellKind.CASILLA, field=rate), row.cells[2])
    grid = grid.model_copy(update={"rows": (row.model_copy(update={"cells": cells}),)})
    sections = (page.sections[0], grid_section.model_copy(update={"blocks": (grid,)}))
    return form.model_copy(update={"pages": (page.model_copy(update={"sections": sections}), *form.pages[1:])})


@pytest.mark.asyncio
async def test_the_help_band_says_why_a_rows_rate_box_shows_no_rate() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_with_unrated_row()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            rate = await _band_on(pilot, screen, "08")
            other = await _band_on(pilot, screen, "07")
            app.exit(None)

    note = lookup_translation("tui.modelo.workbench.rate.not_grounded", locale="en")
    assert note is not None
    assert note in rate
    assert note not in other


@pytest.mark.asyncio
async def test_the_editor_repeats_the_result_line_and_can_send_the_filer_to_the_owning_area() -> None:
    navigated: list[TuiNavigationTargetV1] = []
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions(), navigate=navigated.append)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("g", *"01", "enter")
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            editor = app.screen
            assert isinstance(editor, CasillaEditorScreen)
            status = str(editor.query_one("#editor-status", Static).render())
            header = str(screen.query_one("#wb-result", Static).render())
            editor.dismiss(OpenSourceSurface(surface=SourceSurface.LEDGER))
            await _settle(pilot)
            app.exit(None)

    assert header and status.startswith(header)
    assert navigated == [surface_target(SourceSurface.LEDGER)]


@pytest.mark.asyncio
async def test_a_filed_declarations_symbols_line_names_nothing_left_to_do() -> None:
    reader = FakeReader(form=_filed(), verified=True, filed=True)
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(reader, actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 30)) as pilot:
            await _settle(pilot)
            landed = screen.query_one(CasillaList).highlighted
            await pilot.press("question_mark")
            await _settle(pilot)
            symbols = str(screen.query_one("#wb-help", Static).render()).splitlines()[0]
            app.exit(None)

    assert symbols.startswith("On this screen: ")
    assert "◐" not in symbols
    assert "!" not in symbols
    assert landed is None or landed.field.box != "05", "a filed declaration does not open on an assumed box"


@dataclass
class _SlowFeedingReader(FakeReader):
    """A reader whose help cards say every box is used in box 19, and arrive only once the test lets them."""

    ready: threading.Event = field(default_factory=threading.Event)

    @override
    def help_card(self, casilla_id: CasillaId, language: OutputLanguage) -> ModeloCasillaHelpCardV1:
        """Wait until the test lets the card through, then name the box it feeds."""
        self.ready.wait(timeout=10)
        return super().help_card(casilla_id, language).model_copy(update={"feeds": ("[19]",)})


@pytest.mark.asyncio
async def test_the_editor_names_the_boxes_a_box_affects_even_before_its_help_was_read() -> None:
    reader = _SlowFeedingReader()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(reader, actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            reader.ready.set()
            await _settle(pilot, 8)
            editor = app.screen
            assert isinstance(editor, CasillaEditorScreen)
            shown = " ".join(str(widget.render()) for widget in editor.query(Static))
            app.exit(None)

    assert "[19]" in shown


@pytest.mark.asyncio
async def test_the_findings_list_marks_its_selection_with_a_quiet_surface_not_the_primary_colour() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=sectioned_form()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("i")
            await _settle(pilot)
            findings = app.screen
            assert isinstance(findings, WorkbenchIssuesScreen)
            listed = findings.query_one("#issues-list", OptionList)
            listed.focus()
            await _settle(pilot)
            style = listed.get_component_rich_style("option-list--option-highlighted")
            theme = app.theme_variables
            app.exit(None)

    assert style.bgcolor is not None
    assert style.bgcolor.triplet is not None
    assert style.bgcolor.triplet.hex.lower() == theme["panel"].lower()
