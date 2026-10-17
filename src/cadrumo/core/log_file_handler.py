"""The diagnostic log file handler, which tells a following reader about each append.

The handler keeps its file open between records. Windows reports no directory
change for appends through a handle that stays open, so after each record the
handler also sets a session-local event named for the user and the log
directory. The desktop's log view waits on that event instead of reading the
files on a timer. The event belongs to this user alone: it is created
owner-only, and a name another account holds, or an object of another type,
is refused, which leaves the reader observing the files on its interval.
Elsewhere the handler is the standard rotating handler.
"""

from __future__ import annotations

import logging
import ntpath
import os
import sys
from functools import cache
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from _win32typing import PyHANDLE

_FNV_OFFSET = 0xCBF29CE484222325
_FNV_PRIME = 0x100000001B3


def append_signal_name(directory: str, sid: str) -> str:
    r"""Name the event the user whose SID string is ``sid`` sets after an append in ``directory``.

    The desktop derives the same name: the absolute path without a ``\\?\``
    prefix, with ``\`` separators, no trailing separator and ASCII letters
    lowered, hashed with 64-bit FNV-1a over its UTF-8 bytes.
    """
    # Windows path rules on every platform: the signal only exists on Windows.
    text = ntpath.abspath(directory).removeprefix("\\\\?\\").replace("/", "\\").rstrip("\\")
    return f"Local\\cadrumo-log-append-{sid}-{_fnv1a(text.encode('utf-8').lower()):016x}"


def _fnv1a(data: bytes) -> int:
    """64-bit FNV-1a, which the desktop's platform crate computes alike."""
    digest = _FNV_OFFSET
    for byte in data:
        digest = ((digest ^ byte) * _FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return digest


@cache
def _append_signal(directory: str) -> PyHANDLE | None:
    """Open or create this user's owner-only event for ``directory`` once per process.

    ``None`` when the name is held by another account, by an object of
    another type, or by a descriptor this user cannot fully open.
    """
    if sys.platform == "win32":
        try:
            # Imported here: pywin32 costs several milliseconds to import, and
            # only a process that writes the diagnostic log file needs it.
            import pywintypes
            import win32api
            import win32event
            import win32security

            token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32security.TOKEN_QUERY)
            user = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
            sid = win32security.ConvertSidToStringSid(user)
            attributes = pywintypes.SECURITY_ATTRIBUTES()
            attributes.SECURITY_DESCRIPTOR = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
                f"O:{sid}D:P(A;;GA;;;{sid})", win32security.SDDL_REVISION_1
            )
            handle = win32event.CreateEvent(attributes, True, False, append_signal_name(directory, sid))
            owner = win32security.GetSecurityInfo(
                handle, win32security.SE_KERNEL_OBJECT, win32security.OWNER_SECURITY_INFORMATION
            ).GetSecurityDescriptorOwner()
        except Exception:
            # A reader that cannot be told must never cost a log record.
            return None
        if owner != user:
            handle.Close()
            return None
        return handle
    return None


def announce_append(directory: str) -> None:
    """Set ``directory``'s append event on Windows; elsewhere, and on any refusal, do nothing."""
    if sys.platform == "win32":
        handle = _append_signal(os.path.abspath(directory))
        if handle is None:
            return
        try:
            import win32event

            win32event.SetEvent(handle)
        except Exception:
            # A reader that cannot be told must never cost a log record.
            return


class AnnouncingRotatingFileHandler(RotatingFileHandler):
    """A rotating file handler that announces each record it appends."""

    @override
    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        announce_append(os.path.dirname(self.baseFilename))
