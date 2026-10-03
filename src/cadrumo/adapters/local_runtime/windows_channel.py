"""Windows pipe I/O with retained native peer ownership and serialized release."""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Buffer, Callable
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, cast

from ...application.runtime.contracts import RuntimePeer, RuntimeRefusalCode, RuntimeRefusalError
from .runtime_transport_cleanup import close_runtime_transport_after_failure
from .windows_native_io import (
    PROCESS_QUERY_LIMITED_INFORMATION,
    SYNCHRONIZE,
    NativeWindowsHandle,
    current_windows_owner_sid,
    finish_windows_io,
    native_windows_call,
    owned_windows_handle,
    require_windows,
    windows_deadline_milliseconds,
    windows_image_path,
    windows_owner_sid,
)

if TYPE_CHECKING:
    from .windows_login import WindowsLoginBinding


class WindowsRuntimeChannel:
    """A pipe instance with an authenticated owner and retained peer handle."""

    def __init__(self, handle: int | NativeWindowsHandle, *, server: bool, expected_image: Path | None = None) -> None:
        """Verify the kernel-reported peer process/token before exposing I/O."""
        self._capture_guard = RLock()
        require_windows()
        import pywintypes
        import win32api
        import win32event
        import win32pipe

        self._handle: int | NativeWindowsHandle | None = handle
        self._peer_process: NativeWindowsHandle | None = None
        try:
            pid = native_windows_call(
                win32pipe,
                "GetNamedPipeClientProcessId" if server else "GetNamedPipeServerProcessId",
                int(handle),
            )
            if not isinstance(pid, int) or pid <= 0:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            process = owned_windows_handle(
                native_windows_call(
                    win32api, "OpenProcess", PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid
                )
            )
            self._peer_process = process
            owner = windows_owner_sid(process)
            if (
                owner != current_windows_owner_sid()
                or win32event.WaitForSingleObject(int(process), 0) != win32event.WAIT_TIMEOUT
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            self.image_path = windows_image_path(process)
            if expected_image is not None and self.image_path != expected_image.resolve():
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            self._peer = RuntimePeer(os_owner_id=owner, process_id=pid)
        except pywintypes.error:
            refusal = RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            close_runtime_transport_after_failure(self, refusal)
            raise refusal from None
        except BaseException as error:
            close_runtime_transport_after_failure(self, error)
            raise

    @property
    def peer(self) -> RuntimePeer:
        """Return native process-token identity, not a claimed protocol PID."""
        return self._peer

    def verify_peer_process(self, process_handle: int) -> None:
        """Bind a supplied native handle to this retained authenticated incarnation."""
        if sys.platform != "win32":
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        from ctypes import wintypes

        import win32event

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        identify = kernel.GetProcessId
        identify.argtypes = (wintypes.HANDLE,)
        identify.restype = wintypes.DWORD
        times = kernel.GetProcessTimes
        times.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        )
        times.restype = wintypes.BOOL
        with self._capture_guard:
            if self._handle is None or self._peer_process is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            retained = int(self._peer_process)
            for handle in (retained, process_handle):
                if win32event.WaitForSingleObject(handle, 0) != win32event.WAIT_TIMEOUT:
                    raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                if identify(handle) != self._peer.process_id:
                    raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            self._require_peer_births(cast("Callable[..., int]", times), retained, process_handle)
            for handle in (retained, process_handle):
                if win32event.WaitForSingleObject(handle, 0) != win32event.WAIT_TIMEOUT:
                    raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)

    def _require_peer_births(self, times: Callable[..., int], retained: int, process_handle: int) -> None:
        """Require the same creation timestamp through both held live peer handles."""
        from ctypes import wintypes

        births: list[tuple[int, int]] = []
        for handle in (retained, process_handle):
            created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
            if not times(
                handle,
                ctypes.byref(created),
                ctypes.byref(exited),
                ctypes.byref(kernel_time),
                ctypes.byref(user_time),
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            births.append((created.dwHighDateTime, created.dwLowDateTime))
        if births[0] != births[1]:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)

    def capture_login(self) -> WindowsLoginBinding:
        """Resolve login provenance from this connection's retained peer handle."""
        from .windows_login import capture_windows_login

        with self._capture_guard:
            if self._handle is None or self._peer_process is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            return capture_windows_login(int(self._peer_process), expected_owner=self._peer.os_owner_id)

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        """Read a bounded frame fragment using cancellable overlapped operations."""
        import pywintypes
        import win32api
        import win32event
        import win32file

        if self._handle is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        if not 0 <= count <= 64 * 1024:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        payload = bytearray()
        while len(payload) < count:
            windows_deadline_milliseconds(deadline)
            overlapped = pywintypes.OVERLAPPED()
            overlapped.hEvent = win32event.CreateEvent(None, True, False, None)
            buffer = win32file.AllocateReadBuffer(count - len(payload))
            try:
                win32file.ReadFile(int(self._handle), buffer, overlapped)
                received = finish_windows_io(self._handle, overlapped, deadline=deadline)
                if received == 0:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                if not isinstance(buffer, Buffer):
                    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
                payload.extend(memoryview(buffer)[:received])
            except pywintypes.error:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED) from None
            finally:
                win32api.CloseHandle(overlapped.hEvent)
        return bytes(payload)

    def read_ready(self) -> bool:
        """Peek an overlapped pipe without leaving an idle read thread behind."""
        import pywintypes
        import win32pipe

        if self._handle is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        try:
            _, available, _ = win32pipe.PeekNamedPipe(int(self._handle), 0)
            return available > 0
        except pywintypes.error:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED) from None

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        """Send within the deadline without generic-write/create-instance rights."""
        import pywintypes
        import win32api
        import win32event
        import win32file

        if self._handle is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        if len(payload) > 64 * 1024 + 5:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        windows_deadline_milliseconds(deadline)
        overlapped = pywintypes.OVERLAPPED()
        overlapped.hEvent = win32event.CreateEvent(None, True, False, None)
        try:
            win32file.WriteFile(int(self._handle), bytes(payload), overlapped)
            written = finish_windows_io(self._handle, overlapped, deadline=deadline)
            if written != len(payload):
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        except pywintypes.error:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED) from None
        finally:
            win32api.CloseHandle(overlapped.hEvent)

    def close(self) -> None:
        """Release this pipe and peer handle, independently of other sessions."""
        import win32api

        with self._capture_guard:
            first_error: BaseException | None = None
            if self._handle is not None:
                try:
                    if isinstance(self._handle, int):
                        win32api.CloseHandle(self._handle)
                    else:
                        self._handle.Close()
                except BaseException as error:
                    first_error = error
                else:
                    self._handle = None
            if self._peer_process is not None:
                try:
                    self._peer_process.Close()
                except BaseException as error:
                    if first_error is None:
                        first_error = error
                    else:
                        first_error.add_note(f"Retained peer handle release also failed ({type(error).__name__})")
                else:
                    self._peer_process = None
            if first_error is not None:
                raise first_error
