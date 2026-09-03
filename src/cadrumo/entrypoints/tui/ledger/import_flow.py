"""Import flow over pre-resolved opaque commands and an injected submission door."""

from __future__ import annotations

from typing import cast, override

from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Static

from ..components.widgets import ContentDataTable
from .controller import LedgerWorkspaceController, ledger_copy
from .models import LedgerFlowState, LedgerPreparedImportV1
from .workspace_presentation import LedgerConfirmationFlowScreen, ledger_workspace_page


class LedgerImportScreen(LedgerConfirmationFlowScreen):
    """Select and submit only application-prepared import operations."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain only injected, pre-resolved import choices and their door."""
        super().__init__(controller, id="ledger-import-screen")
        self.selected_choice: LedgerPreparedImportV1 | None = None

    FLOW_NAME = "import"

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.import.title"), classes="cadrumo-banner")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static(ledger_copy("tui.ledger.import.prompt"), markup=False)
            yield ContentDataTable[str](id="ledger-import-choices", cursor_type="row", zebra_stripes=True)
            yield Static("", id="ledger-flow-status", markup=False)
            yield Button(ledger_copy("tui.ledger.import.confirm"), id="ledger-import-confirm", disabled=True)
            yield Button(ledger_copy("tui.ledger.import.cancel"), id="ledger-import-cancel")
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate safe labels without reading command paths or providers."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#ledger-import-choices", DataTable))
        table.add_column(ledger_copy("tui.ledger.column.destination"))
        table.add_column(ledger_copy("tui.ledger.area.import"))
        for choice in self.controller.prepared_imports:
            table.add_row(
                ledger_copy(choice.source_label_key),
                ledger_copy(choice.provider_label_key),
                key=choice.choice_id,
            )
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Move a pre-resolved semantic choice into confirmation state."""
        if self.handle_navigation_selection(event):
            return
        event_table = cast("DataTable[str]", event.data_table)
        if (
            self.flow_state is not LedgerFlowState.EDITING
            or event_table.id != "ledger-import-choices"
            or event.row_key.value is None
        ):
            return
        self.selected_choice = next(
            choice for choice in self.controller.prepared_imports if choice.choice_id == event.row_key.value
        )
        self._transition(LedgerFlowState.CONFIRMING)
        self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.import.confirming"))
        confirm = self.query_one("#ledger-import-confirm", Button)
        confirm.disabled = False
        confirm.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Submit through the injected door or cancel without touching I/O."""
        if event.button.id == "ledger-import-cancel" and self.flow_state in {
            LedgerFlowState.EDITING,
            LedgerFlowState.CONFIRMING,
        }:
            self._cancel_flow()
            return
        if (
            self.flow_state is not LedgerFlowState.CONFIRMING
            or event.button.id != "ledger-import-confirm"
            or self.selected_choice is None
        ):
            return
        self._transition(LedgerFlowState.SUBMITTING)
        event.button.disabled = True
        self.query_one("#ledger-import-cancel", Button).disabled = True
        status = self.query_one("#ledger-flow-status", Static)
        status.update(ledger_copy("tui.ledger.import.progress"))
        self.run_worker(self._submit(), exclusive=True)

    async def _submit(self) -> None:
        """Await the injected door without blocking keyboard message handling."""
        status = self.query_one("#ledger-flow-status", Static)
        selected = self.selected_choice
        if selected is None:  # pragma: no cover - guarded before worker creation
            raise RuntimeError("prepared import selection disappeared before submission")
        try:
            result = await self.controller.submit_import(selected)
        except Exception:
            self._transition(LedgerFlowState.FAILED)
            status.update(ledger_copy("tui.ledger.import.failure"))
        else:
            self._transition(LedgerFlowState.SUCCEEDED)
            status.update(ledger_copy("tui.ledger.import.success", imported=result.imported, skipped=result.skipped))

    def _cancel_flow(self) -> None:
        if self.flow_state not in {LedgerFlowState.EDITING, LedgerFlowState.CONFIRMING}:
            return
        self.selected_choice = None
        self._transition(LedgerFlowState.CANCELLED)
        self.query_one("#ledger-flow-status", Static).update("")
        self.query_one("#ledger-import-confirm", Button).disabled = True
        self.query_one("#ledger-import-cancel", Button).disabled = True

__all__ = ["LedgerImportScreen"]
