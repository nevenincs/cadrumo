"""AeatSyncFiledDeclarationsScreen and its protected projection rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, override

from textual.widgets import DataTable

from ....application.aeat_sync.workspace import (
    AeatSyncOverviewArea,
    AeatSyncWorkspaceZone,
)
from ....core.i18n.render import tr
from .controller import AeatSyncWorkspaceController

if TYPE_CHECKING:
    pass

from .screen_presentation import declaration_address, natural_identity, status_label
from .screen_rows import OperationRow
from .screens import AeatSyncWorkspaceScreen


class AeatSyncFiledDeclarationsScreen(AeatSyncWorkspaceScreen):
    """Filed declaration observation retaining local and AEAT state separately."""

    zone = AeatSyncWorkspaceZone.FILED_DECLARATIONS
    HEADING_LOCALE_KEY = "tui.aeat_sync.filed_declarations.title"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the filed-declarations body."""
        super().__init__(controller, id="aeat-sync-filed-declarations-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render only public filing and receipt state."""
        table.add_column(tr("tui.aeat_sync.column.declaration"), width=22)
        table.add_column(tr("tui.aeat_sync.column.local_filing"), width=14)
        table.add_column(tr("tui.aeat_sync.column.aeat"), width=14)
        table.add_column(tr("tui.aeat_sync.column.receipt"), width=14)
        for row in self.controller.projection.filed_declarations:
            table.add_row(
                declaration_address(row),
                status_label(row.local_filing_state),
                status_label(row.aeat_observation_state),
                status_label(row.justificante_state),
                key=natural_identity(row, prefix="filed"),
            )
        for overview in self.controller.projection.overview:
            if overview.area is AeatSyncOverviewArea.FILED_DECLARATIONS:
                self.add_operation(cast("OperationRow", overview))
