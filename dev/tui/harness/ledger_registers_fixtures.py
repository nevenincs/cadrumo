"""Prorrata, capital-goods and inventory register states for reviewing the shipped Ledger screens.

Each screen is driven through its own controls over an in-memory register that
answers with the registered operations' own public projections, so every frame
shows the request review, result and refusal copy the operator sees. Every
identifier and amount is synthetic; nothing is written to storage.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from enum import StrEnum
from typing import cast, override

from textual.events import Mount
from textual.widgets import Input, Select

from cadrumo.application.prorrata_register.projection_contracts import (
    ProrrataRefusalProjection,
    ProrrataSectorDefinitionProjection,
)
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.ledger.controller import LedgerWorkspaceController
from cadrumo.entrypoints.tui.ledger.registers_capital_goods import LedgerCapitalGoodsDoorV1, LedgerCapitalGoodsScreen
from cadrumo.entrypoints.tui.ledger.registers_inventory import LedgerInventoryDoorV1, LedgerInventoryScreen
from cadrumo.entrypoints.tui.ledger.registers_presentation import LedgerRegisterScreen
from cadrumo.entrypoints.tui.ledger.registers_prorrata import (
    LedgerProrrataRegisterDoorV1,
    LedgerProrrataRegisterScreen,
)
from cadrumo.entrypoints.tui.ledger.tests.registers_fixtures import (
    SYNTHETIC_PURCHASE_PATH,
    MemoryCapitalGoodsDoor,
    MemoryInventoryDoor,
    MemoryProrrataRegisterDoor,
    synthetic_capital_good,
    synthetic_inventory_row,
    synthetic_prorrata_entry,
)
from cadrumo.entrypoints.tui.ledger.tests.workspace_fixtures import (
    ledger_context,
    ledger_projection,
    ledger_review_action,
)
from cadrumo.entrypoints.tui.ledger.workspace_injection import LedgerWorkspaceInjection

from .settling import press_when_enabled, settle

_PRORRATA_INTERFACE = "cadrumo.entrypoints.tui.ledger.registers_prorrata.LedgerProrrataRegisterScreen"
_CAPITAL_GOODS_INTERFACE = "cadrumo.entrypoints.tui.ledger.registers_capital_goods.LedgerCapitalGoodsScreen"
_INVENTORY_INTERFACE = "cadrumo.entrypoints.tui.ledger.registers_inventory.LedgerInventoryScreen"


class RegisterFixtureState(StrEnum):
    """The reviewable states of the three register screens."""

    PRORRATA_EMPTY = "prorrata-empty"
    PRORRATA_POPULATED = "prorrata-populated"
    PRORRATA_ELECTION_STAGED = "prorrata-election-staged"
    PRORRATA_ELECTION_REFUSED = "prorrata-election-refused"
    PRORRATA_SETTLED = "prorrata-settled"
    CAPITAL_GOODS_POPULATED = "capital-goods-populated"
    CAPITAL_GOODS_DECLARATION_STAGED = "capital-goods-declaration-staged"
    CAPITAL_GOODS_DUPLICATE_REFUSED = "capital-goods-duplicate-refused"
    INVENTORY_POPULATED = "inventory-populated"
    INVENTORY_MOVEMENT_STAGED = "inventory-movement-staged"
    INVENTORY_VALUATION_PREVIEWED = "inventory-valuation-previewed"


def _controller() -> LedgerWorkspaceController:
    return LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )


class RegisterCaptureHost(ScreenHostApp[None]):
    """Drive one production register screen to one declared, settled review state."""

    def __init__(self, screen: LedgerRegisterScreen, drive: Callable[[RegisterCaptureHost], object]) -> None:
        """Bind the production screen and the steps that reach the captured state."""
        super().__init__(screen)
        self.register_screen = screen
        self._drive = drive

    @override
    async def on_mount(self, event: Mount | None = None) -> None:
        # Mounted explicitly before driving, so Textual must not dispatch the
        # inherited handler a second time.
        if event is not None:
            event.prevent_default()
        await super().on_mount()
        await self.settle()
        result = self._drive(self)
        if asyncio.iscoroutine(result):
            await result

    async def settle(self) -> None:
        """Wait until the screen has handled every posted message and finished every door call."""
        await settle(self)

    async def press(self, button_id: str) -> None:
        """Press one control once it is enabled, and wait for what it started."""
        await press_when_enabled(self, button_id, within=self.register_screen)

    async def choose(self, select_id: str, value: str) -> None:
        """Choose one value in a closed choice."""
        cast("Select[str]", self.register_screen.query_one(f"#{select_id}", Select)).value = value
        await self.settle()

    def fill(self, **values: str) -> None:
        """Type into inputs named by their DOM ids, with underscores for hyphens."""
        for name, value in values.items():
            self.register_screen.query_one(f"#{name.replace('_', '-')}", Input).value = value

    def show(self, selector: str) -> None:
        """Scroll the page so the reviewed part of the screen is in the frame."""
        self.register_screen.query_one(selector).scroll_visible(top=True, animate=False, immediate=True)


def _prorrata_door(*, empty: bool) -> MemoryProrrataRegisterDoor:
    if empty:
        return MemoryProrrataRegisterDoor()
    return MemoryProrrataRegisterDoor(
        entries=(
            synthetic_prorrata_entry(2024, definitive="78"),
            synthetic_prorrata_entry(2025, provisional="78"),
            synthetic_prorrata_entry(2025, sector_id="S1", regime="especial", provisional="64.5"),
        ),
        sectors=(ProrrataSectorDefinitionProjection(sector_id="S1", letra="a", member_activity_codes=("A01", "A02")),),
    )


async def _stage_election(host: RegisterCaptureHost) -> None:
    await host.choose("prorrata-action", "elect_general")
    host.fill(prorrata_ejercicio="2026", prorrata_percentage="82", prorrata_provenance="synthetic_operator_estimate")
    await host.press("register-review")
    host.show("#register-staged")


async def _refuse_election(host: RegisterCaptureHost) -> None:
    await _stage_election(host)
    await host.press("register-confirm")
    host.show("#register-staged")


async def _settle_sector(host: RegisterCaptureHost) -> None:
    await host.choose("prorrata-action", "settle_sector")
    host.fill(
        prorrata_ejercicio="2025",
        prorrata_sector="S1",
        prorrata_con_derecho="7500.00",
        prorrata_sin_derecho="2500.00",
    )
    await host.press("register-review")
    await host.press("register-confirm")
    host.show("#register-result")


async def _stage_declaration(host: RegisterCaptureHost, identifier: str) -> None:
    host.fill(
        capital_identifier=identifier,
        capital_description="Synthetic delivery van",
        capital_year="2025",
        capital_ledger_id="tx-synthetic-02",
        capital_cuota="4200.00",
        capital_prorrata="80",
        capital_kind="synthetic_kind",
    )
    await host.press("register-review")
    host.show("#register-staged")


async def _refuse_duplicate(host: RegisterCaptureHost) -> None:
    await _stage_declaration(host, "BI-01")
    await host.press("register-confirm")
    host.show("#register-staged")


async def _stage_movement(host: RegisterCaptureHost) -> None:
    await host.choose("inventory-action", "movement_add")
    await host.choose("inventory-movement-kind", "purchase")
    host.fill(
        inventory_actividad="act-01",
        inventory_year="2026",
        inventory_movement_id="mv-01",
        inventory_movement_date="2026-03-01",
        inventory_quantity="5",
        inventory_unit_cost="11.00",
        inventory_taxable_base="55.00",
        inventory_acquisition_path=SYNTHETIC_PURCHASE_PATH,
    )
    await host.press("register-review")
    host.show("#register-staged")


async def _preview_valuation(host: RegisterCaptureHost) -> None:
    await host.choose("inventory-action", "valuation_preview")
    host.fill(inventory_actividad="act-01", inventory_year="2026")
    await host.press("register-review")
    await host.press("register-confirm")
    host.show("#register-result")


def _nothing(_host: RegisterCaptureHost) -> None:
    return None


def build_register_fixture(state: RegisterFixtureState) -> RegisterCaptureHost:
    """Open the register screen the state names over a synthetic in-memory register."""
    if state.value.startswith("prorrata"):
        door = _prorrata_door(empty=state is RegisterFixtureState.PRORRATA_EMPTY)
        if state is RegisterFixtureState.PRORRATA_ELECTION_REFUSED:
            door.refusal = ProrrataRefusalProjection(
                code="REFUSED_PRORRATA_ELECTION",
                reason="provenance_not_electable",
                detail="The provisional provenance named is not one an operator can elect.",
                ejercicio=2026,
                accepted_provenances=("synthetic_operator_estimate",),
            )
        drives: dict[RegisterFixtureState, Callable[[RegisterCaptureHost], object]] = {
            RegisterFixtureState.PRORRATA_ELECTION_STAGED: _stage_election,
            RegisterFixtureState.PRORRATA_ELECTION_REFUSED: _refuse_election,
            RegisterFixtureState.PRORRATA_SETTLED: _settle_sector,
        }
        screen: LedgerRegisterScreen = LedgerProrrataRegisterScreen(
            _controller(), cast(LedgerProrrataRegisterDoorV1, door)
        )
        return RegisterCaptureHost(screen, drives.get(state, _nothing))
    if state.value.startswith("capital-goods"):
        goods = MemoryCapitalGoodsDoor(records=(synthetic_capital_good("BI-01"), synthetic_capital_good("BI-07")))
        capital_drives: dict[RegisterFixtureState, Callable[[RegisterCaptureHost], object]] = {
            RegisterFixtureState.CAPITAL_GOODS_DECLARATION_STAGED: lambda host: _stage_declaration(host, "BI-02"),
            RegisterFixtureState.CAPITAL_GOODS_DUPLICATE_REFUSED: _refuse_duplicate,
        }
        screen = LedgerCapitalGoodsScreen(_controller(), cast(LedgerCapitalGoodsDoorV1, goods))
        return RegisterCaptureHost(screen, capital_drives.get(state, _nothing))
    inventory = MemoryInventoryDoor(rows=(synthetic_inventory_row("act-01"), synthetic_inventory_row("act-02", 2025)))
    inventory_drives: dict[RegisterFixtureState, Callable[[RegisterCaptureHost], object]] = {
        RegisterFixtureState.INVENTORY_MOVEMENT_STAGED: _stage_movement,
        RegisterFixtureState.INVENTORY_VALUATION_PREVIEWED: _preview_valuation,
    }
    screen = LedgerInventoryScreen(_controller(), cast(LedgerInventoryDoorV1, inventory))
    return RegisterCaptureHost(screen, inventory_drives.get(state, _nothing))


def register_fixture_interfaces(state: RegisterFixtureState) -> tuple[str, ...]:
    """The one production screen each state shows."""
    if state.value.startswith("prorrata"):
        return (_PRORRATA_INTERFACE,)
    if state.value.startswith("capital-goods"):
        return (_CAPITAL_GOODS_INTERFACE,)
    return (_INVENTORY_INTERFACE,)


__all__ = [
    "RegisterCaptureHost",
    "RegisterFixtureState",
    "build_register_fixture",
    "register_fixture_interfaces",
]
