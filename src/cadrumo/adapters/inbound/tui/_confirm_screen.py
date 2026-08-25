"""A yes/no dialog for an intent the engine will carry out unconditionally.

Some engine transitions are deliberately unconditional at the engine layer —
:func:`~cadrumo.application.flows.restart_flow` wipes the whole
:class:`~cadrumo.application.flows.FlowState` and states plainly that
confirming the wipe is "a frontend responsibility". A frontend that calls
straight through on one keystroke does not discharge that responsibility; it
ignores it. This screen is the one place that responsibility is met, so every
irreversible engine call the TUI offers behind a single key chord gates
through it rather than growing its own ad hoc yes/no prompt.
"""

from __future__ import annotations

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from ....core.i18n import tr

_CONFIRM_DIALOG_CSS = """
#confirm-dialog {
    border: thick $warning;
    background: $surface;
    padding: 0 1;
    width: 100%;
    height: auto;
}
#confirm-title { text-style: bold; margin: 0; }
#confirm-message { color: $text; margin: 0; }
#confirm-actions { height: auto; align-horizontal: right; margin: 0; }
#confirm-actions Button { margin: 0 0 0 1; }
"""
"""Styling carried by the dialog itself, mirroring
:mod:`~cadrumo.entrypoints.tui.profile.editor`: a host that did not
happen to declare these rules would render the dialog unstyled otherwise."""


class ConfirmScreen(ModalScreen[bool]):
    """Ask before an irreversible action; dismisses ``True`` only on explicit confirm.

    ``escape`` and the cancel button both dismiss ``False`` — declining is
    always the easy, low-effort path, and only the labelled confirm button
    (or the ``y`` chord it mirrors) carries the destructive intent out.
    """

    DEFAULT_CSS = _CONFIRM_DIALOG_CSS
    BINDINGS: ClassVar = [
        Binding("escape", "decline", "", show=False),
        Binding("y", "confirm", "", show=False),
    ]

    def __init__(self, *, title: str, message: str, confirm_label: str, cancel_label: str) -> None:
        super().__init__()
        self._title = title
        self._message = message
        self._confirm_label = confirm_label
        self._cancel_label = cancel_label

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Label(self._title, id="confirm-title")
            yield Static(self._message, id="confirm-message")
            with Horizontal(id="confirm-actions"):
                yield Button(self._cancel_label, id="btn-confirm-cancel")
                yield Button(self._confirm_label, id="btn-confirm-accept", classes="-primary", variant="error")

    def on_mount(self) -> None:
        self.query_one("#btn-confirm-cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-confirm-accept")

    def action_decline(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)


def confirm_restart_dialog() -> ConfirmScreen:
    """Build the one restart-confirmation dialog every flow screen pushes.

    Centralised so the question screen and the review screen — the two
    places ``ctrl+n`` is bound — cannot drift into two different wordings
    for the same irreversible action.
    """
    return ConfirmScreen(
        title=tr("flows.tui.confirm_restart.title"),
        message=tr("flows.tui.confirm_restart.message"),
        confirm_label=tr("flows.tui.confirm_restart.confirm"),
        cancel_label=tr("flows.tui.confirm_restart.cancel"),
    )


__all__ = ["ConfirmScreen", "confirm_restart_dialog"]
