"""Nothing assumed reaches the AEAT, and what blocks filing reads the same everywhere it is counted and drawn.

Driven through the real workbench screen over the synthetic declaration. The
same verified declaration with one assumed value refuses the file for the AEAT
and recording the filing, says why and offers the value to confirm; with that
value entered instead, both proceed. The count beside "resolve what blocks
filing" is the header chip's, whatever else the check found. Every blocker
mark the header, the stepper and the review draw is in the theme's error
colour, in both appearances. With no result to show, the chips start where
the header's other lines start. The bulk-confirm tick reads as unticked until
the filer ticks it. The help band draws the blocker it names in the same colour.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from rich.cells import cell_len
from textual.color import Color
from textual.pilot import Pilot
from textual.widgets import Static

from ......application.modelo.work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormOrigin,
    ModeloWorkForm,
)
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ....components.dialogs import ConfirmScreen
from ....components.host import ScreenHostApp
from ....components.theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME
from ..bulk_confirm import BulkConfirmScreen, TickBox
from ..export import WorkbenchExportScreen
from ..header import attention_chips, blocking_count
from ..progress import NextAction, next_action_text, workbench_progress
from ..review import EditReviewScreen, ReviewNote
from ..screen import ModeloWorkbenchScreen
from ..vocabulary import BLOCKS_MARK, CHECK_MARK
from .declaration_states import with_findings
from .form_edits import replace_fields
from .workbench_fixture import FakeActions, FakeReader, form_field, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SIZE = (140, 40)
_WITHHOLDING = "06"


async def _settle[ResultT](pilot: Pilot[ResultT], times: int = 4) -> None:
    for _ in range(times):
        await pilot.pause()


def _notice(screen: ModeloWorkbenchScreen) -> str:
    return str(screen.query_one("#wb-notice", Static).render())


def _declaration(*, assumed: bool) -> ModeloWorkForm:
    """The synthetic declaration with box 06 typed by hand: assumed (nobody entered it) or entered by the filer."""
    form = synthetic_form(needs_input=False)
    origin = ModeloFormOrigin.DEFAULT_TO_CONFIRM if assumed else ModeloFormOrigin.ENTERED
    manual = form_field(_WITHHOLDING, "Retenciones e ingresos a cuenta", origin, Decimal("300.00"))
    form = replace_fields(form, {_WITHHOLDING: {"origin": manual.origin, "bindings": manual.bindings}})
    counts = form.counts.model_copy(
        update={
            "default_to_confirm": int(assumed),
            "entered": form.counts.entered - int(assumed),
        }
    )
    return form.model_copy(update={"counts": counts})


@pytest.mark.asyncio
@pytest.mark.parametrize("assumed", [True, False], ids=["one-assumed", "none-assumed"])
async def test_an_assumed_value_withholds_the_file_and_the_recording_until_confirmed(assumed: bool) -> None:
    actions = FakeActions()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_declaration(assumed=assumed), verified=True), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settle(pilot)
            await pilot.press("e")
            await _settle(pilot)
            after_export = app.screen
            export_notice = _notice(screen)
            offered = after_export.fields if isinstance(after_export, BulkConfirmScreen) else ()
            await pilot.press("escape")
            await _settle(pilot)
            # Recording the filing is F8 on a declaration that is ready for it, and only then.
            await pilot.press("f8")
            await _settle(pilot)
            after_f8 = app.screen
            if isinstance(after_f8, ConfirmScreen):
                await pilot.click("#btn-confirm-accept")
                await _settle(pilot, 6)
            app.exit(None)

    withheld = tr("tui.modelo.workbench.export.confirm_first", locale="en", count=1)
    if assumed:
        assert isinstance(after_export, BulkConfirmScreen), "the confirm step is offered in place of the export"
        assert [field.address for field in offered] == [ModeloFormCasillaAddressV1(casilla_id=_WITHHOLDING)]
        assert export_notice == withheld
        assert isinstance(after_f8, BulkConfirmScreen), "F8 goes to the confirm step, not to recording"
        assert actions.exports == []
        assert "file" not in actions.requested
    else:
        assert isinstance(after_export, WorkbenchExportScreen)
        assert export_notice != withheld
        assert isinstance(after_f8, ConfirmScreen), "F8 asks before recording the filing"
        assert actions.requested == ["file"]


def test_the_withheld_count_is_the_assumed_values_on_pages_that_apply() -> None:
    held = workbench_progress(_declaration(assumed=True), staged=0, verified=True, filed=False)
    clear = workbench_progress(_declaration(assumed=False), staged=0, verified=True, filed=False)
    filed = workbench_progress(_declaration(assumed=True), staged=0, verified=True, filed=True)

    assert held.filing_withheld and held.assumed == 1
    assert not clear.filing_withheld and clear.next_action is NextAction.EXPORT
    assert not filed.filing_withheld


def _blocked() -> ModeloWorkForm:
    """One blocking finding, two worth checking: the chip counts one thing that blocks filing."""
    return with_findings(synthetic_form(needs_input=False), blocking=(_WITHHOLDING,), worth_checking=("07", None))


def test_resolving_counts_what_blocks_filing_as_the_header_chip_does() -> None:
    form = _blocked()
    progress = workbench_progress(form, staged=0, verified=False, filed=False)
    with override_settings(cadrumo_output_language="en"):
        chips = {chip.level.value: chip.count for chip in attention_chips(form, recorded=False)}
        line = next_action_text(progress, OutputLanguage.EN)

    assert len(form.issues) == 3
    assert progress.next_action is NextAction.RESOLVE
    assert progress.count == chips["blocks"] == blocking_count(form) == 1
    assert line == "Resolve what blocks filing (to do: 1)"


def _glyph_colours(widget: Static, glyph: str) -> list[Color]:
    colours: list[Color] = []
    for y in range(widget.region.height):
        for segment in widget.render_line(y):
            if glyph in segment.text and segment.style is not None and segment.style.color is not None:
                colours.append(Color.from_rich_color(segment.style.color))
    return colours


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", [CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME])
async def test_every_blocker_mark_the_header_and_stepper_draw_is_in_the_error_colour(theme: str) -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_blocked()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            app.theme = theme
            await _settle(pilot)
            error = Color.parse(app.theme_variables["error"])
            foreground = Color.parse(app.theme_variables["foreground"])
            chips = _glyph_colours(screen.query_one("#wb-chips", Static), BLOCKS_MARK.glyph)
            stepper = _glyph_colours(screen.query_one("#wb-stepper", Static), BLOCKS_MARK.glyph)
            check = _glyph_colours(screen.query_one("#wb-chips", Static), CHECK_MARK.glyph)
            # The larger help band names the symbols on screen, the blocker's among them.
            await pilot.press("question_mark")
            await _settle(pilot)
            named = _glyph_colours(screen.query_one("#wb-help", Static), BLOCKS_MARK.glyph)
            app.exit(None)

    assert chips and stepper and named, "the header, the stepper and the help band each draw a blocker mark"
    assert all(colour == error for colour in (*chips, *stepper, *named))
    assert check and all(colour != error for colour in check), "only what blocks is drawn in the error colour"
    assert error != foreground


@pytest.mark.asyncio
async def test_a_review_finding_that_blocks_is_marked_from_the_registry_in_the_error_colour() -> None:
    notes = (
        ReviewNote(box="06", message="Blocks the changes.", blocking=True),
        ReviewNote(box=None, message="Worth checking.", blocking=False),
    )
    with override_settings(cadrumo_output_language="en"):
        review = EditReviewScreen((), notes=notes)
        app = ScreenHostApp(review)
        async with app.run_test(size=_SIZE) as pilot:
            await _settle(pilot)
            findings = review.query_one("#review-findings", Static)
            text = str(findings.render())
            error = Color.parse(app.theme_variables["error"])
            blocks = _glyph_colours(findings, BLOCKS_MARK.glyph)
            check = _glyph_colours(findings, CHECK_MARK.glyph)
            app.exit(None)

    assert f"{BLOCKS_MARK.glyph} [06] Blocks the changes." in text
    assert f"{CHECK_MARK.glyph} Worth checking." in text
    assert blocks and all(colour == error for colour in blocks)
    assert check and all(colour != error for colour in check)


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [80, 140])
async def test_with_no_result_the_chips_start_where_the_other_header_lines_start(width: int) -> None:
    form = _blocked().model_copy(update={"result_addresses": (), "result": None})
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(width, 30)) as pilot:
            await _settle(pilot)
            chips = screen.query_one("#wb-chips", Static)
            chips_x = chips.content_region.x
            stepper_x = screen.query_one("#wb-stepper", Static).content_region.x
            header_x = screen.query_one("#wb-header", Static).content_region.x
            shown = str(chips.render())
            result_shown = screen.query_one("#wb-result", Static).display
            app.exit(None)

    assert not result_shown
    assert shown.startswith(f"{BLOCKS_MARK.glyph} blocking: 1")
    assert chips_x == stepper_x == header_x


@pytest.mark.asyncio
async def test_the_bulk_confirm_tick_reads_unticked_until_the_filer_ticks_it() -> None:
    fields = (form_field(_WITHHOLDING, "Casilla manual", ModeloFormOrigin.DEFAULT_TO_CONFIRM, Decimal("300.00")),)
    with override_settings(cadrumo_output_language="en"):
        dialog = BulkConfirmScreen(fields)
        app = ScreenHostApp(dialog)
        async with app.run_test(size=(80, 24)) as pilot:
            await _settle(pilot)
            tick = dialog.query_one("#bulk-tick", TickBox)
            unticked = str(tick.render())
            await pilot.click("#bulk-tick")
            await _settle(pilot)
            ticked = str(tick.render())
            value = tick.value
            app.exit(None)

    label = tr("tui.modelo.workbench.bulk_confirm.tick", locale="en")
    assert unticked.startswith("[ ]") and label in unticked
    assert "✓" not in unticked and "X" not in unticked
    assert value
    assert ticked.startswith("[✓]")
    assert cell_len(ticked) == cell_len(unticked)
