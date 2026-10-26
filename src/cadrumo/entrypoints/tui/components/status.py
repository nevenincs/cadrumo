"""Reusable, state-local status presentation for Textual surfaces."""

from __future__ import annotations

from typing import ClassVar, Final, Literal, override

from rich.style import Style
from textual.app import ComposeResult, RenderResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.renderables.bar import Bar
from textual.widget import Widget
from textual.widgets import LoadingIndicator, Static

from .theme import tokenised

type StatusTone = Literal["idle", "progress", "success", "warning", "error"]
"""Closed presentation states supported by :class:`PinnedStatusBar`."""

_TONES: Final[tuple[StatusTone, ...]] = ("idle", "progress", "success", "warning", "error")
#: The tone a status carries before any has been applied.
_DEFAULT_TONE: Final[StatusTone] = "idle"
_TONE_CLASSES: Final[tuple[str, ...]] = tuple(f"tone-{tone}" for tone in _TONES)
_GLYPH: Final[dict[StatusTone, str]] = {
    "idle": "·",
    "progress": "◌",
    "success": "✓",
    "warning": "▲",
    "error": "×",
}
#: The spinner's frame period while progress shows, as Textual draws it.
_SPINNER_REFRESH: Final = 1 / 16


class _StatusSpinner(LoadingIndicator):
    """The bar's progress spinner, which refreshes only while progress shows.

    Textual's indicator refreshes on a timer from mount whether it is displayed
    or not, so a hidden one would keep an idle screen waking 16 times a second.
    """

    def on_mount(self) -> None:
        # Textual runs this before the base class's mount handler, which starts
        # the refresh; the bar's tone decides once that handler has run.
        parent = self.parent
        self.call_next(self.spin, isinstance(parent, PinnedStatusBar) and parent.tone == "progress")

    def spin(self, spinning: bool) -> None:
        self.auto_refresh = _SPINNER_REFRESH if spinning else None


class PinnedStatusBar(Vertical):
    """Render supplied summary and status text in a pinned screen channel."""

    DEFAULT_CSS = tokenised("""
    PinnedStatusBar {
        dock: top;
        width: 100%;
        height: auto;
        padding: $cadrumo-space-0 $cadrumo-gutter;
        background: $surface;
        border-bottom: $cadrumo-rule $primary;
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

    PinnedStatusBar > .status-spinner { height: $cadrumo-band-height; display: none; }
    PinnedStatusBar.tone-progress > .status-spinner { display: block; }

    PinnedStatusBar.tone-idle > .status-message { color: $text-muted; }
    PinnedStatusBar.tone-progress > .status-message { color: $accent; }
    PinnedStatusBar.tone-success > .status-message { color: $success; }
    PinnedStatusBar.tone-warning > .status-message { color: $warning; }
    PinnedStatusBar.tone-error > .status-message { color: $error; text-style: bold; }
    """)

    def __init__(self, *, summary: str = "", id: str | None = None, classes: str | None = None) -> None:
        """Initialize the pinned channel with an optional supplied summary."""
        super().__init__(id=id, classes=classes)
        self._summary = self._require_text(summary, field="summary")
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
        for tone in _TONES:
            if self.has_class(f"tone-{tone}"):
                return tone
        return _DEFAULT_TONE

    @override
    def compose(self) -> ComposeResult:
        yield Static(self._summary, markup=False, classes="status-summary")
        yield _StatusSpinner(classes="status-spinner")
        yield Static("", markup=False, classes="status-message")

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
        rendered = self._require_text(message, field="message")
        self._message = rendered
        self.remove_class(*_TONE_CLASSES)
        self.add_class(f"tone-{tone}")
        line = "" if not rendered else f"{_GLYPH[tone]} {rendered}"
        self.query_one(".status-message", Static).update(line)
        self.query_one(_StatusSpinner).spin(tone == "progress")
        self._sync_visibility()

    def _sync_visibility(self) -> None:
        """Consume screen space only while supplied text has something to show."""
        self.set_class(not (self._summary or self._message), "empty")


class ProgressLine(Widget, can_focus=False):
    """A bar filled to ``progress`` of ``total`` steps, repainted only when they change.

    Textual's ``ProgressBar`` re-renders every second from mount to keep an
    estimated time current, which a count of completed steps does not show.
    """

    COMPONENT_CLASSES: ClassVar[set[str]] = {"progress-line--bar", "progress-line--complete"}

    DEFAULT_CSS = tokenised("""
    ProgressLine { width: 1fr; height: $cadrumo-band-height; }
    ProgressLine > .progress-line--bar { color: $primary; background: $surface; }
    ProgressLine > .progress-line--complete { color: $success; background: $surface; }
    """)

    total: reactive[int] = reactive(1)
    progress: reactive[int] = reactive(0)

    def update(self, *, total: int, progress: int) -> None:
        """Show ``progress`` completed steps of ``total``."""
        self.total = total
        self.progress = progress

    @override
    def render(self) -> RenderResult:
        fraction = min(1.0, max(0.0, self.progress / self.total)) if self.total > 0 else 0.0
        style = self.get_component_rich_style("progress-line--complete" if fraction >= 1 else "progress-line--bar")
        return Bar(
            highlight_range=(0, self.size.width * fraction),
            highlight_style=Style.from_color(style.color),
            background_style=Style.from_color(style.bgcolor),
        )


__all__ = ["PinnedStatusBar", "ProgressLine", "StatusTone"]
