"""The setup destination: one screen per admitted route, reading and setting up through the component engine."""

from __future__ import annotations

from textual.screen import Screen

from ..navigation import TuiScreenContextV1
from .door import ComponentsSetupDoor
from .focus import setup_item_focus
from .screen import SetupScreen

__all__ = ["setup_screen_factory"]


def setup_screen_factory(context: TuiScreenContextV1, /) -> Screen[None]:
    """Open the setup screen on the item its focus names, through this build's components role."""
    return SetupScreen(ComponentsSetupDoor(), focus_item=setup_item_focus(context))
