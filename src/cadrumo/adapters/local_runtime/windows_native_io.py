"""Checked native Windows handles, identity reads, and cancellable overlapped I/O."""

from __future__ import annotations

import contextlib
import ctypes
import math
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import remaining_budget

if TYPE_CHECKING:
    from _win32typing import PyOVERLAPPED


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


SYNCHRONIZE = 0x100000


TOKEN_QUERY = 0x0008


CLIENT_PIPE_ACCESS = 0x00120083


SERVER_PIPE_ACCESS = 0x0012019F


SECURITY_IDENTIFICATION = 0x00010000


SECURITY_SQOS_PRESENT = 0x00100000


ERROR_IO_PENDING = 997


ERROR_PIPE_CONNECTED = 535


@runtime_checkable
class NativeWindowsHandle(Protocol):
    """An owned pywin32 handle whose object must survive every integer API call."""

    Close: Callable[[], None]

    def __int__(self) -> int:
        """Expose the native number without releasing its handle object."""
        ...


def owned_windows_handle(value: object) -> NativeWindowsHandle:
    """Admit a retained closable native handle or release the refused candidate."""
    if not isinstance(value, NativeWindowsHandle):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    try:
        if int(value) > 0:
            return value
    except (TypeError, ValueError, OverflowError):
        pass
    value.Close()
    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def native_windows_call(module: object, name: str, *args: object) -> object:
    """Keep one dynamically exposed pywin32 call behind a checked result boundary."""
    function: object = getattr(module, name, None)
    if not callable(function):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    return function(*args)


def require_windows() -> None:
    """Refuse native Windows transport use on another platform."""
    if sys.platform != "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def windows_owner_sid(process: int | NativeWindowsHandle) -> str:
    """Read and verify the native process owner while retaining its token handle."""
    import win32security

    token = owned_windows_handle(native_windows_call(win32security, "OpenProcessToken", process, TOKEN_QUERY))
    try:
        information = native_windows_call(win32security, "GetTokenInformation", int(token), win32security.TokenUser)
        if not isinstance(information, tuple):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        fields = cast("tuple[object, ...]", information)
        if len(fields) != 2:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        sid = fields[0]
        owner = native_windows_call(win32security, "ConvertSidToStringSid", sid)
        if not isinstance(owner, str) or not owner:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        return owner
    finally:
        token.Close()


def current_windows_owner_sid() -> str:
    """Resolve the current process owner from its native token."""
    require_windows()
    import win32api

    return windows_owner_sid(win32api.GetCurrentProcess())


def windows_image_path(process: int | NativeWindowsHandle) -> Path:
    """Read the absolute image path through the held native process handle."""
    if sys.platform != "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    query = kernel.QueryFullProcessImageNameW
    query.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    query.restype = wintypes.BOOL
    buffer = ctypes.create_unicode_buffer(32768)
    size = wintypes.DWORD(len(buffer))
    if not query(int(process), 0, buffer, ctypes.byref(size)):
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    return Path(buffer.value).resolve()


def windows_deadline_milliseconds(deadline: float) -> int:
    """Project the remaining finite budget into a bounded native wait."""
    remaining = remaining_budget(deadline)
    return min(0xFFFFFFFE, max(1, math.ceil(remaining * 1000)))


def finish_windows_io(handle: int | NativeWindowsHandle, overlapped: PyOVERLAPPED, *, deadline: float) -> int:
    """Join cancellation on the owning thread before releasing native I/O state."""
    import pywintypes
    import win32event
    import win32file

    try:
        elapsed = win32event.WaitForSingleObject(overlapped.hEvent, windows_deadline_milliseconds(deadline))
        if elapsed != win32event.WAIT_OBJECT_0:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        return win32file.GetOverlappedResult(int(handle), overlapped, False)
    except RuntimeRefusalError:
        # Cancellation must complete before releasing the OVERLAPPED/read buffer.
        # The operation and CancelIo run on the same thread.
        win32file.CancelIo(int(handle))
        with contextlib.suppress(pywintypes.error):
            win32file.GetOverlappedResult(int(handle), overlapped, True)
        raise
