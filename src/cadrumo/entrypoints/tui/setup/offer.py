"""Offer a setup item's setup only where the item's current row says setup can act now.

A refusal, a paused batch or a reading that stood without its model names the
setup action of the item it needs. Whether that setup can run now is the
item's own row, read through the same quick status the setup page reads. A row
whose one action sets the item up gets the offer, labelled with that action
and the item's name. A row that reads blocked, or any state setup cannot change
from here, shows its own sentence and offers nothing, so the person is never
sent to a setup that refuses. Without a row to read nothing is offered.
"""

from __future__ import annotations

from typing import ClassVar, Protocol, override, runtime_checkable

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Static

from ....application.dependency_contracts import (
    DEPENDENCY_SETUP_RECOVERIES,
    DependencyItemDeclaration,
    DependencyStatusRow,
)
from ....application.dependency_registry import dependency_item_declarations
from ....application.dependency_wording import (
    dependency_action_key,
    dependency_held_sentence,
    dependency_name_key,
)
from ....core.i18n.render import tr
from .focus import SetupItemRequested

__all__ = [
    "SetupItemOffer",
    "SetupRowSourcePort",
    "current_setup_row",
    "offers_setup",
    "setup_held_text",
    "setup_item_for_action",
    "setup_offer_label",
]


def _declaration(item_id: str) -> DependencyItemDeclaration:
    return next(declaration for declaration in dependency_item_declarations() if declaration.item_id == item_id)


def setup_item_for_action(action_id: str | None) -> str | None:
    """Name the setup item whose declared recovery action is ``action_id``; ``None`` for any other action."""
    if action_id is None:
        return None
    return next(
        (
            declaration.item_id
            for declaration in dependency_item_declarations()
            if declaration.recovery_action_id == action_id
        ),
        None,
    )


@runtime_checkable
class SetupRowSourcePort(Protocol):
    """A host that reads one setup item's current row from the quick status."""

    async def read_setup_row(self, item_id: str) -> DependencyStatusRow | None:
        """Return ``item_id``'s current row, or ``None`` when it cannot be read."""
        ...


async def current_setup_row(host: object, item_id: str) -> DependencyStatusRow | None:
    """Read ``item_id``'s current row through ``host``; ``None`` where the host reads no setup status."""
    if not isinstance(host, SetupRowSourcePort):
        return None
    return await host.read_setup_row(item_id)


def offers_setup(row: DependencyStatusRow) -> bool:
    """Whether the row's one action sets its item up now."""
    return row.recovery in DEPENDENCY_SETUP_RECOVERIES


def setup_offer_label(row: DependencyStatusRow) -> str:
    """Label the offer with the row's own action and the item's name."""
    if row.recovery is None:
        raise ValueError("a row without an action offers no setup")
    return f"{tr(dependency_action_key(row.recovery))}: {tr(dependency_name_key(_declaration(row.item_id)))}"


def setup_held_text(row: DependencyStatusRow) -> str:
    """Say why the item cannot be set up from here: its name and its row's own sentence."""
    return dependency_held_sentence(row, _declaration(row.item_id))


class SetupItemOffer(Horizontal):
    """Beside something that could not run for a setup item: its setup, or why there is none.

    Shown for the item a verdict names once its current row is read: a button
    that opens the setup page on the item when the row's action sets it up, or
    the row's own sentence when it cannot be set up from here. Nothing is shown
    when no item is named or its row cannot be read.
    """

    DEFAULT_CSS: ClassVar[str] = """
    SetupItemOffer { height: auto; }
    SetupItemOffer > Static { width: 1fr; height: auto; }
    """

    def __init__(self, *, offer_id: str) -> None:
        """Start empty under the widget identity ``offer_id``; :meth:`show_for` reads the named item's row."""
        super().__init__(id=offer_id)
        self._row: DependencyStatusRow | None = None
        self._reads = 0

    @property
    def row(self) -> DependencyStatusRow | None:
        """The row this offer was last shown for."""
        return self._row

    @override
    def compose(self) -> ComposeResult:
        yield Static("", classes="setup-item-offer-text", markup=False)
        yield Button("", classes="setup-item-offer-button -primary")

    def on_mount(self) -> None:
        """Show nothing until an item is named."""
        self.repaint()

    async def show_for(self, item_id: str | None) -> None:
        """Read ``item_id``'s current row and show its offer; ``None`` clears the offer."""
        self._reads += 1
        read = self._reads
        row = None if item_id is None else await current_setup_row(self.app, item_id)
        if read != self._reads or not self.is_mounted:
            return
        self._row = row
        self.repaint()

    def clear(self) -> None:
        """Withdraw the offer, including one whose row is still being read."""
        self._reads += 1
        self._row = None
        self.repaint()

    def repaint(self) -> None:
        """Word the offer in the current language."""
        row = self._row
        text = self.query_one(".setup-item-offer-text", Static)
        button = self.query_one(".setup-item-offer-button", Button)
        self.display = row is not None
        if row is None:
            text.update("")
            button.display = False
        elif offers_setup(row):
            text.update("")
            text.display = False
            button.label = setup_offer_label(row)
            button.display = True
        else:
            text.update(setup_held_text(row))
            text.display = True
            button.display = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Ask the root to open the setup page on the item."""
        event.stop()
        row = self._row
        if row is not None and offers_setup(row):
            self.app.post_message(SetupItemRequested(row.item_id))
