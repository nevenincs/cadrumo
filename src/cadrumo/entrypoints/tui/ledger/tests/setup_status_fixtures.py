"""A workspace host that reads setup items' quick-status rows.

The TUI root reads an item's row through the setup screen's runtime door before
any surface offers that item's setup. This host answers the same read from the
rows a test binds, as the components role reports them. It records each row
read and each setup request a surface posts.
"""

from __future__ import annotations

from textual.screen import Screen

from .....application.dependency_contracts import DependencyStatusRow
from ...setup.focus import SetupItemRequested
from .workspace_fixtures import WorkspaceHostApp

__all__ = ["LOCAL_AI_DESKTOP", "LOCAL_AI_HELD", "SetupStatusWorkspaceHostApp"]

LOCAL_AI_HELD = "Local AI: This version of Cadrumo does not include this."
LOCAL_AI_DESKTOP = "Local AI: Not set up yet. Set it up in the Cadrumo desktop app."
"""What a surface shows for the local AI while this build cannot set it up."""


class SetupStatusWorkspaceHostApp(WorkspaceHostApp):
    """A workspace host that reads setup rows as the TUI root does and records setup requests."""

    def __init__(self, screen: Screen[None], rows: tuple[DependencyStatusRow, ...]) -> None:
        """Host ``screen`` over the quick status ``rows``."""
        super().__init__(screen)
        self.rows = rows
        self.row_reads: list[str] = []
        self.requested: list[str] = []

    async def read_setup_row(self, item_id: str) -> DependencyStatusRow | None:
        """Answer the item's row from the bound quick status."""
        self.row_reads.append(item_id)
        return next((row for row in self.rows if row.item_id == item_id), None)

    def on_setup_item_requested(self, message: SetupItemRequested) -> None:
        """Record the item a surface asked to set up."""
        self.requested.append(message.item_id)
