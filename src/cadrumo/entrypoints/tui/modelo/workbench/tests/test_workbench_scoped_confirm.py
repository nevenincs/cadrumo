"""Assumed values are confirmed a section at a time, never the whole declaration at once.

``b`` offers the assumed values of the section under the cursor, and says so
when that section holds none. During the confirm step F8 does the same, and
when the section under the cursor holds none it goes to the next part of the
form that does, passing over a page that does not apply this period, and
offers those.
"""

from __future__ import annotations

import pytest
from textual.pilot import Pilot
from textual.widgets import Static

from ......core.config import override_settings
from ....components.host import ScreenHostApp
from ..bulk_confirm import BulkConfirmScreen
from ..casilla_list import CasillaList
from ..screen import ModeloWorkbenchScreen
from .sectioned_form import sectioned_form
from .workbench_fixture import FakeActions, FakeReader

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_NONE_IN_SECTION = "There are no assumed values to confirm in this section."


async def _settle(pilot: Pilot[None], times: int = 4) -> None:
    for _ in range(times):
        await pilot.pause()


def _offered(app: ScreenHostApp[None]) -> list[str | None] | None:
    dialog = app.screen
    return [field.box for field in dialog.fields] if isinstance(dialog, BulkConfirmScreen) else None


async def _go_to(pilot: Pilot[None], box: str) -> None:
    await pilot.press("g", *box, "enter")
    await _settle(pilot)


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["b", "f8"])
async def test_confirming_offers_only_the_section_under_the_cursor(key: str) -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=sectioned_form()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            landed = screen.query_one(CasillaList).highlighted
            await pilot.press(key)
            await _settle(pilot)
            offered = _offered(app)
            status = str(app.screen.query_one("#bulk-status", Static).render()) if offered else None
            app.exit(None)

    assert landed is not None and landed.field.box == "05"
    assert offered == ["05"]
    assert status is not None and status.startswith("◐ to confirm: 4"), "the dialog repeats the header's result line"


@pytest.mark.asyncio
async def test_b_in_a_section_with_nothing_assumed_says_so_and_offers_nothing() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=sectioned_form()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await _go_to(pilot, "08")
            cursor = screen.query_one(CasillaList).highlighted
            await pilot.press("b")
            await _settle(pilot)
            offered = _offered(app)
            notice = str(screen.query_one("#wb-notice", Static).render())
            app.exit(None)

    assert cursor is not None and cursor.field.box == "08"
    assert offered is None
    assert notice == _NONE_IN_SECTION


@pytest.mark.asyncio
async def test_f8_goes_on_to_the_next_part_with_something_assumed_and_offers_only_that() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=sectioned_form()), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await _go_to(pilot, "08")
            await pilot.press("f8")
            await _settle(pilot)
            first = _offered(app)
            await pilot.press("escape")
            await _settle(pilot)
            await _go_to(pilot, "80")
            await pilot.press("f8")
            await _settle(pilot)
            second = _offered(app)
            app.exit(None)

    assert first == ["09"], "the second part printed under the same heading is its own section"
    assert second == ["20"], "the page that does not apply this quarter is passed over"
