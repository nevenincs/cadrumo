"""Retained Windows child process and thread handles."""

from __future__ import annotations

import math
from typing import Final

from ..contracts.contracts import RefusalCode, RefusalError
from .windows_native_io import native_windows_call, owned_windows_handle

_STILL_ACTIVE: Final = 259
"""The status ``GetExitCodeProcess`` reports for a process that has not exited."""


class WindowsOwnedProcess:
    """Retained child handles; closing them does not dispose of the owning job."""

    def __init__(self, *, handle: int, pid: int, thread_handle: int | None = None) -> None:
        """Take ownership of the process and initial thread handles at launch."""
        self._handle: int | None = handle
        self._thread_handle = thread_handle
        self.pid = pid

    def retain_waiter(self) -> WindowsOwnedProcess:
        """Duplicate only wait/query rights before transferring a wait to another thread.

        The duplicate remains valid when the scope closes its original handles;
        its owner must close it after observing exit.
        """
        import win32api

        if self._handle is None:
            raise RefusalError(RefusalCode.UNAVAILABLE)
        current = win32api.GetCurrentProcess()
        duplicate = owned_windows_handle(win32api.DuplicateHandle(current, self._handle, current, 0x00101000, False, 0))
        detached = native_windows_call(duplicate, "Detach")
        if type(detached) is not int or detached <= 0:
            raise RefusalError(RefusalCode.UNAVAILABLE)
        return WindowsOwnedProcess(handle=detached, pid=self.pid)

    def wait(self, *, timeout: float | None) -> int:
        """Wait for this exact child; ``None`` waits for exit without polling."""
        import win32event

        if self._handle is None or (timeout is not None and (not math.isfinite(timeout) or timeout < 0)):
            raise RefusalError(RefusalCode.UNAVAILABLE)
        milliseconds = win32event.INFINITE if timeout is None else min(0xFFFFFFFE, math.ceil(timeout * 1000))
        result = win32event.WaitForSingleObject(self._handle, milliseconds)
        if result == win32event.WAIT_TIMEOUT:
            raise RefusalError(RefusalCode.TIMEOUT)
        if result != win32event.WAIT_OBJECT_0:
            raise RefusalError(RefusalCode.UNAVAILABLE)
        return _native_exit_status(self._handle)

    def exit_code(self) -> int | None:
        """This child's exit status read without waiting; ``None`` while it runs or once its handle is released.

        A process that exits with status 259 reads as still running: that is
        the value Windows itself reports for a live process.
        """
        if self._handle is None:
            return None
        status = _native_exit_status(self._handle)
        return None if status == _STILL_ACTIVE else status

    def close(self) -> None:
        """Attempt both handles, retaining each until its native release succeeds."""
        import win32api

        failures: list[BaseException] = []
        if self._thread_handle is not None:
            try:
                win32api.CloseHandle(self._thread_handle)
            except BaseException as error:
                failures.append(error)
            else:
                self._thread_handle = None
        if self._handle is not None:
            try:
                win32api.CloseHandle(self._handle)
            except BaseException as error:
                failures.append(error)
            else:
                self._handle = None
        if failures:
            raise failures[0]


def _native_exit_status(handle: int) -> int:
    import win32process

    # pywin32 reports the DWORD as a signed C long, so NTSTATUS-style
    # crash codes such as 0xC0000005 would otherwise read as negative.
    return win32process.GetExitCodeProcess(handle) & 0xFFFFFFFF
