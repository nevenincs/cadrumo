"""Read-only Ledger evidence-review queue over canonical safe metadata."""

from __future__ import annotations

from typing import cast, override

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from ..components.widgets import ContentDataTable, ContentScroll
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen, ledger_copy


class LedgerEvidenceScreen(LedgerWorkspaceScreen):
    """Render safe evidence metadata without document content or source locators."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain an injected canonical review queue."""
        super().__init__(controller, id="ledger-evidence-screen")
        self.selected_evidence_id: str | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.evidence.title"), classes="cadrumo-banner")
        with ContentScroll(id="ledger-page", classes="cadrumo-scroll ledger-page"):
            yield ContentDataTable[str](id="ledger-navigation", cursor_type="row", zebra_stripes=True)
            yield Static(ledger_copy("tui.ledger.evidence.safe_metadata"), markup=False)
            yield ContentDataTable[str](id="ledger-evidence", cursor_type="row", zebra_stripes=True)
            yield Static("", id="ledger-evidence-detail", markup=False)
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate application-supplied safe metadata with semantic row keys."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#ledger-evidence", DataTable))
        table.add_column(ledger_copy("tui.ledger.column.entry"))
        table.add_column(ledger_copy("tui.ledger.evidence.column.type"))
        table.add_column(ledger_copy("tui.ledger.evidence.column.status"))
        rows = self.controller.evidence_rows()
        for position, row in enumerate(rows, start=1):
            status_key = "tui.ledger.evidence.pending" if row.pending_review else "tui.ledger.evidence.reviewed"
            table.add_row(str(position), row.mime_type, ledger_copy(status_key), key=row.attachment_id)
        if not rows:
            self.query_one("#ledger-evidence-detail", Static).update(ledger_copy("tui.ledger.evidence.empty"))
        restored = self.controller.restored_evidence_id()
        if restored is not None:
            index = next(index for index, row in enumerate(table.ordered_rows) if row.key.value == restored)
            table.move_cursor(row=index)
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Show safe detail for the selected evidence identity."""
        if self.handle_navigation_selection(event):
            return
        table = cast("DataTable[str]", event.data_table)
        if table.id != "ledger-evidence" or event.row_key.value is None:
            return
        evidence_id = str(event.row_key.value)
        row = next(item for item in self.controller.evidence_rows() if item.attachment_id == evidence_id)
        self.selected_evidence_id = evidence_id
        self.query_one("#ledger-evidence-detail", Static).update(
            ledger_copy(
                "tui.ledger.evidence.detail",
                size=row.bytes_size,
                captured=row.captured_at,
            )
        )


__all__ = ["LedgerEvidenceScreen"]
