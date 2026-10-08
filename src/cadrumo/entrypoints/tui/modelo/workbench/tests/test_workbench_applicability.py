"""A page that does not apply this period asks nothing, and a heading printed twice is listed once.

The read model states per page whether it applies. A page stated not to apply
is dimmed, says so in the period's own words, starts closed and never counts
as to do: not in the navigator, not in the header's chips and not on the
journey. A page that only may not apply is counted like any other, so nothing
is set aside on a guess. A layout that prints two parts of one page under one
heading is listed under that heading once, with both parts' counts.
"""

from __future__ import annotations

import pytest
from rich.text import Text
from textual.pilot import Pilot
from textual.widgets import OptionList, Static

from ......core.config import override_settings
from ......core.i18n.render import tr
from ......core.period import Period
from ....components.host import ScreenHostApp
from ..casilla_list import CasillaList
from ..header import ChipLevel, attention_chips
from ..navigator import NavigatorState, checked_boxes, inapplicable_pages, navigator_rows, presented_form
from ..page_items import workbench_pages
from ..progress import NextAction, workbench_progress
from ..screen import ModeloWorkbenchScreen
from ..wording import does_not_apply_text
from .sectioned_form import LAST_QUARTER_PAGE, sectioned_form
from .workbench_fixture import FakeActions, FakeReader

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_NOT_THIS_QUARTER = "Does not apply this quarter"
_LOCALES = ("es", "en", "ca", "hu")


async def _settle(pilot: Pilot[None], times: int = 4) -> None:
    for _ in range(times):
        await pilot.pause()


def _rows(*, last_quarter_applies: bool | None, current: int = 0) -> tuple[Text, ...]:
    form = sectioned_form(last_quarter_applies=last_quarter_applies)
    rows = navigator_rows(
        workbench_pages(presented_form(form)),
        current=current,
        state=NavigatorState(),
        checked=checked_boxes(form),
        width=60,
        show_attention=True,
        inapplicable=inapplicable_pages(form),
        not_applying=does_not_apply_text(form.period),
    )
    return tuple(row.prompt for row in rows)


def _dimmed(prompt: Text) -> bool:
    return any(span.style == "dim" for span in prompt.spans)


def test_a_page_that_does_not_apply_is_dimmed_closed_and_counts_nothing_even_under_the_cursor() -> None:
    with override_settings(cadrumo_output_language="en"):
        prompts = _rows(last_quarter_applies=False, current=1)

    page = next(prompt for prompt in prompts if "Solo último periodo" in prompt.plain)
    assert page.plain.endswith(_NOT_THIS_QUARTER)
    assert "!" not in page.plain
    assert "◐" not in page.plain
    assert _dimmed(page)
    assert not any("Exonerados" in prompt.plain for prompt in prompts), "a page that does not apply starts closed"


def test_a_page_that_only_may_not_apply_is_counted_like_any_other() -> None:
    with override_settings(cadrumo_output_language="en"):
        prompts = _rows(last_quarter_applies=None)

    page = next(prompt for prompt in prompts if "Solo último periodo" in prompt.plain)
    assert _NOT_THIS_QUARTER not in page.plain
    assert "!1" in page.plain
    assert "◐1" in page.plain
    assert any("Exonerados" in prompt.plain for prompt in prompts), "a page with something to do starts open"


def test_what_a_page_that_does_not_apply_holds_is_never_to_do_in_the_header_or_the_journey() -> None:
    set_aside = sectioned_form(last_quarter_applies=False)
    undecided = sectioned_form(last_quarter_applies=None)

    chips = {chip.level: chip.count for chip in attention_chips(set_aside, recorded=False)}
    progress = workbench_progress(set_aside, staged=0, verified=False, filed=False)
    undecided_chips = {chip.level: chip.count for chip in attention_chips(undecided, recorded=False)}
    undecided_progress = workbench_progress(undecided, staged=0, verified=False, filed=False)

    assert chips == {ChipLevel.CONFIRM: 4}
    assert (progress.next_action, progress.count) == (NextAction.CONFIRM, 4)
    assert undecided_chips == {ChipLevel.MISSING: 1, ChipLevel.CONFIRM: 5}
    assert (undecided_progress.next_action, undecided_progress.count) == (NextAction.FILL, 1)


def test_a_heading_the_layout_prints_twice_is_listed_once_with_both_parts_counted() -> None:
    with override_settings(cadrumo_output_language="en"):
        prompts = [prompt.plain for prompt in _rows(last_quarter_applies=False)]

    results = [prompt for prompt in prompts if "Resultado" in prompt]
    corrective = [prompt for prompt in prompts if "Rectificativa" in prompt]
    assert len(results) == 1
    assert results[0].endswith("◐2")
    assert len(corrective) == 1


@pytest.mark.parametrize("language", _LOCALES)
def test_the_words_for_a_page_that_does_not_apply_name_the_period_in_every_language(language: str) -> None:
    periods = [Period.from_year_and_code(2026, code) for code in ("1T", "01", "0A")]
    with override_settings(cadrumo_output_language="en"):
        english = [does_not_apply_text(period) for period in periods]
    with override_settings(cadrumo_output_language=language):
        words = [does_not_apply_text(period) for period in periods]
        fallback = tr("tui.modelo.workbench.applicability.period")

    assert len(set(words)) == len(words), "a quarter, a month and a year are each named"
    assert all(text and not text.startswith("tui.") for text in (*words, fallback))
    assert all("—" not in text and "–" not in text for text in words)
    if language != "en":
        assert words != english
    else:
        assert words == [_NOT_THIS_QUARTER, "Does not apply this month", "Does not apply this year"]


def _navigator(screen: ModeloWorkbenchScreen) -> list[str]:
    navigator = screen.query_one("#wb-sections", OptionList)
    return [str(navigator.get_option_at_index(index).prompt) for index in range(navigator.option_count)]


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [80, 120, 200])
async def test_the_workbench_says_a_page_does_not_apply_and_never_lands_on_it(width: int) -> None:
    reader = FakeReader(form=sectioned_form(last_quarter_applies=False))
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(reader, actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(width, 30)) as pilot:
            await _settle(pilot)
            landed = screen.query_one(CasillaList).highlighted
            chips = str(screen.query_one("#wb-chips", Static).render())
            navigator = _navigator(screen) if width >= 110 else []
            await pilot.press("n", "n", "n")
            await _settle(pilot)
            after_next = screen.query_one(CasillaList).highlighted
            await pilot.press("left_square_bracket")
            await _settle(pilot)
            title = str(screen.query_one("#wb-page", Static).render())
            crumb = str(screen.query_one("#wb-crumb", Static).render())
            on_page = screen.pages_shown[1].id
            app.exit(None)

    assert on_page == LAST_QUARTER_PAGE
    assert landed is not None and landed.field.box == "05"
    assert "!" not in chips
    assert _NOT_THIS_QUARTER in title
    if width >= 110:
        assert any(row.endswith(_NOT_THIS_QUARTER) for row in navigator)
        assert sum("Resultado" in row for row in navigator) == 1
    else:
        assert crumb.endswith(_NOT_THIS_QUARTER)
    assert after_next is not None and after_next.field.box == "20", "n passes over the page that does not apply"


@pytest.mark.asyncio
async def test_choosing_a_heading_printed_twice_goes_to_its_first_part() -> None:
    reader = FakeReader(form=sectioned_form(last_quarter_applies=False))
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(reader, actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            navigator = screen.query_one("#wb-sections", OptionList)
            index = next(position for position, row in enumerate(_navigator(screen)) if "Resultado" in row)
            navigator.focus()
            navigator.highlighted = index
            await pilot.press("enter")
            await _settle(pilot)
            cursor = screen.query_one(CasillaList).highlighted
            app.exit(None)

    assert cursor is not None and cursor.field.box == "07"
