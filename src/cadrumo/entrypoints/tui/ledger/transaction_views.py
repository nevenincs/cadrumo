"""Canonical transaction detail screen for Ledger."""

from __future__ import annotations

from typing import override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Input, Static

from ....application.ledger.models import ManualLedgerTransactionPatch
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....domain.transactions.models import Transaction
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from .models import LedgerRecordDoorsV1
from .workspace_presentation import door_refusal_text, ledger_workspace_page


class LedgerTransactionDetailScreen(LedgerWorkspaceScreen):
    """Read and edit one transaction through the shared manual operation."""

    def __init__(self, controller: LedgerWorkspaceController, doors: LedgerRecordDoorsV1, transaction_id: str) -> None:
        """Capture the selected transaction identity and bound door."""
        super().__init__(controller, id="ledger-transaction-detail-screen")
        self.doors = doors
        self.transaction_id = transaction_id
        self.baseline: Transaction | None = None
        self._busy = False
        self._reviewed_description: str | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(tr("tui.ledger.records.transaction_detail"), classes="cadrumo-banner")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static("", id="ledger-record-detail", markup=False)
            yield Static(tr("tui.ledger.column.description"), markup=False)
            yield Input(id="ledger-transaction-description")
            yield Button(tr("tui.ledger.invoice.review"), id="ledger-transaction-edit-review", disabled=True)
            yield Button(tr("tui.ledger.records.save"), id="ledger-transaction-edit-save", disabled=True)
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Read the transaction before enabling its detail form."""
        self.populate_navigation()
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.records.loading"))
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
                self.query_one("#ledger-refusal", Static).update(tr("tui.ledger.records.no_change"))
                return
            self._reviewed_description = description
            self.query_one("#ledger-transaction-description", Input).disabled = True
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.records.reviewed"))
            self.query_one("#ledger-transaction-edit-save", Button).disabled = False
        elif event.button.id == "ledger-transaction-edit-save" and self._reviewed_description is not None:
            self._busy = True
            self.query_one("#ledger-transaction-edit-save", Button).disabled = True
            self.query_one("#ledger-transaction-edit-review", Button).disabled = True
            self.run_worker(self._save(self.baseline, self._reviewed_description), exclusive=True)

    async def _save(self, baseline: Transaction, description: str) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        status.update(tr("tui.ledger.records.saving"))
        try:
            patch = ManualLedgerTransactionPatch(description=description)
            result = await self.doors.update_transaction(baseline, patch)
        except (CadrumoError, ValidationError) as error:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            status.update(tr("tui.ledger.records.failed"))
            self._busy = False
            self.query_one("#ledger-transaction-description", Input).disabled = False
            self.query_one("#ledger-transaction-edit-review", Button).disabled = False
            return
        status.update(tr("tui.ledger.records.saved"))
        self.transaction_id = result.transaction_id
        try:
            refreshed = await self.doors.transaction(self.transaction_id)
        except CadrumoError:
            status.update(tr("tui.ledger.flow.refresh_failed"))
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
                    f"{tr('tui.ledger.records.links')}: {transaction.invoice_id or '-'}",
                    f"{tr('tui.ledger.records.identity')}: {transaction.transaction_id}",
                    f"{tr('tui.ledger.records.source')}: {source}",
                )
            )
        )
        self.query_one("#ledger-transaction-description", Input).value = transaction.raw.description

    @override
    def action_back(self) -> None:
        if self._busy:
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.flow.in_flight_refusal"))
            return
        super().action_back()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Keep the pending transaction write on its original screen."""
        if self._busy:
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.flow.in_flight_refusal"))
            return
        self.handle_navigation_selection(event)


__all__ = ["LedgerTransactionDetailScreen"]
