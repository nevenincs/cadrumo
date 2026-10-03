"""The filer finds any box: by page, by search, by number, in another order, and to the next thing to do.

Driven through the workbench over the synthetic form: headings that read like
registry ids are refused for words that name the section's place; the
navigator folds finished pages away and opens them on request; ``/`` finds a
box by number or by words without regard to accents; ``g`` goes to a box by
number or says the form has none; ``o`` lays the whole declaration out by box
number, by amount or what needs attention first; ``n`` carries on to the next
page with something to do and says when nothing is left; and below the
navigator's width a breadcrumb keeps the page, the section and its counts.
"""

from __future__ import annotations

import pytest
from textual.pilot import Pilot
from textual.widgets import Input, OptionList, Static

from ......application.modelo.work_form_models import (
    ModeloFormFieldBlock,
    ModeloFormText,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
)
from ......core.config import override_settings
from ....components.host import ScreenHostApp
from ..casilla_list import CasillaList, CasillaListEntry
from ..navigator import looks_like_identifier, presented_form, section_title
from ..screen import ModeloWorkbenchScreen
from ..search import SearchEntry, WorkbenchSearchPanel, search
from ..sorting import SortOrder
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WIDE = (140, 40)


async def _settle(pilot: Pilot[None], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


def _boxes(screen: ModeloWorkbenchScreen) -> list[str | None]:
    return [item.field.box for item in screen.query_one(CasillaList).items if isinstance(item, CasillaListEntry)]


def _cursor(screen: ModeloWorkbenchScreen) -> str | None:
    entry = screen.query_one(CasillaList).highlighted
    return None if entry is None else entry.field.box


def _navigator(screen: ModeloWorkbenchScreen) -> list[str]:
    navigator = screen.query_one("#wb-sections", OptionList)
    return [str(navigator.get_option_at_index(index).prompt) for index in range(navigator.option_count)]


def _with_headings(*headings: ModeloFormText, official: str | None = None) -> ModeloWorkForm:
    form = synthetic_form()
    page = form.pages[0]
    sections = tuple(
        section.model_copy(update={"heading": heading, "official_heading": official})
        for section, heading in zip(page.sections, headings, strict=True)
    )
    return form.model_copy(update={"pages": (page.model_copy(update={"sections": sections}), *form.pages[1:])})


@pytest.mark.parametrize(
    ("text", "identifier"),
    [
        ("DatosEconomicos/Resultados", True),
        ("calculoimpuestores", True),
        ("rdtotrabajores", True),
        ("regestimadir", True),
        ("modelo-349-operador", True),
        ("calculoimpuestores-4", True),
        ("DatosEconomicos", True),
        ("p2/s1", True),
        ("Resultado", False),
        ("Liquidación", False),
        ("III. Total liquidación", False),
        ("Rendimientos del trabajo", False),
        ("IVA", False),
    ],
)
def test_a_heading_that_reads_like_an_identifier_is_recognised(text: str, identifier: bool) -> None:
    assert looks_like_identifier(text) is identifier


def test_a_section_is_named_by_its_heading_its_official_heading_its_boxes_or_its_place() -> None:
    technical = ModeloFormText(text="rdtotrabajores", disclosure=ModeloFormTextDisclosure.TECHNICAL)
    id_like = ModeloFormText(text="modelo-349-operador", disclosure=ModeloFormTextDisclosure.LOCALIZED)
    with override_settings(cadrumo_output_language="en"):
        by_place = presented_form(_with_headings(technical, id_like))
        by_official = section_title(
            _with_headings(technical, id_like, official="II. Operaciones intracomunitarias").pages[0].sections[0],
            page_number=1,
            part_number=1,
        )

    assert [section.heading.text for section in by_place.pages[0].sections] == ["Boxes 01 to 03", "Boxes 07 to 09"]
    assert by_place.pages[1].sections[0].heading.text == "III. Total liquidación"
    assert by_official.text == "II. Operaciones intracomunitarias"
    assert by_official.disclosure is ModeloFormTextDisclosure.OFFICIAL_SPANISH


@pytest.mark.parametrize("query", ["Liquidación ÚNICA", "liquidacion unica", "LIQUIDACIÓN", "  única  "])
def test_search_folds_case_and_accents(query: str) -> None:
    entry = SearchEntry(
        key=("page", "0100"),
        box="0100",
        label="Liquidación única",
        description="",
        page="III. Total",
        value="",
        origin="",
    )

    assert search((entry,), query) == (entry,)


@pytest.mark.parametrize(
    ("boxes", "expected"),
    [
        (("1735", "1388", "1857"), "Boxes 1388 to 1857"),
        (("009", "001", "0005"), "Boxes 001 to 009"),
        (("0168", "0168", "0168"), "Box 0168"),
        (("D1", "B2", "A3"), "Page 1, part 1"),
        (("001", "A1", "003"), "Page 1, part 1"),
    ],
)
def test_fallback_section_ranges_use_printed_bounds_instead_of_reading_order(
    boxes: tuple[str, ...], expected: str
) -> None:
    technical = ModeloFormText(text="technical", disclosure=ModeloFormTextDisclosure.TECHNICAL)
    section = _with_headings(technical, technical).pages[0].sections[0]
    blocks = []
    for block, box in zip(section.blocks, boxes, strict=True):
        assert isinstance(block, ModeloFormFieldBlock)
        blocks.append(block.model_copy(update={"field": block.field.model_copy(update={"box": box})}))
    section = section.model_copy(update={"blocks": tuple(blocks)})
    with override_settings(cadrumo_output_language="en"):
        title = section_title(section, page_number=1, part_number=1)
    assert title.text == expected and title.disclosure is ModeloFormTextDisclosure.LOCALIZED


@pytest.mark.asyncio
async def test_a_finished_page_starts_closed_and_opens_and_closes_on_request() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_WIDE) as pilot:
            await _settle(pilot)
            opened_at_start = _navigator(screen)
            navigator = screen.query_one("#wb-sections", OptionList)
            navigator.focus()
            navigator.highlighted = 0
            await pilot.press("right")
            await _settle(pilot)
            after_open = _navigator(screen)
            await pilot.press("left")
            await _settle(pilot)
            after_close = _navigator(screen)
            app.exit(None)

    assert opened_at_start == [
        "▹ Liquidación ✓",
        "▿ ▸ Resultado !1",
        "    ! III. Total liquidación !1",
        "  Calculation details ✓",
    ]
    assert after_open[:3] == ["▿ Liquidación ✓", "    ✓ I. Actividades económicas", "    ✓ IVA devengado"]
    assert after_close == opened_at_start


@pytest.mark.asyncio
async def test_search_finds_a_box_by_number_or_by_words_on_any_page_and_goes_there() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_WIDE) as pilot:
            await _settle(pilot)
            await pilot.press("slash")
            await _settle(pilot)
            panel = screen.query_one(WorkbenchSearchPanel)
            header_shown = screen.query_one("#wb-result", Static).display
            await pilot.press(*"liquidacion")
            await _settle(pilot)
            by_words = [hit.box for hit in panel.hits]
            status = str(panel.query_one("#wb-search-status", Static).render())
            screen.query_one("#wb-search-input", Input).value = "2"
            await _settle(pilot)
            by_number = [hit.box for hit in panel.hits]
            first_line = panel.hits[0].text()
            screen.query_one("#wb-search-input", Input).value = "retencion"
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            searching = screen.has_class("-searching")
            landed = _cursor(screen)
            app.exit(None)

    assert header_shown
    assert by_words == ["19"]
    assert status == "Boxes found: 1"
    assert by_number[0] == "02"
    assert first_line == "[02] Gastos deducibles · Liquidación · 9,500.00\u00a0€ · ↓ Imported"
    assert not searching
    assert landed == "06"


@pytest.mark.asyncio
async def test_go_to_box_lands_on_the_number_or_says_the_form_has_none() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_WIDE) as pilot:
            await _settle(pilot)
            await pilot.press("g", *"555", "enter")
            await _settle(pilot)
            refusal = str(screen.query_one("#wb-search-status", Static).render())
            screen.query_one("#wb-search-input", Input).value = "7"
            await pilot.press("enter")
            await _settle(pilot)
            landed = _cursor(screen)
            page = str(screen.query_one("#wb-page", Static).render())
            app.exit(None)

    assert refusal == "There is no box [555] on this form."
    assert landed == "07"
    assert page.startswith("Liquidación")


@pytest.mark.asyncio
async def test_sorting_lays_the_whole_declaration_out_by_box_by_amount_and_by_attention() -> None:
    orders: dict[SortOrder, list[str | None]] = {}
    titles: dict[SortOrder, str] = {}
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_WIDE) as pilot:
            await _settle(pilot)
            for _ in range(3):
                await pilot.press("o")
                await _settle(pilot)
                orders[screen.box_order] = _boxes(screen)
                titles[screen.box_order] = str(screen.query_one("#wb-page", Static).render())
            labelled = next(
                item for item in screen.query_one(CasillaList).items if isinstance(item, CasillaListEntry)
            ).label
            await pilot.press("o")
            await _settle(pilot)
            back = (screen.box_order, _boxes(screen))
            app.exit(None)

    assert orders[SortOrder.BOX] == ["01", "02", "03", "06", "07", "09", "19", "99"]
    assert orders[SortOrder.AMOUNT] == ["01", "03", "02", "19", "07", "09", "99", "06"]
    assert orders[SortOrder.ATTENTION][0] == "06"
    assert titles[SortOrder.BOX].startswith("All pages   sorted by box number")
    assert labelled == "Retenciones e ingresos a cuenta · Resultado · III. Total liquidación"
    assert back == (SortOrder.FORM, ["06", "19"])


@pytest.mark.asyncio
async def test_next_to_do_carries_on_to_the_next_page_and_says_when_nothing_is_left() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_WIDE) as pilot:
            await _settle(pilot)
            await pilot.press("left_square_bracket")
            await _settle(pilot)
            start = _cursor(screen)
            await pilot.press("n")
            await _settle(pilot)
            crossed = (_cursor(screen), str(screen.query_one("#wb-page", Static).render()))
            await pilot.press("n")
            await _settle(pilot)
            notice = str(screen.query_one("#wb-notice", Static).render())
            app.exit(None)

    assert start == "01"
    assert crossed[0] == "06"
    assert crossed[1].startswith("Resultado")
    assert notice == "That was the last thing to do. Next: Complete the marked boxes (to do: 1) [n]"


@pytest.mark.asyncio
async def test_a_narrow_terminal_keeps_the_page_section_and_counts_in_a_breadcrumb() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(100, 30)) as pilot:
            await _settle(pilot)
            crumb = screen.query_one("#wb-crumb", Static)
            text = str(crumb.render())
            shown = crumb.display
            app.exit(None)

    assert shown
    assert text == "page 2 of 3 · Resultado · III. Total liquidación · !1"


@pytest.mark.asyncio
async def test_a_sorted_jump_names_the_targets_page_without_changing_the_remembered_form_page() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await _settle(pilot)
            await pilot.press("right_square_bracket")
            await _settle(pilot)
            remembered = screen._page_index
            assert remembered > 0
            await pilot.press("o", "g", "0", "7", "enter")
            await _settle(pilot)
            crumb = str(screen.query_one("#wb-crumb", Static).render())
            assert _cursor(screen) == "07"
            assert screen.box_order is SortOrder.BOX and screen._page_index == remembered
            assert "page 1 of 3" in crumb and "Liquidación" in crumb
            assert "sorted by box number" in crumb
            app.exit(None)
