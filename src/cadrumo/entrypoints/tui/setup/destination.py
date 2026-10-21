"""The setup destination: one screen per admitted route, bound to the signed-in runtime connection."""

from __future__ import annotations

from textual.screen import Screen

from cadrumo_client.transport.frontend_client import FrontendClient

from ..navigation import TuiScreenContextV1, TuiScreenFactoryV1
from .door import RuntimeSetupDoor
from .screen import SetupScreen

__all__ = ["setup_screen_factory"]


def setup_screen_factory(client: FrontendClient) -> TuiScreenFactoryV1:
    """Return the factory that opens the setup screen on ``client``'s connection."""

    def create(context: TuiScreenContextV1, /) -> Screen[None]:
        del context
        return SetupScreen(RuntimeSetupDoor(client))

    return create
