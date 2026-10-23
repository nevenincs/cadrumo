"""Small Cadrumo apps that the Windows input loop tests run in a console of their own.

Run as ``python -m cadrumo.entrypoints.tui.tests.windows_input_apps idle|resumed|escape``
in a working directory selected by the parent test. The escape app writes what it
received, and the resumed app whether its input loop still waits on a stop event,
to ``result.txt`` there. The idle apps read the base name of the parent's ready and
stop events from ``events.txt`` there, and write their process and input thread
ids to ``idle.txt`` once idle.
"""

from __future__ import annotations

import ctypes
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

#: The wait that ends only when the event is set.
INFINITE = 0xFFFFFFFF
_WAIT_OBJECT_0 = 0x00000000
_WAIT_TIMEOUT = 0x00000102

if sys.platform == "win32":
    _kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    _create_event = _kernel.CreateEventW
    _create_event.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
    _create_event.restype = wintypes.HANDLE
    _set_event = _kernel.SetEvent
    _set_event.argtypes = (wintypes.HANDLE,)
    _set_event.restype = wintypes.BOOL
    _wait = _kernel.WaitForSingleObject
    _wait.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    _wait.restype = wintypes.DWORD
    _close_handle = _kernel.CloseHandle
    _close_handle.argtypes = (wintypes.HANDLE,)
    _close_handle.restype = wintypes.BOOL


def open_event(name: str) -> int:
    """Create a named manual-reset kernel event, or open it if the other process already did."""
    if sys.platform == "win32":
        handle = _create_event(None, True, False, name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        return int(handle)
    raise AssertionError("a kernel event is a Windows test fixture")


def set_event(handle: int) -> None:
    """Set the event, waking every waiter."""
    if sys.platform == "win32":
        if not _set_event(handle):
            raise ctypes.WinError(ctypes.get_last_error())
        return
    raise AssertionError("a kernel event is a Windows test fixture")


def wait_event(handle: int, timeout_ms: int) -> bool:
    """Wait until the event is set or the timeout elapses; return whether it was set."""
    if sys.platform == "win32":
        outcome = int(_wait(handle, timeout_ms))
        if outcome not in (_WAIT_OBJECT_0, _WAIT_TIMEOUT):
            raise ctypes.WinError(ctypes.get_last_error())
        return outcome == _WAIT_OBJECT_0
    raise AssertionError("a kernel event is a Windows test fixture")


def close_event(handle: int) -> None:
    """Close this process's handle to the event."""
    if sys.platform == "win32":
        _close_handle(handle)
        return
    raise AssertionError("a kernel event is a Windows test fixture")


class IdleApp(QuietApp[None]):
    """Draws its screen, then sits idle with nothing focused until the parent test stops it.

    Once idle it reports its input thread, sets the ready event, and exits when
    the stop event is set, so the parent counts the input thread's wakes only
    between the end of startup and the start of the app's own stop.
    """

    @override
    def compose(self) -> ComposeResult:
        yield Static("idle")

    def on_mount(self) -> None:
        self._settle()

    def _settle(self) -> None:
        self.call_after_refresh(self._report_idle)

    def _report_idle(self) -> None:
        (input_thread,) = [thread for thread in threading.enumerate() if thread.name == "textual-input"]
        Path("idle.txt").write_text(f"{os.getpid()} {input_thread.native_id}", encoding="utf-8")
        threading.Thread(target=self._exit_on_stop, name="stop", daemon=True).start()

    def _exit_on_stop(self) -> None:
        name = Path("events.txt").read_text(encoding="utf-8")
        ready, stop = open_event(f"{name}-ready"), open_event(f"{name}-stop")
        set_event(ready)
        # A kernel wait with no timeout, so this thread does not wake the idle app either.
        wait_event(stop, INFINITE)
        self.call_from_thread(self.exit)


class ResumedApp(IdleApp):
    """Suspends and resumes its driver once, then sits idle like ``IdleApp``."""

    @override
    def _settle(self) -> None:
        self.set_timer(0.3, self._suspend_once)

    def _suspend_once(self) -> None:
        with self.suspend():
            pass
        monitor = getattr(self._driver, "_event_thread", None)
        waking = getattr(monitor, "_wake", None) is not None
        Path("result.txt").write_text("waking" if waking else "polling", encoding="utf-8")
        super()._settle()


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
        Path("result.txt").write_text(outcome, encoding="utf-8")
        self.exit()


if __name__ == "__main__":
    {"idle": IdleApp, "resumed": ResumedApp, "escape": EscapeApp}[sys.argv[1]]().run()
