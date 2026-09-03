"""Import flow over pre-resolved opaque commands and an injected submission door."""

from __future__ import annotations

from typing import cast, override

from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Static

from ..components.widgets import ContentDataTable, ContentScroll
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen, ledger_copy
from .models import LedgerFlowState, LedgerPreparedImportV1


class LedgerImportScreen(LedgerWorkspaceScreen):
    """Select and submit only application-prepared import operations."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain only injected, pre-resolved import choices and their door."""
        super().__init__(controller, id="ledger-import-screen")
        self.flow_state = LedgerFlowState.EDITING
        self.selected_choice: LedgerPreparedImportV1 | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.import.title"), classes="cadrumo-banner")
        with ContentScroll(id="ledger-page", classes="cadrumo-scroll ledger-page"):
            yield ContentDataTable[str](id="ledger-navigation", cursor_type="row", zebra_stripes=True)
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
        if event_table.id != "ledger-import-choices" or event.row_key.value is None:
            return
        self.selected_choice = next(
            choice for choice in self.controller.prepared_imports if choice.choice_id == event.row_key.value
        )
        self.flow_state = LedgerFlowState.CONFIRMING
        self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.import.confirming"))
        confirm = self.query_one("#ledger-import-confirm", Button)
        confirm.disabled = False
        confirm.focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Submit through the injected door or cancel without touching I/O."""
        if event.button.id == "ledger-import-cancel":
            self._cancel()
            return
        if event.button.id != "ledger-import-confirm" or self.selected_choice is None:
            return
        self.flow_state = LedgerFlowState.SUBMITTING
        status = self.query_one("#ledger-flow-status", Static)
        status.update(ledger_copy("tui.ledger.import.progress"))
        try:
            result = await self.controller.submit_import(self.selected_choice)
        except Exception:
            self.flow_state = LedgerFlowState.FAILED
            status.update(ledger_copy("tui.ledger.import.failure"))
        else:
            self.flow_state = LedgerFlowState.SUCCEEDED
            status.update(ledger_copy("tui.ledger.import.success", imported=result.imported, skipped=result.skipped))

    def _cancel(self) -> None:
        self.selected_choice = None
        self.flow_state = LedgerFlowState.CANCELLED
        self.query_one("#ledger-flow-status", Static).update("")
        self.query_one("#ledger-import-confirm", Button).disabled = True
        self.query_one("#ledger-import-choices", DataTable).focus()

    @override
    def action_back(self) -> None:
        if self.flow_state is LedgerFlowState.CONFIRMING:
            self._cancel()
            return
        super().action_back()


__all__ = ["LedgerImportScreen"]
