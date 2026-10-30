"""The inventory screen over the registered operations' own request and projection models."""

from __future__ import annotations

from datetime import date
from typing import cast

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Select, Static

from .....application.inventory.registered_evidence_operation import InventoryEvidenceAddRequest
from .....application.inventory.registered_requests import (
    InventoryAcquisitionCostRequest,
    InventoryClosingAuthorityRecordInput,
    InventoryClosingAuthorityRecordRequest,
    InventoryClosingValueRecordRequest,
    InventoryCreateRequest,
    InventoryListRequest,
    InventoryMovementAddRequest,
    InventoryRetireRequest,
    InventoryValuationPreviewRequest,
)
from .....application.operations.public_scalar import PublicDecimal
from .....core.config import override_settings
from .....core.i18n.render import tr
from .....domain.contribuyente.inventory.records import InventoryRetirementReason, MovementKind
from ...tests.settling import settle
from ..controller import LedgerWorkspaceController
from ..registers_inventory import INVENTORY_TOOL_KEY, LedgerInventoryDoorV1, LedgerInventoryScreen, inventory_tool
from ..registers_presentation import REGISTER_PAGE_SIZE
from ..workspace_injection import LedgerWorkspaceInjection
from .registers_fixtures import (
    REGISTERS_PROFILE_ID,
    SYNTHETIC_AUTHORITY_PATH,
    SYNTHETIC_CLOSING_FACTS_PATH,
    SYNTHETIC_PURCHASE_PATH,
    MemoryInventoryDoor,
    synthetic_acquisition_cost,
    synthetic_closing_authority,
    synthetic_closing_value_facts,
    synthetic_inventory_row,
)
from .workspace_fixtures import WorkspaceHostApp, ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _screen(door: MemoryInventoryDoor) -> LedgerInventoryScreen:
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    return LedgerInventoryScreen(controller, cast(LedgerInventoryDoorV1, door))


async def _press(pilot: Pilot[None], screen: LedgerInventoryScreen, button_id: str) -> None:
    screen.query_one(f"#{button_id}", Button).press()
    await settle(pilot)


def _text(screen: LedgerInventoryScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


def _keys(screen: LedgerInventoryScreen) -> list[str]:
    return [str(row.key.value) for row in screen.query_one("#inventory-list", DataTable).ordered_rows]


async def _choose(pilot: Pilot[None], screen: LedgerInventoryScreen, select_id: str, value: str) -> None:
    cast("Select[str]", screen.query_one(f"#{select_id}", Select)).value = value
    await settle(pilot)


def _fill(screen: LedgerInventoryScreen, **values: str) -> None:
    for name, value in values.items():
        screen.query_one(f"#inventory-{name.replace('_', '-')}", Input).value = value


async def _review_and_confirm(pilot: Pilot[None], screen: LedgerInventoryScreen) -> None:
    await _press(pilot, screen, "register-review")
    assert screen.staged is not None, _text(screen, "#ledger-refusal")
    await _press(pilot, screen, "register-confirm")


@pytest.mark.asyncio
async def test_create_add_a_movement_preview_and_record_a_closing_authority_each_show_their_result() -> None:
    door = MemoryInventoryDoor(closing_value="155.00", cogs="45.00")
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.registers.inventory.empty")

            await _choose(pilot, screen, "inventory-action", "create")
            await _choose(pilot, screen, "inventory-method", "pmp")
            _fill(screen, actividad="act-01", year="2026", opening="100.00")
            await _review_and_confirm(pilot, screen)
            assert door.requests[1] == InventoryCreateRequest(
                profile_id=REGISTERS_PROFILE_ID,
                actividad_id="act-01",
                year=2026,
                valuation_method="pmp",
                opening_stock=PublicDecimal(decimal="100.00"),
            )
            assert _keys(screen) == ["act-01|2026"]
            assert tr("tui.ledger.registers.inventory.done.create") in _text(screen, "#register-result")

            await _choose(pilot, screen, "inventory-action", "movement_add")
            assert screen.query_one("#inventory-movement-id-field").display
            assert not screen.query_one("#inventory-method-field").display
            await _choose(pilot, screen, "inventory-movement-kind", "purchase")
            _fill(
                screen,
                movement_id="mv-01",
                movement_date="2026-03-01",
                quantity="5",
                unit_cost="11.00",
                taxable_base="55.00",
                acquisition_path=SYNTHETIC_PURCHASE_PATH,
            )
            await _press(pilot, screen, "register-review")
            assert tr("tui.ledger.registers.inventory.source", path=SYNTHETIC_PURCHASE_PATH) in _text(
                screen, "#register-staged"
            )
            await _press(pilot, screen, "register-confirm")
            movement = next(request for request in door.requests if isinstance(request, InventoryMovementAddRequest))
            assert movement == InventoryMovementAddRequest(
                profile_id=REGISTERS_PROFILE_ID,
                actividad_id="act-01",
                year=2026,
                movement_id="mv-01",
                movement_date=date(2026, 3, 1),
                kind=MovementKind.PURCHASE,
                quantity=PublicDecimal(decimal="5"),
                unit_cost=PublicDecimal(decimal="11.00"),
                taxable_base=PublicDecimal(decimal="55.00"),
                acquisition_cost=InventoryAcquisitionCostRequest.from_domain(synthetic_acquisition_cost()),
            )
            assert screen.query_one("#inventory-list", DataTable).get_row_at(0)[4] == "1"

            await _choose(pilot, screen, "inventory-action", "valuation_preview")
            await _review_and_confirm(pilot, screen)
            assert isinstance(door.requests[-2], InventoryValuationPreviewRequest)
            # The closing value and cost of goods sold are the operation's own figures.
            assert _text(screen, "#register-result") == tr(
                "tui.ledger.registers.inventory.result.valuation",
                actividad="act-01",
                year=2026,
                method="pmp",
                closing="155.00",
                cogs="45.00",
            )

            await _choose(pilot, screen, "inventory-action", "closing_authority")
            _fill(screen, authority_path=SYNTHETIC_AUTHORITY_PATH)
            await _review_and_confirm(pilot, screen)
            closing = door.requests[-2]
            assert closing == InventoryClosingAuthorityRecordRequest(
                profile_id=REGISTERS_PROFILE_ID,
                actividad_id="act-01",
                year=2026,
                authority_record=InventoryClosingAuthorityRecordInput.from_domain(
                    synthetic_closing_authority("act-01", 2026)
                ),
            )
            result = _text(screen, "#register-result")
            assert tr("tui.ledger.registers.inventory.result.fingerprint", fingerprint="d" * 64) in result


@pytest.mark.asyncio
async def test_retire_shows_the_state_and_a_second_retirement_shows_its_keyed_refusal() -> None:
    door = MemoryInventoryDoor((synthetic_inventory_row("act-01", 2026),))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _choose(pilot, screen, "inventory-action", "retire")
            assert screen.query_one("#inventory-retirement-reason-field").display
            assert not screen.query_one("#inventory-correction-reason-field").display
            _fill(screen, actividad="act-01", year="2026")
            await _review_and_confirm(pilot, screen)

            request = door.requests[1]
            assert isinstance(request, InventoryRetireRequest)
            assert request.reason is InventoryRetirementReason.CREATED_IN_ERROR
            result = _text(screen, "#register-result")
            assert tr("application.inventory.workbench.done.applied") in result
            assert tr("application.inventory.workbench.state.retired") in result

            _fill(screen, actividad="act-01", year="2026")
            await _review_and_confirm(pilot, screen)
            assert door.requests[-2:][0] != request
            assert tr(
                "application.inventory.service.errors.inventory_already_retired",
                actividad_id="act-01",
                year="2026",
            ) in _text(screen, "#ledger-refusal")


@pytest.mark.asyncio
async def test_a_movement_for_an_absent_inventory_shows_the_registered_refusal() -> None:
    door = MemoryInventoryDoor()
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _choose(pilot, screen, "inventory-action", "movement_add")
            await _choose(pilot, screen, "inventory-movement-kind", "count")
            _fill(
                screen, actividad="act-09", year="2026", movement_id="mv-09", movement_date="2026-12-31", quantity="3"
            )
            await _review_and_confirm(pilot, screen)
            refusal = _text(screen, "#ledger-refusal")
            assert tr("tui.ledger.registers.inventory.refusal.activity_not_found") in refusal
            assert isinstance(screen.staged, InventoryMovementAddRequest)
            assert _keys(screen) == []


@pytest.mark.asyncio
async def test_a_second_inventory_for_the_same_activity_and_year_is_refused() -> None:
    door = MemoryInventoryDoor(rows=(synthetic_inventory_row("act-01"),))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            table = screen.query_one("#inventory-list", DataTable)
            table.focus()
            table.move_cursor(row=0)
            await pilot.press("enter")
            await settle(pilot)
            assert screen.query_one("#inventory-actividad", Input).value == "act-01"
            assert screen.query_one("#inventory-year", Input).value == "2026"
            await _review_and_confirm(pilot, screen)
            assert tr("tui.ledger.registers.inventory.refusal.activity_conflict") in _text(screen, "#ledger-refusal")
            assert len(door.rows) == 1


@pytest.mark.asyncio
async def test_an_unreadable_source_file_is_refused_before_anything_is_sent() -> None:
    door = MemoryInventoryDoor(rows=(synthetic_inventory_row("act-01"),))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _choose(pilot, screen, "inventory-action", "closing_authority")
            _fill(screen, actividad="act-01", year="2026", authority_path="missing.json")
            await _press(pilot, screen, "register-review")
            assert screen.staged is None
            assert _text(screen, "#ledger-refusal") == "unreadable: missing.json"
            assert door.requests == [InventoryListRequest(profile_id=REGISTERS_PROFILE_ID), "missing.json"]

            _fill(screen, authority_path="")
            await _press(pilot, screen, "register-review")
            field = tr("tui.ledger.registers.inventory.field.authority_record")
            assert _text(screen, "#ledger-refusal") == tr("tui.ledger.registers.required", field=field)


@pytest.mark.asyncio
async def test_an_impossible_movement_date_is_refused_before_anything_is_sent() -> None:
    door = MemoryInventoryDoor(rows=(synthetic_inventory_row("act-01"),))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _choose(pilot, screen, "inventory-action", "movement_add")
            _fill(
                screen, actividad="act-01", year="2026", movement_id="mv-01", movement_date="2026-02-30", quantity="1"
            )
            await _press(pilot, screen, "register-review")
            assert screen.staged is None
            field = tr("tui.ledger.registers.inventory.field.movement_date")
            assert _text(screen, "#ledger-refusal") == tr(
                "tui.ledger.registers.invalid_date", field=field, value="2026-02-30"
            )


@pytest.mark.asyncio
async def test_the_inventory_list_holds_one_page_of_a_thousand_rows_and_pages_both_ways() -> None:
    door = MemoryInventoryDoor(rows=tuple(synthetic_inventory_row(f"act-{index:04d}") for index in range(1200)))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            table = screen.query_one("#inventory-list", DataTable)
            assert table.row_count == REGISTER_PAGE_SIZE
            await _press(pilot, screen, "inventory-list-next")
            assert _keys(screen)[0] == f"act-{REGISTER_PAGE_SIZE:04d}|2026"
            await _press(pilot, screen, "inventory-list-previous")
            assert _keys(screen)[0] == "act-0000|2026"


def test_the_inventory_tool_attaches_to_the_overview() -> None:
    tool = inventory_tool(cast(LedgerInventoryDoorV1, MemoryInventoryDoor()))
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), tools=(tool,)),
    )
    assert tool.key == INVENTORY_TOOL_KEY
    assert isinstance(tool.build(controller), LedgerInventoryScreen)


@pytest.mark.asyncio
async def test_a_purchase_document_is_stored_with_no_inventory_chosen_and_no_digest_typed() -> None:
    door = MemoryInventoryDoor()
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _choose(pilot, screen, "inventory-action", "evidence_add")
            screen.query_one("#inventory-evidence-path", Input).value = "invoice.pdf"
            await _review_and_confirm(pilot, screen)
            assert any(
                isinstance(item, InventoryEvidenceAddRequest) and item.source_path == "invoice.pdf"
                for item in door.requests
            )
            assert f"document-{'d' * 64}" in _text(screen, "#register-result")


@pytest.mark.asyncio
async def test_a_closing_value_is_recorded_from_a_facts_file_with_no_fingerprint_typed() -> None:
    door = MemoryInventoryDoor(rows=(synthetic_inventory_row("act-01"),))
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _choose(pilot, screen, "inventory-action", "closing_value")
            _fill(screen, actividad="act-01", year="2026")
            screen.query_one("#inventory-closing-facts-path", Input).value = SYNTHETIC_CLOSING_FACTS_PATH
            await _review_and_confirm(pilot, screen)
            submitted = door.requests[-2]
            assert isinstance(submitted, InventoryClosingValueRecordRequest)
            assert submitted.facts == synthetic_closing_value_facts()
            assert (submitted.actividad_id, submitted.year) == ("act-01", 2026)
