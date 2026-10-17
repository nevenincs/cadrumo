"""The Textual app base that keeps a Cadrumo app from waking while nobody uses it."""

from __future__ import annotations

from textual.app import App
from textual.events import DescendantFocus
from textual.widgets import Input, TextArea


class QuietApp[ReturnType](App[ReturnType]):
    """A Textual app that schedules no work of its own while it sits idle.

    Textual blinks a focused text cursor on a half-second timer and repaints
    the screen on each blink, with no app-wide switch for that, so a text
    widget's cursor is held steady as the widget takes focus.
    """

    def on_descendant_focus(self, event: DescendantFocus) -> None:
        """Hold the cursor of the text widget taking focus steady."""
        widget = event.widget
        if isinstance(widget, Input | TextArea):
            widget.cursor_blink = False


__all__ = ["QuietApp"]
