"""Local Ledger invoice reconciliation and affected-declaration surface."""

from __future__ import annotations

from typing import cast, override

from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Static

from ....application.ledger.workspace import LedgerInvoiceReconciliationRefV1
from ....core.identity.hex_ids import InvoiceId
from ....core.identity.transaction_ids import TransactionId
from ....core.invoice_link import LinkInconsistencyDirection
from ..components.widgets import ContentDataTable
from .controller import LedgerWorkspaceController, ledger_copy
from .models import LedgerFlowState
from .workspace_presentation import LedgerConfirmationFlowScreen, ledger_workspace_page

#: Operator copy for each one-sided link direction, keyed by the canonical
#: value rather than a hand-typed string.
#:
#: The workspace projection flattens
#: :class:`~core.invoice_link.LinkInconsistencyDirection` to a bare ``str``
#: before it reaches this screen, so this mapping is the only place the
#: membership survives on the TUI side. A direction added to the enum and not
#: to this map reaches ``on_mount`` unrenderable and raises while the
#: reconciliation table is being built — the operator's screen fails to open
#: rather than showing the row it could not label. Keying off the enum keeps
#: that a red test instead of a render-time refusal.
DIRECTION_STATE_COPY_KEYS: dict[str, str] = {
    LinkInconsistencyDirection.INVOICE_ONLY.value: "tui.ledger.reconciliation.direction_state.invoice_only",
    LinkInconsistencyDirection.TRANSACTION_ONLY.value: "tui.ledger.reconciliation.direction_state.transaction_only",
}


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
            yield Static(
                ledger_copy("tui.ledger.reconciliation.suggestions"),
                classes="cadrumo-heading cadrumo-heading-lead",
                markup=False,
            )
            yield ContentDataTable[str](id="ledger-suggestions", cursor_type="row", zebra_stripes=True)
            yield Static(
                ledger_copy("tui.ledger.reconciliation.inconsistencies"),
                classes="cadrumo-heading",
                markup=False,
            )
            yield ContentDataTable[str](id="ledger-inconsistencies", cursor_type="row", zebra_stripes=True)
            yield Static(
                ledger_copy("tui.ledger.reconciliation.affected"),
                classes="cadrumo-heading",
                markup=False,
            )
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
        self._populate_suggestion_table(suggestions)
        inconsistencies = cast("DataTable[str]", self.query_one("#ledger-inconsistencies", DataTable))
        self._populate_inconsistency_table(inconsistencies)
        affected = cast("DataTable[str]", self.query_one("#ledger-affected", DataTable))
        self._populate_affected_declaration_table(affected)
        self._show_empty_state_if_needed()
        self._hide_submission_controls_if_unavailable()
        self._restore_suggestion_focus(suggestions)
        self._focus_first_populated_table(suggestions, inconsistencies, affected)

    def _populate_suggestion_table(self, table: DataTable[str]) -> None:
        """Render canonical match evidence and retain each semantic pair as its row key."""
        table.add_column(ledger_copy("tui.ledger.reconciliation.entry"), key="entry", width=12)
        table.add_column(ledger_copy("tui.ledger.reconciliation.invoice"), key="invoice", width=12)
        table.add_column(ledger_copy("tui.ledger.reconciliation.match_evidence"), key="evidence", width=38)
        for row in self.controller.projection.invoice_reconciliations:
            table.add_row(
                str(row.transaction_id)[:12],
                str(row.invoice_id)[:12],
                self._match_evidence(row),
                key=f"{row.transaction_id}:{row.invoice_id}",
                height=3,
            )

    @staticmethod
    def _match_evidence(row: LedgerInvoiceReconciliationRefV1) -> str:
        """Show both values behind each canonical match verdict."""
        yes = ledger_copy("tui.ledger.reconciliation.yes")
        no = ledger_copy("tui.ledger.reconciliation.no")
        return "\n".join(
            (
                f"{ledger_copy('tui.ledger.reconciliation.score')}: {row.score}",
                # The verdict AND the two values it was reached on. A bare
                # yes/no asks the operator to confirm a link while hiding
                # what was compared, and a bare "no" reports a
                # disagreement without saying between what and what.
                f"{ledger_copy('tui.ledger.reconciliation.amount_match')}: "
                f"{yes if row.amount_match else no} "
                f"({row.transaction_amount} / {row.invoice_total})",
                f"{ledger_copy('tui.ledger.reconciliation.counterparty_match')}: "
                f"{yes if row.counterparty_match else no} "
                f"({row.transaction_counterparty} / {row.invoice_counterparty})",
            )
        )

    def _populate_inconsistency_table(self, table: DataTable[str]) -> None:
        """Render each one-sided link with its canonical direction label."""
        table.add_column(ledger_copy("tui.ledger.reconciliation.entry"), width=12)
        table.add_column(ledger_copy("tui.ledger.reconciliation.invoice"), width=12)
        table.add_column(ledger_copy("tui.ledger.reconciliation.direction"), width=30)
        for row in self.controller.projection.link_inconsistencies:
            direction_key = DIRECTION_STATE_COPY_KEYS.get(row.direction)
            if direction_key is None:
                raise ValueError("unsupported canonical link inconsistency direction")
            table.add_row(
                str(row.transaction_id)[:12],
                str(row.invoice_id)[:12],
                ledger_copy(direction_key),
                key=f"{row.transaction_id}:{row.invoice_id}",
            )

    def _populate_affected_declaration_table(self, table: DataTable[str]) -> None:
        """Render affected declaration coordinates and their change counts."""
        table.add_columns(
            ledger_copy("tui.ledger.reconciliation.modelo"),
            ledger_copy("tui.ledger.reconciliation.period"),
            ledger_copy("tui.ledger.reconciliation.changes"),
        )
        for row in self.controller.projection.affected_declarations:
            table.add_row(
                str(row.modelo),
                str(row.period),
                f"{row.changed_count}/{row.removed_count}",
                key=str(row.calculation_revision_id),
            )

    def _show_empty_state_if_needed(self) -> None:
        """Tell the operator when all three reconciliation projections are empty."""
        projection = self.controller.projection
        if not (
            projection.invoice_reconciliations or projection.link_inconsistencies or projection.affected_declarations
        ):
            self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.reconciliation.empty"))

    def _hide_submission_controls_if_unavailable(self) -> None:
        """Keep mutation controls absent when the authorized link door is missing."""
        if not self.controller.can_submit_links():
            self.query_one("#ledger-reconciliation-confirm", Button).display = False
            self.query_one("#ledger-reconciliation-cancel", Button).display = False

    def _restore_suggestion_focus(self, table: DataTable[str]) -> None:
        """Restore the semantic transaction focus when its suggestion is visible."""
        restored = self.controller.restored_transaction_id()
        if restored is None:
            return
        index = next(
            (
                index
                for index, row in enumerate(self.controller.projection.invoice_reconciliations)
                if row.transaction_id == restored
            ),
            None,
        )
        if index is not None:
            table.move_cursor(row=index)

    @staticmethod
    def _focus_first_populated_table(*tables: DataTable[str]) -> None:
        """Focus suggestions first, otherwise the first table containing rows."""
        next((table for table in tables if table.row_count), tables[0]).focus()

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
