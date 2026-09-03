"""Calculation revision list with opaque semantic selection."""

from __future__ import annotations

from typing import cast, override

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from ..components.widgets import ContentDataTable, ContentScroll
from .controller import (
    DeclarationsWorkspaceController,
    DeclarationsWorkspaceScreen,
    declarations_copy,
    natural_address,
    revision_state_label,
)


class DeclarationsRevisionsScreen(DeclarationsWorkspaceScreen):
    """Distinguish calculation revision identity from registry revision vocabulary."""

    def __init__(self, controller: DeclarationsWorkspaceController) -> None:
        """Retain injected state and semantic selection."""
        super().__init__(controller, id="declarations-revisions-screen")
        self.selected_calculation_revision_id: str | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(declarations_copy("tui.declarations.revisions.title"), classes="cadrumo-banner", markup=False)
        with ContentScroll(id="declarations-page", classes="cadrumo-scroll declarations-page"):
            yield ContentDataTable[str](id="declarations-navigation", cursor_type="row", zebra_stripes=True)
            yield Static(declarations_copy("tui.declarations.revisions.explanation"), markup=False)
            yield ContentDataTable[str](id="declarations-revisions", cursor_type="row", zebra_stripes=True)
            yield Static(id="declarations-refusal", classes="declarations-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate calculation revisions from the safe projection."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#declarations-revisions", DataTable))
        table.add_column(declarations_copy("tui.declarations.column.declaration"), key="declaration")
        table.add_column(declarations_copy("tui.declarations.column.calculation_revision"), key="revision")
        table.add_column(declarations_copy("tui.declarations.column.local_state"), key="state")
        for row in self.controller.projection.calculation_revisions:
            table.add_row(
                natural_address(row.modelo, row.filing_year, row.period),
                row.created_at.date().isoformat(),
                revision_state_label(row.state),
                key=row.calculation_revision_id,
            )
        if not table.row_count:
            self.query_one("#declarations-refusal", Static).update(declarations_copy("tui.declarations.empty"))
        restored = self.controller.restored_id("declarations.calculation_revision")
        index = next((i for i, item in enumerate(table.ordered_rows) if item.key.value == restored), None)
        if index is None:
            self.query_one("#declarations-navigation", DataTable).focus()
        else:
            table.move_cursor(row=index)
            table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Route a navigation row or invoke the injected revision handoff."""
        if self.handle_navigation(event):
            return
        table = cast("DataTable[str]", event.data_table)
        if table.id != "declarations-revisions" or event.row_key.value is None:
            return
        row = next(
            item
            for item in self.controller.projection.calculation_revisions
            if item.calculation_revision_id == event.row_key.value
        )
        self.selected_calculation_revision_id = row.calculation_revision_id
        if self.controller.revision_handoff is None:
            self.refuse_handoff()
        else:
            self.controller.revision_handoff(row)


__all__ = ["DeclarationsRevisionsScreen"]
