"""Small Cadrumo apps that the Windows input loop tests run in a console of their own.

Run as ``python -m cadrumo.entrypoints.tui.tests.windows_input_apps idle|escape``.
The escape app writes what it received to the file named by
``CADRUMO_TEST_RESULT``.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from ctypes import byref, wintypes
from pathlib import Path
from typing import override

from textual import events
from textual.app import ComposeResult
from textual.widgets import Static

from ..components.quiet_app import QuietApp


class IdleApp(QuietApp[None]):
    """Sits idle with nothing focused, then stops itself on one one-shot timer."""

    @override
    def compose(self) -> ComposeResult:
        yield Static("idle")

    def on_mount(self) -> None:
        self.set_timer(4.0, self.exit)


def _press_escape() -> None:
    """Write a lone Escape key into this process's own console input."""
    if sys.platform == "win32":
        from textual.drivers import win32

        time.sleep(1.0)
        record = win32.INPUT_RECORD()
        record.EventType = 0x0001
        record.Event.KeyEvent.bKeyDown = True
        record.Event.KeyEvent.wRepeatCount = 1
        record.Event.KeyEvent.wVirtualKeyCode = 0x1B
        record.Event.KeyEvent.uChar.UnicodeChar = "\x1b"
        written = wintypes.DWORD(0)
        console = win32.GetStdHandle(win32.STD_INPUT_HANDLE)
        win32.KERNEL32.WriteConsoleInputW(console, byref(record), 1, byref(written))


class EscapeApp(QuietApp[None]):
    """Presses a lone Escape on its own console once idle and records whether it arrived."""

    @override
    def compose(self) -> ComposeResult:
        yield Static("idle")

    def on_mount(self) -> None:
        threading.Thread(target=_press_escape, daemon=True).start()
        self.set_timer(6.0, lambda: self._finish("missed"))

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self._finish("escape")

    def _finish(self, outcome: str) -> None:
        Path(os.environ["CADRUMO_TEST_RESULT"]).write_text(outcome, encoding="utf-8")
        self.exit()


if __name__ == "__main__":
    {"idle": IdleApp, "escape": EscapeApp}[sys.argv[1]]().run()
