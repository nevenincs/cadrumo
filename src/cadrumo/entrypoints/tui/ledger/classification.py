"""Explicit, command-backed classification flow for one selected transaction."""

from __future__ import annotations

from typing import cast, override

from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Static

from ....application.ledger.models import ManualLedgerTransactionPatch
from ....domain.transactions.enums import BusinessClassification
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen, ledger_copy
from .models import LedgerFlowState

_CHOICES = (
    (BusinessClassification.BUSINESS, "tui.ledger.classification.business"),
    (BusinessClassification.PERSONAL, "tui.ledger.classification.personal"),
    (BusinessClassification.REVIEWED_EXCLUDED, "tui.ledger.classification.excluded"),
)


class LedgerClassificationScreen(LedgerWorkspaceScreen):
    """Let an operator explicitly edit, confirm, or cancel one classification."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain an injected command-capable workspace controller."""
        super().__init__(controller, id="ledger-classification-screen")
        self._flow_state = LedgerFlowState.EDITING
        self.selected_classification: BusinessClassification | None = None

    @property
    def flow_state(self) -> LedgerFlowState:
        """Expose the monotonic interaction state without a public setter."""
        return self._flow_state

    def _transition(self, target: LedgerFlowState) -> None:
        allowed = {
            LedgerFlowState.EDITING: {LedgerFlowState.CONFIRMING, LedgerFlowState.CANCELLED},
            LedgerFlowState.CONFIRMING: {LedgerFlowState.SUBMITTING, LedgerFlowState.CANCELLED},
            LedgerFlowState.SUBMITTING: {LedgerFlowState.SUCCEEDED, LedgerFlowState.FAILED},
        }
        if target not in allowed.get(self._flow_state, set()):
            raise RuntimeError("invalid classification flow transition")
        self._flow_state = target

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.classification.title"), classes="cadrumo-banner")
        with ContentScroll(id="ledger-page", classes="cadrumo-scroll ledger-page"):
            yield ContentDataTable[str](id="ledger-navigation", cursor_type="row", zebra_stripes=True)
            position, total, short_id = self.controller.classification_target_coordinate()
            yield Static(
                ledger_copy(
                    "tui.ledger.classification.target",
                    position=position,
                    total=total,
                    short_id=short_id,
                ),
                id="ledger-classification-target",
                markup=False,
            )
            yield Static(ledger_copy("tui.ledger.classification.prompt"), markup=False)
            yield ContentDataTable[str](id="ledger-classifications", cursor_type="row", zebra_stripes=True)
            yield Static("", id="ledger-flow-status", markup=False)
            yield Button(
                ledger_copy("tui.ledger.classification.confirm"),
                id="ledger-classification-confirm",
                disabled=True,
            )
            yield Button(ledger_copy("tui.ledger.classification.cancel"), id="ledger-classification-cancel")
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate explicit authored choices without inferring a classification."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#ledger-classifications", DataTable))
        table.add_column(ledger_copy("tui.ledger.column.status"))
        for classification, key in _CHOICES:
            table.add_row(ledger_copy(key), key=classification.value)
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Move an explicit choice into confirmation state."""
        if self.handle_navigation_selection(event):
            return
        event_table = cast("DataTable[str]", event.data_table)
        if (
            self.flow_state is not LedgerFlowState.EDITING
            or event_table.id != "ledger-classifications"
            or event.row_key.value is None
        ):
            return
        self.selected_classification = BusinessClassification(str(event.row_key.value))
        self._transition(LedgerFlowState.CONFIRMING)
        self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.classification.confirming"))
        confirm = self.query_one("#ledger-classification-confirm", Button)
        confirm.disabled = False
        confirm.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Confirm through the injected door or cancel without mutation."""
        if event.button.id == "ledger-classification-cancel" and self.flow_state in {
            LedgerFlowState.EDITING,
            LedgerFlowState.CONFIRMING,
        }:
            self._cancel()
            return
        if (
            self.flow_state is not LedgerFlowState.CONFIRMING
            or event.button.id != "ledger-classification-confirm"
            or self.selected_classification is None
        ):
            return
        self._transition(LedgerFlowState.SUBMITTING)
        event.button.disabled = True
        self.query_one("#ledger-classification-cancel", Button).disabled = True
        status = self.query_one("#ledger-flow-status", Static)
        status.update(ledger_copy("tui.ledger.classification.progress"))
        self.run_worker(self._submit(), exclusive=True)

    async def _submit(self) -> None:
        """Await the injected door without blocking keyboard message handling."""
        status = self.query_one("#ledger-flow-status", Static)
        selected = self.selected_classification
        if selected is None:  # pragma: no cover - guarded before worker creation
            raise RuntimeError("classification selection disappeared before submission")
        try:
            await self.controller.submit_classification(
                ManualLedgerTransactionPatch(business_classification=selected)
            )
        except Exception:
            self._transition(LedgerFlowState.FAILED)
            status.update(ledger_copy("tui.ledger.classification.failure"))
        else:
            self._transition(LedgerFlowState.SUCCEEDED)
            status.update(ledger_copy("tui.ledger.classification.success"))

    def _cancel(self) -> None:
        if self.flow_state not in {LedgerFlowState.EDITING, LedgerFlowState.CONFIRMING}:
            return
        self.selected_classification = None
        self._transition(LedgerFlowState.CANCELLED)
        self.query_one("#ledger-flow-status", Static).update("")
        self.query_one("#ledger-classification-confirm", Button).disabled = True
        self.query_one("#ledger-classification-cancel", Button).disabled = True

    @override
    def action_back(self) -> None:
        if self.flow_state is LedgerFlowState.SUBMITTING:
            self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.flow.in_flight_refusal"))
            return
        if self.flow_state is LedgerFlowState.CONFIRMING:
            self._cancel()
            return
        super().action_back()


__all__ = ["LedgerClassificationScreen"]
