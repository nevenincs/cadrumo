"""The Textual app base that keeps a Cadrumo app from waking while nobody uses it."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, ClassVar, Literal, override

from textual import events, on
from textual.app import App, AutopilotCallbackType
from textual.driver import Driver
from textual.events import DescendantFocus
from textual.widgets import Input, TextArea

from ....core.config import Settings
from ....core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from ....core.errors.hierarchy import CadrumoError
from ....core.logging import get_logger

if TYPE_CHECKING:
    from rich.console import RenderableType


class TuiRunFailedError(CadrumoError):
    """A Textual run ended unsuccessfully without retaining an exception."""

    def __init__(self, exit_code: int) -> None:
        """Retain the unsuccessful status independently of the app's return value."""
        self.exit_code = exit_code
        super().__init__(context={"exit_code": exit_code})


class QuietApp[ReturnType](App[ReturnType]):
    """A Textual app that schedules no work of its own while it sits idle.

    Textual blinks a focused text cursor on a half-second timer and repaints
    the screen on each blink, with no app-wide switch for that, so a text
    widget's cursor is held steady as the widget takes focus. On Windows the
    console input loop waits for input instead of waking every 100 ms.
    """

    DEFER_TERMINAL_READY: ClassVar[bool] = False
    """Roots that load asynchronously announce their first actionable screen themselves."""

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
        self._terminal_presented = False

    @on(events.Mount)
    def _present_mounted_terminal(self) -> None:
        """Reveal ordinary screens only after their first refresh."""
        if not self.DEFER_TERMINAL_READY:
            self.call_after_refresh(self.present_terminal)

    def _terminal_presentation(self, phase: Literal["loading", "ready"]) -> None:
        # Use the driver's ordered output queue, after the screen's VT frame.
        # This is presentation only; it carries no sign-in or profile state.
        if os.environ.get("TERM_PROGRAM") == "cadrumo" and not self.is_headless and self._driver is not None:
            self._driver.write(f"\x1b]777;cadrumo;presentation;{phase}\x1b\\")

    def present_terminal(self) -> None:
        """Announce a rendered screen, including an actionable refusal."""
        if self.is_running and not self._exit and not self._terminal_presented:
            self._terminal_presented = True
            self._terminal_presentation("ready")

    @override
    def exit(
        self,
        result: ReturnType | None = None,
        return_code: int = 0,
        message: RenderableType | None = None,
    ) -> None:
        """Cover terminal teardown and the handoff to the next Textual app."""
        if self._terminal_presented:
            self._terminal_presented = False
            self._terminal_presentation("loading")
        super().exit(result, return_code, message)

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
