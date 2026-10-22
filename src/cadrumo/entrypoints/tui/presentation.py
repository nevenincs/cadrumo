"""Pages the person asks this TUI to show from their desktop, as the root's own navigation targets.

A request names a page and nothing else. The root admits it exactly as it
admits a palette choice, against the destinations its current session can
open, so a request never reaches a page the root would refuse.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from textual.message import Message

from cadrumo_client.contracts.presentation import PresentationDestination

from .navigation import TuiDestinationIdV1, TuiFocusIdentityV1, TuiNavigationTargetV1, TuiScreenContextV1

PROFILE_AEAT_AUTH_FOCUS: Final = "profile.aeat_auth"
"""The profile page's focus that opens its AEAT access editor once the page is up."""

_ROUTES: Final[Mapping[PresentationDestination, tuple[TuiDestinationIdV1, str]]] = MappingProxyType(
    {
        "home": ("workbench.home", "presentation.home"),
        "ledger": ("workbench.ledger", "presentation.ledger"),
        "withholding": ("workbench.withholding", "presentation.withholding"),
        "declarations": ("workbench.declarations", "presentation.declarations"),
        "aeat_sync": ("workbench.aeat_sync", "presentation.aeat_sync"),
        "operations": ("workbench.operations", "presentation.operations"),
        "installation": ("workbench.installation", "presentation.installation"),
        "setup": ("workbench.setup", "presentation.setup"),
        "reference": ("workbench.reference", "presentation.reference"),
        "profile": ("workbench.profile", "profile.overview"),
        "aeat_auth": ("workbench.profile", PROFILE_AEAT_AUTH_FOCUS),
    }
)


class PagePresentationRequested(Message):
    """The person asked, from their desktop, that this session show one page."""

    def __init__(self, destination: PresentationDestination) -> None:
        """Carry only the requested page."""
        super().__init__()
        self.destination: PresentationDestination = destination


def presentation_target(destination: PresentationDestination) -> TuiNavigationTargetV1:
    """Return the navigation target the root admits for one requested page."""
    route, semantic_key = _ROUTES[destination]
    return TuiNavigationTargetV1(
        destination=route, focus=TuiFocusIdentityV1(destination=route, semantic_key=semantic_key)
    )


def opens_aeat_auth(context: TuiScreenContextV1) -> bool:
    """Whether a profile page was opened to edit its AEAT access."""
    return (
        context.destination == "workbench.profile"
        and context.focus is not None
        and context.focus.semantic_key == PROFILE_AEAT_AUTH_FOCUS
    )
