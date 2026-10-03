"""Verify that a scheduler task engine launched this live process."""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from ctypes import wintypes
from typing import cast

_WINDOWS_DLL_LOADER = "WinDLL"
_MAX_ANCESTORS = 8


class _ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def _creation_time(kernel: ctypes.CDLL, pid: int) -> int | None:
    open_process = kernel.OpenProcess
    open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    open_process.restype = wintypes.HANDLE
    handle = open_process(0x1000, False, pid)
    if not handle:
        return None
    try:
        get_times = kernel.GetProcessTimes
        get_times.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        )
        get_times.restype = wintypes.BOOL
        created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
        if not get_times(
            handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel_time), ctypes.byref(user_time)
        ):
            return None
        return (created.dwHighDateTime << 32) | created.dwLowDateTime
    finally:
        close_handle = kernel.CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL
        close_handle(handle)


def task_engine_owns_process(engine_pid: int, process_pid: int) -> bool:
    """Accept a short live ancestry chain with creation times ruling out reuse."""
    if engine_pid <= 0 or process_pid <= 0:
        return False
    loader = cast(Callable[..., ctypes.CDLL], getattr(ctypes, _WINDOWS_DLL_LOADER))
    kernel = loader("kernel32", use_last_error=True)
    snapshot = kernel.CreateToolhelp32Snapshot
    snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    snapshot.restype = wintypes.HANDLE
    handle = snapshot(0x00000002, 0)
    if not handle or handle == ctypes.c_void_p(-1).value:
        return False
    parents: dict[int, int] = {}
    try:
        first = kernel.Process32FirstW
        following = kernel.Process32NextW
        for operation in (first, following):
            operation.argtypes = (wintypes.HANDLE, ctypes.POINTER(_ProcessEntry))
            operation.restype = wintypes.BOOL
        entry = _ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        found = first(handle, ctypes.byref(entry))
        while found:
            parents[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
            found = following(handle, ctypes.byref(entry))
    finally:
        close_handle = kernel.CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL
        close_handle(handle)
    pid = process_pid
    child_created = _creation_time(kernel, pid)
    # Installed console/venv redirectors can create a five-process chain from
    # the service action to its host. Retain every native birth-order check,
    # allowing that observed chain within a fixed traversal bound.
    for _ in range(_MAX_ANCESTORS):
        if child_created is None or pid not in parents:
            return False
        if pid == engine_pid:
            return True
        parent_pid = parents[pid]
        parent_created = _creation_time(kernel, parent_pid)
        if parent_created is None or parent_created > child_created:
            return False
        pid, child_created = parent_pid, parent_created
    return False
