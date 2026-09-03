"""Local Ledger invoice reconciliation and affected-declaration surface."""

from __future__ import annotations

from typing import cast, override

from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Static

from ....core.identity import InvoiceId, TransactionId
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen, ledger_copy
from .models import LedgerFlowState


class LedgerReconciliationScreen(LedgerWorkspaceScreen):
    """Render local-only reconciliation and submit admitted visible links."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain the injected safe workspace projection and link door."""
        super().__init__(controller, id="ledger-reconciliation-screen")
        self._flow_state = LedgerFlowState.EDITING
        self.selected_pair: tuple[TransactionId, InvoiceId] | None = None

    @property
    def flow_state(self) -> LedgerFlowState:
        """Expose the guarded link lifecycle."""
        return self._flow_state

    def _transition(self, target: LedgerFlowState) -> None:
        allowed = {
            LedgerFlowState.EDITING: {LedgerFlowState.CONFIRMING, LedgerFlowState.CANCELLED},
            LedgerFlowState.CONFIRMING: {LedgerFlowState.SUBMITTING, LedgerFlowState.CANCELLED},
            LedgerFlowState.SUBMITTING: {LedgerFlowState.SUCCEEDED, LedgerFlowState.FAILED},
        }
        if target not in allowed.get(self._flow_state, set()):
            raise RuntimeError("invalid reconciliation flow transition")
        self._flow_state = target

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.reconciliation.title"), classes="cadrumo-banner")
        with ContentScroll(id="ledger-page", classes="cadrumo-scroll ledger-page"):
            yield ContentDataTable[str](id="ledger-navigation", cursor_type="row", zebra_stripes=True)
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
        suggestions.add_columns(
            ledger_copy("tui.ledger.reconciliation.entry"),
            ledger_copy("tui.ledger.reconciliation.invoice"),
            ledger_copy("tui.ledger.reconciliation.match"),
        )
        for row in self.controller.projection.invoice_reconciliations:
            key = f"{row.transaction_id}:{row.invoice_id}"
            match_key = (
                "tui.ledger.reconciliation.match.full"
                if row.amount_match and row.counterparty_match
                else "tui.ledger.reconciliation.match.partial"
            )
            suggestions.add_row(
                str(row.transaction_id)[:12],
                str(row.invoice_id)[:12],
                ledger_copy(match_key),
                key=key,
            )
        inconsistencies = cast("DataTable[str]", self.query_one("#ledger-inconsistencies", DataTable))
        inconsistencies.add_columns(
            ledger_copy("tui.ledger.reconciliation.entry"), ledger_copy("tui.ledger.reconciliation.invoice")
        )
        for row in self.controller.projection.link_inconsistencies:
            inconsistencies.add_row(
                str(row.transaction_id)[:12],
                str(row.invoice_id)[:12],
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
        suggestions.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Admit only a semantic pair supplied by the visible suggestion projection."""
        if self.handle_navigation_selection(event):
            return
        table = cast("DataTable[str]", event.data_table)
        if self.flow_state is not LedgerFlowState.EDITING or table.id != "ledger-suggestions":
            return
        index = event.cursor_row
        source = self.controller.projection.invoice_reconciliations[index]
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
            self._transition(LedgerFlowState.CANCELLED)
            event.button.disabled = True
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
    def action_back(self) -> None:
        if self.flow_state is LedgerFlowState.SUBMITTING:
            self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.flow.in_flight_refusal"))
            return
        super().action_back()


__all__ = ["LedgerReconciliationScreen"]
