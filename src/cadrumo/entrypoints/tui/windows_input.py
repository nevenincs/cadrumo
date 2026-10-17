"""A Textual driver for Windows whose console input loop sleeps until input arrives.

Textual's Windows driver reads console input in a loop that wakes every 100 ms
to give its escape-sequence parser a chance to time out a lone Escape, whether
or not anything arrived. This driver's loop waits on the console input handle
and on its stop signal with no timeout. Only after input does it wait at most
one escape delay, so a partial sequence that was fed still times out on time.
Otherwise it is Textual's own driver and input loop.
"""

from __future__ import annotations

import sys

if sys.platform == "win32":
    import asyncio
    import ctypes
    import math
    import threading
    from collections.abc import Callable
    from ctypes import byref, wintypes
    from typing import TYPE_CHECKING, override

    from textual import constants
    from textual._xterm_parser import XTermParser
    from textual.drivers import win32
    from textual.drivers._writer_thread import WriterThread
    from textual.drivers.windows_driver import WindowsDriver

    if TYPE_CHECKING:
        from textual.app import App
        from textual.events import Event

    _CREATE_EVENT_MANUAL_RESET = 0x0001
    _EVENT_MODIFY_STATE = 0x0002
    _SYNCHRONIZE = 0x00100000
    _INFINITE = -1
    _KEY_EVENT = 0x0001
    _WINDOW_BUFFER_SIZE_EVENT = 0x0004
    _MAXIMUM_EVENTS = 1024
    #: The wait after input that lets a lone Escape the parser holds time out.
    _ESCAPE_WAIT_MS = math.ceil(constants.ESCAPE_DELAY * 1000) + 1

    _kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    _create_event = _kernel.CreateEventExW
    _create_event.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32)
    _create_event.restype = wintypes.HANDLE
    _set_event = _kernel.SetEvent
    _set_event.argtypes = (wintypes.HANDLE,)
    _set_event.restype = wintypes.BOOL
    _reset_event = _kernel.ResetEvent
    _reset_event.argtypes = (wintypes.HANDLE,)
    _reset_event.restype = wintypes.BOOL
    _close_handle = _kernel.CloseHandle
    _close_handle.argtypes = (wintypes.HANDLE,)
    _close_handle.restype = wintypes.BOOL

    class _WakingEvent(threading.Event):
        """The driver's stop flag, mirrored in a kernel event the input wait includes.

        Textual's driver stops input by setting this flag and joining the input
        thread, and clears it before input starts again after a suspend, so the
        kernel event follows both.
        """

        def __init__(self) -> None:
            super().__init__()
            self.handle: int | None = None
            self.open()

        def open(self) -> None:
            """Create the kernel event if a suspend closed it, in the flag's current state."""
            if self.handle is None:
                self.handle = _create_event(None, None, _CREATE_EVENT_MANUAL_RESET, _EVENT_MODIFY_STATE | _SYNCHRONIZE)
                if self.handle and self.is_set():
                    _set_event(self.handle)

        @override
        def set(self) -> None:
            super().set()
            if self.handle:
                _set_event(self.handle)

        @override
        def clear(self) -> None:
            super().clear()
            if self.handle:
                _reset_event(self.handle)

        def close(self) -> None:
            if self.handle:
                _close_handle(self.handle)
                self.handle = None

    class _InputMonitor(win32.EventMonitor):
        """Textual's console input loop, waiting on input or stop instead of a 100 ms tick."""

        def __init__(
            self,
            loop: asyncio.AbstractEventLoop,
            app: App,
            exit_event: _WakingEvent,
            process_event: Callable[[Event], None],
        ) -> None:
            super().__init__(loop, app, exit_event, process_event)
            self._wake = exit_event.handle

        @override
        def run(self) -> None:
            exit_requested = self.exit_event.is_set
            parser = XTermParser(debug=constants.DEBUG)
            try:
                read_count = wintypes.DWORD(0)
                console = win32.GetStdHandle(win32.STD_INPUT_HANDLE)
                records = (win32.INPUT_RECORD * _MAXIMUM_EVENTS)()
                handles = [console] if self._wake is None else [console, self._wake]
                keys: list[str] = []
                # Without a stop event, fall back to Textual's own interval so a stop is still seen.
                timeout = _INFINITE if self._wake is not None else 100
                while not exit_requested():
                    for event in parser.tick():
                        self.process_event(event)
                    ready = win32.wait_for_handles(handles, timeout)
                    if ready is not console:
                        # A stop, or the escape wait elapsed: the loop rechecks both, then sleeps again.
                        timeout = _INFINITE if self._wake is not None else 100
                        continue
                    win32.KERNEL32.ReadConsoleInputW(console, byref(records), _MAXIMUM_EVENTS, byref(read_count))
                    keys.clear()
                    new_size: tuple[int, int] | None = None
                    for record in records[: read_count.value]:
                        if record.EventType == _KEY_EVENT:
                            key_event = record.Event.KeyEvent
                            if key_event.bKeyDown:
                                if key_event.dwControlKeyState and key_event.wVirtualKeyCode == 0:
                                    continue
                                keys.append(key_event.uChar.UnicodeChar)
                        elif record.EventType == _WINDOW_BUFFER_SIZE_EVENT:
                            size = record.Event.WindowBufferSizeEvent.dwSize
                            new_size = (size.X, size.Y)
                    if keys:
                        # Round-trip through UTF-16 so surrogate pairs combine, as Textual does.
                        text = "".join(keys).encode("utf-16", "surrogatepass").decode("utf-16")
                        for event in parser.feed(text):
                            self.process_event(event)
                    if new_size is not None:
                        self.on_size_change(*new_size)
                    timeout = _ESCAPE_WAIT_MS
            except Exception as error:
                self.app.log.error("EVENT MONITOR ERROR", error)

    class QuietWindowsDriver(WindowsDriver):
        """Textual's Windows driver with an input loop that sleeps until input or stop."""

        def __init__(
            self,
            app: App,
            *,
            debug: bool = False,
            mouse: bool = True,
            size: tuple[int, int] | None = None,
        ) -> None:
            """Initialize like Textual's driver, with a stop flag the input wait can see."""
            super().__init__(app, debug=debug, mouse=mouse, size=size)
            self._waking = _WakingEvent()
            self.exit_event = self._waking

        @override
        def start_application_mode(self) -> None:
            loop = asyncio.get_running_loop()
            self._restore_console = win32.enable_application_mode()
            self._writer_thread = WriterThread(self._file)
            self._writer_thread.start()
            self.write("\x1b[?1049h")  # Enable alt screen
            self._enable_mouse_support()
            self.write("\x1b[?25l")  # Hide cursor
            self.write("\033[?1004h")  # Enable FocusIn/FocusOut.
            self.write("\x1b[>1u")  # https://sw.kovidgoyal.net/kitty/keyboard-protocol/
            self.flush()
            self._enable_bracketed_paste()
            # Textual closes the driver on a suspend and starts it again on resume.
            self._waking.open()
            self._event_thread = _InputMonitor(loop, self._app, self._waking, self.process_message)
            self._event_thread.start()

        @override
        def close(self) -> None:
            super().close()
            self._waking.close()

    __all__ = ["QuietWindowsDriver"]
