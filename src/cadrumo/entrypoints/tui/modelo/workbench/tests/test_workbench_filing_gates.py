"""Nothing assumed reaches the AEAT, and what blocks filing reads the same everywhere it is counted and drawn.

Driven through the real workbench screen over the synthetic declaration. The
same verified declaration with one assumed value, one issue that blocks
filing or one calculation note that blocks it, refuses the file for the AEAT and recording the filing, says which
reason holds it and opens what resolves it; with neither, F8 creates the file,
and recording comes next once it exists. The count beside "resolve what blocks
filing" is the header chip's, whatever else the check found. Every blocker
mark the header, the stepper and the review draw is in the theme's error
colour, in both appearances. With no result to show, the chips start where
the header's other lines start. The bulk-confirm tick reads as unticked until
the filer ticks it. The help band draws the blocker it names in the same colour.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from rich.cells import cell_len
from textual.color import Color
from textual.pilot import Pilot
from textual.widgets import Static

from ......application.modelo.calculation_notes import CALCULATION_NOTE_ATTENTION
from ......application.modelo.work_form_models import (
    ModeloFormAttention,
    ModeloFormCalculationNote,
    ModeloFormCasillaAddressV1,
    ModeloFormExport,
    ModeloFormOrigin,
    ModeloWorkForm,
)
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......domain.modelos.verification_report import VerificationCompletenessStatus
from ....components.host import ScreenHostApp
from ....components.theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME
from ..bulk_confirm import BulkConfirmScreen, TickBox
from ..export import WorkbenchExportScreen
from ..header import attention_chips, blocking_count
from ..issues import IssueLevel, WorkbenchIssuesScreen, issue_lines
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


def _checked_with_a_blocker(form: ModeloWorkForm) -> ModeloWorkForm:
    """The form checked complete, yet with one blocking issue standing, as a calculation diagnostic stands."""
    blocked = with_findings(form, blocking=(_WITHHOLDING,))
    return blocked.model_copy(update={"verification": VerificationCompletenessStatus.COMPLETE})


def _with_a_blocking_note(form: ModeloWorkForm) -> ModeloWorkForm:
    """The form whose latest calculation noted an amount from the records that reached no box, which blocks filing."""
    note = ModeloFormCalculationNote(reason="unrouted_observation", attention=ModeloFormAttention.BLOCKS, durable=True)
    return form.model_copy(update={"calculation_notes": (note,)})


def _cause(name: str) -> ModeloWorkForm:
    """The same verified declaration, withheld by one assumed value, one blocking issue or note, or by nothing."""
    if name == "one-assumed":
        return _declaration(assumed=True)
    if name == "one-blocking":
        return _checked_with_a_blocker(_declaration(assumed=False))
    if name == "one-blocking-note":
        return _with_a_blocking_note(_declaration(assumed=False))
    return _declaration(assumed=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("cause", ["one-assumed", "one-blocking", "one-blocking-note", "nothing-withholds"])
async def test_the_file_and_the_recording_are_withheld_by_each_cause_and_say_which(cause: str) -> None:
    actions = FakeActions()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=_cause(cause), verified=True), actions=actions)
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
            # F8 runs the one action the next-action line names, and never passes what withholds the filing.
            await pilot.press("f8")
            await _settle(pilot)
            after_f8 = app.screen
            app.exit(None)

    assert actions.exports == []
    assert "file" not in actions.requested
    if cause == "one-assumed":
        assert isinstance(after_export, BulkConfirmScreen), "the confirm step is offered in place of the export"
        assert [field.address for field in offered] == [ModeloFormCasillaAddressV1(casilla_id=_WITHHOLDING)]
        assert export_notice == tr("tui.modelo.workbench.export.confirm_first", locale="en", count=1)
        assert isinstance(after_f8, BulkConfirmScreen), "F8 goes to the confirm step"
    elif cause in {"one-blocking", "one-blocking-note"}:
        assert isinstance(after_export, WorkbenchIssuesScreen), "what blocks filing is shown in place of the export"
        assert export_notice == tr("tui.modelo.workbench.export.resolve_first", locale="en", count=1)
        assert isinstance(after_f8, WorkbenchIssuesScreen), "F8 goes to what blocks filing"
    else:
        assert isinstance(after_export, WorkbenchExportScreen)
        assert isinstance(after_f8, WorkbenchExportScreen), "F8 creates the file, the one action the line names"


def _with_current_file(form: ModeloWorkForm) -> ModeloWorkForm:
    revision = form.calculation_revision_id
    assert revision is not None
    export = ModeloFormExport(
        exported_at=datetime(2026, 4, 2, tzinfo=UTC), calculation_revision_id=revision, current=True
    )
    return form.model_copy(update={"last_export": export})


def test_recording_comes_after_the_file_and_is_withheld_as_the_file_is() -> None:
    clear = _cause("nothing-withholds")
    file_first = workbench_progress(clear, staged=0, verified=True, filed=False)
    record_next = workbench_progress(_with_current_file(clear), staged=0, verified=True, filed=False)
    assumed = workbench_progress(_with_current_file(_cause("one-assumed")), staged=0, verified=True, filed=False)
    blocking = workbench_progress(_with_current_file(_cause("one-blocking")), staged=0, verified=True, filed=False)
    filed = workbench_progress(_cause("one-blocking"), staged=0, verified=True, filed=True)

    assert file_first.next_action is NextAction.EXPORT and not file_first.filing_withheld
    assert record_next.next_action is NextAction.RECORD_AFTER_FILE and not record_next.filing_withheld
    assert assumed.filing_withheld and assumed.assumed == 1 and assumed.next_action is NextAction.CONFIRM
    assert blocking.filing_withheld and blocking.blocking == 1 and blocking.next_action is NextAction.RESOLVE
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


@pytest.mark.parametrize("reason", ["m349_clave_inferred_from_category", "orphaned_override"])
def test_a_value_the_calculation_inferred_is_worth_checking_and_never_promised_a_confirmation(reason: str) -> None:
    """Nothing in the editor confirms a note, so no chip counts one to confirm while the next step is the file."""
    note = ModeloFormCalculationNote(reason=reason, attention=CALCULATION_NOTE_ATTENTION[reason])
    form = _declaration(assumed=False).model_copy(update={"calculation_notes": (note,)})
    with override_settings(cadrumo_output_language="en"):
        chips = {chip.level.value: chip.count for chip in attention_chips(form, recorded=False)}
        progress = workbench_progress(form, staged=0, verified=True, filed=False)
        lines = issue_lines(form)

    assert note.attention is ModeloFormAttention.CHECK
    assert "confirm" not in chips
    assert progress.next_action is NextAction.EXPORT
    assert [line.level for line in lines if line.from_calculation] == [IssueLevel.CHECK]
    assert blocking_count(form) == 0


def test_an_assumed_box_is_still_counted_to_confirm_and_offered_next() -> None:
    """Teeth for the rule above: the confirm chip and the confirm step still count what a filer can confirm."""
    form = _declaration(assumed=True)
    with override_settings(cadrumo_output_language="en"):
        chips = {chip.level.value: chip.count for chip in attention_chips(form, recorded=False)}
    progress = workbench_progress(form, staged=0, verified=True, filed=False)

    assert chips["confirm"] == 1
    assert progress.next_action is NextAction.CONFIRM and progress.count == 1
