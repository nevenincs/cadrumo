"""The diagnostic log file handler, which tells a following reader about each append.

The handler keeps its file open between records. Windows reports no directory
change for appends through a handle that stays open, so after each record the
handler also sets a session-local event named for the log directory. The
desktop's log view waits on that event instead of reading the files on a timer.
Elsewhere the handler is the standard rotating handler.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
from collections.abc import Callable
from functools import cache
from logging.handlers import RotatingFileHandler
from typing import Any, NamedTuple, override

from .errors.hierarchy import InternalInvariantError

_FNV_OFFSET = 0xCBF29CE484222325
_FNV_PRIME = 0x100000001B3
_EVENT_MODIFY_STATE = 0x0002
_SYNCHRONIZE = 0x00100000
_CREATE_EVENT_MANUAL_RESET = 0x0001


def append_signal_name(directory: str) -> str:
    r"""Name the event set after an append to a file in ``directory``.

    The desktop derives the same name: the path without a ``\\?\`` prefix,
    with ``\`` separators, no trailing separator and ASCII letters lowered,
    hashed with 64-bit FNV-1a over its UTF-8 bytes.
    """
    text = directory.removeprefix("\\\\?\\").replace("/", "\\").rstrip("\\")
    digest = _FNV_OFFSET
    for byte in text.encode("utf-8").lower():
        digest = ((digest ^ byte) * _FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return f"Local\\cadrumo-log-append-{digest:016x}"


class _Kernel32Calls(NamedTuple):
    """The two kernel32 entry points an announcement binds."""

    create: Callable[..., Any]
    set: Callable[..., Any]


@cache
def _kernel32_calls() -> _Kernel32Calls:
    """Bind the kernel32 entry points once per process.

    The ``sys.platform == "win32"`` block is the guard shape every checker
    this project runs narrows on, so the bindings resolve when the tree is
    analysed for a platform that does not ship them.
    """
    if sys.platform == "win32":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel.CreateEventExW
        create.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32)
        create.restype = ctypes.c_void_p
        set_event = kernel.SetEvent
        set_event.argtypes = (ctypes.c_void_p,)
        set_event.restype = ctypes.c_int
        return _Kernel32Calls(create=create, set=set_event)
    raise InternalInvariantError("the Windows append-signal bindings are not available on this platform")


@cache
def _append_signal(name: str) -> int | None:
    """Open or create the named manual-reset event once per process."""
    handle = _kernel32_calls().create(None, name, _CREATE_EVENT_MANUAL_RESET, _EVENT_MODIFY_STATE | _SYNCHRONIZE)
    return int(handle) if handle else None


def announce_append(directory: str) -> None:
    """Set ``directory``'s append event on Windows; elsewhere, and on failure, do nothing."""
    if sys.platform != "win32":
        return
    try:
        handle = _append_signal(append_signal_name(os.path.abspath(directory)))
        if handle is not None:
            _kernel32_calls().set(handle)
    except OSError:
        # A reader that cannot be told must never cost a log record.
        return


class AnnouncingRotatingFileHandler(RotatingFileHandler):
    """A rotating file handler that announces each record it appends."""

    @override
    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        announce_append(os.path.dirname(self.baseFilename))
