"""Filesystem change timestamps for cached immutable file admission."""

from __future__ import annotations

import ctypes
import os
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any, NamedTuple


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
    """
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


def file_change_time_ns(path: Path, status: os.stat_result) -> int:
    """Read metadata change time; Windows stat ctime is creation time.

    Windows FILE_BASIC_INFO exposes ChangeTime independently of the writable
    LastWriteTime. Share deletion so this query does not prevent publication.
    """
    if os.name != "nt":
        return status.st_ctime_ns
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
