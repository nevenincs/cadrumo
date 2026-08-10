"""A permanent two-line channel for TUI state and diagnostics.

The body of a screen scrolls because its content can grow. Progress and
failure messages must not scroll with it: they describe the operation the
operator is waiting on and are the only explanation when that operation
cannot finish. This widget therefore owns its space at the top of the screen
and keeps the durable summary separate from the transient message below it.

Both lines are plain text. Operator-controlled values and exception messages
may contain Rich markup characters, so enabling markup here would turn data
into presentation and could hide or restyle the very diagnostic being shown.
"""

from __future__ import annotations

import math
from time import monotonic
from typing import Final, Literal

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Static

from ....core.redaction import redact_for_cli_output

StatusTone = Literal["idle", "progress", "success", "warning", "error"]
"""Closed presentation states supported by :class:`PinnedStatusBar`."""

_TONE_CLASSES: Final[tuple[str, ...]] = tuple(
    f"tone-{tone}" for tone in ("idle", "progress", "success", "warning", "error")
)
_GLYPH: Final[dict[StatusTone, str]] = {
    "idle": "·",
    "progress": "◌",
    "success": "✓",
    "warning": "⚠",
    "error": "✕",
}


class PinnedStatusBar(Vertical):
    """Always-visible summary and message lines for one full-screen surface."""

    DEFAULT_CSS = """
    PinnedStatusBar {
        dock: top;
        width: 100%;
        height: auto;
        min-height: 3;
        padding: 0 2;
        background: $surface;
        border-bottom: solid $primary;
    }

    PinnedStatusBar > .status-summary {
        width: 100%;
        height: 1;
    }

    PinnedStatusBar > .status-message {
        width: 100%;
        height: auto;
        min-height: 1;
    }

    PinnedStatusBar > .status-summary {
        color: $text-muted;
        text-style: bold;
    }

    PinnedStatusBar.tone-idle > .status-message { color: $text-muted; }
    PinnedStatusBar.tone-progress > .status-message { color: $accent; }
    PinnedStatusBar.tone-success > .status-message { color: $success; }
    PinnedStatusBar.tone-warning > .status-message { color: $warning; }
    PinnedStatusBar.tone-error > .status-message { color: $error; text-style: bold; }
    """

    tone: reactive[StatusTone] = reactive("idle", init=False)
    """Current closed tone, observable through Textual's reactive API."""

    def __init__(self, *, summary: str = "", id: str | None = None, classes: str | None = None) -> None:
        super().__init__(id=id, classes=classes)
        self._summary = redact_for_cli_output(self._require_text(summary, field="summary"))
        self._message = ""
        self._countdown_message = ""
        self._countdown_deadline: float | None = None
        self._countdown_timer: Timer | None = None
        self.add_class("tone-idle")

    @staticmethod
    def _require_text(value: object, *, field: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field} must be str, got {type(value).__name__}")
        return value

    @property
    def summary(self) -> str:
        """Plain summary currently held by the first line."""
        return self._summary

    @property
    def message(self) -> str:
        """Plain message currently held by the second line, without its glyph."""
        return self._message

    def compose(self) -> ComposeResult:
        yield Static(self._summary, markup=False, classes="status-summary")
        yield Static("", markup=False, classes="status-message")

    def set_summary(self, summary: str) -> None:
        """Replace the durable first line without changing message state."""
        self._summary = redact_for_cli_output(self._require_text(summary, field="summary"))
        self.query_one(".status-summary", Static).update(self._summary)

    def clear_message(self) -> None:
        """Return the message line to idle while preserving its reserved row."""
        self._cancel_countdown()
        self._set_message("idle", "")

    def show_progress(self, message: str, *, timeout_seconds: int | None = None) -> None:
        """Show an operation that is still running."""
        self._cancel_countdown()
        if timeout_seconds is None:
            self._set_message("progress", message)
            return
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._countdown_message = self._require_text(message, field="message")
        self._countdown_deadline = monotonic() + timeout_seconds
        self._render_countdown()
        self._countdown_timer = self.set_interval(1, self._render_countdown)

    def show_success(self, message: str) -> None:
        """Show a completed operation."""
        self._cancel_countdown()
        self._set_message("success", message)

    def show_warning(self, message: str) -> None:
        """Show a completed operation requiring attention."""
        self._cancel_countdown()
        self._set_message("warning", message)

    def show_error(self, message: str) -> None:
        """Show a refusal or failure requiring operator action."""
        self._cancel_countdown()
        self._set_message("error", message)

    def _render_countdown(self) -> None:
        deadline = self._countdown_deadline
        if deadline is None:
            return
        remaining = max(0, math.ceil(deadline - monotonic()))
        minutes, seconds = divmod(remaining, 60)
        self._set_message("progress", f"{self._countdown_message} Time remaining {minutes}:{seconds:02d}.")
        if remaining == 0 and self._countdown_timer is not None:
            self._countdown_timer.pause()

    def _cancel_countdown(self) -> None:
        if self._countdown_timer is not None:
            self._countdown_timer.pause()
        self._countdown_timer = None
        self._countdown_deadline = None
        self._countdown_message = ""

    def _set_message(self, tone: StatusTone, message: str) -> None:
        rendered = redact_for_cli_output(self._require_text(message, field="message"))
        self._message = rendered
        self.tone = tone
        self.remove_class(*_TONE_CLASSES)
        self.add_class(f"tone-{tone}")
        line = "" if not rendered else f"{_GLYPH[tone]} {rendered}"
        self.query_one(".status-message", Static).update(line)


__all__ = ["PinnedStatusBar", "StatusTone"]
