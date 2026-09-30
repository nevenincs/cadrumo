"""The box panel answers the filer's questions about one box, and keeps a value only as they decide.

Driven by hosting the panel alone over synthetic fields, so each test proves
what the panel says and what it closes with: the answer blocks in order, an
assumed value prefilled for Enter to confirm, Enter asking to move on and
Ctrl+Enter staying, a read-only box explained without an input, and the input
and buttons in view on an 80x24 terminal in every language.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, Input, Static

from ......application.modelo.source_policy import SourceFamily
from ......application.modelo.work_form_models import (
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormValueSource,
)
from ......core.aggregation import BindingSourceKind
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ....components.host import ScreenHostApp
from ..editor import CasillaEditorScreen, EditorDecision, can_change_text, read_only_reason
from ..ports import WorkbenchChangeKind
from .workbench_fixture import FakeActions, fed_by, form_field

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LANGUAGES = ("es", "en", "ca", "hu")
_LONG_HELP = "Casilla 06: " + " ".join(["Retenciones e ingresos a cuenta soportados en el trimestre."] * 8)


async def _settle(pilot: Pilot[EditorDecision | None], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


def _assumed() -> ModeloFormField:
    return form_field(
        "06",
        "Retenciones e ingresos a cuenta",
        ModeloFormOrigin.DEFAULT_TO_CONFIRM,
        Decimal("0.00"),
        help_text="Casilla 06: retenciones soportadas en el trimestre.",
    )


def _sourced() -> ModeloFormField:
    return form_field(
        "01",
        "Ingresos computables",
        ModeloFormOrigin.IMPORTED,
        Decimal("24000.00"),
        editability=ModeloFormEditability.LOCKED_SOURCE,
        bindings=(fed_by("m130.ingresos", BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION),),
    ).model_copy(update={"source": ModeloFormValueSource(family=SourceFamily.RECORDS)})


def _editor(
    field: ModeloFormField,
    language: str,
    *,
    can_restore: bool = False,
    reason: str | None = None,
    feeds: tuple[str, ...] = (),
) -> CasillaEditorScreen:
    return CasillaEditorScreen(
        field,
        parse=FakeActions().parse,
        language=OutputLanguage(language),
        can_restore=can_restore,
        read_only_reason=reason,
        feeds=feeds,
    )


def _text(editor: CasillaEditorScreen, widget_id: str) -> str:
    return str(editor.query_one(widget_id, Static).render())


@pytest.mark.asyncio
async def test_the_panel_answers_what_it_asks_what_it_holds_whether_it_changes_and_what_it_affects() -> None:
    with override_settings(cadrumo_output_language="en"):
        editor = _editor(_assumed(), "en", feeds=("07", "19"))
        app = ScreenHostApp(editor)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            asks = _text(editor, "#editor-asks-text")
            now = _text(editor, "#editor-now-text")
            can_change = _text(editor, "#editor-can-change-text")
            affects = _text(editor, "#editor-affects-text")
            where = editor.query("#editor-where")
            save = str(editor.query_one("#editor-save", Button).label)

    assert asks == "Retenciones soportadas en el trimestre."
    assert now.startswith("0.00")
    assert "◐ Assumed" in now
    assert can_change == "Yes. Type the new value below."
    assert affects == "[07], [19]"
    assert not where, "a box no source feeds has no 'where it comes from' answer"
    assert save == "Keep for review"


@pytest.mark.asyncio
async def test_a_sourced_box_says_where_it_comes_from_and_where_to_change_it_without_an_input() -> None:
    field = _sourced()
    with override_settings(cadrumo_output_language="es"):
        reason = read_only_reason(field, OutputLanguage.ES)
        assert reason is not None
        editor = _editor(field, "es", reason=reason)
        app = ScreenHostApp(editor)
        async with app.run_test(size=(80, 24)) as pilot:
            await _settle(pilot)
            where = _text(editor, "#editor-where-text")
            can_change = _text(editor, "#editor-can-change-text")
            inputs = editor.query(Input)
            buttons = [str(button.label) for button in editor.query(Button)]
            await pilot.press("enter")
            await _settle(pilot)

    assert where == "De tus registros"
    assert can_change == "Aquí no. Cámbialo en tus registros (Libro mayor) y vuelve a calcular."
    assert not inputs
    assert buttons == ["Volver"]
    assert app.return_value is None


def test_a_recorded_declaration_makes_even_a_typed_box_read_only() -> None:
    with override_settings(cadrumo_output_language="en"):
        typed = read_only_reason(_assumed(), OutputLanguage.EN)
        recorded = read_only_reason(_assumed(), OutputLanguage.EN, recorded=True)

    assert typed is None
    assert recorded == "No. This declaration is recorded as filed."


def test_a_replaceable_source_names_the_value_the_filers_value_would_replace() -> None:
    carried = form_field(
        "05",
        "Pagos fraccionados anteriores",
        ModeloFormOrigin.IMPORTED,
        Decimal("500.00"),
        editability=ModeloFormEditability.OVERRIDABLE_SOURCE,
        bindings=(fed_by("m130.anteriores", BindingSourceKind.PREVIOUS_FILING),),
    )
    with override_settings(cadrumo_output_language="en"):
        now_source = can_change_text(carried, OutputLanguage.EN)
        replaced = can_change_text(
            carried.model_copy(update={"origin": ModeloFormOrigin.OVERRIDES_SOURCE}), OutputLanguage.EN
        )

    assert now_source.startswith("Yes. Your value will replace the source's 500.00")
    assert "source's value, in this declaration only" in replaced


@pytest.mark.asyncio
async def test_enter_on_an_assumed_value_confirms_it_as_it_is_and_asks_to_move_on() -> None:
    field = _assumed()
    with override_settings(cadrumo_output_language="es"):
        editor = _editor(field, "es")
        app = ScreenHostApp(editor)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            prefilled = editor.query_one("#editor-input", Input).value
            hint = _text(editor, "#editor-readback")
            await pilot.press("enter")
            await _settle(pilot)

    decision = app.return_value
    assert prefilled == "0,00"
    assert hint.startswith("Pulsa ⏎ para confirmar 0,00")
    assert isinstance(decision, EditorDecision)
    assert decision.kind is WorkbenchChangeKind.SET
    assert decision.value == field.value
    assert decision.advance


@pytest.mark.asyncio
async def test_typing_over_an_assumed_value_replaces_it_and_ctrl_enter_stays_on_the_box() -> None:
    with override_settings(cadrumo_output_language="es"):
        editor = _editor(_assumed(), "es")
        app = ScreenHostApp(editor)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press(*"125,5")
            await _settle(pilot)
            readback = _text(editor, "#editor-readback")
            await pilot.press("ctrl+enter")
            await _settle(pilot)

    decision = app.return_value
    assert readback.startswith("✓ Se leerá como 125,50")
    assert readback.endswith("€")
    assert isinstance(decision, EditorDecision)
    assert decision.value == Decimal("125.5")
    assert not decision.advance


@pytest.mark.asyncio
async def test_a_box_with_nothing_assumed_opens_empty_and_keeps_nothing_until_a_value_reads() -> None:
    empty = form_field("06", "Retenciones", ModeloFormOrigin.NEEDS_INPUT)
    with override_settings(cadrumo_output_language="en"):
        editor = _editor(empty, "en")
        app = ScreenHostApp(editor)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            value = editor.query_one("#editor-input", Input).value
            disabled = editor.query_one("#editor-save", Button).disabled
            await pilot.press("enter")
            await _settle(pilot)
            still_open = app.screen is editor

    assert value == ""
    assert disabled
    assert still_open


@pytest.mark.asyncio
@pytest.mark.parametrize("language", _LANGUAGES)
@pytest.mark.parametrize("size", [(80, 24), (140, 40)])
async def test_the_input_and_every_button_stay_in_view_however_long_the_answers(
    language: str, size: tuple[int, int]
) -> None:
    carried = form_field(
        "05",
        "Pagos fraccionados de periodos anteriores del mismo ejercicio",
        ModeloFormOrigin.IMPORTED,
        Decimal("500.00"),
        editability=ModeloFormEditability.OVERRIDABLE_SOURCE,
        help_text=_LONG_HELP,
        bindings=(fed_by("m130.anteriores", BindingSourceKind.PREVIOUS_FILING),),
    ).model_copy(update={"source": ModeloFormValueSource(family=SourceFamily.EARLIER_FILINGS)})
    with override_settings(cadrumo_output_language=language):
        editor = _editor(carried, language, can_restore=True, feeds=("07", "12", "19"))
        app = ScreenHostApp(editor)
        async with app.run_test(size=size) as pilot:
            await _settle(pilot)
            widgets = [editor.query_one("#editor-input", Input), *editor.query(Button)]
            regions = [widget.region for widget in widgets]
            labels = [str(button.label) for button in editor.query(Button)]
            body = editor.query_one("#editor-body")
            scrolls = body.max_scroll_y > 0

    assert len(labels) == 3
    for region in regions:
        assert region.width > 0
        assert region.height > 0
        assert region.x >= 0
        assert region.y >= 0
        assert region.right <= size[0]
        assert region.bottom <= size[1]
    if size == (80, 24):
        assert scrolls, "the long answers must scroll rather than push the buttons away"
