"""A workspace host that reads setup items' quick-status rows, and the rows the real registry derives.

The TUI root reads an item's row through the setup screen's runtime door before
any surface offers that item's setup. This host answers the same read from rows
the real row derivation builds out of one probe reading each: absent, so the
row's action sets the item up, or blocked as not in this build, as every item
reads while this build sets nothing up. It records each row read and each
setup request a surface posts.
"""

from __future__ import annotations

from textual.screen import Screen

from .....application.dependency_contracts import (
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyProbeOutcome,
    DependencyProbeReading,
    DependencyStatusRow,
)
from .....application.dependency_registry import dependency_item_declarations, derive_dependency_row
from ...setup.focus import SetupItemRequested
from .workspace_fixtures import WorkspaceHostApp

__all__ = ["LOCAL_AI_HELD", "SetupStatusWorkspaceHostApp", "absent_row", "not_in_this_build_row"]

LOCAL_AI_HELD = "Local AI: This version of Cadrumo does not include this."
"""What a surface shows for the local AI while this build cannot set it up."""


def _row(item_id: str, outcome: DependencyProbeOutcome) -> DependencyStatusRow:
    declaration = next(declaration for declaration in dependency_item_declarations() if declaration.item_id == item_id)
    blocked = DependencyBlockedReason.NOT_IN_THIS_BUILD if outcome is DependencyProbeOutcome.BLOCKED else None
    return derive_dependency_row(
        declaration,
        DependencyProbeReading(
            item_id=item_id, mode=DependencyCheckMode.QUICK, outcome=outcome, blocked_reason=blocked
        ),
    )


def absent_row(item_id: str) -> DependencyStatusRow:
    """The row of an item that is not on this computer and that setup can add."""
    return _row(item_id, DependencyProbeOutcome.ABSENT)


def not_in_this_build_row(item_id: str) -> DependencyStatusRow:
    """The row of an item this build cannot set up."""
    return _row(item_id, DependencyProbeOutcome.BLOCKED)


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
