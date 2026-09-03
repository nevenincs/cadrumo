"""Data-quality-first Ledger overview over an injected workspace projection."""

from __future__ import annotations

from typing import cast, override

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from ....application.ledger.workspace import LedgerWorkspaceArea
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import (
    LedgerWorkspaceController,
    LedgerWorkspaceScreen,
    area_label,
    item_count_label,
    ledger_copy,
    status_label,
)


class LedgerOverviewScreen(LedgerWorkspaceScreen):
    """Lead with unresolved work and affected declarations, never financial totals."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain the injected read-only workspace controller."""
        super().__init__(controller, id="ledger-overview-screen")

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.overview.title"), classes="cadrumo-banner")
        with ContentScroll(id="ledger-page", classes="cadrumo-scroll ledger-page"):
            yield ContentDataTable[str](id="ledger-navigation", cursor_type="row", zebra_stripes=True)
            yield Static(ledger_copy("tui.ledger.overview.quality"))
            yield ContentDataTable[str](id="ledger-quality", cursor_type="row", zebra_stripes=True)
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate the complete navigation and quality-first summary."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#ledger-quality", DataTable))
        table.add_column(ledger_copy("tui.ledger.column.area"), key="area")
        table.add_column(ledger_copy("tui.ledger.column.status"), key="status")
        table.add_column(ledger_copy("tui.ledger.column.items"), key="items")
        for area in (
            LedgerWorkspaceArea.REVIEW,
            LedgerWorkspaceArea.CLASSIFICATION,
            LedgerWorkspaceArea.EVIDENCE,
            LedgerWorkspaceArea.RECONCILIATION,
        ):
            state = self.controller.state_for(area)
            status = status_label(state.status)
            table.add_row(area_label(area), status, item_count_label(state), key=area.value)
        affected = len(self.controller.projection.affected_declarations)
        table.add_row(
            ledger_copy("tui.ledger.overview.affected_declarations"),
            (ledger_copy("tui.ledger.status.needs_attention") if affected else ledger_copy("tui.ledger.status.empty")),
            str(affected),
            key="affected-declarations",
        )
        self.query_one("#ledger-navigation", DataTable).focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Route an Enter press on the one-stop destination table."""
        self.handle_navigation_selection(event)


__all__ = ["LedgerOverviewScreen"]
