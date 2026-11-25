"""AeatSyncNotificationsScreen and its protected projection rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from textual.widgets import DataTable

from ....application.aeat_sync.workspace import (
    AeatSyncWorkspaceZone,
)
from ....core.i18n.render import tr
from .controller import AeatSyncWorkspaceController

if TYPE_CHECKING:
    pass

from .screen_presentation import notification_identity, status_label
from .screens import AeatSyncWorkspaceScreen


class AeatSyncNotificationsScreen(AeatSyncWorkspaceScreen):
    """Notification metadata surface with no identity or document content."""

    zone = AeatSyncWorkspaceZone.NOTIFICATIONS
    HEADING_LOCALE_KEY = "tui.aeat_sync.notifications.title"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the notifications body."""
        super().__init__(controller, id="aeat-sync-notifications-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render dates and public read/custody metadata only."""
        table.add_column(tr("tui.aeat_sync.column.issued"), width=12)
        table.add_column(tr("tui.aeat_sync.column.read"), width=12)
        table.add_column(tr("tui.aeat_sync.column.category"), width=16)
        table.add_column(tr("tui.aeat_sync.column.document_custody"), width=18)
        self._notification_rows.clear()
        for row in self.controller.projection.notifications:
            key = notification_identity(row)
            self._notification_rows[key] = row
            table.add_row(
                str(row.issued_on),
                status_label(row.read_state),
                status_label(row.category),
                status_label(row.document_custody_state),
                key=key,
            )
