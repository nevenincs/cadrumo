"""Windows session changes pushed to the runtime: logon, logoff, lock, unlock, connect and disconnect."""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Callable
from threading import Event, Thread

from cadrumo.core.diagnostic_log import diagnostic_event
from cadrumo.core.logging import get_logger

_LOGGER = get_logger(__name__)

_WM_WTSSESSION_CHANGE = 0x02B1
_REGISTRATION_SECONDS = 5.0


class WindowsSessionNotifications:
    """A message-only window registered for every session's change notifications.

    Its thread sleeps in the message loop until Windows reports a change, then
    calls ``changed``; nothing is read on a timer. Registration can be refused,
    for instance before the terminal service is ready, and ``start`` says so,
    leaving the caller to observe on its own.
    """

    def __init__(self, changed: Callable[[], None]) -> None:
        """Bind the callback each reported change invokes, on the notification thread."""
        self._changed = changed
        self._ready = Event()
        self._registered = False
        self._thread: Thread | None = None
        self._thread_id: int | None = None
        self._window: int | None = None
        self._previous: int = 0

    def start(self) -> bool:
        """Register on a dedicated thread, returning whether notifications will arrive."""
        if sys.platform != "win32":
            return False
        self._thread = Thread(target=self._run, name="runtime-session-notifications", daemon=True)
        self._thread.start()
        self._ready.wait(_REGISTRATION_SECONDS)
        return self._registered

    def close(self) -> None:
        """End the message loop, which unregisters and destroys the window."""
        thread, thread_id = self._thread, self._thread_id
        if thread is None:
            return
        if thread_id is not None:
            import pywintypes
            import win32api
            import win32con

            # An error means the loop has already ended.
            with contextlib.suppress(pywintypes.error):
                win32api.PostThreadMessage(thread_id, win32con.WM_QUIT, 0, 0)
        thread.join(_REGISTRATION_SECONDS)

    def _run(self) -> None:
        import pywintypes
        import win32api
        import win32con
        import win32gui
        import win32ts

        try:
            try:
                # The system's own message-only class; only its procedure is replaced.
                window = int(
                    win32gui.CreateWindowEx(0, "Message", "", 0, 0, 0, 0, 0, win32con.HWND_MESSAGE, 0, 0, None)
                )
            except pywintypes.error as error:
                _unavailable(error)
                return
            try:
                try:
                    self._previous = win32gui.SetWindowLong(window, win32con.GWL_WNDPROC, self._procedure)
                    win32ts.WTSRegisterSessionNotification(window, win32ts.NOTIFY_FOR_ALL_SESSIONS)
                except pywintypes.error as error:
                    _unavailable(error)
                    return
                self._window = window
                self._thread_id = win32api.GetCurrentThreadId()
                self._registered = True
                self._ready.set()
                win32gui.PumpMessages()
                win32ts.WTSUnRegisterSessionNotification(window)
            finally:
                win32gui.DestroyWindow(window)
        finally:
            self._ready.set()

    def _procedure(self, window: int, message: int, change: int, session: int) -> int:
        import win32gui

        if message == _WM_WTSSESSION_CHANGE:
            self._changed()
            return 0
        return int(win32gui.CallWindowProc(self._previous, window, message, change, session))


def _unavailable(error: BaseException) -> None:
    diagnostic_event(
        _LOGGER,
        "runtime_session_notifications_unavailable",
        fields={"winerror": getattr(error, "winerror", None)},
    )
