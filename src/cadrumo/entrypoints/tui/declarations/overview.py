"""Routes share the single grouped declaration portfolio."""

from __future__ import annotations

from typing import ClassVar

from .controller import DeclarationsWorkspaceController
from .grouped import GroupedDeclarationsScreen


class DeclarationsOverviewScreen(GroupedDeclarationsScreen):
    """The Declarations workspace landing body."""


class DeclarationsModeloWorkspaceLauncherScreen(GroupedDeclarationsScreen):
    """The same body when entered through a direct declaration-work route."""

    IS_WORKSPACE_OVERVIEW: ClassVar[bool] = False

    def __init__(self, controller: DeclarationsWorkspaceController) -> None:
        """Retain the direct route identity for its parent navigation."""
        super().__init__(controller, id="declarations-modelo-workspace-launcher-screen")


__all__ = ["DeclarationsModeloWorkspaceLauncherScreen", "DeclarationsOverviewScreen"]
