"""The Textual app base that keeps a Cadrumo app from waking while nobody uses it."""

from __future__ import annotations

import os
import sys
from typing import override

from textual.app import App, AutopilotCallbackType
from textual.driver import Driver
from textual.events import DescendantFocus
from textual.widgets import Input, TextArea

from ....core.config import Settings
from ....core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from ....core.logging import get_logger


class TuiRunFailedError(RuntimeError):
    """A Textual run ended unsuccessfully without retaining an exception."""

    def __init__(self, exit_code: int) -> None:
        """Retain the unsuccessful status independently of the app's return value."""
        self.exit_code = exit_code
        super().__init__(f"TUI exited unsuccessfully (code {exit_code})")


class QuietApp[ReturnType](App[ReturnType]):
    """A Textual app that schedules no work of its own while it sits idle.

    Textual blinks a focused text cursor on a half-second timer and repaints
    the screen on each blink, with no app-wide switch for that, so a text
    widget's cursor is held steady as the widget takes focus. On Windows the
    console input loop waits for input instead of waking every 100 ms.
    """

    def __init__(self) -> None:
        """Choose native ANSI handling before Textual installs its color filters."""
        # Textual chooses the NO_COLOR filter during construction. Its RGB
        # monochrome filter would turn the desktop theme's ANSI roles black.
        # It also reads a mere presence of NO_COLOR as monochrome, while
        # Cadrumo declares the variable a boolean: NO_COLOR=false keeps colour
        # in the CLI, so it keeps colour here.
        if "NO_COLOR" in os.environ and not Settings().no_color:
            del os.environ["NO_COLOR"]
        super().__init__(ansi_color=True if os.environ.get("TERM_PROGRAM") == "cadrumo" else None)

    @override
    async def run_async(
        self,
        *,
        headless: bool = False,
        inline: bool = False,
        inline_no_clear: bool = False,
        mouse: bool = True,
        size: tuple[int, int] | None = None,
        auto_pilot: AutopilotCallbackType | None = None,
    ) -> ReturnType | None:
        """Propagate failures after Textual has restored the terminal and shut down.

        Textual's production runner returns the app value even after an event
        or worker crashes. Its test runner alone re-raises the saved exception.
        A failed run must never look like an operator's ordinary dismissal to
        the session owner. ``App.run`` delegates here too.
        """
        try:
            result = await super().run_async(
                headless=headless,
                inline=inline,
                inline_no_clear=inline_no_clear,
                mouse=mouse,
                size=size,
                auto_pilot=auto_pilot,
            )
            if self._exception is not None:
                raise self._exception
            if self.return_code not in (None, 0):
                raise TuiRunFailedError(self.return_code)
            return result
        except BaseException as error:
            diagnostic_event(
                get_logger(__name__),
                "tui_application_failed",
                fields={
                    **diagnostic_error_fields(error),
                    "exit_code": self.return_code,
                    "outcome": "failed",
                },
                primary_error=error,
            )
            raise

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


__all__ = ["QuietApp", "TuiRunFailedError"]
