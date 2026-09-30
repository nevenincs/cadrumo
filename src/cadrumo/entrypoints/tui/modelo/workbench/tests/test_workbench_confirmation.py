"""Confirming assumed values: one at a time or together, and never over a source.

The edit session stages a confirmation as the filer's own typed value, only on
a box the filer types into that holds an assumed value; a box a source fills
is refused, because keeping a value over it would replace the source. The
bulk dialog lists every box it would confirm with its value, confirms nothing
until the filer ticks that the values are right, and fits a small terminal. It
repeats the header's result line first, since it covers the header, under a
title in the strongest style.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual.color import Color
from textual.pilot import Pilot
from textual.widgets import Button, Checkbox, Static

from ......application.modelo.work_form_models import (
    ModeloFormBindingAddressV1,
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
)
from ......core.aggregation import BindingSourceKind
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ....components.host import ScreenHostApp
from ..bulk_confirm import BulkConfirmScreen
from ..ports import WorkbenchChangeKind
from ..session import Displacement, StageRefusal, WorkbenchEditSession
from .workbench_fixture import fed_by, form_field

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _assumed(box: str = "06", value: str = "0.00") -> ModeloFormField:
    return form_field(box, f"Casilla manual {box}", ModeloFormOrigin.DEFAULT_TO_CONFIRM, Decimal(value))


def _bound_assumed() -> ModeloFormField:
    return form_field(
        "05",
        "Pagos fraccionados anteriores",
        ModeloFormOrigin.DEFAULT_TO_CONFIRM,
        Decimal("500.00"),
        editability=ModeloFormEditability.OVERRIDABLE_SOURCE,
        bindings=(fed_by("m130.anteriores", BindingSourceKind.PREVIOUS_FILING),),
    )


def test_confirming_an_assumed_value_stages_it_as_the_filers_own_at_its_box() -> None:
    field = _assumed(value="12.50")
    session = WorkbenchEditSession(OutputLanguage.EN)

    refusal = session.stage_confirmation(field)

    assert refusal is None
    (change,) = session.changes
    assert change.kind is WorkbenchChangeKind.SET
    assert change.value == Decimal("12.50")
    assert change.displaces is Displacement.NOTHING
    assert change.text == change.previous_text
    (submitted,) = session.payload()
    assert submitted.address == ModeloFormCasillaAddressV1(casilla_id="06")


def test_a_bound_box_is_never_confirmed_because_that_would_override_its_source() -> None:
    session = WorkbenchEditSession(OutputLanguage.EN)
    binding_input = _assumed("07").model_copy(
        update={
            "address": ModeloFormBindingAddressV1(binding_id="m130.manual"),
            "box": None,
            "editability": ModeloFormEditability.EDITABLE_OVERRIDE,
        }
    )

    assert session.stage_confirmation(_bound_assumed()) is StageRefusal.NOT_EDITABLE
    assert session.stage_confirmation(binding_input) is StageRefusal.NOT_EDITABLE
    assert not session.dirty


def test_only_an_assumed_value_can_be_confirmed() -> None:
    session = WorkbenchEditSession(OutputLanguage.EN)
    entered = form_field("07", "Base imponible", ModeloFormOrigin.ENTERED, Decimal("1000.00"))
    missing = form_field("08", "Cuota", ModeloFormOrigin.NEEDS_INPUT)

    assert session.stage_confirmation(entered) is StageRefusal.NOTHING_TO_CONFIRM
    assert session.stage_confirmation(missing) is StageRefusal.NOTHING_TO_CONFIRM
    assert not session.dirty


def test_keeping_an_assumed_value_unchanged_in_the_editor_stages_a_confirmation() -> None:
    field = _assumed()
    session = WorkbenchEditSession(OutputLanguage.EN)

    assert session.stage_value(field, field.value, "0.00 €") is None
    (change,) = session.payload()
    assert change.kind is WorkbenchChangeKind.SET
    assert change.value == field.value


async def _settle(pilot: Pilot[tuple[ModeloFormField, ...] | None], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


@pytest.mark.asyncio
async def test_bulk_confirm_lists_every_box_and_confirms_nothing_until_ticked() -> None:
    fields = (_assumed("06", "0.00"), _assumed("08", "21.00"))
    with override_settings(cadrumo_output_language="es"):
        dialog = BulkConfirmScreen(fields)
        app = ScreenHostApp(dialog)
        async with app.run_test(size=(80, 24)) as pilot:
            await _settle(pilot)
            table = dialog.query_one("#bulk-table", Static)
            listed = "\n".join(line.text for line in table.render_lines(table.region.reset_offset))
            count = str(dialog.query_one("#bulk-count", Static).render())
            confirm = dialog.query_one("#bulk-confirm", Button)
            locked = confirm.disabled
            left_out = dialog.query("#bulk-left-out")
            dialog.query_one("#bulk-tick", Checkbox).value = True
            await _settle(pilot)
            unlocked = not confirm.disabled
            regions = [button.region for button in dialog.query(Button)]
            await pilot.click("#bulk-confirm")
            await _settle(pilot)

    assert "[06]" in listed
    assert "[08]" in listed
    assert "0,00" in listed
    assert "21,00" in listed
    assert count == "Casillas por confirmar: 2"
    assert locked
    assert unlocked
    assert not left_out
    for region in regions:
        assert region.width > 0
        assert region.right <= 80
        assert region.bottom <= 24
    assert app.return_value == fields


@pytest.mark.asyncio
async def test_bulk_confirm_leaves_out_a_bound_box_and_says_so() -> None:
    with override_settings(cadrumo_output_language="en"):
        dialog = BulkConfirmScreen((_assumed(), _bound_assumed()))
        app = ScreenHostApp(dialog)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            listed = dialog.fields
            note = str(dialog.query_one("#bulk-left-out", Static).render())
            await pilot.press("escape")
            await _settle(pilot)

    assert [field.box for field in listed] == ["06"]
    assert note.startswith("Boxes filled from a source are not listed")
    assert app.return_value is None


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("size", [(80, 24), (140, 40)])
async def test_bulk_confirm_repeats_the_header_result_line_first_and_titles_in_the_strongest_style(
    language: str, size: tuple[int, int]
) -> None:
    status_line = "Resultado: 1.300,00 € a ingresar"
    with override_settings(cadrumo_output_language=language):
        dialog = BulkConfirmScreen((_assumed(),), status_line=status_line)
        app = ScreenHostApp(dialog)
        async with app.run_test(size=size) as pilot:
            await _settle(pilot)
            panel = dialog.query_one("#bulk-panel")
            status_widget = dialog.query_one("#bulk-status", Static)
            shown = str(status_widget.render())
            status = status_widget.region
            title_widget = dialog.query_one("#bulk-title", Static)
            title = title_widget.region
            first_row = panel.region.y + panel.gutter.top
            bold = title_widget.styles.text_style.bold
            colour = title_widget.styles.color
            intro_colour = dialog.query_one("#bulk-intro").styles.color
            foreground = Color.parse(app.theme_variables["foreground"])
            regions = [button.region for button in dialog.query(Button)]

    assert shown == status_line
    assert status.y == first_row
    assert title.y == status.bottom
    assert bold
    assert colour == foreground
    assert intro_colour != colour
    for region in regions:
        assert region.width > 0
        assert region.right <= size[0]
        assert region.bottom <= size[1]


@pytest.mark.asyncio
async def test_bulk_confirm_without_a_result_line_starts_at_its_title() -> None:
    with override_settings(cadrumo_output_language="en"):
        dialog = BulkConfirmScreen((_assumed(),))
        app = ScreenHostApp(dialog)
        async with app.run_test(size=(80, 24)) as pilot:
            await _settle(pilot)
            status = dialog.query("#bulk-status")

    assert not status
