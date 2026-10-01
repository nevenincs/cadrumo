"""The header states the result, the deadline and what needs the filer, in their words, at every width.

The result reads from the direction the read model declares, never from the
sign: a word and the magnitude when the direction is known, the plain word
"Result" and the signed amount when it is not, the words alone where no amount
is payable, and "not calculated yet" or "could not be calculated" when there is
no figure. Staged changes mark it out of date. The deadline reads in days,
"today" or "passed", its urgency reinforced by colour, and disappears once the
declaration is recorded as filed. Each attention level with anything in it has
a chip. On a terminal of 80, 120 or 200 columns the header never runs past the
edge, and never drops the result: the modelo's name goes first, then the box,
then the least urgent chips.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from rich.cells import cell_len
from textual.pilot import Pilot
from textual.widgets import Static

from ......application.modelo.work_form_models import ModeloFormOrigin, ModeloFormResultDirection, ModeloWorkForm
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......core.result_disposition import ResultDisposition
from ....components.host import ScreenHostApp
from ..header import (
    ChipLevel,
    DeadlineTone,
    attention_chips,
    deadline_help,
    deadline_view,
    fit_result_line,
    result_view,
    status_line,
)
from ..screen import ModeloWorkbenchScreen
from .declaration_states import recorded_as_filed, with_deadline, with_findings, with_result
from .form_edits import replace_fields
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_EN = OutputLanguage.EN
_NBSP = "\u00a0"
_OWN = "Cadrumo's calculation. AEAT has not seen it."


async def _settle(pilot: Pilot[None], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


def _view(form: ModeloWorkForm, *, staged: int = 0, recorded: bool = False) -> tuple[str, tuple[str, ...]]:
    with override_settings(cadrumo_output_language="en"):
        view = result_view(form, _EN, staged=staged, recorded=recorded)
    assert view is not None
    return view.text, view.help


@pytest.mark.parametrize(
    ("direction", "value", "expected"),
    [
        (ModeloFormResultDirection.TO_PAY, Decimal("1300"), f"To pay  1,300.00{_NBSP}€  [19]"),
        (ModeloFormResultDirection.TO_REFUND, Decimal("-350"), f"To be refunded  350.00{_NBSP}€  [19]"),
        (ModeloFormResultDirection.TO_CARRY_FORWARD, Decimal("-80"), f"To carry forward  80.00{_NBSP}€  [19]"),
    ],
)
def test_a_known_direction_reads_as_its_word_and_the_magnitude(
    direction: ModeloFormResultDirection, value: Decimal, expected: str
) -> None:
    text, help_lines = _view(with_result(synthetic_form(), direction, value))

    assert text == expected
    assert help_lines[0] == _OWN
    signed = [line for line in help_lines if "without its sign" in line]
    if value < 0:
        with override_settings(cadrumo_output_language="en"):
            sign_help = tr(
                "tui.modelo.workbench.header.result.sign_help", box="19", value=f"−{expected.split('  ')[1]}"
            )
        assert signed == [sign_help]
    else:
        assert not signed


def test_an_unknown_direction_keeps_the_sign_under_the_plain_word_and_says_why() -> None:
    text, help_lines = _view(with_result(synthetic_form(), ModeloFormResultDirection.UNKNOWN, Decimal("-12.5")))

    assert text == f"Result  −12.50{_NBSP}€  [19]"
    assert "Cadrumo does not yet say whether this amount is to pay or to refund." in help_lines[1]


def test_a_nil_return_and_a_negative_result_nothing_carries_read_as_words_alone() -> None:
    nil, _ = _view(with_result(synthetic_form(), ModeloFormResultDirection.NIL, Decimal("0")))
    negative, help_lines = _view(with_result(synthetic_form(), ModeloFormResultDirection.NEGATIVE, Decimal("-40")))
    with override_settings(cadrumo_output_language="en"):
        words = tr("tui.modelo.workbench.header.result.negative")

    assert nil == "Result zero  [19]"
    assert negative == f"{words}  [19]"
    assert not [line for line in help_lines if "without its sign" in line]


def test_a_negative_instalment_to_deduct_later_names_its_amount_and_the_signed_box() -> None:
    form = with_result(
        synthetic_form(),
        ModeloFormResultDirection.TO_DEDUCT_LATER,
        Decimal("-100"),
        disposition=ResultDisposition.RESULTADO_A_DEDUCIR,
    )
    text, help_lines = _view(form)
    with override_settings(cadrumo_output_language="en"):
        words = tr("tui.modelo.workbench.header.result.negative_carried", amount=f"100.00{_NBSP}€")
        sign_help = tr("tui.modelo.workbench.header.result.sign_help", box="19", value=f"−100.00{_NBSP}€")

    assert text == f"{words}  [19]"
    assert "100.00" in words
    assert sign_help in help_lines


def test_a_refund_election_still_to_make_names_both_ways_and_the_magnitude() -> None:
    text, _ = _view(
        with_result(
            synthetic_form(),
            ModeloFormResultDirection.TO_CARRY_FORWARD,
            Decimal("-350"),
            disposition=ResultDisposition.COMPENSACION,
            election=True,
        )
    )

    assert text == f"To carry forward or to be refunded: you choose when you create the file  350.00{_NBSP}€  [19]"


def test_other_result_boxes_are_named_in_the_help() -> None:
    form = synthetic_form().model_copy(update={"result_addresses": ("19", "09")})

    _, help_lines = _view(with_result(form, ModeloFormResultDirection.TO_PAY, Decimal("1300")))

    assert f"Other result boxes on this form: [09] 210.00{_NBSP}€" in help_lines


def test_without_a_figure_the_result_says_so_and_a_failure_blocks() -> None:
    not_calculated, _ = _view(synthetic_form(calculated=False))
    failed_form = replace_fields(synthetic_form(), {"19": {"origin": ModeloFormOrigin.CALCULATION_FAILED}})
    failed, _ = _view(failed_form)

    assert not_calculated == "Result: not calculated yet [c]"
    assert failed == "Result: could not be calculated [i]"
    assert next(chip.level for chip in attention_chips(failed_form, recorded=False)) is ChipLevel.BLOCKS


def test_an_informative_declaration_states_no_result() -> None:
    form = synthetic_form().model_copy(update={"result_addresses": ()})

    with override_settings(cadrumo_output_language="en"):
        assert result_view(form, _EN, staged=0, recorded=False) is None


def test_staged_changes_mark_the_result_out_of_date_until_recorded() -> None:
    with override_settings(cadrumo_output_language="en"):
        staged = result_view(synthetic_form(), _EN, staged=2, recorded=False)
        recorded = result_view(recorded_as_filed(synthetic_form()), _EN, staged=2, recorded=True)

    assert staged is not None and staged.stale == "◷ out of date: changes not applied yet: 2 [R]"
    assert recorded is not None and recorded.stale is None


@pytest.mark.parametrize(
    ("days", "text", "tone"),
    [
        (21, "Deadline 29/04/2026 · days left: 21", DeadlineTone.NORMAL),
        (7, "Deadline 15/04/2026 · days left: 7", DeadlineTone.SOON),
        (4, "Deadline 12/04/2026 · days left: 4", DeadlineTone.SOON),
        (3, "Deadline 11/04/2026 · days left: 3", DeadlineTone.URGENT),
        (1, "Deadline 09/04/2026 · days left: 1", DeadlineTone.URGENT),
        (0, "Deadline today, 08/04/2026", DeadlineTone.URGENT),
    ],
)
def test_the_deadline_reads_in_days_and_grows_urgent(days: int, text: str, tone: DeadlineTone) -> None:
    with override_settings(cadrumo_output_language="en"):
        view = deadline_view(with_deadline(synthetic_form(), days_left=days), _EN, recorded=False)

    assert view is not None
    assert (view.text, view.tone) == (text, tone)
    assert "days left: 0" not in view.text


def test_a_passed_a_missing_a_moved_and_a_recorded_deadline() -> None:
    form = synthetic_form()
    with override_settings(cadrumo_output_language="en"):
        passed = deadline_view(with_deadline(form, days_late=3), _EN, recorded=False)
        missing = deadline_view(form, _EN, recorded=False)
        moved = deadline_help(with_deadline(form, days_left=10, shifted_by=2), _EN, recorded=False)
        unmoved = deadline_help(with_deadline(form, days_left=10), _EN, recorded=False)
        recorded = deadline_view(with_deadline(form, days_left=10), _EN, recorded=True)

    assert passed is not None and passed.text == "Deadline passed on 05/04/2026: filing now is late"
    assert passed.tone is DeadlineTone.URGENT
    assert missing is not None and missing.tone is DeadlineTone.MUTED
    assert missing.text == "No deadline on record for this period"
    assert moved == "The usual deadline is 16/04/2026. It moves to 18/04/2026 because of a weekend or holiday."
    assert unmoved is None
    assert recorded is None


def test_every_attention_level_with_something_in_it_has_a_chip_and_none_once_recorded() -> None:
    form = replace_fields(
        with_findings(synthetic_form(), blocking=("06", None), worth_checking=("01",)),
        {"07": {"origin": ModeloFormOrigin.DEFAULT_TO_CONFIRM}},
    )
    form = form.model_copy(update={"counts": form.counts.model_copy(update={"default_to_confirm": 1})})

    with override_settings(cadrumo_output_language="en"):
        chips = [chip.text for chip in attention_chips(form, recorded=False)]
    recorded = attention_chips(recorded_as_filed(form), recorded=True)

    assert chips == ["▲ blocking: 2", "! missing: 1", "◐ to confirm: 1", "◆ to check: 1"]
    assert recorded == ()


def test_a_narrow_line_keeps_the_result_and_what_blocks_taking_a_second_line_before_dropping_either() -> None:
    form = with_findings(synthetic_form(), blocking=("06",), worth_checking=("01",))
    with override_settings(cadrumo_output_language="en"):
        view = result_view(form, _EN, staged=3, recorded=False)
        chips = attention_chips(form, recorded=False)
        assert view is not None
        wide = fit_result_line(view, chips, 200)
        narrow = fit_result_line(view, chips, 76)
        tightest = fit_result_line(view, chips, 10)
        repeated = status_line(form, _EN, staged=3, recorded=False)
        assert repeated is not None
        whole = repeated.text()
        wide_text = wide.text()
        narrow_marks = cell_len(narrow.marks_text())

    assert wide.result.endswith("[19]") and len(wide.chips) == len(chips)
    assert narrow.stacked, "what blocks and what is missing do not fit beside the result, so they take a line"
    assert cell_len(narrow.result) <= 76 and narrow_marks <= 76
    assert [chip.level for chip in narrow.chips][:2] == [ChipLevel.BLOCKS, ChipLevel.MISSING]
    assert tightest.stacked and cell_len(tightest.result) <= 10 and tightest.chips == ()
    assert whole == wide_text


def _header(screen: ModeloWorkbenchScreen) -> dict[str, str]:
    return {
        selector: str(screen.query_one(selector, Static).render())
        for selector in ("#wb-header", "#wb-deadline", "#wb-result", "#wb-stale", "#wb-chips")
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [80, 100, 120, 200])
async def test_the_header_fits_every_width_and_keeps_the_result(width: int) -> None:
    form = with_deadline(
        with_findings(
            with_result(synthetic_form(), ModeloFormResultDirection.TO_PAY, Decimal("1300")),
            blocking=("06",),
            worth_checking=("01",),
        ),
        days_left=5,
    )
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(width, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            await pilot.press(*"5", "enter")
            await _settle(pilot)
            parts = _header(screen)
            deadline = screen.query_one("#wb-deadline", Static)
            soon = deadline.has_class("-soon")
            dimmed = screen.query_one("#wb-result", Static).has_class("-stale")
            rows = {
                selector: screen.query_one(selector, Static).size.height
                for selector in ("#wb-header", "#wb-deadline", "#wb-result")
            }
            identity_width = screen.query_one("#wb-header", Static).size.width + deadline.size.width
            app.exit(None)

    assert parts["#wb-result"].startswith(f"To pay  1,300.00{_NBSP}€")
    assert parts["#wb-deadline"] == "Deadline 13/04/2026 · days left: 5"
    assert soon
    assert parts["#wb-stale"] == "◷ out of date: changes not applied yet: 1 [R]"
    assert dimmed
    assert set(rows.values()) == {1}
    assert identity_width <= width
    if width >= 200:
        assert parts["#wb-result"].endswith("[19]")
    if width >= 120:
        assert parts["#wb-header"] == "Modelo 130 · IRPF instalment payment, direct assessment · 1st quarter 2026"
        assert "◆ to check: 1" in parts["#wb-chips"]
    else:
        assert parts["#wb-header"] == "Modelo 130 · 1st quarter 2026"
    assert "▲ blocking: 1" in parts["#wb-chips"] or width < 100


_HEADER_WIDGETS = ("#wb-header", "#wb-deadline", "#wb-result", "#wb-stale", "#wb-chips", "#wb-stepper", "#wb-next")


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [80, 100, 120])
async def test_a_choice_still_to_make_keeps_every_header_part_inside_the_screen(width: int) -> None:
    form = with_deadline(
        with_findings(
            with_result(
                synthetic_form(),
                ModeloFormResultDirection.TO_CARRY_FORWARD,
                Decimal("-45"),
                disposition=ResultDisposition.COMPENSACION,
                election=True,
            ),
            blocking=("06",),
            worth_checking=("01",),
        ),
        days_left=5,
    )
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(width, 30)) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            await pilot.press(*"5", "enter")
            await _settle(pilot)
            placed = {
                selector: (widget.region, str(widget.render()))
                for selector in _HEADER_WIDGETS
                if (widget := screen.query_one(selector, Static)).display and str(widget.render())
            }
            app.exit(None)

    result = placed["#wb-result"][1]
    assert f"45.00{_NBSP}€" in result
    assert "#wb-chips" in placed and "#wb-stale" in placed, "nothing the filer must see is dropped"
    for selector, (region, text) in placed.items():
        assert region.x >= 0 and region.right <= width, f"{selector} runs past the screen at {width}: {region}"
        assert region.height == 1, f"{selector} wraps at {width}"
        assert cell_len(text) <= region.width, f"{selector} is cut at {width}: {text!r}"


@pytest.mark.asyncio
async def test_the_header_is_refreshed_the_moment_a_change_is_staged() -> None:
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            before = _header(screen)["#wb-stale"]
            await pilot.press("enter")
            await _settle(pilot)
            await pilot.press(*"300,50", "enter")
            await _settle(pilot)
            after = _header(screen)["#wb-stale"]
            app.exit(None)

    assert before == ""
    assert after == "◷ desactualizado: cambios sin aplicar: 1 [R]"


def _colour(screen: ModeloWorkbenchScreen, selector: str, *, background: bool = False) -> str:
    styles = screen.query_one(selector).styles
    return (styles.background if background else styles.color).hex


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("direction", "late", "expected"),
    [
        (ModeloFormResultDirection.TO_PAY, False, "warning"),
        (ModeloFormResultDirection.TO_PAY, True, "error"),
        (ModeloFormResultDirection.TO_REFUND, True, "foreground"),
    ],
)
async def test_the_result_carries_the_emphasis_and_the_title_bar_is_a_neutral_surface(
    direction: ModeloFormResultDirection, late: bool, expected: str
) -> None:
    form = with_result(synthetic_form(needs_input=False), direction, Decimal("1300"))
    form = with_deadline(form, days_late=2) if late else with_deadline(form, days_left=20)
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            theme = app.theme_variables
            result = _colour(screen, "#wb-result")
            identity = _colour(screen, "#wb-identity", background=True)
            next_step = _colour(screen, "#wb-next")
            bold = screen.query_one("#wb-result").styles.text_style.bold
            app.exit(None)

    assert result.lower() == theme[expected].lower()
    assert bold
    assert identity.lower() != theme["primary"].lower(), "the title bar is not the loudest thing on screen"
    assert next_step.lower() != theme["primary"].lower()
    assert next_step.lower() != theme["accent"].lower()


@pytest.mark.parametrize("language", list(OutputLanguage))
@pytest.mark.parametrize("width", [76, 116])
def test_a_loss_carried_forward_keeps_its_words_whole_dropping_the_box_first(
    language: OutputLanguage, width: int
) -> None:
    form = with_findings(
        with_result(synthetic_form(calculated=True), ModeloFormResultDirection.TO_DEDUCT_LATER, Decimal("-100")),
        blocking=(None,),
        worth_checking=(None,),
    )
    with override_settings(cadrumo_output_language=language.value):
        view = result_view(form, language, staged=0, recorded=False)
        assert view is not None
        line = fit_result_line(view, attention_chips(form, recorded=False), width)
        widest = cell_len(line.marks_text() if line.stacked else line.text())

    assert line.result in (view.text, view.short_text), "the words that say the loss carries forward are never cut"
    assert ChipLevel.BLOCKS in [chip.level for chip in line.chips]
    assert cell_len(line.result) <= width and widest <= width
