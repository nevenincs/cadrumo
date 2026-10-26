"""Open the setup screen on one setup item: the navigation target, its focus, and the request a screen posts.

A refused operation whose recovery is one setup item's action asks the root
to open the setup page on that item's row. The request carries only the item;
the root admits it as it admits any other navigation, so a page that cannot be
opened, or a destination that must not be left yet, keeps the person where
they are.
"""

from __future__ import annotations

from typing import Final

from textual.message import Message

from ....application.dependency_registry import dependency_item_declarations
from ..navigation import TuiFocusIdentityV1, TuiNavigationTargetV1, TuiScreenContextV1

__all__ = ["SETUP_ITEM_FOCUS_PREFIX", "SetupItemRequested", "setup_item_focus", "setup_item_target"]

SETUP_ITEM_FOCUS_PREFIX: Final = "setup.item."
"""The setup page's focus that selects one item's row, followed by the item id."""


def _declared(item_id: str) -> bool:
    return any(declaration.item_id == item_id for declaration in dependency_item_declarations())


class SetupItemRequested(Message):
    """The person asked to set up one item from the refusal that needs it."""

    def __init__(self, item_id: str) -> None:
        """Carry only the setup item's id."""
        super().__init__()
        self.item_id: str = item_id


def setup_item_target(item_id: str) -> TuiNavigationTargetV1:
    """Return the navigation target that opens the setup page on ``item_id``'s row.

    Raises:
        ValueError: ``item_id`` is not a declared setup item.
    """
    if not _declared(item_id):
        raise ValueError(f"unknown setup item: {item_id!r}")
    return TuiNavigationTargetV1(
        destination="workbench.setup",
        focus=TuiFocusIdentityV1(destination="workbench.setup", semantic_key=SETUP_ITEM_FOCUS_PREFIX + item_id),
    )


def setup_item_focus(context: TuiScreenContextV1) -> str | None:
    """Return the setup item a setup page was opened on, or ``None`` for the page as a whole."""
    focus = context.focus
    if context.destination != "workbench.setup" or focus is None:
        return None
    key = focus.semantic_key
    if not key.startswith(SETUP_ITEM_FOCUS_PREFIX):
        return None
    item_id = key.removeprefix(SETUP_ITEM_FOCUS_PREFIX)
    return item_id if _declared(item_id) else None
