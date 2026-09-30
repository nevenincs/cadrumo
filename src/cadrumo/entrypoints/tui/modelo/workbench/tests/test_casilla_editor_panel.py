"""The box panel answers the filer's questions about one box, and keeps a value only as they decide.

Driven by hosting the panel alone over synthetic fields, so each test proves
what the panel says and what it closes with: the answer blocks in order, with
the new value straight after "Can you change it?" and the format under the
input; an assumed value prefilled for Enter to confirm; Enter, the highlighted
action, asking to move on and Ctrl+Enter staying; a read-only box explained
without an input, naming the owning area once and offering to open it; the
header's result line repeated first; a title in the strongest style; a panel
as tall as what it says; and the input and buttons in view on an 80x24
terminal in every language.
"""

from __future__ import annotations

from decimal import Decimal
from typing import override

import pytest
from textual.app import App, ComposeResult
from textual.color import Color
from textual.geometry import Region
from textual.pilot import Pilot
from textual.widgets import Button, Input, Static

from ......application.modelo.source_policy import SourceFamily, SourceSurface
from ......application.modelo.work_form_models import (
    ModeloFormEarlierFiling,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormValueSource,
)
from ......core.aggregation import BindingSourceKind
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......core.period import Period
from ....components.host import ScreenHostApp
from ....tests.frame import screen_text
from ..casilla_list import CasillaList, CasillaListEntry
from ..editor import (
    CasillaEditorScreen,
    EditorDecision,
    EditorOutcome,
    can_change_text,
    open_area_target,
    read_only_reason,
    where_from_text,
)
from ..ports import WorkbenchChangeKind
from ..sources import OpenSourceSurface
from ..wording import period_words
from .workbench_fixture import FakeActions, fed_by, form_field

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LANGUAGES = ("es", "en", "ca", "hu")
_SIZES = [(80, 24), (140, 40)]
_LONG_HELP = "Casilla 06: " + " ".join(["Retenciones e ingresos a cuenta soportados en el trimestre."] * 8)
_STATUS = "Resultado: 1.300,00 € a ingresar"


async def _settle(pilot: Pilot[EditorOutcome | None], times: int = 3) -> None:
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


def _calculated() -> ModeloFormField:
    return form_field(
        "03",
        "Rendimiento neto",
        ModeloFormOrigin.CALCULATED,
        Decimal("1000.00"),
        editability=ModeloFormEditability.CALCULATED,
    )


def _editor(
    field: ModeloFormField,
    language: str,
    *,
    can_clear: bool = False,
    can_restore: bool = False,
    reason: str | None = None,
    feeds: tuple[str, ...] = (),
    status_line: str | None = None,
) -> CasillaEditorScreen:
    return CasillaEditorScreen(
        field,
        parse=FakeActions().parse,
        language=OutputLanguage(language),
        can_clear=can_clear,
        can_restore=can_restore,
        read_only_reason=reason,
        feeds=feeds,
        status_line=status_line,
    )


def _read_only(
    field: ModeloFormField, language: str, *, feeds: tuple[str, ...] = (), status_line: str | None = None
) -> CasillaEditorScreen:
    reason = read_only_reason(field, OutputLanguage(language))
    assert reason is not None
    return _editor(field, language, reason=reason, feeds=feeds, status_line=status_line)


def _text(editor: CasillaEditorScreen, widget_id: str) -> str:
    return str(editor.query_one(widget_id, Static).render())


def _labels(editor: CasillaEditorScreen) -> list[str]:
    return [str(button.label) for button in editor.query(Button)]


def _longest_blank_run(text: str, region: Region) -> int:
    """The most consecutive rows inside a panel's border, at ``region``, that paint nothing."""
    rows = text.splitlines()[region.y + 1 : region.bottom - 1]
    longest = run = 0
    for row in rows:
        inside = row[region.x + 1 : region.right - 1]
        run = run + 1 if not inside.strip() else 0
        longest = max(longest, run)
    return longest


@pytest.mark.asyncio
async def test_the_panel_answers_what_it_asks_what_it_holds_whether_it_changes_and_what_it_affects() -> None:
    with override_settings(cadrumo_output_language="en"):
        editor = _editor(_assumed(), "en", feeds=("[07]", "[19]"))
        app = ScreenHostApp(editor)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            asks = _text(editor, "#editor-asks-text")
            now = _text(editor, "#editor-now-text")
            can_change = _text(editor, "#editor-can-change-text")
            affects = _text(editor, "#editor-affects-text")
            where = editor.query("#editor-where")
            status = editor.query("#editor-status")

    assert asks == "Retenciones soportadas en el trimestre."
    assert now.startswith("0.00")
    assert "◐ Assumed" in now
    assert can_change == "Yes. Type the new value below."
    assert affects == "[07], [19]"
    assert not where, "a box no source feeds has no 'where it comes from' answer"
    assert not status, "without a result line the panel starts at its title"


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("size", _SIZES)
async def test_the_boxes_it_affects_come_between_can_you_change_it_and_the_new_value(
    language: str, size: tuple[int, int]
) -> None:
    with override_settings(cadrumo_output_language=language):
        editor = _editor(_assumed(), language, feeds=("[07]",))
        app = ScreenHostApp(editor)
        async with app.run_test(size=size) as pilot:
            await _settle(pilot)
            can_change = editor.query_one("#editor-can-change").region
            entry = editor.query_one("#editor-entry").region
            field_input = editor.query_one("#editor-input", Input).region
            hint = editor.query_one("#editor-hint").region
            hint_text = _text(editor, "#editor-hint")
            money_format = tr("tui.modelo.workbench.editor.format.money")
            affects = editor.query_one("#editor-affects").region

    assert affects.y == can_change.bottom, "'Affects' comes straight after 'Can you change it?'"
    assert entry.y >= affects.bottom, "the new value comes after the boxes it affects"
    assert hint.y == field_input.bottom, "the format is right under the input"
    assert hint.x == field_input.x
    assert hint_text == money_format


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("size", _SIZES)
@pytest.mark.parametrize("case", ["editable", "read_only"])
async def test_the_panel_is_as_tall_as_what_it_says_with_no_empty_band(
    language: str, size: tuple[int, int], case: str
) -> None:
    with override_settings(cadrumo_output_language=language):
        editor = (
            _editor(_assumed(), language, feeds=("[07]",), status_line=_STATUS)
            if case == "editable"
            else _read_only(_sourced(), language, feeds=("[03]",), status_line=_STATUS)
        )
        app = ScreenHostApp(editor)
        async with app.run_test(size=size) as pilot:
            await _settle(pilot)
            panel_widget = editor.query_one("#editor-panel")
            panel = panel_widget.region
            gutter = panel_widget.gutter.bottom
            body_widget = editor.query_one("#editor-body")
            body = body_widget.region
            foot = editor.query_one("#editor-foot").region
            actions = editor.query_one("#editor-actions").region
            text = screen_text(app, *size)
            scrolls = body_widget.max_scroll_y > 0

    assert not scrolls, "short answers need no scrolling"
    assert foot.y == body.bottom, "nothing separates the answers from what follows them"
    assert panel.bottom - actions.bottom == gutter, "the panel ends at its buttons"
    assert panel.height < size[1], "a short panel does not take the whole terminal"
    assert _longest_blank_run(text, panel) <= 1


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("size", _SIZES)
async def test_the_header_result_line_is_the_panels_first_line(language: str, size: tuple[int, int]) -> None:
    with override_settings(cadrumo_output_language=language):
        editor = _editor(_assumed(), language, status_line=_STATUS)
        app = ScreenHostApp(editor)
        async with app.run_test(size=size) as pilot:
            await _settle(pilot)
            panel = editor.query_one("#editor-panel")
            status_widget = editor.query_one("#editor-status", Static)
            status = status_widget.region
            title = editor.query_one("#editor-title").region
            shown = str(status_widget.render())
            first_row = panel.region.y + panel.gutter.top

    assert shown == _STATUS
    assert status.y == first_row
    assert title.y == status.bottom


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["editable", "read_only"])
async def test_the_title_carries_the_strongest_weight(case: str) -> None:
    with override_settings(cadrumo_output_language="en"):
        editor = _editor(_assumed(), "en") if case == "editable" else _read_only(_sourced(), "en")
        app = ScreenHostApp(editor)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            title = editor.query_one("#editor-title")
            label = editor.query(".editor-block-label").first()
            foreground = Color.parse(app.theme_variables["foreground"])
            primary = Color.parse(app.theme_variables["primary"])

    assert title.styles.text_style.bold
    assert title.styles.color == foreground
    assert title.styles.color != primary
    assert label.styles.color != title.styles.color


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("size", _SIZES)
async def test_the_highlighted_button_keeps_and_goes_to_the_next_box(language: str, size: tuple[int, int]) -> None:
    with override_settings(cadrumo_output_language=language):
        editor = _editor(_assumed(), language)
        app = ScreenHostApp(editor)
        async with app.run_test(size=size) as pilot:
            await _settle(pilot)
            primary = [str(button.label) for button in editor.query(Button) if button.variant == "primary"]
            keep = editor.query_one("#editor-save", Button)
            keep_variant = keep.variant
            save_next = tr("tui.modelo.workbench.editor.save_next")
            await pilot.click("#editor-save-next")
            await _settle(pilot)

    decision = app.return_value
    assert primary == [save_next]
    assert keep_variant == "default"
    assert isinstance(decision, EditorDecision)
    assert decision.kind is WorkbenchChangeKind.SET
    assert decision.advance


@pytest.mark.asyncio
async def test_the_secondary_button_keeps_the_value_and_stays_on_the_box() -> None:
    with override_settings(cadrumo_output_language="en"):
        editor = _editor(_assumed(), "en")
        app = ScreenHostApp(editor)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            label = str(editor.query_one("#editor-save", Button).label)
            await pilot.click("#editor-save")
            await _settle(pilot)

    decision = app.return_value
    assert label == "Keep for review"
    assert isinstance(decision, EditorDecision)
    assert decision.value == Decimal("0.00")
    assert not decision.advance


@pytest.mark.asyncio
@pytest.mark.parametrize("size", _SIZES)
async def test_a_sourced_box_says_where_it_comes_from_what_it_affects_and_where_to_change_it(
    size: tuple[int, int],
) -> None:
    with override_settings(cadrumo_output_language="es"):
        editor = _read_only(_sourced(), "es", feeds=("[03]",))
        app = ScreenHostApp(editor)
        async with app.run_test(size=size) as pilot:
            await _settle(pilot)
            now = _text(editor, "#editor-now-text")
            where = _text(editor, "#editor-where-text")
            can_change = _text(editor, "#editor-can-change-text")
            affects = _text(editor, "#editor-affects-text")
            keys = _text(editor, "#editor-keys")
            inputs = editor.query(Input)
            buttons = _labels(editor)
            await pilot.press("enter")
            await _settle(pilot)
        area = tr("tui.destination.ledger")

    assert "De tus registros" in now
    assert where == "Registros de ingresos", "the answer names the source, not the kind of place the Now line names"
    assert can_change == f"Aquí no. Cámbialo en {area} y vuelve a calcular."
    assert affects == "[03]"
    assert keys == f"Teclas: a Abrir {area} · Esc Volver"
    assert not inputs
    assert buttons == ["Volver", f"Abrir {area}"]
    assert app.return_value is None, "Enter on the focused Back closes without a request"


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("size", _SIZES)
@pytest.mark.parametrize("how", ["key", "button"])
async def test_a_read_only_box_asks_to_open_the_area_that_owns_its_source(
    language: str, size: tuple[int, int], how: str
) -> None:
    with override_settings(cadrumo_output_language=language):
        editor = _read_only(_sourced(), language)
        app = ScreenHostApp(editor)
        async with app.run_test(size=size) as pilot:
            await _settle(pilot)
            if how == "key":
                await pilot.press("a")
            else:
                await pilot.click("#editor-open")
            await _settle(pilot)

    assert app.return_value == OpenSourceSurface(SourceSurface.LEDGER)


@pytest.mark.asyncio
async def test_a_box_no_area_owns_offers_nothing_to_open() -> None:
    field = _calculated()
    with override_settings(cadrumo_output_language="en"):
        editor = _read_only(field, "en")
        app = ScreenHostApp(editor)
        async with app.run_test(size=(80, 24)) as pilot:
            await _settle(pilot)
            buttons = _labels(editor)
            keys = editor.query("#editor-keys")
            await pilot.press("a")
            await _settle(pilot)
            still_open = app.screen is editor

    assert open_area_target(field) is None
    assert buttons == ["Back"]
    assert not keys
    assert still_open


@pytest.mark.asyncio
async def test_a_box_that_takes_a_value_offers_no_area_and_a_types_into_it() -> None:
    carried = form_field(
        "05",
        "Pagos fraccionados anteriores",
        ModeloFormOrigin.IMPORTED,
        Decimal("500.00"),
        editability=ModeloFormEditability.OVERRIDABLE_SOURCE,
        bindings=(fed_by("m130.anteriores", BindingSourceKind.PREVIOUS_FILING),),
    )
    with override_settings(cadrumo_output_language="en"):
        editor = _editor(carried, "en")
        app = ScreenHostApp(editor)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("a")
            await _settle(pilot)
            typed = editor.query_one("#editor-input", Input).value
            still_open = app.screen is editor

    assert editor.open_area is None
    assert typed == "a"
    assert still_open


@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_place_to_change_a_sourced_value_is_named_once_as_the_menu_names_it(language: str) -> None:
    with override_settings(cadrumo_output_language=language):
        text = can_change_text(_sourced(), OutputLanguage(language))
        area = tr("tui.destination.ledger")

    assert text.count(area) == 1
    assert "(" not in text


def test_where_it_comes_from_adds_the_kind_of_place_only_when_the_now_line_does_not_say_it() -> None:
    assumed_over_records = form_field(
        "02",
        "Gastos",
        ModeloFormOrigin.DEFAULT_TO_CONFIRM,
        Decimal("0.00"),
        bindings=(
            fed_by("m130.gastos", BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION),
            fed_by("m130.ingresos", BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION),
        ),
    ).model_copy(update={"source": ModeloFormValueSource(family=SourceFamily.RECORDS)})
    with override_settings(cadrumo_output_language="en"):
        imported = where_from_text(_sourced())
        assumed = where_from_text(assumed_over_records)
        expenses = tr(
            "flows.modelo_review.filter.option.binding_source.ledger_renta_gastos_pago_fraccionado_aggregation"
        )

    assert imported == "Income records"
    assert assumed == f"From your records\n{expenses} · Income records"


def test_where_it_comes_from_names_the_earlier_declarations_a_value_is_carried_from() -> None:
    carried = form_field(
        "05",
        "Pagos fraccionados anteriores",
        ModeloFormOrigin.IMPORTED,
        Decimal("500.00"),
        editability=ModeloFormEditability.OVERRIDABLE_SOURCE,
        bindings=(fed_by("m130.anteriores", BindingSourceKind.PREVIOUS_FILING),),
    ).model_copy(
        update={
            "source": ModeloFormValueSource(
                family=SourceFamily.EARLIER_FILINGS,
                earlier_filings=(ModeloFormEarlierFiling(modelo="130", period=Period.from_year_and_code(2025, "4T")),),
            )
        }
    )
    period = Period.from_year_and_code(2025, "4T")
    with override_settings(cadrumo_output_language="es"):
        where = where_from_text(carried)
        filing = tr(
            "tui.modelo.workbench.origin_source.imported.named_filing", modelo="130", period=period_words(period)
        )

    assert where == f"Declaración anterior\n{filing}"
    assert "130" in filing


def test_a_value_from_aeat_data_names_only_the_aeat_data() -> None:
    from_draft = _sourced().model_copy(
        update={
            "source": ModeloFormValueSource(
                family=SourceFamily.AEAT_DRAFT,
                source_kind=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
            )
        }
    )
    with override_settings(cadrumo_output_language="en"):
        where = where_from_text(from_draft)

    assert where == "From AEAT data"


def test_a_recorded_declaration_makes_even_a_typed_box_read_only() -> None:
    with override_settings(cadrumo_output_language="en"):
        typed = read_only_reason(_assumed(), OutputLanguage.EN)
        recorded = read_only_reason(_assumed(), OutputLanguage.EN, recorded=True)
        correction = tr("tui.modelo.workbench.editor.can_change.recorded")

    assert typed is None
    # A filed declaration's answer says how to change it: by starting a correction.
    assert recorded == correction
    assert "correction" in recorded


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
            disabled = [editor.query_one(button, Button).disabled for button in ("#editor-save", "#editor-save-next")]
            readback_shown = editor.query_one("#editor-readback").display
            await pilot.press("enter")
            await _settle(pilot)
            still_open = app.screen is editor

    assert value == ""
    assert all(disabled)
    assert not readback_shown, "an empty read-back takes no row"
    assert still_open


@pytest.mark.asyncio
@pytest.mark.parametrize("language", _LANGUAGES)
@pytest.mark.parametrize("size", _SIZES)
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
        editor = _editor(
            carried,
            language,
            can_clear=True,
            can_restore=True,
            feeds=("[07]", "[12]", "[19]"),
            status_line=_STATUS,
        )
        app = ScreenHostApp(editor)
        async with app.run_test(size=size) as pilot:
            await _settle(pilot)
            panel = editor.query_one("#editor-panel").region
            widgets = [editor.query_one("#editor-input", Input), *editor.query(Button)]
            regions = [widget.region for widget in widgets]
            labels = _labels(editor)
            body = editor.query_one("#editor-body")
            scrolls = body.max_scroll_y > 0
            shown = body.region.height

    assert len(labels) == 5
    for region in regions:
        assert region.width > 0
        assert region.height > 0
        assert region.x >= panel.x
        assert region.y >= panel.y
        assert region.right <= panel.right
        assert region.bottom <= panel.bottom
        assert region.right <= size[0]
        assert region.bottom <= size[1]
    assert shown > 0, "some of the answers stay in view"
    if size == (80, 24):
        assert scrolls, "the long answers must scroll rather than push the buttons away"


class _RowHarness(App[None]):
    def __init__(self, entry: CasillaListEntry) -> None:
        super().__init__()
        self._entry = entry

    @override
    def compose(self) -> ComposeResult:
        yield CasillaList((self._entry,), language=OutputLanguage.EN)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("origin", "value", "filed_words", "asking"),
    [
        (
            ModeloFormOrigin.DEFAULT_TO_CONFIRM,
            Decimal("0.00"),
            "Assumed, nobody entered it",
            "◐ Assumed, please confirm",
        ),
        (ModeloFormOrigin.NEEDS_INPUT, None, "Empty, nobody filled it in", "! Needs your input"),
    ],
)
async def test_on_a_filed_declaration_the_panel_and_the_row_say_what_a_box_holds_without_asking(
    origin: ModeloFormOrigin, value: Decimal | None, filed_words: str, asking: str
) -> None:
    field = form_field("06", "Retenciones e ingresos a cuenta", origin, value)
    with override_settings(cadrumo_output_language="en"):
        reason = read_only_reason(field, OutputLanguage.EN, recorded=True)
        filed = CasillaEditorScreen(
            field, parse=FakeActions().parse, language=OutputLanguage.EN, read_only_reason=reason, recorded=True
        )
        async with ScreenHostApp(filed).run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            filed_now = _text(filed, "#editor-now-text")
        still_open = _editor(field, "en")
        async with ScreenHostApp(still_open).run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            open_now = _text(still_open, "#editor-now-text")
        rows: dict[bool, str] = {}
        for recorded in (False, True):
            app = _RowHarness(CasillaListEntry(field, recorded=recorded))
            async with app.run_test(size=(140, 10)) as pilot:
                await pilot.pause()
                widget = app.query_one(CasillaList)
                rows[recorded] = next(
                    text for y in range(widget.size.height) if "[06]" in (text := widget.render_line(y).text)
                )

    # The same declaration not yet filed still asks, so the filed words are the filing's doing.
    assert open_now.endswith(asking)
    assert asking in rows[False]
    # A box holding nothing says so once, in its words; one holding a value states it first.
    assert filed_now == filed_words if value is None else filed_now.endswith(f" · {filed_words}")
    assert filed_words in rows[True]
    for said in (filed_now, rows[True]):
        assert asking.split(" ", 1)[1] not in said
        assert asking[0] not in said.replace("[06]", "")
