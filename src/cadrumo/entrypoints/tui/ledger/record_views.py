"""Canonical invoice and transaction detail flows for the Ledger workspace."""

from __future__ import annotations

from typing import cast, override

from pydantic import ValidationError
from textual.app import App, ComposeResult
from textual.widgets import Button, DataTable, Input, Static

from ....application.invoices.catalogue_lifecycle import CatalogueInvoicePatch
from ....application.ledger.models import ManualLedgerTransactionPatch
from ....core.errors.hierarchy import CadrumoError
from ....domain.invoices.models import Invoice
from ....domain.transactions.models import Transaction
from ..components.widgets import ContentDataTable
from ..components.workspace_host import replace_workspace_body
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen, ledger_copy
from .record_doors import LedgerRecordDoors
from .workspace_presentation import door_refusal_text, ledger_workspace_page


class LedgerInvoiceCatalogueScreen(LedgerWorkspaceScreen):
    """Read the bucket's canonical invoices and open one by its full identity."""

    def __init__(self, controller: LedgerWorkspaceController, doors: LedgerRecordDoors) -> None:
        """Keep the injected bucket-bound door for every later selection."""
        super().__init__(controller, id="ledger-invoice-catalogue-screen")
        self.doors = doors

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.records.invoices"), classes="cadrumo-banner")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield ContentDataTable[str](id="ledger-invoice-catalogue", cursor_type="row", zebra_stripes=True)
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Show headings and load canonical invoices without blocking the UI."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#ledger-invoice-catalogue", DataTable))
        table.add_columns(
            ledger_copy("tui.ledger.invoice.field.invoice_number"),
            ledger_copy("tui.ledger.invoice.field.invoice_date"),
            ledger_copy("tui.ledger.invoice.field.counterparty_name"),
            ledger_copy("tui.ledger.column.amount"),
        )
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        status.update(ledger_copy("tui.ledger.records.loading"))
        try:
            invoices = await self.doors.invoices()
        except CadrumoError as error:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
        else:
            table = cast("DataTable[str]", self.query_one("#ledger-invoice-catalogue", DataTable))
            for invoice in invoices:
                table.add_row(
                    invoice.invoice_number,
                    invoice.issued_at.isoformat(),
                    invoice.counterparty_name,
                    f"{invoice.grand_total} {invoice.currency}",
                    key=invoice.invoice_id,
                )
            table.focus()
        finally:
            status.update("")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the selected invoice by its stable catalogue identity."""
        if self.handle_navigation_selection(event):
            return
        if event.data_table.id == "ledger-invoice-catalogue" and event.row_key.value is not None:
            replace_workspace_body(
                cast("App[object]", self.app),
                LedgerInvoiceDetailScreen(self.controller, self.doors, str(event.row_key.value)),
            )


class LedgerInvoiceDetailScreen(LedgerWorkspaceScreen):
    """Read an invoice, then submit a supported notes patch against its baseline."""

    def __init__(self, controller: LedgerWorkspaceController, doors: LedgerRecordDoors, invoice_id: str) -> None:
        """Capture the selected invoice and door before any navigation changes."""
        super().__init__(controller, id="ledger-invoice-detail-screen")
        self.doors = doors
        self.invoice_id = invoice_id
        self.baseline: Invoice | None = None
        self._busy = False
        self._reviewed_notes: str | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.records.invoice_detail"), classes="cadrumo-banner")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static("", id="ledger-record-detail", markup=False)
            yield Static(ledger_copy("tui.ledger.invoice.field.notes"), markup=False)
            yield Input(id="ledger-invoice-notes")
            yield Button(ledger_copy("tui.ledger.invoice.review"), id="ledger-invoice-edit-review", disabled=True)
            yield Button(ledger_copy("tui.ledger.records.save"), id="ledger-invoice-edit-save", disabled=True)
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Read the current canonical baseline before enabling an update."""
        self.populate_navigation()
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.records.loading"))
        try:
            invoice = await self.doors.invoice(self.invoice_id)
        except CadrumoError as error:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
        else:
            self._show_invoice(invoice)
            self.query_one("#ledger-invoice-edit-review", Button).disabled = False
        finally:
            self.query_one("#ledger-flow-status", Static).update("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Review the note change, then write only the reviewed value."""
        if self._busy or self.baseline is None:
            return
        if event.button.id == "ledger-invoice-edit-review":
            notes = self.query_one("#ledger-invoice-notes", Input).value
            if notes == self.baseline.notes:
                self.query_one("#ledger-refusal", Static).update(ledger_copy("tui.ledger.records.no_change"))
                return
            self._reviewed_notes = notes
            self.query_one("#ledger-invoice-notes", Input).disabled = True
            self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.records.reviewed"))
            self.query_one("#ledger-invoice-edit-save", Button).disabled = False
        elif event.button.id == "ledger-invoice-edit-save" and self._reviewed_notes is not None:
            self._busy = True
            self.query_one("#ledger-invoice-edit-save", Button).disabled = True
            self.query_one("#ledger-invoice-edit-review", Button).disabled = True
            self.run_worker(self._save(self.baseline, self._reviewed_notes), exclusive=True)

    async def _save(self, baseline: Invoice, notes: str) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        status.update(ledger_copy("tui.ledger.records.saving"))
        try:
            patch = CatalogueInvoicePatch(notes=notes)
            await self.doors.update_invoice(baseline, patch)
        except (CadrumoError, ValidationError) as error:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            status.update(ledger_copy("tui.ledger.records.failed"))
            self._busy = False
            self.query_one("#ledger-invoice-notes", Input).disabled = False
            self.query_one("#ledger-invoice-edit-review", Button).disabled = False
            return
        status.update(ledger_copy("tui.ledger.records.saved"))
        try:
            refreshed = await self.doors.invoice(self.invoice_id)
        except CadrumoError:
            status.update(ledger_copy("tui.ledger.flow.refresh_failed"))
        else:
            self._show_invoice(refreshed)
            self._reviewed_notes = None
            self.query_one("#ledger-invoice-notes", Input).disabled = False
            self.query_one("#ledger-invoice-edit-review", Button).disabled = False
        self._busy = False

    def _show_invoice(self, invoice: Invoice) -> None:
        """Render one canonical invoice returned by the shared read operation."""
        self.baseline = invoice
        linked_ids = ", ".join(invoice.linked_transaction_ids) or "-"
        source = (
            f"{invoice.provenance.source_path.name}:{invoice.provenance.source_row_index}"
            if invoice.provenance is not None
            else "-"
        )
        self.query_one("#ledger-record-detail", Static).update(
            "\n".join(
                (
                    f"{invoice.kind.value} · {invoice.invoice_number} · {invoice.issued_at.isoformat()}",
                    f"{invoice.counterparty_name} · {invoice.counterparty_tax_id or '-'}",
                    f"{invoice.base_total} + {invoice.iva_total} = {invoice.grand_total} {invoice.currency}",
                    f"{ledger_copy('tui.ledger.records.links')}: {linked_ids}",
                    f"{ledger_copy('tui.ledger.records.source')}: {source}",
                )
            )
        )
        self.query_one("#ledger-invoice-notes", Input).value = invoice.notes

    @override
    def action_back(self) -> None:
        if self._busy:
            self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.flow.in_flight_refusal"))
            return
        super().action_back()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Refuse navigation while a write is in flight."""
        if self._busy:
            self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.flow.in_flight_refusal"))
            return
        self.handle_navigation_selection(event)


class LedgerTransactionDetailScreen(LedgerWorkspaceScreen):
    """Read and edit one transaction through the shared manual operation."""

    def __init__(self, controller: LedgerWorkspaceController, doors: LedgerRecordDoors, transaction_id: str) -> None:
        """Capture the selected transaction identity and bound door."""
        super().__init__(controller, id="ledger-transaction-detail-screen")
        self.doors = doors
        self.transaction_id = transaction_id
        self.baseline: Transaction | None = None
        self._busy = False
        self._reviewed_description: str | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.records.transaction_detail"), classes="cadrumo-banner")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static("", id="ledger-record-detail", markup=False)
            yield Static(ledger_copy("tui.ledger.column.description"), markup=False)
            yield Input(id="ledger-transaction-description")
            yield Button(ledger_copy("tui.ledger.invoice.review"), id="ledger-transaction-edit-review", disabled=True)
            yield Button(ledger_copy("tui.ledger.records.save"), id="ledger-transaction-edit-save", disabled=True)
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Read the transaction before enabling its detail form."""
        self.populate_navigation()
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.records.loading"))
        try:
            transaction = await self.doors.transaction(self.transaction_id)
        except CadrumoError as error:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
        else:
            self._show_transaction(transaction)
            self.query_one("#ledger-transaction-edit-review", Button).disabled = False
        finally:
            self.query_one("#ledger-flow-status", Static).update("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Review one description edit, then submit it once."""
        if self._busy or self.baseline is None:
            return
        if event.button.id == "ledger-transaction-edit-review":
            description = self.query_one("#ledger-transaction-description", Input).value.strip()
            if not description or description == self.baseline.raw.description:
                self.query_one("#ledger-refusal", Static).update(ledger_copy("tui.ledger.records.no_change"))
                return
            self._reviewed_description = description
            self.query_one("#ledger-transaction-description", Input).disabled = True
            self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.records.reviewed"))
            self.query_one("#ledger-transaction-edit-save", Button).disabled = False
        elif event.button.id == "ledger-transaction-edit-save" and self._reviewed_description is not None:
            self._busy = True
            self.query_one("#ledger-transaction-edit-save", Button).disabled = True
            self.query_one("#ledger-transaction-edit-review", Button).disabled = True
            self.run_worker(self._save(self.baseline, self._reviewed_description), exclusive=True)

    async def _save(self, baseline: Transaction, description: str) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        status.update(ledger_copy("tui.ledger.records.saving"))
        try:
            patch = ManualLedgerTransactionPatch(description=description)
            result = await self.doors.update_transaction(baseline, patch)
        except (CadrumoError, ValidationError) as error:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            status.update(ledger_copy("tui.ledger.records.failed"))
            self._busy = False
            self.query_one("#ledger-transaction-description", Input).disabled = False
            self.query_one("#ledger-transaction-edit-review", Button).disabled = False
            return
        status.update(ledger_copy("tui.ledger.records.saved"))
        self.transaction_id = result.transaction_id
        try:
            refreshed = await self.doors.transaction(self.transaction_id)
        except CadrumoError:
            status.update(ledger_copy("tui.ledger.flow.refresh_failed"))
        else:
            self._show_transaction(refreshed)
            self._reviewed_description = None
            self.query_one("#ledger-transaction-description", Input).disabled = False
            self.query_one("#ledger-transaction-edit-review", Button).disabled = False
        self._busy = False

    def _show_transaction(self, transaction: Transaction) -> None:
        """Render one canonical transaction returned by the shared read operation."""
        self.baseline = transaction
        source = (
            f"{transaction.raw.provenance.source_path.name}:{transaction.raw.provenance.source_row_index}"
            if transaction.created_event_id is None
            else "-"
        )
        self.query_one("#ledger-record-detail", Static).update(
            "\n".join(
                (
                    f"{transaction.raw.booked_date} · {transaction.raw.description}",
                    f"{transaction.direction.value} · {transaction.raw.amount} {transaction.raw.currency}",
                    f"{ledger_copy('tui.ledger.records.links')}: {transaction.invoice_id or '-'}",
                    f"{ledger_copy('tui.ledger.records.identity')}: {transaction.transaction_id}",
                    f"{ledger_copy('tui.ledger.records.source')}: {source}",
                )
            )
        )
        self.query_one("#ledger-transaction-description", Input).value = transaction.raw.description

    @override
    def action_back(self) -> None:
        if self._busy:
            self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.flow.in_flight_refusal"))
            return
        super().action_back()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Keep the pending transaction write on its original screen."""
        if self._busy:
            self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.flow.in_flight_refusal"))
            return
        self.handle_navigation_selection(event)


__all__ = ["LedgerInvoiceCatalogueScreen", "LedgerInvoiceDetailScreen", "LedgerTransactionDetailScreen"]
