"""The register screens as surfaces: geometry, the event loop, the overview tools and language changes."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast

import pytest
from textual.containers import VerticalScroll
from textual.widgets import Button, DataTable, Input, Select
from textual.worker import NoActiveWorker, get_current_worker

from .....application.ledger.workspace import LedgerWorkspaceArea
from .....application.prorrata_register.operation_requests import ProrrataListRequest
from .....application.prorrata_register.projection_contracts import ProrrataSectorDefinitionProjection
from .....application.user_profile.language_resolver import adopt_profile_output_language, register_language_resolver
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from ...components.host import ScreenHostApp
from ...tests.frame import geometry_band
from ..controller import LedgerWorkspaceController
from ..overview import LedgerOverviewScreen
from ..registers_capital_goods import LedgerCapitalGoodsDoorV1, LedgerCapitalGoodsScreen, capital_goods_tool
from ..registers_inventory import LedgerInventoryDoorV1, LedgerInventoryScreen, inventory_tool
from ..registers_presentation import LedgerRegisterScreen
from ..registers_prorrata import (
    PRORRATA_TOOL_KEY,
    LedgerProrrataRegisterDoorV1,
    LedgerProrrataRegisterScreen,
    prorrata_register_tool,
)
from ..tools import LedgerToolV1
from ..workspace_injection import LedgerWorkspaceInjection
from .registers_fixtures import (
    REGISTERS_PROFILE_ID,
    MemoryCapitalGoodsDoor,
    MemoryInventoryDoor,
    MemoryProrrataRegisterDoor,
    synthetic_capital_good,
    synthetic_inventory_row,
    synthetic_prorrata_entry,
)
from .test_ledger_selection_journey import _WorkspaceHostApp
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _controller(*, tools: tuple[LedgerToolV1, ...] = ()) -> LedgerWorkspaceController:
    return LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), tools=tools),
    )


def _prorrata() -> LedgerRegisterScreen:
    door = MemoryProrrataRegisterDoor(
        entries=(synthetic_prorrata_entry(2024, definitive="78"), synthetic_prorrata_entry(2025, sector_id="S1")),
        sectors=(ProrrataSectorDefinitionProjection(sector_id="S1", letra="a", member_activity_codes=("A01",)),),
    )
    return LedgerProrrataRegisterScreen(_controller(), cast(LedgerProrrataRegisterDoorV1, door))


def _capital_goods() -> LedgerRegisterScreen:
    door = MemoryCapitalGoodsDoor(records=(synthetic_capital_good("BI-01"), synthetic_capital_good("BI-02")))
    return LedgerCapitalGoodsScreen(_controller(), cast(LedgerCapitalGoodsDoorV1, door))


def _inventory() -> LedgerRegisterScreen:
    door = MemoryInventoryDoor(rows=(synthetic_inventory_row("act-01"), synthetic_inventory_row("act-02", 2025)))
    return LedgerInventoryScreen(_controller(), cast(LedgerInventoryDoorV1, door))


_SCREENS: dict[str, Callable[[], LedgerRegisterScreen]] = {
    "prorrata": _prorrata,
    "capital_goods": _capital_goods,
    "inventory": _inventory,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", tuple(_SCREENS))
@pytest.mark.parametrize("theme", ("cadrumo-dark", "cadrumo-light"))
@pytest.mark.parametrize("size", ((80, 24), (100, 30), (120, 40), (200, 50)))
async def test_each_register_fits_every_size_with_one_scroll_owner(
    surface: str, theme: str, size: tuple[int, int]
) -> None:
    screen = _SCREENS[surface]()
    app = ScreenHostApp[None](screen)
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=size) as pilot:
            app.theme = theme
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert all(table.row_count for table in screen.query(DataTable) if table.id != "ledger-navigation")
            assert geometry_band(app, size[0]) == []
            assert all(table.max_scroll_x == 0 for table in screen.query(DataTable))
            owners = tuple(
                widget for widget in screen.query(VerticalScroll) if widget.display and widget.show_vertical_scrollbar
            )
            assert all(owner.id == "ledger-page" for owner in owners)


class _WorkerBoundary:
    """Records each door call and whether it ran inside a Textual worker rather than a message handler."""

    def __init__(self) -> None:
        self.entries: list[tuple[str, bool]] = []

    def enter(self, name: str) -> None:
        try:
            get_current_worker()
        except NoActiveWorker:
            self.entries.append((name, False))
        else:
            self.entries.append((name, True))

    @property
    def outside_workers(self) -> list[str]:
        return [name for name, in_worker in self.entries if not in_worker]


def _guard[DoorT](door: DoorT, boundary: _WorkerBoundary, names: tuple[str, ...]) -> DoorT:
    """Wrap each named door method so its call is recorded at the door boundary."""
    for name in names:
        method = cast("Callable[..., Awaitable[object]]", getattr(door, name))

        def guarded(*args: object, _name: str = name, _method: Callable[..., Awaitable[object]] = method) -> object:
            boundary.enter(_name)
            return _method(*args)

        setattr(door, name, guarded)
    return door


@pytest.mark.asyncio
async def test_every_register_door_call_runs_in_a_worker() -> None:
    boundary = _WorkerBoundary()
    prorrata = _guard(MemoryProrrataRegisterDoor(), boundary, ("read_register", "apply"))
    screen = LedgerProrrataRegisterScreen(_controller(), cast(LedgerProrrataRegisterDoorV1, prorrata))
    app = ScreenHostApp[None](screen)
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(120, 60)) as pilot:
            await app.workers.wait_for_complete()
            cast("Select[str]", screen.query_one("#prorrata-action", Select)).value = "seed"
            await pilot.pause()
            screen.query_one("#prorrata-ejercicio", Input).value = "2026"
            for button_id in ("register-review", "register-confirm"):
                screen.query_one(f"#{button_id}", Button).press()
                await pilot.pause()
                await app.workers.wait_for_complete()
                await pilot.pause()
    assert boundary.entries == [("read_register", True), ("apply", True), ("read_register", True)]

    inventory_boundary = _WorkerBoundary()
    inventory = _guard(
        MemoryInventoryDoor(rows=(synthetic_inventory_row("act-01"),)),
        inventory_boundary,
        ("read_register", "read_closing_authority", "record_closing_authority"),
    )
    capital_boundary = _WorkerBoundary()
    capital = _guard(MemoryCapitalGoodsDoor(), capital_boundary, ("read_register",))
    for register in (
        LedgerInventoryScreen(_controller(), cast(LedgerInventoryDoorV1, inventory)),
        LedgerCapitalGoodsScreen(_controller(), cast(LedgerCapitalGoodsDoorV1, capital)),
    ):
        async with ScreenHostApp[None](register).run_test(size=(120, 60)) as pilot:
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
    assert inventory_boundary.entries == [("read_register", True)]
    assert capital_boundary.entries == [("read_register", True)]


@pytest.mark.asyncio
async def test_the_worker_boundary_catches_a_door_called_from_a_handler() -> None:
    """Detector teeth: the same boundary flags a call made straight from the event loop."""
    boundary = _WorkerBoundary()
    door = _guard(MemoryProrrataRegisterDoor(), boundary, ("read_register",))
    await door.read_register(ProrrataListRequest(profile_id=REGISTERS_PROFILE_ID))
    assert boundary.outside_workers == ["read_register"]


@pytest.mark.asyncio
async def test_the_overview_lists_the_three_registers_and_opens_one_in_place() -> None:
    tools = (
        prorrata_register_tool(cast(LedgerProrrataRegisterDoorV1, MemoryProrrataRegisterDoor())),
        capital_goods_tool(cast(LedgerCapitalGoodsDoorV1, MemoryCapitalGoodsDoor())),
        inventory_tool(cast(LedgerInventoryDoorV1, MemoryInventoryDoor())),
    )
    controller = _controller(tools=tools)
    assert controller.tools_for(LedgerWorkspaceArea.OVERVIEW) == tools
    app = _WorkspaceHostApp(LedgerOverviewScreen(controller))
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            table = app.screen.query_one("#ledger-tools", DataTable)
            assert [str(row.key.value) for row in table.ordered_rows] == [tool.key for tool in tools]
            assert str(table.get_row_at(0)[0]) == tr("tui.ledger.registers.prorrata.tool")
            table.focus()
            table.move_cursor(row=0)
            await pilot.press("enter")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            opened = app.screen
            assert isinstance(opened, LedgerProrrataRegisterScreen)
            assert opened.back_area is LedgerWorkspaceArea.OVERVIEW
            await pilot.press("escape")
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, LedgerOverviewScreen)
    assert tools[0].key == PRORRATA_TOOL_KEY


@pytest.mark.asyncio
async def test_a_language_change_rewords_the_register_in_place_and_keeps_the_chosen_record() -> None:
    screen = cast(LedgerInventoryScreen, _inventory())
    with override_settings(cadrumo_output_language=""):
        register_language_resolver()
        adopt_profile_output_language(OutputLanguage.EN)
        try:
            async with ScreenHostApp[None](screen).run_test(size=(120, 60)) as pilot:
                await pilot.app.workers.wait_for_complete()
                await pilot.pause()
                table = screen.query_one("#inventory-list", DataTable)
                table.focus()
                table.move_cursor(row=1)
                await pilot.press("enter")
                await pilot.pause()
                cast("Select[str]", screen.query_one("#inventory-action", Select)).value = "valuation_preview"
                await pilot.pause()
                adopt_profile_output_language(OutputLanguage.ES)
                await screen.refresh_language()
                await pilot.pause()
                await pilot.pause()
                action = cast("Select[str]", screen.query_one("#inventory-action", Select))
                header = str(table.columns[next(iter(table.columns))].label)
                expected_header = tr("tui.ledger.registers.inventory.column.actividad")
                chosen = str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
        finally:
            adopt_profile_output_language(None)
    assert action.value == "valuation_preview"
    assert header == expected_header
    assert chosen == "act-02|2025"
    assert screen.selected_key == "act-02|2025"
    assert table.row_count == 2
