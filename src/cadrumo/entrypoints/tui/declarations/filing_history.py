"""Local filing history with separate AEAT observation axes."""

from __future__ import annotations

from typing import cast, override

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from ..components.widgets import ContentDataTable, ContentScroll
from .controller import (
    DeclarationsWorkspaceController,
    DeclarationsWorkspaceScreen,
    declarations_copy,
    evidence_label,
    filing_state_label,
    natural_address,
)
from ....application.modelo.declarations_workspace import (
    DeclarationsWorkspaceFilingRefV1,
    DeclarationsWorkspaceLifecycleRefV1,
)


def _lifecycle_label(row: DeclarationsWorkspaceLifecycleRefV1) -> str:
    """Render sanitized lifecycle meaning without exposing its transport token."""
    return declarations_copy(f"tui.declarations.lifecycle.{row.kind.value}")


class DeclarationsFilingHistoryScreen(DeclarationsWorkspaceScreen):
    """Show local record currency separately from external AEAT evidence."""

    def __init__(self, controller: DeclarationsWorkspaceController) -> None:
        """Retain injected state and semantic selection."""
        super().__init__(controller, id="declarations-filing-history-screen")
        self.selected_filing_record_id: str | None = None
        self.selected_lifecycle_fact_id: str | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(declarations_copy("tui.declarations.filing_history.title"), classes="cadrumo-banner", markup=False)
        with ContentScroll(id="declarations-page", classes="cadrumo-scroll declarations-page"):
            yield ContentDataTable[str](id="declarations-navigation", cursor_type="row", zebra_stripes=True)
            yield Static(declarations_copy("tui.declarations.filing_history.axes"), markup=False)
            yield ContentDataTable[str](id="declarations-filings", cursor_type="row", zebra_stripes=True)
            yield Static(id="declarations-refusal", classes="declarations-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate separate local and external filing axes."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#declarations-filings", DataTable))
        table.add_column(
            declarations_copy("tui.declarations.column.declaration"), key="declaration", width=22
        )
        table.add_column(declarations_copy("tui.declarations.column.when"), key="when", width=10)
        table.add_column(
            declarations_copy("tui.declarations.column.local_filing"), key="local", width=13
        )
        table.add_column(
            declarations_copy("tui.declarations.column.aeat_accepted"), key="accepted", width=7
        )
        table.add_column(
            declarations_copy("tui.declarations.column.aeat_evidence"), key="evidence", width=13
        )
        history = [
            (row.filed_at, "filing", row)
            for row in self.controller.projection.filings
        ] + [
            (row.occurred_at, "lifecycle", row)
            for row in self.controller.projection.lifecycle
        ]
        for occurred_at, kind, source in sorted(history, key=lambda item: item[0], reverse=True):
            if kind == "lifecycle":
                lifecycle = cast("DeclarationsWorkspaceLifecycleRefV1", source)
                table.add_row(
                    natural_address(lifecycle.modelo, lifecycle.filing_year, lifecycle.period),
                    occurred_at.date().isoformat(),
                    _lifecycle_label(lifecycle),
                    declarations_copy("tui.declarations.value.not_applicable"),
                    declarations_copy("tui.declarations.value.not_applicable"),
                    key=f"lifecycle:{lifecycle.fact_id}",
                )
                continue
            filing = cast("DeclarationsWorkspaceFilingRefV1", source)
            table.add_row(
                natural_address(filing.modelo, filing.filing_year, filing.period),
                occurred_at.date().isoformat(),
                filing_state_label(filing.local_status),
                declarations_copy(
                    "tui.declarations.value.yes"
                    if filing.aeat_accepted
                    else "tui.declarations.value.no"
                ),
                evidence_label(filing.evidence_kind),
                key=f"filing:{filing.filing_record_id}",
            )
        if not table.row_count:
            self.query_one("#declarations-refusal", Static).update(declarations_copy("tui.declarations.empty"))
        restored = self.controller.restored_id("declarations.filing")
        restored_key = f"filing:{restored}" if restored is not None else None
        index = next((i for i, item in enumerate(table.ordered_rows) if item.key.value == restored_key), None)
        if index is None:
            self.query_one("#declarations-navigation", DataTable).focus()
        else:
            table.move_cursor(row=index)
            table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Route a navigation row or invoke the injected filing handoff."""
        if self.handle_navigation(event):
            return
        table = cast("DataTable[str]", event.data_table)
        if table.id != "declarations-filings" or event.row_key.value is None:
            return
        semantic_key = str(event.row_key.value)
        if semantic_key.startswith("lifecycle:"):
            self.selected_lifecycle_fact_id = semantic_key.removeprefix("lifecycle:")
            return
        filing_record_id = semantic_key.removeprefix("filing:")
        row = next(item for item in self.controller.projection.filings if item.filing_record_id == filing_record_id)
        self.selected_filing_record_id = row.filing_record_id
        if self.controller.filing_handoff is None:
            self.refuse_handoff()
        else:
            self.controller.filing_handoff(row)


__all__ = ["DeclarationsFilingHistoryScreen"]
