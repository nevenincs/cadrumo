"""Every symbol is one key away: ``?`` names the ones on screen, twice opens them all, and nothing drifts.

Driven through the workbench over the synthetic form: the first ``?`` widens
the help band and its first line names exactly the symbols drawn on the page,
the header and the navigator, with how often each appears; the second opens
"Symbols and keys" under the header, which stays in view, listing every mark
the workbench can draw; Escape or a third ``?`` closes it. The first time the
workbench opens in a session the notice line says where to look, once. The
footer keeps help and the next step in reach at 80, 120 and 200 columns.
"""

from __future__ import annotations

import pytest
from textual.pilot import Pilot
from textual.widgets import Footer, OptionList, Static

from ......core.config import override_settings
from ....components.host import ScreenHostApp
from ..casilla_list import CasillaList
from ..legend import LEGEND_LOCALE_KEYS, legend_glyphs
from ..screen import ModeloWorkbenchScreen
from ..vocabulary import WORKBENCH_MARKS
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WIDE = (140, 40)
_SEPARATOR = " · "
# Glyphs that are also ordinary letters or punctuation in the words around them,
# so their presence in rendered text proves nothing; the fixture draws none.
_AMBIGUOUS = frozenset({"i", "-"})


async def _settle(pilot: Pilot[None], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


def _screen_text(screen: ModeloWorkbenchScreen) -> str:
    parts = [
        str(screen.query_one(selector, Static).render())
        for selector in ("#wb-header", "#wb-deadline", "#wb-result", "#wb-stale", "#wb-chips", "#wb-stepper")
    ]
    casilla_list = screen.query_one(CasillaList)
    parts.extend(casilla_list.render_line(y).text for y in range(casilla_list.size.height))
    navigator = screen.query_one("#wb-sections", OptionList)
    parts.extend(str(navigator.get_option_at_index(index).prompt) for index in range(navigator.option_count))
    return "\n".join(parts)


def _listed(line: str) -> dict[str, int | None]:
    """Each glyph the line names, with its count of boxes, or ``None`` for a mark listed by name alone."""
    _, _, entries = line.partition(": ")
    listed: dict[str, int | None] = {}
    for entry in entries.split(_SEPARATOR):
        glyph, _, rest = entry.partition(" ")
        last = rest.rsplit(" ", 1)[-1]
        listed[glyph] = int(last) if last.isdigit() else None
    return listed


def test_the_legend_explains_every_mark_the_workbench_draws_once() -> None:
    explained = [entry.mark.glyph for group in LEGEND_LOCALE_KEYS for entry in group.entries]

    assert len(explained) == len(set(explained))
    assert legend_glyphs() == {mark.glyph for mark in WORKBENCH_MARKS}


@pytest.mark.asyncio
async def test_the_first_question_mark_names_exactly_the_symbols_on_screen() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_WIDE) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            await pilot.press(*"300,5", "enter")
            await _settle(pilot)
            await pilot.press("question_mark")
            await _settle(pilot)
            band = str(screen.query_one("#wb-help", Static).render()).splitlines()
            expanded = screen.query_one("#wb-help", Static).has_class("-expanded")
            on_screen = _screen_text(screen)
            app.exit(None)

    listed = _listed(band[0])
    drawn = {mark.glyph for mark in WORKBENCH_MARKS if mark.glyph not in _AMBIGUOUS and mark.glyph in on_screen}
    assert expanded
    assert band[0].startswith("On this screen: ")
    assert band[1] == "Press ? again for all symbols and keys."
    assert set(listed) - _AMBIGUOUS == drawn
    assert not set(listed) & _AMBIGUOUS
    assert listed["Δ"] == 1, "a box's state is counted once per box"
    assert listed["◷"] is None, "a mark that is not a box's state is named without a count"
    assert listed["▸"] is None


@pytest.mark.asyncio
async def test_the_second_opens_every_symbol_under_the_header_and_escape_or_a_third_closes_it() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_WIDE) as pilot:
            await _settle(pilot)
            await pilot.press("question_mark", "question_mark")
            await _settle(pilot)
            panel = str(screen.query_one("#wb-legend-text", Static).render())
            open_state = (
                screen.query_one("#wb-legend").display,
                screen.query_one("#wb-body").display,
                screen.query_one("#wb-result", Static).display,
            )
            await pilot.press("escape")
            await _settle(pilot)
            after_escape = (screen.query_one("#wb-legend").display, app.screen is screen)
            await pilot.press("question_mark", "question_mark", "question_mark")
            await _settle(pilot)
            after_third = (screen.query_one("#wb-legend").display, screen.query_one("#wb-body").display)
            app.exit(None)

    assert open_state == (True, False, True)
    assert panel.startswith("Symbols and keys   esc Close")
    assert "── On this screen ──" in panel
    for mark in WORKBENCH_MARKS:
        assert f" {mark.glyph} " in panel
    assert "◐ Assumed, please confirm: Cadrumo holds a value here that nobody entered." in panel
    assert after_escape == (False, True)
    assert after_third == (False, True)


@pytest.mark.asyncio
async def test_the_first_open_notice_is_said_once_and_goes_at_the_first_key() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_WIDE) as pilot:
            await _settle(pilot)
            first = str(screen.query_one("#wb-notice", Static).render())
            await pilot.press("down")
            await _settle(pilot)
            after_key = str(screen.query_one("#wb-notice", Static).render())
            again = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
            await app.push_screen(again)
            await _settle(pilot)
            second = str(again.query_one("#wb-notice", Static).render())
            app.exit(None)

    assert first == "New here? Press ? to see what each symbol means."
    assert after_key == ""
    assert second == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [80, 120, 200])
async def test_the_footer_keeps_help_and_the_next_step_in_reach(width: int) -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(width, 30)) as pilot:
            await _settle(pilot)
            footer = screen.query_one(Footer)
            keys = " ".join(str(child.render()) for child in footer.query("*"))
            edge = max(child.region.right for child in footer.query("*"))
            app.exit(None)

    assert "? Help" in keys
    assert "f8 Next step" in keys
    assert edge <= width


@pytest.mark.asyncio
async def test_on_a_short_terminal_the_greeting_and_an_empty_result_line_give_their_lines_to_the_boxes() -> None:
    # Calculated, with no settlement box, nothing exported and nothing to count, as a Modelo 349 is.
    form = synthetic_form(needs_input=False, calculated=True).model_copy(
        update={"result": None, "result_addresses": (), "issues": (), "verification": None}
    )
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await _settle(pilot)
            notice = screen.query_one("#wb-notice", Static)
            notice_shown, notice_height = notice.display, notice.region.height
            outcome = screen.query_one("#wb-outcome")
            outcome_shown, outcome_height = outcome.display, outcome.region.height
            app.exit(None)

    assert not notice_shown and notice_height == 0, "a short terminal is not greeted on the notice line"
    assert not outcome_shown and outcome_height == 0, "a line with no result, file or count takes no row"
