"""Invoice catalogue, record detail, invoice import and invoice wizard states for reviewing the shipped Ledger screens.

Each screen is driven through its own controls over in-memory doors that
answer with the registered operations' public projections. Every record is
synthetic; nothing is read from or written to storage.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from enum import StrEnum
from typing import cast, override

from textual.events import Mount
from textual.screen import Screen
from textual.widgets import Input, Select

from cadrumo.domain.iva.schema import InvoiceKind
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.ledger.controller import LedgerWorkspaceController
from cadrumo.entrypoints.tui.ledger.invoices_import import LedgerInvoiceImportScreen
from cadrumo.entrypoints.tui.ledger.invoices_wizard import LedgerInvoiceWizardScreen
from cadrumo.entrypoints.tui.ledger.models import LedgerRecordDoorsV1
from cadrumo.entrypoints.tui.ledger.record_views import LedgerInvoiceCatalogueScreen, LedgerInvoiceDetailScreen
from cadrumo.entrypoints.tui.ledger.tests.invoices_fixtures import (
    SYNTHETIC_SOURCE_PATH,
    MemoryInvoiceImportDoor,
    MemoryInvoiceWizardDoor,
    MemoryRecordDoors,
    invoice_snapshot,
    transaction_projection,
)
from cadrumo.entrypoints.tui.ledger.tests.workspace_fixtures import (
    ledger_context,
    ledger_projection,
    ledger_review_action,
)
from cadrumo.entrypoints.tui.ledger.transaction_views import LedgerTransactionDetailScreen
from cadrumo.entrypoints.tui.ledger.workspace_injection import LedgerWorkspaceInjection

from .settling import press_when_enabled, settle


class InvoicesFixtureState(StrEnum):
    """The reviewable states of the invoice and record screens."""

    CATALOGUE = "catalogue"
    CATALOGUE_EMPTY = "catalogue-empty"
    INVOICE_DETAIL = "invoice-detail"
    INVOICE_STAGED = "invoice-staged"
    INVOICE_REMOVE = "invoice-remove"
    TRANSACTION_DETAIL = "transaction-detail"
    TRANSACTION_STAGED = "transaction-staged"
    IMPORT_FORM = "import-form"
    IMPORT_REVIEW = "import-review"
    IMPORT_OUTCOME = "import-outcome"
    WIZARD_FIRST_STEP = "wizard-first-step"
    WIZARD_REVIEW = "wizard-review"
    WIZARD_REFUSED = "wizard-refused"


_INTERFACES = {
    "catalogue": "cadrumo.entrypoints.tui.ledger.record_views.LedgerInvoiceCatalogueScreen",
    "invoice": "cadrumo.entrypoints.tui.ledger.record_views.LedgerInvoiceDetailScreen",
    "transaction": "cadrumo.entrypoints.tui.ledger.transaction_views.LedgerTransactionDetailScreen",
    "import": "cadrumo.entrypoints.tui.ledger.invoices_import.LedgerInvoiceImportScreen",
    "wizard": "cadrumo.entrypoints.tui.ledger.invoices_wizard.LedgerInvoiceWizardScreen",
    "confirm": "cadrumo.entrypoints.tui.components.dialogs.ConfirmScreen",
}
_WIZARD_VALUES = {
    "counterparty_name": "Talleres Sintéticos SL",
    "counterparty_nif": "B00000000",
    "country_code": "ES",
    "invoice_number": "2026-0042",
    "invoice_date": "2026-03-15",
    "taxable_base": "250.00",
    "iva_rate": "21",
    "notes": "Revisión trimestral",
}


def _controller(doors: MemoryRecordDoors) -> LedgerWorkspaceController:
    return LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), record_doors=cast(LedgerRecordDoorsV1, doors)),
    )


class InvoicesCaptureHost(ScreenHostApp[None]):
    """Drive one production screen to a declared, settled review state."""

    def __init__(self, screen: Screen[None], drive: Callable[[InvoicesCaptureHost], object] | None = None) -> None:
        """Bind the production screen and the steps that reach the captured state."""
        super().__init__(screen)
        self.captured = screen
        self._drive = drive

    @override
    async def on_mount(self, event: Mount | None = None) -> None:
        # Mounted explicitly before driving, so Textual must not dispatch the
        # inherited handler a second time.
        if event is not None:
            event.prevent_default()
        await super().on_mount()
        await self.settle()
        if self._drive is not None:
            result = self._drive(self)
            if asyncio.iscoroutine(result):
                await result
            await self.settle()

    async def settle(self) -> None:
        """Wait until the screen has handled every posted message and finished every door call."""
        await settle(self)

    async def press(self, button_id: str) -> None:
        """Press one of the captured screen's buttons once it is enabled, and wait for what it started."""
        await press_when_enabled(self, button_id, within=self.captured)

    def type_into(self, selector: str, value: str) -> None:
        """Type a value into one of the captured screen's inputs."""
        self.captured.query_one(selector, Input).value = value


async def _stage_invoice(host: InvoicesCaptureHost) -> None:
    host.type_into("#ledger-invoice-notes", "Pagada por transferencia")
    cast("Select[str]", host.captured.query_one("#ledger-invoice-payment-status", Select)).value = "PAID"
    await host.press("ledger-invoice-edit-review")


async def _ask_remove(host: InvoicesCaptureHost) -> None:
    await host.press("ledger-invoice-remove")


async def _stage_transaction(host: InvoicesCaptureHost) -> None:
    host.type_into("#ledger-transaction-description", "Cuota mensual de software")
    await host.press("ledger-transaction-edit-review")


async def _review_import(host: InvoicesCaptureHost) -> None:
    cast(
        "Select[str]", host.captured.query_one("#ledger-invoices-import-kind", Select)
    ).value = InvoiceKind.RECEIVED.value
    host.type_into("#ledger-invoices-import-path", SYNTHETIC_SOURCE_PATH)
    host.type_into("#ledger-invoices-import-country", "ES")
    await host.press("ledger-invoices-import-review")


async def _import_outcome(host: InvoicesCaptureHost) -> None:
    await _review_import(host)
    await host.press("ledger-invoices-import-confirm")


async def _review_wizard(host: InvoicesCaptureHost) -> None:
    for name, value in _WIZARD_VALUES.items():
        host.type_into(f"#ledger-invoices-wizard-{name.replace('_', '-')}", value)
    for _ in range(3):
        await host.press("ledger-invoices-wizard-next")
    await host.press("ledger-invoices-wizard-review")


async def _refused_wizard(host: InvoicesCaptureHost) -> None:
    await _review_wizard(host)
    await host.press("ledger-invoices-wizard-confirm")


def build_invoices_fixture(state: InvoicesFixtureState) -> InvoicesCaptureHost:
    """Open the screen a state belongs to over synthetic in-memory doors and drive it there."""
    invoices = tuple(
        invoice_snapshot(index, kind=(InvoiceKind.RECEIVED, InvoiceKind.ISSUED)[index % 2]) for index in range(12)
    )
    doors = MemoryRecordDoors(
        () if state is InvoicesFixtureState.CATALOGUE_EMPTY else invoices,
        (transaction_projection(invoice_id=invoices[0].invoice_id),),
    )
    controller = _controller(doors)
    record_doors = cast(LedgerRecordDoorsV1, doors)
    if state in {InvoicesFixtureState.CATALOGUE, InvoicesFixtureState.CATALOGUE_EMPTY}:
        return InvoicesCaptureHost(LedgerInvoiceCatalogueScreen(controller, record_doors))
    if state in {
        InvoicesFixtureState.INVOICE_DETAIL,
        InvoicesFixtureState.INVOICE_STAGED,
        InvoicesFixtureState.INVOICE_REMOVE,
    }:
        drive = {
            InvoicesFixtureState.INVOICE_STAGED: _stage_invoice,
            InvoicesFixtureState.INVOICE_REMOVE: _ask_remove,
        }.get(state)
        return InvoicesCaptureHost(LedgerInvoiceDetailScreen(controller, record_doors, invoices[0].invoice_id), drive)
    if state in {InvoicesFixtureState.TRANSACTION_DETAIL, InvoicesFixtureState.TRANSACTION_STAGED}:
        screen = LedgerTransactionDetailScreen(controller, record_doors, transaction_projection().transaction_id)
        return InvoicesCaptureHost(
            screen, _stage_transaction if state is InvoicesFixtureState.TRANSACTION_STAGED else None
        )
    if state in {
        InvoicesFixtureState.IMPORT_FORM,
        InvoicesFixtureState.IMPORT_REVIEW,
        InvoicesFixtureState.IMPORT_OUTCOME,
    }:
        drive = {
            InvoicesFixtureState.IMPORT_REVIEW: _review_import,
            InvoicesFixtureState.IMPORT_OUTCOME: _import_outcome,
        }.get(state)
        return InvoicesCaptureHost(LedgerInvoiceImportScreen(controller, MemoryInvoiceImportDoor()), drive)
    wizard_door = MemoryInvoiceWizardDoor()
    if state is InvoicesFixtureState.WIZARD_REFUSED:
        wizard_door.refused_fields = (("invoice_date", "must be a date on or before today"),)
    drive = {
        InvoicesFixtureState.WIZARD_REVIEW: _review_wizard,
        InvoicesFixtureState.WIZARD_REFUSED: _refused_wizard,
    }.get(state)
    return InvoicesCaptureHost(LedgerInvoiceWizardScreen(controller, wizard_door), drive)


def invoices_fixture_interfaces(state: InvoicesFixtureState) -> tuple[str, ...]:
    """The production screen each state shows."""
    if state.value.startswith("catalogue"):
        return (_INTERFACES["catalogue"],)
    if state is InvoicesFixtureState.INVOICE_REMOVE:
        # The removal question is asked in a dialog over the invoice it names.
        return (_INTERFACES["invoice"], _INTERFACES["confirm"])
    return (_INTERFACES[state.value.split("-")[0]],)


__all__ = ["InvoicesCaptureHost", "InvoicesFixtureState", "build_invoices_fixture", "invoices_fixture_interfaces"]
