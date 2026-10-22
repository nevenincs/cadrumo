"""Add entry, Export entries, Ledger status and checks, and Reset ledger over the real request models."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Input, Select, Static

from .....application.export.tabular import ExportSerializationFormat
from .....application.ledger.check_operation import LedgerCheckRequest
from .....application.ledger.export_operation import LedgerExportRequest
from .....application.ledger.ledger_add_contracts import LedgerAddRequest
from .....application.ledger.list_operation import LedgerListRequest
from .....application.ledger.reset_operation import LedgerResetRequest
from .....application.ledger.status_operation import LedgerStatusRequest
from .....application.operations.public_period import PublicPeriod
from .....core.config import override_settings
from .....core.i18n.render import tr
from .....core.operations import OperationEffect
from ...components.dialogs import ConfirmScreen
from ..entries_add import LedgerEntryAddScreen
from ..entries_browse import LedgerEntriesBrowseScreen
from ..entries_export import LedgerEntriesExportScreen
from ..entries_health import LedgerHealthScreen
from ..entries_reset import LedgerResetScreen
from ..models import LedgerFlowState
from .entries_door_fixtures import REFUSED_ADD_AMOUNT, MemoryEntriesLedger, entries_controller
from .test_ledger_selection_journey import _WorkspaceHostApp

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


async def _settle(pilot: Pilot[None]) -> None:
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def _press(pilot: Pilot[None], screen: Screen[None], button_id: str) -> None:
    screen.query_one(f"#{button_id}", Button).press()
    await _settle(pilot)


def _text(screen: Screen[None], selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


def _type(screen: Screen[None], values: dict[str, str]) -> None:
    for selector, value in values.items():
        screen.query_one(selector, Input).value = value


_REQUIRED = {
    "#entries-add-booked-date": "2026-03-14",
    "#entries-add-amount": "120.50",
    "#entries-add-description": "Material de oficina",
}


@pytest.mark.asyncio
async def test_an_entry_with_only_the_required_facts_is_reviewed_then_added() -> None:
    ledger = MemoryEntriesLedger.with_entries(2)
    screen = LedgerEntryAddScreen(entries_controller(), ledger.doors())
    app = _WorkspaceHostApp(screen)
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            _type(screen, _REQUIRED)
            await _press(pilot, screen, "entries-add-review")
            assert screen.flow_state is LedgerFlowState.CONFIRMING
            assert ledger.requested("add") == []
            assert "Material de oficina" in _text(screen, "#entries-add-summary")
            await _press(pilot, screen, "entries-add-confirm")
            assert screen.flow_state is LedgerFlowState.SUCCEEDED
            assert screen.query_one("#entries-add-open", Button).has_class("-open")

            await _press(pilot, screen, "entries-add-open")
            await _settle(pilot)
            browse = app.screen
            assert isinstance(browse, LedgerEntriesBrowseScreen)
            assert browse.selected_id is not None
    [request] = [cast(LedgerAddRequest, request) for request in ledger.requested("add")]
    assert (request.booked_date, request.amount, request.direction, request.description) == (
        "2026-03-14",
        "120.50",
        "OUTGOING",
        "Material de oficina",
    )
    assert request.business_classification == "NOT_YET_PROCESSED"
    assert request.taxable_base is None
    browse_request = cast(LedgerListRequest, ledger.requested("list")[0])
    assert browse_request.filters == ("period=03", "year=2026")


@pytest.mark.asyncio
async def test_a_negative_amount_is_refused_by_the_request_before_review() -> None:
    ledger = MemoryEntriesLedger()
    screen = LedgerEntryAddScreen(entries_controller(), ledger.doors())
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            _type(screen, {**_REQUIRED, "#entries-add-amount": "-120.50"})
            await _press(pilot, screen, "entries-add-review")
            assert screen.flow_state is LedgerFlowState.EDITING
            assert "non-negative magnitude" in _text(screen, "#ledger-refusal")
    assert ledger.requests == []


@pytest.mark.asyncio
async def test_the_workers_refusal_is_shown_and_the_entry_can_be_edited_again() -> None:
    ledger = MemoryEntriesLedger()
    screen = LedgerEntryAddScreen(entries_controller(), ledger.doors())
    app = _WorkspaceHostApp(screen)
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            _type(screen, {**_REQUIRED, "#entries-add-amount": REFUSED_ADD_AMOUNT})
            await _press(pilot, screen, "entries-add-review")
            await _press(pilot, screen, "entries-add-confirm")
            assert screen.flow_state is LedgerFlowState.FAILED
            refusal = _text(screen, "#ledger-refusal")
            assert tr("tui.ledger.entry_tools.add.refused") in refusal
            assert "amount refused by the ledger" in refusal
            assert ledger.entries == []

            await _press(pilot, screen, "entries-add-again")
            await _settle(pilot)
            again = app.screen
            assert isinstance(again, LedgerEntryAddScreen)
            assert again.query_one("#entries-add-amount", Input).value == REFUSED_ADD_AMOUNT
            assert again.flow_state is LedgerFlowState.EDITING


@pytest.mark.asyncio
async def test_a_cancelled_entry_writes_nothing() -> None:
    ledger = MemoryEntriesLedger()
    screen = LedgerEntryAddScreen(entries_controller(), ledger.doors())
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            _type(screen, _REQUIRED)
            await _press(pilot, screen, "entries-add-review")
            await _press(pilot, screen, "entries-add-cancel")
            assert screen.flow_state is LedgerFlowState.CANCELLED
    assert ledger.requested("add") == []


@pytest.mark.asyncio
async def test_optional_tax_facts_reach_the_request_only_when_typed() -> None:
    ledger = MemoryEntriesLedger()
    screen = LedgerEntryAddScreen(entries_controller(), ledger.doors())
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            _type(
                screen,
                {**_REQUIRED, "#entries-add-taxable-base": "100.00", "#entries-add-iva-rate": "0.21"},
            )
            cast("Select[str]", screen.query_one("#entries-add-business-classification", Select)).value = "BUSINESS"
            cast("Select[str]", screen.query_one("#entries-add-direction", Select)).value = "INCOMING"
            await _press(pilot, screen, "entries-add-review")
            await _press(pilot, screen, "entries-add-confirm")
    [request] = [cast(LedgerAddRequest, request) for request in ledger.requested("add")]
    assert (request.taxable_base, request.iva_rate, request.iva_amount) == ("100.00", "0.21", None)
    assert (request.business_classification, request.direction) == ("BUSINESS", "INCOMING")


def _export_path(tmp_path: Path) -> str:
    return str(tmp_path / "ledger.csv")


@pytest.mark.asyncio
async def test_export_to_a_typed_path_reports_what_was_written(tmp_path: Path) -> None:
    ledger = MemoryEntriesLedger.with_entries(2)
    screen = LedgerEntriesExportScreen(entries_controller(), ledger.doors())
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            _type(screen, {"#entries-export-path": _export_path(tmp_path), "#entries-export-year": "2026"})
            cast("Select[str]", screen.query_one("#entries-export-period", Select)).value = "1T"
            screen.query_one("#entries-export-inactive", Checkbox).value = True
            await _press(pilot, screen, "entries-export-review")
            assert ledger.requested("export") == []
            await _press(pilot, screen, "entries-export-confirm")
            assert screen.flow_state is LedgerFlowState.SUCCEEDED
            assert tr("tui.ledger.entry_tools.export.written", path=_export_path(tmp_path)) in _text(
                screen, "#ledger-flow-status"
            )
    [request] = [cast(LedgerExportRequest, request) for request in ledger.requested("export")]
    assert request.output_path == _export_path(tmp_path)
    assert request.export_format is ExportSerializationFormat.CSV
    assert request.period == PublicPeriod(filing_year=2026, code="1T")
    assert request.include_inactive


@pytest.mark.asyncio
async def test_a_partial_export_says_partial(tmp_path: Path) -> None:
    ledger = MemoryEntriesLedger.with_entries(2)
    ledger.export_effect = OperationEffect.PARTIAL
    screen = LedgerEntriesExportScreen(entries_controller(), ledger.doors())
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            _type(screen, {"#entries-export-path": _export_path(tmp_path)})
            await _press(pilot, screen, "entries-export-review")
            await _press(pilot, screen, "entries-export-confirm")
            status = _text(screen, "#ledger-flow-status")
            assert tr("tui.ledger.entry_tools.export.partial", path=_export_path(tmp_path)) in status
            assert tr("tui.ledger.entry_tools.export.written", path=_export_path(tmp_path)) not in status


@pytest.mark.asyncio
async def test_a_relative_export_path_is_refused_before_review() -> None:
    ledger = MemoryEntriesLedger.with_entries(2)
    screen = LedgerEntriesExportScreen(entries_controller(), ledger.doors())
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            _type(screen, {"#entries-export-path": "ledger.csv"})
            await _press(pilot, screen, "entries-export-review")
            assert screen.flow_state is LedgerFlowState.EDITING
            assert _text(screen, "#ledger-refusal") == tr("tui.ledger.entry_tools.export.path_invalid")
    assert ledger.requests == []


@pytest.mark.asyncio
async def test_a_refused_export_is_shown_with_its_registered_refusal(tmp_path: Path) -> None:
    ledger = MemoryEntriesLedger.with_entries(2)
    ledger.refuse_with_registered_error("export")
    screen = LedgerEntriesExportScreen(entries_controller(), ledger.doors())
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            _type(screen, {"#entries-export-path": _export_path(tmp_path)})
            await _press(pilot, screen, "entries-export-review")
            await _press(pilot, screen, "entries-export-confirm")
            assert screen.flow_state is LedgerFlowState.FAILED
            assert _text(screen, "#ledger-refusal") == tr("errors.refused.refused_cli_validation_boundary")


@pytest.mark.asyncio
async def test_status_and_checks_read_a_chosen_period_in_words() -> None:
    ledger = MemoryEntriesLedger.with_entries(4)
    screen = LedgerHealthScreen(entries_controller(), ledger.doors())
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            _type(screen, {"#entries-health-year": "2026"})
            cast("Select[str]", screen.query_one("#entries-health-period", Select)).value = "1T"
            await _press(pilot, screen, "entries-health-read")
            assert tr("tui.ledger.entry_tools.health.ready", checked=4) in _text(screen, "#entries-health-status")
            check = _text(screen, "#entries-health-check")
            assert tr("tui.ledger.entry_tools.health.not_ready", findings=1, checked=4) in check
            assert "Category is missing." in check
            assert tr("tui.ledger.entry_tools.health.ready", checked=4) in _text(screen, "#entries-health-preflight")
    period = PublicPeriod(filing_year=2026, code="1T")
    assert cast(LedgerStatusRequest, ledger.requested("status")[0]).period == period
    assert cast(LedgerCheckRequest, ledger.requested("check")[0]).period == period
    assert len(ledger.requested("preflight")) == 1


@pytest.mark.asyncio
async def test_without_a_period_readiness_is_not_measured_and_preflight_is_not_run() -> None:
    ledger = MemoryEntriesLedger.with_entries(4)
    screen = LedgerHealthScreen(entries_controller(), ledger.doors())
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            await _press(pilot, screen, "entries-health-read")
            assert tr("tui.ledger.entry_tools.health.not_measured") in _text(screen, "#entries-health-status")
            assert _text(screen, "#entries-health-preflight") == tr(
                "tui.ledger.entry_tools.health.preflight_needs_period"
            )
    assert ledger.requested("preflight") == []


@pytest.mark.asyncio
async def test_a_refused_status_read_is_shown() -> None:
    ledger = MemoryEntriesLedger.with_entries(1)
    ledger.refuse_with_registered_error("status")
    screen = LedgerHealthScreen(entries_controller(), ledger.doors())
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            await _press(pilot, screen, "entries-health-read")
            assert _text(screen, "#ledger-refusal") == tr("errors.refused.refused_cli_validation_boundary")
            assert _text(screen, "#entries-health-status") == ""


async def _preview_reset(pilot: Pilot[None], screen: LedgerResetScreen) -> None:
    _type(screen, {"#entries-reset-reason": "start over with a clean import"})
    await _press(pilot, screen, "entries-reset-preview-button")


@pytest.mark.asyncio
async def test_reset_runs_a_dry_run_first_and_a_declined_confirmation_writes_nothing() -> None:
    ledger = MemoryEntriesLedger.with_entries(5)
    screen = LedgerResetScreen(entries_controller(), ledger.doors())
    app = _WorkspaceHostApp(screen)
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            await _preview_reset(pilot, screen)
            assert tr("tui.ledger.entry_tools.reset.would_remove", count=5) in _text(screen, "#entries-reset-preview")
            await _press(pilot, screen, "entries-reset-run")
            dialog = app.screen
            assert isinstance(dialog, ConfirmScreen)
            assert str(dialog.query_one("#confirm-message", Static).render()) == tr(
                "tui.ledger.entry_tools.reset.confirm_message", count=5
            )
            dialog.query_one("#btn-confirm-cancel", Button).press()
            await _settle(pilot)
            assert screen.flow_state is LedgerFlowState.CANCELLED
            assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.entry_tools.reset.cancelled")
    assert [cast(LedgerResetRequest, request).dry_run for request in ledger.requested("reset")] == [True]
    assert len(ledger.entries) == 5


@pytest.mark.asyncio
async def test_a_confirmed_reset_runs_exactly_the_previewed_request() -> None:
    ledger = MemoryEntriesLedger.with_entries(5)
    screen = LedgerResetScreen(entries_controller(), ledger.doors())
    app = _WorkspaceHostApp(screen)
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            await _preview_reset(pilot, screen)
            await _press(pilot, screen, "entries-reset-run")
            app.screen.query_one("#btn-confirm-accept", Button).press()
            await _settle(pilot)
            assert screen.flow_state is LedgerFlowState.SUCCEEDED
            assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.entry_tools.reset.done", count=5)
    requests = [cast(LedgerResetRequest, request) for request in ledger.requested("reset")]
    assert [(request.dry_run, request.reason) for request in requests] == [
        (True, "start over with a clean import"),
        (False, "start over with a clean import"),
    ]
    assert ledger.entries == []


@pytest.mark.asyncio
async def test_reset_needs_a_reason_before_its_preview() -> None:
    ledger = MemoryEntriesLedger.with_entries(1)
    screen = LedgerResetScreen(entries_controller(), ledger.doors())
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            await _press(pilot, screen, "entries-reset-preview-button")
            assert _text(screen, "#ledger-refusal") == tr("tui.ledger.entry_tools.reset.reason_required")
            assert screen.query_one("#entries-reset-run", Button).disabled
    assert ledger.requests == []
