"""The inventory screen states which ledger transaction books a purchase, that none does, or clears the statement."""

from __future__ import annotations

from typing import cast

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, Input, Select, Static

from .....application.inventory.registered_requests import InventoryMovementClaimRequest
from .....core.config import override_settings
from .....core.i18n.render import tr
from .....domain.contribuyente.inventory.records import PurchaseLedgerRow
from ...tests.settling import settle
from ..controller import LedgerWorkspaceController
from ..registers_inventory import LedgerInventoryDoorV1, LedgerInventoryScreen
from ..workspace_injection import LedgerWorkspaceInjection
from .registers_fixtures import INVENTORY_YEAR, REGISTERS_PROFILE_ID, MemoryInventoryDoor, synthetic_inventory_row
from .workspace_fixtures import WorkspaceHostApp, ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TRANSACTION = "ab" * 32


def _screen(door: MemoryInventoryDoor) -> LedgerInventoryScreen:
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    return LedgerInventoryScreen(controller, cast(LedgerInventoryDoorV1, door))


def _text(screen: LedgerInventoryScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


async def _prepare(pilot: Pilot[None], screen: LedgerInventoryScreen, ledger_row: str) -> None:
    cast("Select[str]", screen.query_one("#inventory-action", Select)).value = "movement_claim"
    await settle(pilot)
    cast("Select[str]", screen.query_one("#inventory-ledger-row", Select)).value = ledger_row
    screen.query_one("#inventory-actividad", Input).value = "act-01"
    screen.query_one("#inventory-year", Input).value = str(INVENTORY_YEAR)
    screen.query_one("#inventory-movement-id", Input).value = "mv-01"


async def _review(pilot: Pilot[None], screen: LedgerInventoryScreen) -> None:
    screen.query_one("#register-review", Button).press()
    await settle(pilot)


@pytest.mark.asyncio
async def test_a_claim_names_the_transaction_and_is_sent_through_the_change_door() -> None:
    door = MemoryInventoryDoor((synthetic_inventory_row("act-01", INVENTORY_YEAR),))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _prepare(pilot, screen, PurchaseLedgerRow.CLAIMED.value)
            screen.query_one("#inventory-claimed-transaction", Input).value = _TRANSACTION
            await _review(pilot, screen)
            assert screen.staged is not None
            assert tr("tui.ledger.registers.inventory.ledger_row.claimed") in _text(screen, "#register-staged")
            assert _TRANSACTION in _text(screen, "#register-staged")
            screen.query_one("#register-confirm", Button).press()
            await settle(pilot)

            sent = door.requests[-2]
            assert isinstance(sent, InventoryMovementClaimRequest)
            assert (sent.profile_id, sent.actividad_id, sent.year) == (REGISTERS_PROFILE_ID, "act-01", INVENTORY_YEAR)
            assert (sent.movement_id, sent.ledger_row, sent.claimed_transaction_id) == (
                "mv-01",
                PurchaseLedgerRow.CLAIMED,
                _TRANSACTION,
            )
            assert tr("application.inventory.workbench.done.applied") in _text(screen, "#register-result")


@pytest.mark.asyncio
async def test_none_is_stated_without_a_transaction_and_unstated_clears_the_statement() -> None:
    door = MemoryInventoryDoor((synthetic_inventory_row("act-01", INVENTORY_YEAR),))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            for row in (PurchaseLedgerRow.NONE, PurchaseLedgerRow.UNSTATED):
                await _prepare(pilot, screen, row.value)
                await _review(pilot, screen)
                assert screen.staged is not None, _text(screen, "#ledger-refusal")
                screen.query_one("#register-confirm", Button).press()
                await settle(pilot)
                sent = door.requests[-2]
                assert isinstance(sent, InventoryMovementClaimRequest)
                assert (sent.ledger_row, sent.claimed_transaction_id) == (row, None)


@pytest.mark.asyncio
async def test_a_claim_without_its_transaction_and_a_transaction_without_a_claim_are_refused_unsent() -> None:
    door = MemoryInventoryDoor((synthetic_inventory_row("act-01", INVENTORY_YEAR),))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            sent_before = len(door.requests)
            await _prepare(pilot, screen, PurchaseLedgerRow.CLAIMED.value)
            await _review(pilot, screen)
            assert screen.staged is None
            assert _text(screen, "#ledger-refusal")

            await _prepare(pilot, screen, PurchaseLedgerRow.NONE.value)
            screen.query_one("#inventory-claimed-transaction", Input).value = _TRANSACTION
            await _review(pilot, screen)
            assert screen.staged is None
            assert _text(screen, "#ledger-refusal")
            assert len(door.requests) == sent_before


@pytest.mark.asyncio
async def test_the_claim_shows_only_the_fields_it_takes() -> None:
    door = MemoryInventoryDoor((synthetic_inventory_row("act-01", INVENTORY_YEAR),))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _prepare(pilot, screen, PurchaseLedgerRow.CLAIMED.value)
            for shown in ("movement-id", "ledger-row", "claimed-transaction", "actividad", "year"):
                assert screen.query_one(f"#inventory-{shown}-field").display, shown
            for hidden in ("quantity", "acquisition-path", "target-movement", "method"):
                assert not screen.query_one(f"#inventory-{hidden}-field").display, hidden
