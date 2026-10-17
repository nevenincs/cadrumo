"""The Textual app base that keeps a Cadrumo app from waking while nobody uses it."""

from __future__ import annotations

import sys
from typing import override

from textual.app import App
from textual.driver import Driver
from textual.events import DescendantFocus
from textual.widgets import Input, TextArea


class QuietApp[ReturnType](App[ReturnType]):
    """A Textual app that schedules no work of its own while it sits idle.

    Textual blinks a focused text cursor on a half-second timer and repaints
    the screen on each blink, with no app-wide switch for that, so a text
    widget's cursor is held steady as the widget takes focus. On Windows the
    console input loop waits for input instead of waking every 100 ms.
    """

    @override
    def get_driver_class(self) -> type[Driver]:
        """Use the Windows driver whose input loop sleeps until input arrives."""
        driver = super().get_driver_class()
        if sys.platform == "win32":
            from textual.drivers.windows_driver import WindowsDriver

            if driver is WindowsDriver:
                from ..windows_input import QuietWindowsDriver

                return QuietWindowsDriver
        return driver

    def on_descendant_focus(self, event: DescendantFocus) -> None:
        """Hold the cursor of the text widget taking focus steady."""
        widget = event.widget
        if isinstance(widget, Input | TextArea):
            widget.cursor_blink = False


__all__ = ["QuietApp"]
