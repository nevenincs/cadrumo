"""The setup destination: one screen per admitted route, bound to the signed-in runtime connection."""

from __future__ import annotations

from textual.screen import Screen

from cadrumo_client.transport.frontend_client import FrontendClient

from ..navigation import TuiScreenContextV1, TuiScreenFactoryV1
from .door import RuntimeSetupDoor
from .focus import setup_item_focus
from .screen import SetupScreen

__all__ = ["setup_screen_factory"]


def setup_screen_factory(client: FrontendClient) -> TuiScreenFactoryV1:
    """Return the factory that opens the setup screen on ``client``'s connection, on the item its focus names."""

    def create(context: TuiScreenContextV1, /) -> Screen[None]:
        return SetupScreen(RuntimeSetupDoor(client), focus_item=setup_item_focus(context))

    return create
