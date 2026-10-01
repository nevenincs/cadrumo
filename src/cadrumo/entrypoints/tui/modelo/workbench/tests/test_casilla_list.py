"""The casilla list shows every field's state in words and marks, and keeps its cursor by address.

Driven through a real Textual pilot: keyboard movement skips headings, the
attention key lands on what needs the filer, actions name the address under the
cursor, and replacing the items keeps the same casilla under the cursor. Values
read in the filer's language and absence is spoken in words, never as a zero.
"""

from __future__ import annotations

from decimal import Decimal
from typing import override

import pytest
from textual.app import App, ComposeResult

from ......application.modelo.source_policy import source_policy
from ......application.modelo.work_form_models import (
    ModeloFormBinding,
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormText,
    ModeloFormTextDisclosure,
)
from ......core.aggregation import BindingSourceKind
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ....components.theme import install_cadrumo_themes
from ..casilla_list import CasillaList, CasillaListEntry, CasillaListHeading, CasillaListItem, CasillaListNote
from ..vocabulary import origin_words

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _field(
    casilla_id: str,
    label: str,
    origin: ModeloFormOrigin,
    value: Decimal | None = None,
    *,
    editability: ModeloFormEditability = ModeloFormEditability.EDITABLE_VALUE,
) -> ModeloFormField:
    return ModeloFormField(
        address=ModeloFormCasillaAddressV1(casilla_id=casilla_id),
        box=casilla_id,
        label=ModeloFormText(text=label, disclosure=ModeloFormTextDisclosure.LOCALIZED),
        help=None,
        data_type="money",
        value=value,
        origin=origin,
        editability=editability,
        required=origin is ModeloFormOrigin.NEEDS_INPUT,
    )


_ITEMS: tuple[CasillaListItem, ...] = (
    CasillaListHeading("I. Estimación directa"),
    CasillaListEntry(
        _field(
            "01",
            "Ingresos",
            ModeloFormOrigin.IMPORTED,
            Decimal("12345.67"),
            editability=ModeloFormEditability.LOCKED_SOURCE,
        )
    ),
    CasillaListEntry(
        _field(
            "03",
            "Rendimiento neto",
            ModeloFormOrigin.CALCULATED,
            Decimal("0"),
            editability=ModeloFormEditability.CALCULATED,
        )
    ),
    CasillaListHeading("III. Total liquidación"),
    CasillaListEntry(_field("06", "Retenciones", ModeloFormOrigin.NEEDS_INPUT)),
    CasillaListEntry(_field("16", "Deducción vivienda", ModeloFormOrigin.NOT_APPLICABLE)),
)


class _ListHarness(App[None]):
    def __init__(self, items: tuple[CasillaListItem, ...], language: OutputLanguage) -> None:
        super().__init__()
        self._items = items
        self._language = language
        self.messages: list[str] = []

    @override
    def compose(self) -> ComposeResult:
        yield CasillaList(self._items, language=self._language, id="list")

    def on_mount(self) -> None:
        install_cadrumo_themes(self, appearance="dark")
        self.query_one(CasillaList).focus()

    def on_casilla_list_edit_requested(self, message: CasillaList.EditRequested) -> None:
        self.messages.append(f"edit:{message.entry.key[1]}")

    def on_casilla_list_clear_requested(self, message: CasillaList.ClearRequested) -> None:
        self.messages.append(f"clear:{message.entry.key[1]}")


def _screen_lines(widget: CasillaList) -> list[str]:
    return [widget.render_line(y).text for y in range(widget.size.height)]


@pytest.mark.asyncio
async def test_values_read_in_the_filers_language_and_absence_is_spoken() -> None:
    with override_settings(cadrumo_output_language="es"):
        app = _ListHarness(_ITEMS, OutputLanguage.ES)
        async with app.run_test(size=(120, 24)) as pilot:
            await pilot.pause()
            text = "\n".join(_screen_lines(app.query_one(CasillaList)))

    assert "12.345,67\u00a0\u20ac" in text
    assert "Importada" in text
    assert "Falta tu dato" in text
    assert "No aplica" in text
    assert "[06]" in text
    retenciones = next(line for line in text.splitlines() if "Retenciones" in line)
    assert "0,00" not in retenciones


@pytest.mark.asyncio
async def test_the_cursor_moves_between_fields_and_skips_headings() -> None:
    app = _ListHarness(_ITEMS, OutputLanguage.EN)
    async with app.run_test(size=(80, 24)) as pilot:
        widget = app.query_one(CasillaList)
        await pilot.pause()
        first = widget.highlighted
        await pilot.press("down", "down")
        third = widget.highlighted
        await pilot.press("enter")
        await pilot.pause()

    assert first is not None and first.key == ("casilla", "01")
    assert third is not None and third.key == ("casilla", "06")
    assert app.messages == ["edit:06"]


@pytest.mark.asyncio
async def test_the_attention_key_lands_on_what_needs_the_filer() -> None:
    app = _ListHarness(_ITEMS, OutputLanguage.EN)
    async with app.run_test(size=(80, 24)) as pilot:
        widget = app.query_one(CasillaList)
        await pilot.pause()
        await pilot.press("n")
        landed = widget.highlighted
        await pilot.press("x")
        await pilot.pause()

    assert landed is not None and landed.key == ("casilla", "06")
    assert app.messages == ["clear:06"]


@pytest.mark.asyncio
async def test_replacing_the_items_keeps_the_same_address_under_the_cursor() -> None:
    app = _ListHarness(_ITEMS, OutputLanguage.EN)
    async with app.run_test(size=(80, 24)) as pilot:
        widget = app.query_one(CasillaList)
        await pilot.pause()
        assert widget.focus_address(("casilla", "16"))
        staged = CasillaListEntry(
            _field("06", "Retenciones", ModeloFormOrigin.NEEDS_INPUT), staged_text="100,00 \u20ac"
        )
        widget.set_items((*_ITEMS[:4], staged, *_ITEMS[5:]))
        await pilot.pause()
        kept = widget.highlighted
        lines = _screen_lines(widget)

    assert kept is not None and kept.key == ("casilla", "16")
    staged_line = next(line for line in lines if "Retenciones" in line)
    assert "\u0394" in staged_line
    assert "100,00" in staged_line


@pytest.mark.asyncio
async def test_compact_density_puts_every_field_on_one_line() -> None:
    app = _ListHarness(_ITEMS, OutputLanguage.EN)
    async with app.run_test(size=(80, 24)) as pilot:
        widget = app.query_one(CasillaList)
        widget.set_density("compact")
        await pilot.pause()
        lines = [line for line in _screen_lines(widget) if line.strip()]

    assert len(lines) == len(_ITEMS)


@pytest.mark.asyncio
async def test_headings_and_notes_keep_their_own_style_when_rendered() -> None:
    items: tuple[CasillaListItem, ...] = (
        CasillaListHeading("I. Estimación directa"),
        CasillaListHeading("Régimen general", level=1),
        CasillaListNote("Fixed by the official design"),
        _ITEMS[1],
    )
    app = _ListHarness(items, OutputLanguage.EN)
    async with app.run_test(size=(80, 24)) as pilot:
        widget = app.query_one(CasillaList)
        await pilot.pause()
        plain = widget.rich_style
        heading_style = widget.get_component_rich_style("casilla-list--heading")
        muted_style = widget.get_component_rich_style("casilla-list--muted")
        heading, subheading, note = (next(iter(widget.render_line(y))).style for y in range(3))

    # Headings carry the strongest weight, in the text colour, and never the muted one descriptions use.
    assert heading is not None and heading.bold and heading.underline and heading.color == heading_style.color
    assert heading.color == plain.color
    assert subheading is not None and subheading.bold and subheading.color == plain.color
    assert heading.color != muted_style.color
    assert note is not None and note.color == muted_style.color
    assert note.color != plain.color


@pytest.mark.asyncio
async def test_on_the_widest_list_the_source_follows_the_origin_words_after_the_rows_separator() -> None:
    sourced = _field(
        "01", "Ingresos", ModeloFormOrigin.IMPORTED, Decimal("10"), editability=ModeloFormEditability.LOCKED_SOURCE
    ).model_copy(
        update={
            "bindings": (
                ModeloFormBinding(
                    binding_id="m130.ingresos",
                    policy=source_policy(BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION),
                    resolved=True,
                ),
            )
        }
    )
    with override_settings(cadrumo_output_language="en"):
        app = _ListHarness((CasillaListEntry(sourced),), OutputLanguage.EN)
        async with app.run_test(size=(200, 10)) as pilot:
            await pilot.pause()
            line = next(row for row in _screen_lines(app.query_one(CasillaList)) if "[01]" in row)
        words = origin_words(sourced)
        source = tr(source_policy(BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION).label_key)

    assert f"{words} · {source}" in line
