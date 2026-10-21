"""Windows pipe I/O with retained native peer ownership and serialized release."""

from __future__ import annotations

import contextlib
import ctypes
import sys
from collections.abc import Buffer, Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import cast

from ..contracts.contracts import ChannelWake, Peer, RefusalCode, RefusalError
from .transport_cleanup import close_transport_after_failure
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

_ERROR_OPERATION_ABORTED = 995


class WindowsChannel:
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
        # The byte an idle readiness wait read, owed to the next read.
        self._pending = b""
        try:
            pid = native_windows_call(
                win32pipe,
                "GetNamedPipeClientProcessId" if server else "GetNamedPipeServerProcessId",
                int(handle),
            )
            if not isinstance(pid, int) or pid <= 0:
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
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
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            self.image_path = windows_image_path(process)
            if expected_image is not None and self.image_path != expected_image.resolve():
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            self._peer = Peer(os_owner_id=owner, process_id=pid, image_path=str(self.image_path))
        except pywintypes.error:
            refusal = RefusalError(RefusalCode.PEER_UNTRUSTED)
            close_transport_after_failure(self, refusal)
            raise refusal from None
        except BaseException as error:
            close_transport_after_failure(self, error)
            raise

    @property
    def peer(self) -> Peer:
        """Return native process-token identity, not a claimed protocol PID."""
        return self._peer

    def verify_peer_process(self, process_handle: int) -> None:
        """Bind a supplied native handle to this retained authenticated incarnation."""
        if sys.platform != "win32":
            raise RefusalError(RefusalCode.UNAVAILABLE)
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
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            retained = int(self._peer_process)
            for handle in (retained, process_handle):
                if win32event.WaitForSingleObject(handle, 0) != win32event.WAIT_TIMEOUT:
                    raise RefusalError(RefusalCode.PEER_UNTRUSTED)
                if identify(handle) != self._peer.process_id:
                    raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            self._require_peer_births(cast("Callable[..., int]", times), retained, process_handle)
            for handle in (retained, process_handle):
                if win32event.WaitForSingleObject(handle, 0) != win32event.WAIT_TIMEOUT:
                    raise RefusalError(RefusalCode.PEER_UNTRUSTED)

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
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            births.append((created.dwHighDateTime, created.dwLowDateTime))
        if births[0] != births[1]:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)

    def require_live_peer(self) -> None:
        """Recheck this connection's retained process incarnation and lifetime."""
        with self._capture_guard:
            if self._peer_process is None:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            self.verify_peer_process(int(self._peer_process))

    @contextmanager
    def pinned_peer_process_handle(self) -> Generator[int]:
        """Hold the verified peer process handle while host policy samples login facts."""
        with self._capture_guard:
            if self._handle is None or self._peer_process is None:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            yield int(self._peer_process)
            self.require_live_peer()

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        """Read a bounded frame fragment using cancellable overlapped operations."""
        import pywintypes
        import win32api
        import win32event
        import win32file

        if self._handle is None:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        if not 0 <= count <= 64 * 1024:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        payload = bytearray(self._pending[:count])
        self._pending = self._pending[count:]
        while len(payload) < count:
            windows_deadline_milliseconds(deadline)
            overlapped = pywintypes.OVERLAPPED()
            overlapped.hEvent = win32event.CreateEvent(None, True, False, None)
            buffer = win32file.AllocateReadBuffer(count - len(payload))
            try:
                win32file.ReadFile(int(self._handle), buffer, overlapped)
                received = finish_windows_io(self._handle, overlapped, deadline=deadline)
                if received == 0:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                if not isinstance(buffer, Buffer):
                    raise RefusalError(RefusalCode.UNAVAILABLE)
                payload.extend(memoryview(buffer)[:received])
            except pywintypes.error:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED) from None
            finally:
                win32api.CloseHandle(overlapped.hEvent)
        return bytes(payload)

    def read_ready(self) -> bool:
        """Peek an overlapped pipe without leaving an idle read thread behind."""
        import pywintypes
        import win32pipe

        if self._handle is None:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        if self._pending:
            return True
        try:
            _, available, _ = win32pipe.PeekNamedPipe(int(self._handle), 0)
            return available > 0
        except pywintypes.error:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED) from None

    def wait_readable(self, *wakes: ChannelWake) -> bool:
        """Wait on a one-byte overlapped read and ``wakes`` together; a byte read is owed to the next read."""
        import pywintypes
        import win32api
        import win32event
        import win32file

        if self._handle is None:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        if self._pending:
            return True
        handle = int(self._handle)
        overlapped = pywintypes.OVERLAPPED()
        overlapped.hEvent = win32event.CreateEvent(None, True, False, None)
        buffer = win32file.AllocateReadBuffer(1)
        try:
            try:
                win32file.ReadFile(handle, buffer, overlapped)
            except pywintypes.error:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED) from None
            try:
                signalled = win32event.WaitForMultipleObjects(
                    [overlapped.hEvent, *(wake.waitable for wake in wakes)], False, win32event.INFINITE
                )
            except BaseException:
                # The read must settle on this thread before its buffer is released.
                with contextlib.suppress(pywintypes.error):
                    win32file.CancelIo(handle)
                with contextlib.suppress(pywintypes.error):
                    win32file.GetOverlappedResult(handle, overlapped, True)
                raise
            woken = signalled != win32event.WAIT_OBJECT_0
            if woken:
                # A handle another thread closed meanwhile has already ended the read.
                with contextlib.suppress(pywintypes.error):
                    win32file.CancelIo(handle)
            try:
                received = win32file.GetOverlappedResult(handle, overlapped, True)
            except pywintypes.error as error:
                if woken and error.winerror == _ERROR_OPERATION_ABORTED:
                    return False
                # Ended by a closed handle or a peer that went away.
                raise RefusalError(RefusalCode.CONNECTION_CLOSED) from None
            if not isinstance(buffer, Buffer):
                raise RefusalError(RefusalCode.UNAVAILABLE)
            # A wake that raced a completed read still delivers its byte.
            self._pending = bytes(memoryview(buffer)[:received])
            return True
        finally:
            win32api.CloseHandle(overlapped.hEvent)

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        """Send within the deadline without generic-write/create-instance rights."""
        import pywintypes
        import win32api
        import win32event
        import win32file

        if self._handle is None:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        if len(payload) > 64 * 1024 + 5:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        windows_deadline_milliseconds(deadline)
        overlapped = pywintypes.OVERLAPPED()
        overlapped.hEvent = win32event.CreateEvent(None, True, False, None)
        try:
            win32file.WriteFile(int(self._handle), bytes(payload), overlapped)
            written = finish_windows_io(self._handle, overlapped, deadline=deadline)
            if written != len(payload):
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        except pywintypes.error:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED) from None
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
