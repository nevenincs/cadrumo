"""AeatSyncOverviewScreen and its protected projection rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, override

from textual.widgets import DataTable

from ....application.aeat_sync.workspace import (
    AeatSyncWorkspaceZone,
)
from ....core.i18n.render import tr
from .controller import AeatSyncWorkspaceController

if TYPE_CHECKING:
    pass

from .screen_presentation import status_label
from .screen_rows import OperationRow
from .screens import AeatSyncWorkspaceScreen


class AeatSyncOverviewScreen(AeatSyncWorkspaceScreen):
    """Overview preserving local, AEAT, and discrepancy axes per area."""

    zone = AeatSyncWorkspaceZone.OVERVIEW
    HEADING_LOCALE_KEY = "tui.aeat_sync.overview.title"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the overview body."""
        super().__init__(controller, id="aeat-sync-overview-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render public overview states without collapsing either source."""
        table.add_column(tr("tui.aeat_sync.column.area"), width=15)
        table.add_column(tr("tui.aeat_sync.column.local"), width=13)
        table.add_column(tr("tui.aeat_sync.column.aeat"), width=13)
        table.add_column(tr("tui.aeat_sync.column.difference"), width=16)
        for row in self.controller.projection.overview:
            table.add_row(
                status_label(row.area),
                status_label(row.local_state),
                status_label(row.aeat_state),
                status_label(row.discrepancy_kind),
                key=f"overview:{row.area.value}",
            )
            self.add_operation(cast("OperationRow", row))
