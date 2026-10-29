"""The categorisation tools: listed by their area, opened in place, and guarded by the selection.

Tools that act on the whole ledger are listed by Entries, which opens with no
entry selected; tools that act on one entry are listed by Classification.
"""

from __future__ import annotations

import pytest
from textual.widgets import DataTable

from .....application.ledger.workspace import LedgerWorkspaceArea
from .....core.config import override_settings
from .....core.i18n.render import tr
from ...tests.settling import settle
from ..categorisation_common import CategorisationScreen
from ..categorisation_tools import ENTRY_LIST_TOOL_KEYS, categorisation_tools
from ..classification import LedgerClassificationScreen
from ..entries import LedgerEntriesScreen
from ..workspace_screen import LedgerWorkspaceScreen
from .categorisation_memory_doors import MemoryCategorisationProfile, categorisation_controller
from .categorisation_pilot import keys, text
from .workspace_fixtures import WorkspaceHostApp

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_TOOL_KEYS = (
    "ledger.tool.categorisation.bulk",
    "ledger.tool.categorisation.iva",
    "ledger.tool.categorisation.review",
    "ledger.tool.categorisation.rules",
    "ledger.tool.categorisation.counterparties",
    "ledger.tool.categorisation.split",
    "ledger.tool.categorisation.allocate",
    "ledger.tool.categorisation.participation",
    "ledger.tool.categorisation.ratios",
    "ledger.tool.categorisation.diagnostics",
)
"""Every categorisation tool, in the order the tools are given to the workspace."""

_ENTRY_LIST = tuple(key for key in _TOOL_KEYS if key in ENTRY_LIST_TOOL_KEYS)
_SELECTED_ENTRY = tuple(key for key in _TOOL_KEYS if key not in ENTRY_LIST_TOOL_KEYS)


def test_whole_ledger_tools_are_listed_by_entries_and_entry_tools_by_classification() -> None:
    tools = categorisation_tools(MemoryCategorisationProfile().doors().bundle())

    assert tuple(tool.key for tool in tools) == _TOOL_KEYS
    assert _ENTRY_LIST == (
        "ledger.tool.categorisation.bulk",
        "ledger.tool.categorisation.rules",
        "ledger.tool.categorisation.counterparties",
        "ledger.tool.categorisation.ratios",
        "ledger.tool.categorisation.diagnostics",
    )
    assert _SELECTED_ENTRY == (
        "ledger.tool.categorisation.iva",
        "ledger.tool.categorisation.review",
        "ledger.tool.categorisation.split",
        "ledger.tool.categorisation.allocate",
        "ledger.tool.categorisation.participation",
    )
    assert {tool.key: tool.area for tool in tools} == {
        **dict.fromkeys(_ENTRY_LIST, LedgerWorkspaceArea.ENTRIES),
        **dict.fromkeys(_SELECTED_ENTRY, LedgerWorkspaceArea.CLASSIFICATION),
    }
    assert all(tool.label_key == "tui.ledger.categorisation.tool." + tool.key.rsplit(".", 1)[1] for tool in tools)


async def _open_and_return(
    area_screen: LedgerWorkspaceScreen, key: str, listed: tuple[str, ...], area: LedgerWorkspaceArea
) -> None:
    app = WorkspaceHostApp(area_screen)
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            assert keys(area_screen, "#ledger-tools") == list(listed)
            table = area_screen.query_one("#ledger-tools", DataTable)
            table.focus()
            table.move_cursor(row=listed.index(key))
            await pilot.press("enter")
            await settle(pilot)
            opened = app.screen
            assert isinstance(opened, CategorisationScreen)
            assert opened.back_area is area
            assert text(opened, "#ledger-refusal") == ""
            assert not opened.query("#categorisation-choose-entry")
            await pilot.press("escape")
            await settle(pilot)
            assert isinstance(app.screen, type(area_screen))


@pytest.mark.asyncio
@pytest.mark.parametrize("key", _ENTRY_LIST)
async def test_a_whole_ledger_tool_opens_from_entries_with_no_entry_selected_and_returns_to_it(key: str) -> None:
    tools = categorisation_tools(MemoryCategorisationProfile().doors().bundle())
    controller = categorisation_controller(selected=None, tools=tools)
    assert controller.refusal_for(LedgerWorkspaceArea.CLASSIFICATION) is not None
    await _open_and_return(LedgerEntriesScreen(controller), key, _ENTRY_LIST, LedgerWorkspaceArea.ENTRIES)


@pytest.mark.asyncio
@pytest.mark.parametrize("key", _SELECTED_ENTRY)
async def test_an_entry_tool_opens_from_classification_and_returns_to_it(key: str) -> None:
    tools = categorisation_tools(MemoryCategorisationProfile().doors().bundle())
    controller = categorisation_controller(tools=tools)
    await _open_and_return(
        LedgerClassificationScreen(controller), key, _SELECTED_ENTRY, LedgerWorkspaceArea.CLASSIFICATION
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("key", _SELECTED_ENTRY)
async def test_an_entry_tool_without_a_selected_entry_says_how_to_choose_one(key: str) -> None:
    profile = MemoryCategorisationProfile()
    tool = next(item for item in categorisation_tools(profile.doors().bundle()) if item.key == key)
    screen = tool.build(categorisation_controller(selected=None))
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            assert text(screen, "#categorisation-choose-entry") == tr("tui.ledger.categorisation.choose_entry")
            assert not screen.query("Input")
            assert not screen.query("#categorisation-confirm")
