"""The inventory screen states which ledger transaction books a purchase, that none does, or clears the statement."""

from __future__ import annotations

from datetime import date
from typing import cast

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, Input, Select, Static

from .....application.inventory.registered_claim_candidates_operation import (
    InventoryClaimCandidateProjection,
    InventoryClaimCandidatesRequest,
)
from .....application.inventory.registered_options_operation import (
    inventory_option_effect_key,
    inventory_option_label_key,
)
from .....application.inventory.registered_projections import InventoryMovementProjection
from .....application.inventory.registered_requests import InventoryMovementClaimRequest
from .....application.operations.public_scalar import PublicDecimal
from .....core.config import override_settings
from .....core.i18n.render import tr
from .....domain.contribuyente.inventory.records import MovementKind, PurchaseLedgerRow
from ...refusal.panel import RefusalSlot
from ...tests.settling import settle
from ..controller import LedgerWorkspaceController
from ..registers_inventory import LedgerInventoryDoorV1, LedgerInventoryScreen
from ..workspace_injection import LedgerWorkspaceInjection
from .registers_fixtures import INVENTORY_YEAR, REGISTERS_PROFILE_ID, MemoryInventoryDoor, synthetic_inventory_row
from .workspace_fixtures import WorkspaceHostApp, ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TRANSACTION = "ab" * 32
_OTHER_TRANSACTION = "cd" * 32


def _screen(door: MemoryInventoryDoor) -> LedgerInventoryScreen:
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    return LedgerInventoryScreen(controller, cast(LedgerInventoryDoorV1, door))


def _text(screen: LedgerInventoryScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


def _candidate(transaction_id: str, description: str) -> InventoryClaimCandidateProjection:
    return InventoryClaimCandidateProjection(
        transaction_id=transaction_id,
        booked_date=date(INVENTORY_YEAR, 2, 3),
        counterparty="Synthetic Supplier SL",
        description=description,
        currency="EUR",
        taxable_base=PublicDecimal(decimal="100.00"),
        iva_amount=None,
        recargo_amount=None,
    )


def _served_label(row: PurchaseLedgerRow) -> str:
    return tr(inventory_option_label_key("purchase_ledger_row", row))


def _offered(screen: LedgerInventoryScreen) -> list[str]:
    select = cast("Select[str]", screen.query_one("#inventory-claimed-transaction", Select))
    return [str(value) for _label, value in select._options if value is not Select.NULL]


async def _prepare(pilot: Pilot[None], screen: LedgerInventoryScreen, ledger_row: str) -> None:
    cast("Select[str]", screen.query_one("#inventory-action", Select)).value = "movement_claim"
    await settle(pilot)
    cast("Select[str]", screen.query_one("#inventory-ledger-row", Select)).value = ledger_row
    screen.query_one("#inventory-actividad", Input).value = "act-01"
    screen.query_one("#inventory-year", Input).value = str(INVENTORY_YEAR)
    screen.query_one("#inventory-movement-id", Input).value = "mv-01"


async def _offer(pilot: Pilot[None], screen: LedgerInventoryScreen) -> None:
    screen.query_one("#inventory-claim-load", Button).press()
    await settle(pilot)


def _pick(screen: LedgerInventoryScreen, transaction_id: str) -> None:
    cast("Select[str]", screen.query_one("#inventory-claimed-transaction", Select)).value = transaction_id


async def _review(pilot: Pilot[None], screen: LedgerInventoryScreen) -> None:
    screen.query_one("#register-review", Button).press()
    await settle(pilot)


@pytest.mark.asyncio
async def test_a_claim_names_the_picked_transaction_and_is_sent_through_the_change_door() -> None:
    door = MemoryInventoryDoor((synthetic_inventory_row("act-01", INVENTORY_YEAR),))
    door.candidates = (_candidate(_OTHER_TRANSACTION, "Other goods"), _candidate(_TRANSACTION, "Synthetic goods"))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _prepare(pilot, screen, PurchaseLedgerRow.CLAIMED.value)
            await _offer(pilot, screen)
            read = door.requests[-1]
            assert isinstance(read, InventoryClaimCandidatesRequest)
            assert (read.actividad_id, read.year, read.movement_id) == ("act-01", INVENTORY_YEAR, "mv-01")
            _pick(screen, _TRANSACTION)
            await _review(pilot, screen)
            assert screen.staged is not None
            staged = _text(screen, "#register-staged")
            assert _served_label(PurchaseLedgerRow.CLAIMED) in staged
            assert tr(inventory_option_effect_key("purchase_ledger_row", PurchaseLedgerRow.CLAIMED)) in staged
            assert _TRANSACTION in staged
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
    door.candidates = (_candidate(_TRANSACTION, "Synthetic goods"),)
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _prepare(pilot, screen, PurchaseLedgerRow.CLAIMED.value)
            await _review(pilot, screen)
            assert screen.staged is None
            assert _text(screen, "#ledger-refusal")

            await _prepare(pilot, screen, PurchaseLedgerRow.NONE.value)
            await _offer(pilot, screen)
            _pick(screen, _TRANSACTION)
            sent_before = len(door.requests)
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


@pytest.mark.asyncio
async def test_the_offered_transactions_are_the_served_ones_in_served_order_and_say_when_there_are_none() -> None:
    door = MemoryInventoryDoor((synthetic_inventory_row("act-01", INVENTORY_YEAR),))
    door.candidates = (_candidate(_OTHER_TRANSACTION, "Other goods"), _candidate(_TRANSACTION, "Synthetic goods"))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _prepare(pilot, screen, PurchaseLedgerRow.CLAIMED.value)
            assert _offered(screen) == []
            await _offer(pilot, screen)
            assert _offered(screen) == [_OTHER_TRANSACTION, _TRANSACTION]
            assert _text(screen, "#inventory-claim-status") == ""

            # Naming another purchase drops the offer made for the first.
            screen.query_one("#inventory-movement-id", Input).value = "mv-02"
            await settle(pilot)
            assert _offered(screen) == []

            door.candidates = ()
            await _offer(pilot, screen)
            assert _text(screen, "#inventory-claim-status") == tr("tui.ledger.registers.inventory.claim.none_offered")


@pytest.mark.asyncio
async def test_a_refused_candidate_read_shows_the_served_refusal_and_offers_nothing() -> None:
    door = MemoryInventoryDoor()
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _prepare(pilot, screen, PurchaseLedgerRow.CLAIMED.value)
            await _offer(pilot, screen)
            request = door.requests[-1]
            assert isinstance(request, InventoryClaimCandidatesRequest)
            served = (await door.claim_candidates(request)).refusal
            assert served is not None
            assert served.refusal_words is not None
            slot = screen.query_one("#inventory-claim-refusal", RefusalSlot)
            assert slot.refusal is not None
            assert slot.refusal.sentence == served.refusal_words
            assert _offered(screen) == []


def _purchase(movement_id: str, row: PurchaseLedgerRow, transaction: str | None) -> InventoryMovementProjection:
    return InventoryMovementProjection(
        movement_id=movement_id,
        movement_date=date(INVENTORY_YEAR, 3, 1),
        kind=MovementKind.PURCHASE,
        sku="default",
        quantity=PublicDecimal(decimal="2"),
        unit_cost=None,
        taxable_base=None,
        iva_rate=PublicDecimal(decimal="0"),
        iva_amount=None,
        deductible_iva_ratio=PublicDecimal(decimal="1"),
        acquisition_cost=None,
        schema_version="1",
        ledger_row=row,
        claimed_transaction_id=transaction,
    )


@pytest.mark.asyncio
async def test_inspecting_an_inventory_states_each_purchase_claim_in_the_served_words() -> None:
    door = MemoryInventoryDoor((synthetic_inventory_row("act-01", INVENTORY_YEAR),))
    door.movements[("act-01", INVENTORY_YEAR)] = [
        _purchase("mv-01", PurchaseLedgerRow.CLAIMED, _TRANSACTION),
        _purchase("mv-02", PurchaseLedgerRow.NONE, None),
        _purchase("mv-03", PurchaseLedgerRow.UNSTATED, None),
    ]
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            cast("Select[str]", screen.query_one("#inventory-action", Select)).value = "inspect"
            await settle(pilot)
            screen.query_one("#inventory-actividad", Input).value = "act-01"
            screen.query_one("#inventory-year", Input).value = str(INVENTORY_YEAR)
            await _review(pilot, screen)
            screen.query_one("#register-confirm", Button).press()
            await settle(pilot)
            lines = _text(screen, "#register-result").splitlines()
            by_id = {
                movement: next(line for line in lines if movement in line) for movement in ("mv-01", "mv-02", "mv-03")
            }
            assert _served_label(PurchaseLedgerRow.CLAIMED) in by_id["mv-01"]
            assert _TRANSACTION in by_id["mv-01"]
            assert _served_label(PurchaseLedgerRow.NONE) in by_id["mv-02"]
            assert _served_label(PurchaseLedgerRow.UNSTATED) in by_id["mv-03"]
