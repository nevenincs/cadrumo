"""The filter cycles through every way of narrowing a page, is always named, and an empty page says where to go.

Driven through the real workbench over the synthetic declaration: ``f`` steps
through every filter and back to all boxes, the page line naming each one; a
page the filter leaves empty says so and names the next page that has
something; and below 110 columns, where the page line is hidden, the crumb
names a filter that hides something and an order other than the form's.
"""

from __future__ import annotations

import pytest
from textual.pilot import Pilot
from textual.widgets import Static

from ......core.config import override_settings
from ......core.i18n.render import tr
from ....components.host import ScreenHostApp
from ..page_items import WorkbenchFilter
from ..screen import ModeloWorkbenchScreen
from ..sorting import SORT_LOCALE_KEYS
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


async def _settle(pilot: Pilot[None], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


def _filter_words(item: WorkbenchFilter) -> str:
    return tr(f"tui.modelo.workbench.filter.{item.value}", locale="en")


@pytest.mark.asyncio
async def test_f_steps_through_every_filter_naming_each_on_the_page_line() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=synthetic_form(needs_input=False)), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            lines = [str(screen.query_one("#wb-page", Static).render())]
            for _ in WorkbenchFilter:
                await pilot.press("f")
                await _settle(pilot)
                lines.append(str(screen.query_one("#wb-page", Static).render()))
            app.exit(None)

    named = [next((item for item in WorkbenchFilter if _filter_words(item) in line), None) for line in lines]
    assert named == [*WorkbenchFilter, WorkbenchFilter.ALL]


@pytest.mark.asyncio
async def test_a_page_the_filter_empties_says_so_and_names_the_next_page_with_something() -> None:
    form = synthetic_form(needs_input=True)
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            # It opens on the result page, which holds nothing the filer typed; the first page holds box 07.
            await pilot.press("f", "f")
            await _settle(pilot)
            empty = str(screen.query_one("#wb-page", Static).render())
            await pilot.press("left_square_bracket")
            await _settle(pilot)
            listed = str(screen.query_one("#wb-page", Static).render())
            app.exit(None)

    first_page = form.pages[0].heading.text
    assert _filter_words(WorkbenchFilter.MINE) in empty
    assert tr("tui.modelo.workbench.filter.empty_next", locale="en", page=first_page) in empty
    assert tr("tui.modelo.workbench.filter.empty", locale="en") not in listed


@pytest.mark.asyncio
async def test_below_110_columns_the_crumb_names_a_filter_that_hides_something_and_the_order() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=synthetic_form(needs_input=False)), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(90, 30)) as pilot:
            await _settle(pilot)
            default = str(screen.query_one("#wb-crumb", Static).render())
            await pilot.press("f", "f")
            await _settle(pilot)
            filtered = str(screen.query_one("#wb-crumb", Static).render())
            await pilot.press("o")
            await _settle(pilot)
            sorted_crumb = str(screen.query_one("#wb-crumb", Static).render())
            order = screen.box_order
            app.exit(None)

    assert _filter_words(WorkbenchFilter.ALL) not in default
    assert _filter_words(WorkbenchFilter.MINE) in filtered
    assert _filter_words(WorkbenchFilter.MINE) in sorted_crumb
    assert tr(SORT_LOCALE_KEYS[order], locale="en") in sorted_crumb
