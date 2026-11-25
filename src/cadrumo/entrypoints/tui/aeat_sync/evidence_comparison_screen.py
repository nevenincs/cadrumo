"""AeatSyncEvidenceComparisonScreen and its protected projection rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, override

from textual.widgets import DataTable

from ....application.aeat_sync.workspace import (
    AeatSyncWorkspaceZone,
)
from .controller import AeatSyncWorkspaceController

if TYPE_CHECKING:
    pass

from .screen_presentation import census_value, declaration_address, fit_columns, natural_identity, status_label
from .screen_rows import OperationRow
from .screens import AeatSyncWorkspaceScreen


class AeatSyncEvidenceComparisonScreen(AeatSyncWorkspaceScreen):
    """Evidence comparison screen retaining the two observed source states."""

    zone = AeatSyncWorkspaceZone.EVIDENCE_COMPARISON
    HEADING_LOCALE_KEY = "tui.aeat_sync.evidence_comparison.title"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the evidence-comparison body."""
        super().__init__(controller, id="aeat-sync-evidence-comparison-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render a safe public comparison coordinate and discrepancy."""
        taken = fit_columns(
            self.app.size.width,
            _POPULATE_ROWS_PRIMARY_COLUMNS_LOCALE_KEYS,
            _POPULATE_ROWS_PAIRED_COLUMNS_LOCALE_KEYS,
        )
        for name, header, size in taken:
            table.add_column(header, key=name, width=size)
        for row in self.controller.projection.evidence_comparison:
            cells = {
                "declaration": declaration_address(row),
                "local": status_label(row.local_state),
                "aeat": status_label(row.aeat_state),
                "difference": status_label(row.discrepancy_kind),
                "local_value": census_value(row.local_value),
                "aeat_value": census_value(row.aeat_value),
            }
            table.add_row(
                *(cells[name] for name, _, _ in taken),
                key=natural_identity(row, prefix="comparison"),
            )
            self.add_operation(cast("OperationRow", row))


_POPULATE_ROWS_PRIMARY_COLUMNS_LOCALE_KEYS = (
    ("declaration", "tui.aeat_sync.column.declaration", 22),
    ("difference", "tui.aeat_sync.column.difference", 16),
    ("local", "tui.aeat_sync.column.local", 13),
    ("aeat", "tui.aeat_sync.column.aeat", 13),
)


_POPULATE_ROWS_PAIRED_COLUMNS_LOCALE_KEYS = (
    ("local_value", "tui.aeat_sync.column.local_value", 18),
    ("aeat_value", "tui.aeat_sync.column.aeat_value", 18),
)
