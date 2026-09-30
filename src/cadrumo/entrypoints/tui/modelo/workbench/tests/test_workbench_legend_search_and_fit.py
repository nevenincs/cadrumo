"""The symbols line counts boxes, search finds box numbers as numbers, and a small terminal still shows boxes.

The first line of the widened help band counts each box's state once per box
and names every other symbol without a count; the one symbol for values from
the filer's data is named for all of them. While the symbols panel is open the
footer offers only its own keys. A box number typed alone finds that box
however it is padded, then the boxes whose number starts so, never one number
inside another; the first hit is selected and the help band explains it. On an
80 by 24 terminal at least ten boxes show. A settlement result always reads as
money, and a section whose heading reads like an identifier is named by the
boxes it holds.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual.pilot import Pilot
from textual.widgets import Footer, Input, Static

from ......application.modelo.work_form_models import (
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormOrigin,
    ModeloFormResultDirection,
    ModeloFormSection,
    ModeloFormText,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
)
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ....components.host import ScreenHostApp
from ..casilla_list import CasillaList
from ..header import result_view
from ..legend import on_screen_text
from ..navigator import section_title
from ..page_items import workbench_pages
from ..screen import ModeloWorkbenchScreen
from ..search import search, search_entries
from ..vocabulary import CONFIRM_MARK, DONE_MARK, HERE_MARK, ORIGIN_MARKS
from .declaration_states import with_result
from .form_edits import replace_fields
from .workbench_fixture import FakeActions, FakeReader, form_field, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_NBSP = "\u00a0"


async def _settle(pilot: Pilot[None], times: int = 4) -> None:
    for _ in range(times):
        await pilot.pause()


def _numbered_form(boxes: tuple[str, ...]) -> ModeloWorkForm:
    """The fixture form with one more page section holding a box for every number given."""
    fields = [form_field(box, f"Casilla {box}", ModeloFormOrigin.ENTERED, Decimal("1")) for box in boxes]
    form = synthetic_form()
    page = form.pages[0]
    section = ModeloFormSection(
        id="p1.numbered",
        heading=ModeloFormText(text="Numeradas", disclosure=ModeloFormTextDisclosure.LOCALIZED),
        official_heading=None,
        blocks=tuple(ModeloFormFieldBlock(id=f"n{field.box}", field=field) for field in fields),
        counts=page.counts,
    )
    first = page.model_copy(update={"sections": (*page.sections, section)})
    return form.model_copy(update={"pages": (first, *form.pages[1:])})


def test_the_symbols_line_counts_each_boxs_state_once_and_names_the_rest() -> None:
    confirm, calculated, imported = (
        CONFIRM_MARK,
        ORIGIN_MARKS[ModeloFormOrigin.CALCULATED],
        ORIGIN_MARKS[ModeloFormOrigin.IMPORTED],
    )
    with override_settings(cadrumo_output_language="en"):
        line = on_screen_text(
            (confirm, confirm, calculated, imported),
            (confirm, confirm, DONE_MARK, HERE_MARK, HERE_MARK),
        )

    assert line == (
        "On this screen: ◐ Assumed, please confirm 2 · = Calculated 1 · ↓ From your data 1 · ✓ Done · ▸ You are here"
    )


@pytest.mark.asyncio
async def test_while_the_symbols_panel_is_open_the_footer_offers_only_its_own_keys() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 30)) as pilot:
            await _settle(pilot)
            await pilot.press("question_mark", "question_mark")
            await _settle(pilot)
            open_keys = [
                str(key.render())
                for key in screen.query_one(Footer).query("FooterKey")
                if not key.has_class("-command-palette")
            ]
            await pilot.press("escape")
            await _settle(pilot)
            closed_keys = [str(key.render()) for key in screen.query_one(Footer).query("FooterKey")]
            app.exit(None)

    assert "esc Close" in open_keys
    assert "↑↓ Scroll" in open_keys
    assert not any(key in " ".join(open_keys) for key in ("Back", "Next step", "Search", "Edit", "Help"))
    assert "esc Back" in closed_keys
    assert "f8 Next step" in closed_keys


def test_a_box_number_typed_alone_is_found_as_a_number_never_inside_another() -> None:
    form = _numbered_form(("10", "11", "12", "14", "0100", "210"))
    with override_settings(cadrumo_output_language="en"):
        entries = search_entries(workbench_pages(form), staged={}, language=OutputLanguage.EN)

    def found(query: str) -> list[str | None]:
        return [entry.box for entry in search(entries, query)]

    assert found("01") == ["01", "0100"]
    assert found("0001") == ["01"]
    assert found("1") == ["01", "10", "11", "12", "14", "0100", "19"]
    assert "210" not in found("1"), "a number is never found inside another"
    assert found("19") == ["19"]


@pytest.mark.asyncio
async def test_the_first_hit_is_selected_and_the_help_band_explains_it() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("slash")
            await _settle(pilot)
            screen.query_one("#wb-search-input", Input).value = "retencion"
            await _settle(pilot)
            band = str(screen.query_one("#wb-help", Static).render()).splitlines()
            app.exit(None)

    assert band[0] == "[06] Retenciones e ingresos a cuenta"


def _many_boxes() -> ModeloWorkForm:
    boxes = tuple(f"{number:02d}" for number in range(20, 44))
    fields: list[ModeloFormField] = [
        form_field(box, f"Casilla manual {box}", ModeloFormOrigin.ENTERED, Decimal("10"), help_text="Explicación.")
        for box in boxes
    ]
    form = synthetic_form(needs_input=False)
    page = form.pages[0]
    section = page.sections[0].model_copy(
        update={"blocks": tuple(ModeloFormFieldBlock(id=f"m{field.box}", field=field) for field in fields)}
    )
    return form.model_copy(update={"pages": (page.model_copy(update={"sections": (section,)}), *form.pages[1:])})


@pytest.mark.asyncio
async def test_an_80_by_24_terminal_shows_ten_boxes_or_more() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_many_boxes()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await _settle(pilot)
            casilla_list = screen.query_one(CasillaList)
            rows = [casilla_list.render_line(y).text for y in range(casilla_list.size.height)]
            help_rows = screen.query_one("#wb-help", Static).size.height
            page_title = screen.query_one("#wb-page", Static).display
            await pilot.press("question_mark")
            await _settle(pilot)
            expanded_rows = screen.query_one("#wb-help", Static).size.height
            app.exit(None)

    boxes = [row for row in rows if "[" in row and "]" in row]
    assert len(boxes) >= 10, rows
    assert help_rows == 1
    assert not page_title, "the breadcrumb already says where the filer is"
    assert expanded_rows > help_rows, "? still widens the help band"


def test_a_settlement_result_reads_as_money_whatever_type_its_box_declares() -> None:
    form = replace_fields(synthetic_form(), {"19": {"data_type": "decimal"}})
    form = with_result(form, ModeloFormResultDirection.TO_PAY, Decimal("1106.69"))
    with override_settings(cadrumo_output_language="en"):
        view = result_view(form, OutputLanguage.EN, staged=0, recorded=False)

    assert view is not None
    assert view.text == f"To pay  1,106.69{_NBSP}€  [19]"


def test_a_section_named_like_an_identifier_is_named_by_its_boxes_or_else_its_place() -> None:
    technical = ModeloFormText(text="calculoimpuestores", disclosure=ModeloFormTextDisclosure.TECHNICAL)
    one = form_field("0018", "Rendimientos", ModeloFormOrigin.ENTERED, Decimal("1"))
    two = form_field("0025", "Gastos", ModeloFormOrigin.ENTERED, Decimal("1"))

    def section(*fields: ModeloFormField) -> ModeloFormSection:
        return ModeloFormSection(
            id="s",
            heading=technical,
            official_heading=None,
            blocks=tuple(ModeloFormFieldBlock(id=f"f{field.box}", field=field) for field in fields),
            counts=synthetic_form().counts,
        )

    titles = {}
    for language in ("en", "es", "ca", "hu"):
        with override_settings(cadrumo_output_language=language):
            titles[language] = [
                section_title(section(*fields), page_number=1, part_number=3).text
                for fields in ((one, two), (one,), ())
            ]

    assert titles["en"] == ["Boxes 0018 to 0025", "Box 0018", "Page 1, part 3"]
    assert titles["es"] == ["Casillas 0018 a 0025", "Casilla 0018", titles["es"][2]]
    for language, (boxes, box, _) in titles.items():
        assert "0018" in boxes and "0025" in boxes and "0018" in box, language
        assert "—" not in boxes and "–" not in boxes, language
