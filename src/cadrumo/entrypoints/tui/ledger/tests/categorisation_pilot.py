"""Drive a mounted categorisation tool the way an operator does, and read what it says."""

from __future__ import annotations

from typing import cast

from textual.pilot import Pilot
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Static

from ..categorisation_common import CategorisationScreen


async def settle(pilot: Pilot[None]) -> None:
    """Let posted messages land and every door call they started finish."""
    for _ in range(3):
        await pilot.pause()
        await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def press(pilot: Pilot[None], screen: Screen[None], button_id: str) -> None:
    """Press one button and wait for what it started."""
    screen.query_one(f"#{button_id}", Button).press()
    await settle(pilot)


def type_into(screen: Screen[None], selector: str, value: str) -> None:
    """Type a value into one input, replacing what it held."""
    screen.query_one(selector, Input).value = value


def text(screen: Screen[None], selector: str) -> str:
    """The text one static line shows."""
    return str(screen.query_one(selector, Static).render())


def keys(screen: Screen[None], selector: str) -> list[str]:
    """The semantic row keys of one table, in order."""
    table = cast("DataTable[str]", screen.query_one(selector, DataTable))
    return [str(row.key.value) for row in table.ordered_rows]


def rows(screen: Screen[None], selector: str) -> list[list[str]]:
    """The rendered cells of one table, row by row."""
    table = cast("DataTable[str]", screen.query_one(selector, DataTable))
    return [[str(cell) for cell in table.get_row_at(index)] for index in range(table.row_count)]


async def review_and_confirm(pilot: Pilot[None], screen: CategorisationScreen, button_id: str) -> None:
    """Stage a change with its review button, then confirm the reviewed change."""
    await press(pilot, screen, button_id)
    if screen.staged is None:
        raise AssertionError(f"nothing was staged: {text(screen, '#ledger-refusal')}")
    await press(pilot, screen, "categorisation-confirm")


__all__ = ["keys", "press", "review_and_confirm", "rows", "settle", "text", "type_into"]
