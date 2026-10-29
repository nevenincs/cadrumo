"""Register views the person asks this TUI to show from their desktop, as the root's own navigation targets.

A request names one register view whose surfaces include the TUI, and the
parameters that element declares. The root admits it exactly as it admits a
palette choice, against the destinations its current session can open, so a
request never reaches a page the root would refuse. How the TUI implements
each register id is this module's table, never the register's.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from textual.message import Message

from cadrumo_client.contracts.navigation import ViewLink

from .ledger.controller import LEDGER_TRANSACTION_FOCUS
from .navigation import TuiDestinationIdV1, TuiFocusIdentityV1, TuiNavigationTargetV1, TuiScreenContextV1

PROFILE_AEAT_AUTH_FOCUS: Final = "profile.aeat_auth"
"""The profile page's focus that opens its AEAT access editor once the page is up."""

TUI_ROUTES: Final[Mapping[str, tuple[TuiDestinationIdV1, str]]] = MappingProxyType(
    {
        "home": ("workbench.home", "presentation.home"),
        "ledger": ("workbench.ledger", "presentation.ledger"),
        "withholding": ("workbench.withholding", "presentation.withholding"),
        "declarations": ("workbench.declarations", "presentation.declarations"),
        "aeat-sync": ("workbench.aeat_sync", "presentation.aeat_sync"),
        "operations": ("workbench.operations", "presentation.operations"),
        "installation": ("workbench.installation", "presentation.installation"),
        "reference": ("workbench.reference", "presentation.reference"),
        "profile": ("workbench.profile", "profile.overview"),
        "profile/aeat-access": ("workbench.profile", PROFILE_AEAT_AUTH_FOCUS),
    }
)
"""Each register id the TUI implements, with the destination and focus it opens."""

TUI_PARAM_FOCUS: Final[Mapping[str, Mapping[str, str]]] = MappingProxyType(
    {"ledger": MappingProxyType({"select": LEDGER_TRANSACTION_FOCUS})}
)
"""Per register id, each link parameter the TUI honours and the focus that restores its value."""


class PagePresentationRequested(Message):
    """The person asked, from their desktop, that this session show one register view."""

    def __init__(self, view: ViewLink) -> None:
        """Carry only the requested view and its parameters."""
        super().__init__()
        self.view: ViewLink = view


def presentation_target(view: ViewLink) -> TuiNavigationTargetV1:
    """Return the navigation target the root admits for one requested view.

    A parameter the TUI honours replaces the page's own focus with the focus
    that restores its value, such as one Ledger transaction selected by id.

    Raises:
        KeyError: The TUI does not implement the view.
    """
    route, semantic_key = TUI_ROUTES[view.view_id]
    restore_token: str | None = None
    honoured = TUI_PARAM_FOCUS.get(view.view_id, {})
    for name, value in view.params:
        focus = honoured.get(name)
        if focus is not None:
            semantic_key, restore_token = focus, value
    return TuiNavigationTargetV1(
        destination=route,
        focus=TuiFocusIdentityV1(destination=route, semantic_key=semantic_key, restore_token=restore_token),
    )


def opens_aeat_auth(context: TuiScreenContextV1) -> bool:
    """Whether a profile page was opened to edit its AEAT access."""
    return (
        context.destination == "workbench.profile"
        and context.focus is not None
        and context.focus.semantic_key == PROFILE_AEAT_AUTH_FOCUS
    )
