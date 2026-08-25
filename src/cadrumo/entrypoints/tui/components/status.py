"""Reusable, state-local status presentation for Textual surfaces."""

from __future__ import annotations

from typing import Final, Literal, override

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from ....core.redaction import redact_for_cli_output

StatusTone = Literal["idle", "progress", "success", "warning", "error"]
"""Closed presentation states supported by :class:`PinnedStatusBar`."""

_TONES: Final[tuple[StatusTone, ...]] = ("idle", "progress", "success", "warning", "error")
_TONE_CLASSES: Final[tuple[str, ...]] = tuple(f"tone-{tone}" for tone in _TONES)
_GLYPH: Final[dict[StatusTone, str]] = {
    "idle": "·",
    "progress": "◌",
    "success": "✓",
    "warning": "⚠",
    "error": "✕",
}


class PinnedStatusBar(Vertical):
    """Render supplied summary and status text in a pinned screen channel."""

    DEFAULT_CSS = """
    PinnedStatusBar {
        dock: top;
        width: 100%;
        height: auto;
        padding: 0 2;
        background: $surface;
        border-bottom: solid $primary;
    }

    PinnedStatusBar.empty { display: none; }

    PinnedStatusBar > .status-summary {
        width: 100%;
        height: auto;
    }

    PinnedStatusBar > .status-summary.empty { display: none; }

    PinnedStatusBar > .status-message {
        width: 100%;
        height: auto;
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

    def __init__(self, *, summary: str = "", id: str | None = None, classes: str | None = None) -> None:
        """Initialize the pinned channel with an optional supplied summary."""
        super().__init__(id=id, classes=classes)
        self._summary = redact_for_cli_output(self._require_text(summary, field="summary"))
        self._message = ""
        self.add_class("tone-idle")
        self.set_class(not self._summary, "empty")

    @staticmethod
    def _require_text(value: object, *, field: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field} must be str, got {type(value).__name__}")
        return value

    @property
    def summary(self) -> str:
        """Plain summary currently rendered by the first line."""
        return self._summary

    @property
    def message(self) -> str:
        """Plain status text currently rendered by the second line."""
        return self._message

    @property
    def tone(self) -> StatusTone:
        """Closed tone currently rendered by the status message."""
        return next((tone for tone in _TONES if self.has_class(f"tone-{tone}")), "idle")

    @override
    def compose(self) -> ComposeResult:
        yield Static(self._summary, markup=False, classes="status-summary")
        yield Static("", markup=False, classes="status-message")

    def set_summary(self, summary: str) -> None:
        """Render a replacement summary without changing the status message."""
        self._summary = redact_for_cli_output(self._require_text(summary, field="summary"))
        summary_line = self.query_one(".status-summary", Static)
        summary_line.update(self._summary)
        summary_line.set_class(not self._summary, "empty")
        self._sync_visibility()

    def clear_message(self) -> None:
        """Render an idle empty message and collapse an empty channel."""
        self._set_message("idle", "")

    def show_progress(self, message: str) -> None:
        """Render the supplied in-progress status text."""
        self._set_message("progress", message)

    def show_success(self, message: str) -> None:
        """Render the supplied completed status text."""
        self._set_message("success", message)

    def show_warning(self, message: str) -> None:
        """Render the supplied attention status text."""
        self._set_message("warning", message)

    def show_error(self, message: str) -> None:
        """Render the supplied failure or refusal status text."""
        self._set_message("error", message)

    def _set_message(self, tone: StatusTone, message: str) -> None:
        rendered = redact_for_cli_output(self._require_text(message, field="message"))
        self._message = rendered
        self.remove_class(*_TONE_CLASSES)
        self.add_class(f"tone-{tone}")
        line = "" if not rendered else f"{_GLYPH[tone]} {rendered}"
        self.query_one(".status-message", Static).update(line)
        self._sync_visibility()

    def _sync_visibility(self) -> None:
        """Consume screen space only while supplied text has something to show."""
        self.set_class(not (self._summary or self._message), "empty")


__all__ = ["PinnedStatusBar", "StatusTone"]
