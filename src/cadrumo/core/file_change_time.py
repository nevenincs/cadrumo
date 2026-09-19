"""Filesystem change timestamps for cached immutable file admission."""

from __future__ import annotations

import ctypes
import os
import sys
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any, NamedTuple

from .errors.hierarchy import InternalInvariantError


class _FileBasicInfo(ctypes.Structure):
    _fields_ = (
        ("creation_time", ctypes.c_int64),
        ("last_access_time", ctypes.c_int64),
        ("last_write_time", ctypes.c_int64),
        ("change_time", ctypes.c_int64),
        ("attributes", ctypes.c_uint32),
    )


class _Kernel32Calls(NamedTuple):
    """The three kernel32 entry points this query binds."""

    create: Callable[..., Any]
    query: Callable[..., Any]
    close: Callable[..., Any]


@cache
def _kernel32_calls() -> _Kernel32Calls:
    """Bind the kernel32 entry points once per process.

    Loading the library and assigning ``argtypes`` costs more than the file
    query itself, and the authority reader verifies database identity on every
    component load -- thousands of times in one command. The bindings are
    process-wide immutable state, so binding them per call bought nothing.

    The ``sys.platform == "win32"`` block, rather than an early return off
    Windows, is what establishes the platform for the ``ctypes`` Windows API
    below: it is the only guard shape every checker this project runs narrows
    on, so the bindings resolve when the tree is analysed for a platform that
    does not ship them.
    """
    if sys.platform == "win32":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = (
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        )
        create.restype = ctypes.c_void_p
        query = kernel.GetFileInformationByHandleEx
        query.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)
        query.restype = ctypes.c_int
        close = kernel.CloseHandle
        close.argtypes = (ctypes.c_void_p,)
        close.restype = ctypes.c_int
        return _Kernel32Calls(create=create, query=query, close=close)
    raise InternalInvariantError("the Windows change-time bindings are not available on this platform")


def file_change_time_ns(path: Path, status: os.stat_result) -> int:
    """Read metadata change time; Windows stat ctime is creation time.

    Windows FILE_BASIC_INFO exposes ChangeTime independently of the writable
    LastWriteTime. Share deletion so this query does not prevent publication.
    Every other platform reports metadata change time as ``st_ctime_ns``.
    """
    if sys.platform == "win32":
        create, query, close = _kernel32_calls()
        handle = create(str(path), 0x80, 0x7, None, 3, 0, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            info = _FileBasicInfo()
            if not query(handle, 0, ctypes.byref(info), ctypes.sizeof(info)):
                raise ctypes.WinError(ctypes.get_last_error())
            return int(info.change_time) * 100
        finally:
            close(handle)
    return status.st_ctime_ns
