"""A Windows session change reaches the runtime as a callback, with no timer behind it."""

from __future__ import annotations

import sys
from threading import Event

import pytest

from ..windows_session_notifications import WindowsSessionNotifications

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires Windows session notifications"),
]

_WM_WTSSESSION_CHANGE = 0x02B1
_WTS_SESSION_LOCK = 0x7


def test_a_reported_session_change_calls_back_and_closing_ends_the_loop() -> None:
    import win32gui

    heard = Event()
    notifications = WindowsSessionNotifications(heard.set)
    assert notifications.start(), "this logon refused session notifications"
    try:
        assert not heard.wait(0.3), "nothing is reported before a change"
        # Windows sends exactly this to the registered window when a session locks.
        win32gui.PostMessage(notifications._window, _WM_WTSSESSION_CHANGE, _WTS_SESSION_LOCK, 1)
        assert heard.wait(2)
    finally:
        notifications.close()
    thread = notifications._thread
    assert thread is not None and not thread.is_alive()
