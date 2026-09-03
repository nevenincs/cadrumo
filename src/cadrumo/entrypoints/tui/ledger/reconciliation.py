"""Local Ledger invoice reconciliation and affected-declaration surface."""

from __future__ import annotations

from typing import cast, override

from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Static

from ....core.identity import InvoiceId, TransactionId
from ..components.widgets import ContentDataTable
from .controller import LedgerWorkspaceController, ledger_copy
from .models import LedgerFlowState
from .workspace_presentation import LedgerConfirmationFlowScreen, ledger_workspace_page


class LedgerReconciliationScreen(LedgerConfirmationFlowScreen):
    """Render local-only reconciliation and submit admitted visible links."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain the injected safe workspace projection and link door."""
        super().__init__(controller, id="ledger-reconciliation-screen")
        self.selected_pair: tuple[TransactionId, InvoiceId] | None = None

    FLOW_NAME = "reconciliation"

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.reconciliation.title"), classes="cadrumo-banner")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static(ledger_copy("tui.ledger.reconciliation.local_only"), markup=False)
            yield ContentDataTable[str](id="ledger-suggestions", cursor_type="row", zebra_stripes=True)
            yield Static(ledger_copy("tui.ledger.reconciliation.inconsistencies"), markup=False)
            yield ContentDataTable[str](id="ledger-inconsistencies", cursor_type="row", zebra_stripes=True)
            yield Static(ledger_copy("tui.ledger.reconciliation.affected"), markup=False)
            yield ContentDataTable[str](id="ledger-affected", cursor_type="row", zebra_stripes=True)
            yield Static("", id="ledger-flow-status", markup=False)
            yield Button(
                ledger_copy("tui.ledger.reconciliation.confirm"),
                id="ledger-reconciliation-confirm",
                disabled=True,
            )
            yield Button(ledger_copy("tui.ledger.reconciliation.cancel"), id="ledger-reconciliation-cancel")
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate all three local authorities without joining remote AEAT state."""
        self.populate_navigation()
        suggestions = cast("DataTable[str]", self.query_one("#ledger-suggestions", DataTable))
        suggestions.add_column(ledger_copy("tui.ledger.reconciliation.entry"), key="entry", width=12)
        suggestions.add_column(ledger_copy("tui.ledger.reconciliation.invoice"), key="invoice", width=12)
        suggestions.add_column(ledger_copy("tui.ledger.reconciliation.match_evidence"), key="evidence", width=38)
        for row in self.controller.projection.invoice_reconciliations:
            key = f"{row.transaction_id}:{row.invoice_id}"
            yes = ledger_copy("tui.ledger.reconciliation.yes")
            no = ledger_copy("tui.ledger.reconciliation.no")
            evidence = "\n".join(
                (
                    f"{ledger_copy('tui.ledger.reconciliation.score')}: {row.score}",
                    f"{ledger_copy('tui.ledger.reconciliation.amount_match')}: {yes if row.amount_match else no}",
                    f"{ledger_copy('tui.ledger.reconciliation.counterparty_match')}: "
                    f"{yes if row.counterparty_match else no}",
                )
            )
            suggestions.add_row(
                str(row.transaction_id)[:12],
                str(row.invoice_id)[:12],
                evidence,
                key=key,
                height=3,
            )
        inconsistencies = cast("DataTable[str]", self.query_one("#ledger-inconsistencies", DataTable))
        inconsistencies.add_column(ledger_copy("tui.ledger.reconciliation.entry"), width=12)
        inconsistencies.add_column(ledger_copy("tui.ledger.reconciliation.invoice"), width=12)
        inconsistencies.add_column(ledger_copy("tui.ledger.reconciliation.direction"), width=30)
        for row in self.controller.projection.link_inconsistencies:
            direction_keys = {
                "invoice-only": "tui.ledger.reconciliation.direction.invoice_only",
                "transaction-only": "tui.ledger.reconciliation.direction.transaction_only",
            }
            direction_key = direction_keys.get(row.direction)
            if direction_key is None:
                raise ValueError("unsupported canonical link inconsistency direction")
            inconsistencies.add_row(
                str(row.transaction_id)[:12],
                str(row.invoice_id)[:12],
                ledger_copy(direction_key),
                key=f"{row.transaction_id}:{row.invoice_id}",
            )
        affected = cast("DataTable[str]", self.query_one("#ledger-affected", DataTable))
        affected.add_columns(
            ledger_copy("tui.ledger.reconciliation.modelo"),
            ledger_copy("tui.ledger.reconciliation.period"),
            ledger_copy("tui.ledger.reconciliation.changes"),
        )
        for row in self.controller.projection.affected_declarations:
            affected.add_row(
                str(row.modelo),
                str(row.period),
                f"{row.changed_count}/{row.removed_count}",
                key=str(row.calculation_revision_id),
            )
        if not (
            self.controller.projection.invoice_reconciliations
            or self.controller.projection.link_inconsistencies
            or self.controller.projection.affected_declarations
        ):
            self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.reconciliation.empty"))
        if not self.controller.can_submit_links():
            self.query_one("#ledger-reconciliation-confirm", Button).display = False
            self.query_one("#ledger-reconciliation-cancel", Button).display = False
        restored = self.controller.restored_transaction_id()
        if restored is not None:
            index = next(
                (
                    index
                    for index, row in enumerate(self.controller.projection.invoice_reconciliations)
                    if row.transaction_id == restored
                ),
                None,
            )
            if index is not None:
                suggestions.move_cursor(row=index)
        next((table for table in (suggestions, inconsistencies, affected) if table.row_count), suggestions).focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Admit only a semantic pair supplied by the visible suggestion projection."""
        if self.handle_navigation_selection(event):
            return
        table = cast("DataTable[str]", event.data_table)
        if self.flow_state is not LedgerFlowState.EDITING or table.id != "ledger-suggestions":
            return
        if not self.controller.can_submit_links():
            self.query_one("#ledger-flow-status", Static).update(
                ledger_copy("tui.ledger.refusal.submission_unavailable")
            )
            return
        semantic_key = str(event.row_key.value)
        source = next(
            (
                row
                for row in self.controller.projection.invoice_reconciliations
                if f"{row.transaction_id}:{row.invoice_id}" == semantic_key
            ),
            None,
        )
        if source is None:
            raise ValueError("selected reconciliation row is absent from the visible projection")
        self.selected_pair = (source.transaction_id, source.invoice_id)
        self._transition(LedgerFlowState.CONFIRMING)
        self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.reconciliation.confirming"))
        button = self.query_one("#ledger-reconciliation-confirm", Button)
        button.disabled = False
        button.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Submit once through the injected door or cancel before persistence."""
        if event.button.id == "ledger-reconciliation-cancel" and self.flow_state in {
            LedgerFlowState.EDITING,
            LedgerFlowState.CONFIRMING,
        }:
            self._cancel_flow()
            return
        if (
            self.flow_state is not LedgerFlowState.CONFIRMING
            or event.button.id != "ledger-reconciliation-confirm"
            or self.selected_pair is None
        ):
            return
        self._transition(LedgerFlowState.SUBMITTING)
        event.button.disabled = True
        self.query_one("#ledger-reconciliation-cancel", Button).disabled = True
        self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.reconciliation.progress"))
        self.run_worker(self._submit(), exclusive=True)

    async def _submit(self) -> None:
        pair = self.selected_pair
        if pair is None:  # pragma: no cover
            raise RuntimeError("reconciliation selection disappeared")
        status = self.query_one("#ledger-flow-status", Static)
        try:
            await self.controller.submit_link(*pair)
        except Exception:
            self._transition(LedgerFlowState.FAILED)
            status.update(ledger_copy("tui.ledger.reconciliation.failure"))
        else:
            self._transition(LedgerFlowState.SUCCEEDED)
            status.update(ledger_copy("tui.ledger.reconciliation.success"))

    @override
    def _cancel_flow(self) -> None:
        """Cancel only before the injected mutation begins."""
        if self.flow_state not in {LedgerFlowState.EDITING, LedgerFlowState.CONFIRMING}:
            return
        self._transition(LedgerFlowState.CANCELLED)
        self.selected_pair = None
        self.query_one("#ledger-reconciliation-confirm", Button).disabled = True
        self.query_one("#ledger-reconciliation-cancel", Button).disabled = True


__all__ = ["LedgerReconciliationScreen"]
