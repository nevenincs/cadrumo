"""Detect whether this browser owner can present an interactive window."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .....application.runtime.contracts import RuntimeRefusalError


def interactive_desktop_available() -> bool:
    """Check the browser owner's environment, independently of headless settings.

    A client in a background session can use a desktop runtime; only the
    process actually launching Chromium is checked here.
    """
    if sys.platform == "win32":
        from ....local_runtime.windows_desktop_logon import current_windows_desktop_logon

        try:
            current_windows_desktop_logon()
        except RuntimeRefusalError:
            return False
        return True
    if sys.platform == "darwin":
        try:
            return Path("/dev/console").stat().st_uid == os.getuid() and os.getuid() != 0
        except OSError:
            return False
    if sys.platform == "linux":
        # Chromium's default Linux backend uses X11, including XWayland.
        # Without DISPLAY it cannot show a window even in a Wayland session.
        return bool(os.environ.get("DISPLAY"))
    return False
