"""Full-screen display of a freshly minted recovery mnemonic.

The terminal-direct channel the scripted door uses cannot render inside a
full-screen application without corrupting the display, so this screen is
the full-screen door's channel: the 24 words render here, on the screen
only, and are never written to a file, an envelope, or a log. The operator
confirms they have written them down; the confirmation is what releases
the flow, and the wipeable container is zeroised at that moment — the
earliest the flow allows, per the enrollment's own contract.

The secret never enters a widget value or a Textual state that outlives
the screen: the mnemonic is read from the wipeable buffer once, into the
rendered markup, and the buffer is zeroised on confirm.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, Static

from ....core.i18n import tr

if TYPE_CHECKING:
    from collections.abc import Callable

    from ....application.user_profile import ProfileRecoveryEnrollment


class RecoveryWordsScreen(Screen[None]):
    """Show the mnemonic once, wipe on the operator's confirmation."""

    DEFAULT_CSS = """
    RecoveryWordsScreen {
        align: center middle;
    }
    #words-panel {
        width: 72;
        height: auto;
        border: round $primary;
        padding: 1 2;
    }
    #words-heading { text-style: bold; margin-bottom: 1; }
    #words-value { color: $warning; margin-bottom: 1; }
    #words-warning { color: $text-muted; margin-bottom: 1; }
    #words-actions { height: auto; align-horizontal: right; }
    """

    def __init__(self, *, enrollment: ProfileRecoveryEnrollment, on_done: Callable[[], None]) -> None:
        super().__init__()
        self._enrollment = enrollment
        self._on_done = on_done
        self._wiped = False

    def compose(self) -> ComposeResult:
        with Container(id="words-panel"):
            yield Static(tr("cli.config.custody.recovery_words_heading"), id="words-heading")
            yield Static(self._enrollment.recovery_key.mnemonic, id="words-value")
            yield Static(tr("cli.config.custody.recovery_words_warning"), id="words-warning")
            with Container(id="words-actions"):
                yield Button(tr("cli.config.custody.recovery_words_confirm"), id="btn-confirm-words")

    @on(Button.Pressed, "#btn-confirm-words")
    def _confirm(self) -> None:
        if self._wiped:
            return
        self._wiped = True
        self._enrollment.recovery_key.wipe()
        self.dismiss(None)
        self._on_done()
