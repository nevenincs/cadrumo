"""Full-screen display of a freshly minted recovery mnemonic.

The terminal-direct channel the scripted door uses cannot render inside a
full-screen application without corrupting the display, so this screen is
the full-screen door's channel: the 24 words render here, on the screen
only, and are never written to a file, an envelope, or a log. The operator
confirms they have written them down; the confirmation returns the exact
proof to the application publication gate, which zeroises the wipeable
container as soon as that comparison completes.

The secret never enters a widget value or a Textual state that outlives
the screen: the mnemonic is read from the wipeable buffer once, into the
rendered markup. The masked re-entry is cleared before the screen closes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from ....core.i18n import tr

if TYPE_CHECKING:
    from collections.abc import Callable

    from ....application.user_profile import ProfileRecoveryEnrollment


class RecoveryWordsScreen(Screen[None]):
    """Show the mnemonic once and return masked exact re-entry proof."""

    DEFAULT_CSS = """
    RecoveryWordsScreen {
        align: center middle;
    }
    #words-panel {
        width: 100%;
        height: auto;
        border: round $primary;
        padding: 1 2;
    }
    #words-heading { text-style: bold; margin-bottom: 1; }
    #words-value { color: $warning; margin-bottom: 1; }
    #words-warning { color: $text-muted; margin-bottom: 1; }
    #words-actions { height: auto; align-horizontal: right; }
    """

    def __init__(
        self,
        *,
        enrollment: ProfileRecoveryEnrollment,
        on_confirm: Callable[[str], None],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__()
        self._enrollment = enrollment
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._resolved = False

    @override
    def compose(self) -> ComposeResult:
        with Container(id="words-panel"):
            yield Static(tr("cli.config.custody.recovery_words_heading"), id="words-heading")
            yield Static(self._enrollment.recovery_key.mnemonic, id="words-value")
            yield Static(tr("cli.config.custody.recovery_words_warning"), id="words-warning")
            yield Input(
                password=True,
                placeholder=tr("cli.config.profile.create_recovery_verification_prompt"),
                id="field-recovery-verification",
            )
            with Container(id="words-actions"):
                yield Button(tr("cli.config.custody.recovery_words_cancel"), id="btn-cancel-words")
                yield Button(tr("cli.config.custody.recovery_words_confirm"), id="btn-confirm-words")

    @on(Button.Pressed, "#btn-confirm-words")
    def _confirm(self) -> None:
        if self._resolved:
            return
        supplied = self.query_one("#field-recovery-verification", Input).value
        expected = self._enrollment.recovery_key.mnemonic
        try:
            if supplied != expected:
                self._refuse_once()
                self.dismiss(None)
                return
        finally:
            self.query_one("#field-recovery-verification", Input).value = ""
            del expected
        self._resolved = True
        self.dismiss(None)
        self._on_confirm(supplied)

    @on(Button.Pressed, "#btn-cancel-words")
    def _cancel(self) -> None:
        self._refuse_once()
        self.dismiss(None)

    def on_unmount(self) -> None:
        """Treat escape, shutdown, and every non-confirm exit as refusal."""
        self._refuse_once()

    def _refuse_once(self) -> None:
        if self._resolved:
            return
        self._resolved = True
        self._enrollment.recovery_key.wipe()
        self._on_cancel()
