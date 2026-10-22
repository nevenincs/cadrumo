"""The tools seam: further screens an area lists, opens in place, and returns from."""

from __future__ import annotations

from typing import cast, override

import pytest
from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from .....application.ledger.workspace import LedgerWorkspaceArea
from .....application.user_profile.language_resolver import adopt_profile_output_language, register_language_resolver
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from ..controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from ..entries import LedgerEntriesScreen
from ..overview import LedgerOverviewScreen
from ..routes import resolve_ledger_screen
from ..tools import LedgerToolV1
from ..workspace_injection import LedgerWorkspaceInjection
from ..workspace_presentation import ledger_workspace_page
from .test_ledger_selection_journey import _WorkspaceHostApp
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _ToolScreen(LedgerWorkspaceScreen):
    """A tool body that only says which tool it is."""

    def __init__(self, controller: LedgerWorkspaceController, name: str) -> None:
        super().__init__(controller, id="ledger-test-tool-screen")
        self.tool_name = name

    @override
    def compose(self) -> ComposeResult:
        yield Static(self.tool_name, id="ledger-test-tool-name", markup=False)
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static("", id="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        self.populate_navigation()


def _tool(area: LedgerWorkspaceArea, name: str, label_key: str = "tui.ledger.area.review") -> LedgerToolV1:
    return LedgerToolV1(
        key=f"ledger.tool.test.{name}",
        label_key=label_key,
        area=area,
        build=lambda controller: _ToolScreen(controller, name),
    )


def _open(controller: LedgerWorkspaceController) -> LedgerWorkspaceScreen:
    return _ToolScreen(controller, "unused")


def _controller(*tools: LedgerToolV1) -> LedgerWorkspaceController:
    return LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), tools=tools),
    )


def _rows(screen: LedgerWorkspaceScreen) -> tuple[str, ...]:
    table = cast("DataTable[str]", screen.query_one("#ledger-tools", DataTable))
    return tuple(str(row.key.value) for row in table.ordered_rows)


@pytest.mark.parametrize("key", ["ledger.tool.test", "ledger.test.name", "ledger.tool.Test.name", "tool.test.name"])
def test_a_tool_key_outside_the_tool_namespace_is_refused(key: str) -> None:
    with pytest.raises(ValueError, match=r"ledger\.tool"):
        LedgerToolV1(key=key, label_key="tui.ledger.area.review", area=LedgerWorkspaceArea.OVERVIEW, build=_open)


def test_a_tool_without_a_label_key_is_refused() -> None:
    with pytest.raises(ValueError, match="label key"):
        LedgerToolV1(key="ledger.tool.test.name", label_key="", area=LedgerWorkspaceArea.OVERVIEW, build=_open)


def test_two_tools_sharing_a_key_are_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="unique"):
        _controller(_tool(LedgerWorkspaceArea.OVERVIEW, "same"), _tool(LedgerWorkspaceArea.ENTRIES, "same"))


@pytest.mark.asyncio
async def test_an_area_lists_only_its_own_tools_beneath_the_navigation() -> None:
    controller = _controller(
        _tool(LedgerWorkspaceArea.OVERVIEW, "first"),
        _tool(LedgerWorkspaceArea.ENTRIES, "elsewhere"),
        _tool(LedgerWorkspaceArea.OVERVIEW, "second"),
    )
    screen = LedgerOverviewScreen(controller)
    async with _WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        rows = _rows(screen)
        page = screen.query_one("#ledger-page")
        order = [child.id for child in page.children]
        heading = str(screen.query_one("#ledger-tools-heading", Static).render())
    assert rows == ("ledger.tool.test.first", "ledger.tool.test.second")
    assert order.index("ledger-navigation") + 1 == order.index("ledger-tools-heading")
    assert order.index("ledger-tools-heading") + 1 == order.index("ledger-tools")
    assert heading == tr("tui.ledger.tools.heading")


@pytest.mark.asyncio
async def test_an_area_without_tools_lists_none() -> None:
    screen = LedgerOverviewScreen(_controller(_tool(LedgerWorkspaceArea.ENTRIES, "elsewhere")))
    async with _WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert not screen.query("#ledger-tools")
        assert not screen.query("#ledger-tools-heading")


@pytest.mark.asyncio
async def test_a_chosen_tool_opens_in_place_and_back_returns_to_its_own_area() -> None:
    controller = _controller(_tool(LedgerWorkspaceArea.ENTRIES, "rules"))
    entries = resolve_ledger_screen(controller, controller.route_target(LedgerWorkspaceArea.ENTRIES))
    assert isinstance(entries, LedgerEntriesScreen)
    app = _WorkspaceHostApp(entries)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()
        tools = entries.query_one("#ledger-tools", DataTable)
        tools.focus()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        opened = app.screen
        assert isinstance(opened, _ToolScreen)
        assert opened.tool_name == "rules"
        # Entries reads its own rows as transactions; the tool row must not reach it as one.
        assert opened.controller.restored_transaction_id() is None
        await pilot.press("escape")
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, LedgerEntriesScreen)


@pytest.mark.asyncio
async def test_the_tool_list_rewords_in_place_when_the_profile_language_changes() -> None:
    # The profile language, as production switches it: the list is reworded after
    # the body's own repaint, on the app's loop, where only the profile snapshot applies.
    controller = _controller(_tool(LedgerWorkspaceArea.OVERVIEW, "named", label_key="tui.ledger.area.entries"))
    screen = LedgerOverviewScreen(controller)
    with override_settings(cadrumo_output_language=""):
        register_language_resolver()
        adopt_profile_output_language(OutputLanguage.EN)
        try:
            async with _WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                english = str(cast("DataTable[str]", screen.query_one("#ledger-tools", DataTable)).get_row_at(0)[0])
                adopt_profile_output_language(OutputLanguage.ES)
                await screen.refresh_language()
                await pilot.pause()
                await pilot.pause()
                spanish = str(cast("DataTable[str]", screen.query_one("#ledger-tools", DataTable)).get_row_at(0)[0])
                expected = tr("tui.ledger.area.entries")
        finally:
            adopt_profile_output_language(None)
    assert english != spanish
    assert spanish == expected
