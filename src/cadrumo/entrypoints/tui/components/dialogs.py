"""Reusable confirmation dialog for irreversible TUI actions."""

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from ..components.theme import tokenised

_CONFIRM_DIALOG_CSS = tokenised("""
#confirm-dialog {
    border: $cadrumo-radius-overlay $warning;
    background: $surface;
    padding: $cadrumo-space-0 $cadrumo-space-1;
    width: 100%;
    height: auto;
}
#confirm-title { text-style: bold; margin: $cadrumo-space-0; }
#confirm-message { color: $text; margin: $cadrumo-space-0; }
#confirm-actions { height: auto; align-horizontal: right; margin: $cadrumo-space-0; }
#confirm-actions Button { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap; }
""")


class ConfirmScreen(ModalScreen[bool]):
    """Ask before an irreversible action and default to declining it."""

    DEFAULT_CSS = _CONFIRM_DIALOG_CSS
    BINDINGS: ClassVar = [Binding("escape", "decline", "", show=False), Binding("y", "confirm", "", show=False)]

    def __init__(self, *, title: str, message: str, confirm_label: str, cancel_label: str) -> None:
        """Store the localized confirmation copy."""
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
        """Focus the safe declining action first."""
        self.query_one("#btn-confirm-cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dismiss with the selected confirmation state."""
        self.dismiss(event.button.id == "btn-confirm-accept")

    def action_decline(self) -> None:
        """Dismiss without approving the action."""
        self.dismiss(False)

    def action_confirm(self) -> None:
        """Dismiss with explicit approval."""
        self.dismiss(True)


__all__ = ["ConfirmScreen"]
