"""Declarations landing over safe natural coordinates."""

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
    work_state_label,
)


class DeclarationsOverviewScreen(DeclarationsWorkspaceScreen):
    """List local declaration facts without implying filing or AEAT state."""

    def __init__(self, controller: DeclarationsWorkspaceController) -> None:
        """Retain injected state and semantic selection."""
        super().__init__(controller, id="declarations-overview-screen")
        self.selected_work_unit_id: str | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(declarations_copy("tui.declarations.overview.title"), classes="cadrumo-banner", markup=False)
        with ContentScroll(id="declarations-page", classes="cadrumo-scroll declarations-page"):
            yield ContentDataTable[str](id="declarations-navigation", cursor_type="row", zebra_stripes=True)
            yield ContentDataTable[str](id="declarations-list", cursor_type="row", zebra_stripes=True)
            yield Static(id="declarations-refusal", classes="declarations-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate safe natural-coordinate declaration rows."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#declarations-list", DataTable))
        table.add_column(declarations_copy("tui.declarations.column.declaration"), key="declaration")
        table.add_column(declarations_copy("tui.declarations.column.local_state"), key="state")
        table.add_column(declarations_copy("tui.declarations.column.calculation"), key="calculation")
        for row in self.controller.projection.declarations:
            table.add_row(
                natural_address(row.modelo, row.filing_year, row.period),
                work_state_label(row.state),
                declarations_copy(
                    "tui.declarations.value.available" if row.has_current_calculation else "tui.declarations.value.none"
                ),
                key=row.work_unit_id,
            )
        if not table.row_count:
            self.query_one("#declarations-refusal", Static).update(declarations_copy("tui.declarations.empty"))
        restored = self.controller.restored_id("declarations.work")
        row_index = next((i for i, item in enumerate(table.ordered_rows) if item.key.value == restored), None)
        if row_index is None:
            self.query_one("#declarations-navigation", DataTable).focus()
        else:
            table.move_cursor(row=row_index)
            table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Route a navigation row or invoke the injected declaration handoff."""
        if self.handle_navigation(event):
            return
        table = cast("DataTable[str]", event.data_table)
        if table.id != "declarations-list" or event.row_key.value is None:
            return
        row = next(item for item in self.controller.projection.declarations if item.work_unit_id == event.row_key.value)
        self.selected_work_unit_id = row.work_unit_id
        if self.controller.declaration_handoff is None:
            self.refuse_handoff()
        else:
            self.controller.declaration_handoff(row)


__all__ = ["DeclarationsOverviewScreen"]
