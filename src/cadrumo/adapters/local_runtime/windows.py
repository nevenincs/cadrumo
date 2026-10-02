"""Local-only Windows pipes with first-instance ownership and native peer tokens."""

from __future__ import annotations

import contextlib
import ctypes
import hashlib
import math
import sys
import time
from collections.abc import Buffer, Callable
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable
from uuid import UUID

from ...application.runtime.contracts import RuntimePeer, RuntimeRefusalCode, RuntimeRefusalError
from .framing import close_runtime_transport_after_failure

if TYPE_CHECKING:
    from _win32typing import PyOVERLAPPED

    from .windows_login import WindowsLoginBinding

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SYNCHRONIZE = 0x100000
_TOKEN_QUERY = 0x0008
_CLIENT_PIPE_ACCESS = 0x00120083
_SERVER_PIPE_ACCESS = 0x0012019F
_SECURITY_IDENTIFICATION = 0x00010000
_SECURITY_SQOS_PRESENT = 0x00100000
_ERROR_IO_PENDING = 997
_ERROR_PIPE_CONNECTED = 535


@runtime_checkable
class _NativeHandle(Protocol):
    """An owned pywin32 handle whose object must survive every integer API call."""

    Close: Callable[[], None]

    def __int__(self) -> int: ...


def _owned_handle(value: object) -> _NativeHandle:
    if not isinstance(value, _NativeHandle):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    try:
        if int(value) > 0:
            return value
    except (TypeError, ValueError, OverflowError):
        pass
    value.Close()
    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _native_call(module: object, name: str, *args: object) -> object:
    """Keep one dynamically exposed pywin32 call behind a checked result boundary."""
    function: object = getattr(module, name, None)
    if not callable(function):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    return function(*args)


def _require_windows() -> None:
    if sys.platform != "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _owner_sid(process: int | _NativeHandle) -> str:
    import win32security

    token = _owned_handle(_native_call(win32security, "OpenProcessToken", process, _TOKEN_QUERY))
    try:
        information = _native_call(win32security, "GetTokenInformation", int(token), win32security.TokenUser)
        if not isinstance(information, tuple):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        fields = cast("tuple[object, ...]", information)
        if len(fields) != 2:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        sid = fields[0]
        owner = _native_call(win32security, "ConvertSidToStringSid", sid)
        if not isinstance(owner, str) or not owner:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        return owner
    finally:
        token.Close()


def _current_owner_sid() -> str:
    _require_windows()
    import win32api

    return _owner_sid(win32api.GetCurrentProcess())


def _image_path(process: int | _NativeHandle) -> Path:
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


def _milliseconds(deadline: float) -> int:
    remaining = deadline - time.monotonic()
    if not math.isfinite(remaining) or remaining <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    return min(0xFFFFFFFE, max(1, math.ceil(remaining * 1000)))


def _finish_io(handle: int | _NativeHandle, overlapped: PyOVERLAPPED, *, deadline: float) -> int:
    import pywintypes
    import win32event
    import win32file

    try:
        elapsed = win32event.WaitForSingleObject(overlapped.hEvent, _milliseconds(deadline))
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


class WindowsRuntimeChannel:
    """A pipe instance with an authenticated owner and retained peer handle."""

    def __init__(self, handle: int | _NativeHandle, *, server: bool, expected_image: Path | None = None) -> None:
        """Verify the kernel-reported peer process/token before exposing I/O."""
        self._capture_guard = RLock()
        _require_windows()
        import pywintypes
        import win32api
        import win32event
        import win32pipe

        self._handle: int | _NativeHandle | None = handle
        self._peer_process: _NativeHandle | None = None
        try:
            pid = _native_call(
                win32pipe,
                "GetNamedPipeClientProcessId" if server else "GetNamedPipeServerProcessId",
                int(handle),
            )
            if not isinstance(pid, int) or pid <= 0:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            process = _owned_handle(
                _native_call(win32api, "OpenProcess", _PROCESS_QUERY_LIMITED_INFORMATION | _SYNCHRONIZE, False, pid)
            )
            self._peer_process = process
            owner = _owner_sid(process)
            if (
                owner != _current_owner_sid()
                or win32event.WaitForSingleObject(int(process), 0) != win32event.WAIT_TIMEOUT
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            self.image_path = _image_path(process)
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
            for handle in (retained, process_handle):
                if win32event.WaitForSingleObject(handle, 0) != win32event.WAIT_TIMEOUT:
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
            _milliseconds(deadline)
            overlapped = pywintypes.OVERLAPPED()
            overlapped.hEvent = win32event.CreateEvent(None, True, False, None)
            buffer = win32file.AllocateReadBuffer(count - len(payload))
            try:
                win32file.ReadFile(int(self._handle), buffer, overlapped)
                received = _finish_io(self._handle, overlapped, deadline=deadline)
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
        _milliseconds(deadline)
        overlapped = pywintypes.OVERLAPPED()
        overlapped.hEvent = win32event.CreateEvent(None, True, False, None)
        try:
            win32file.WriteFile(int(self._handle), bytes(payload), overlapped)
            written = _finish_io(self._handle, overlapped, deadline=deadline)
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


class WindowsRuntimeEndpoint:
    """First-instance ownership held continuously across independent pipe clients."""

    def __init__(self, *, storage_root: Path, worker_namespace: UUID | None = None) -> None:
        """Derive a version-independent owner/root pipe name from physical identity."""
        _require_windows()
        self._owner = _current_owner_sid()
        try:
            root = storage_root.resolve(strict=True)
            if not root.is_dir():
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
            metadata = root.stat()
        except (OSError, ValueError):
            raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None
        self.storage_identity = hashlib.sha256(
            f"{self._owner}:{metadata.st_dev}:{metadata.st_ino}".encode()
        ).hexdigest()
        self.pipe_name = "\\\\.\\pipe\\cadrumo-runtime-" + self.storage_identity
        if worker_namespace is not None:
            self.pipe_name += "-worker-" + worker_namespace.hex
        self._pending: _NativeHandle | None = None

    @property
    def os_owner_id(self) -> str:
        """Return the native account identity used to derive this endpoint."""
        return self._owner

    def _new_instance(self, *, first: bool) -> _NativeHandle:
        import pywintypes
        import win32file
        import win32pipe
        import win32security

        descriptor = _native_call(
            win32security,
            "ConvertStringSecurityDescriptorToSecurityDescriptor",
            f"O:{self._owner}D:P(A;;0x{_SERVER_PIPE_ACCESS:08x};;;{self._owner})",
            1,
        )
        if type(descriptor) is not type(win32security.SECURITY_DESCRIPTOR()):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        security = pywintypes.SECURITY_ATTRIBUTES()
        security.SECURITY_DESCRIPTOR = descriptor
        security.bInheritHandle = False
        flags = win32pipe.PIPE_ACCESS_DUPLEX | win32file.FILE_FLAG_OVERLAPPED
        if first:
            flags |= win32pipe.FILE_FLAG_FIRST_PIPE_INSTANCE
        try:
            handle = _native_call(
                win32pipe,
                "CreateNamedPipe",
                self.pipe_name,
                flags,
                win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_REJECT_REMOTE_CLIENTS,
                win32pipe.PIPE_UNLIMITED_INSTANCES,
                65541,
                65541,
                0,
                security,
            )
            return _owned_handle(handle)
        except pywintypes.error:
            code = RuntimeRefusalCode.OWNER_BUSY if first else RuntimeRefusalCode.UNAVAILABLE
            raise RuntimeRefusalError(code) from None

    def listen(self) -> None:
        """Refuse existing instances instead of trusting or replacing their owner."""
        if self._pending is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.OWNER_BUSY)
        self._pending = self._new_instance(first=True)

    def connect(self, *, timeout: float = 5.0, expected_image: Path | None = None) -> WindowsRuntimeChannel:
        """Open narrowly selected pipe rights, then authenticate the actual server."""
        import pywintypes
        import win32file
        import win32pipe

        deadline = time.monotonic() + timeout
        while True:
            _milliseconds(deadline)
            try:
                handle = win32file.CreateFile(
                    self.pipe_name,
                    _CLIENT_PIPE_ACCESS,
                    0,
                    None,
                    win32file.OPEN_EXISTING,
                    win32file.FILE_FLAG_OVERLAPPED | _SECURITY_SQOS_PRESENT | _SECURITY_IDENTIFICATION,
                    None,
                )
                return WindowsRuntimeChannel(int(handle.Detach()), server=False, expected_image=expected_image)
            except pywintypes.error as error:
                if error.winerror != 231:
                    code = (
                        RuntimeRefusalCode.ENDPOINT_NOT_READY
                        if error.winerror == 2
                        else RuntimeRefusalCode.ENDPOINT_UNTRUSTED
                    )
                    raise RuntimeRefusalError(code) from None
                try:
                    _native_call(win32pipe, "WaitNamedPipe", self.pipe_name, _milliseconds(deadline))
                except pywintypes.error as error:
                    code = (
                        RuntimeRefusalCode.ENDPOINT_NOT_READY
                        if error.winerror in (2, 121, 231)
                        else RuntimeRefusalCode.ENDPOINT_UNTRUSTED
                    )
                    raise RuntimeRefusalError(code) from None

    def accept(self, *, timeout: float = 5.0) -> WindowsRuntimeChannel:
        """Provision the next instance before transferring this connected handle."""
        import pywintypes
        import win32api
        import win32event
        import win32pipe

        if self._pending is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        overlapped = pywintypes.OVERLAPPED()
        overlapped.hEvent = win32event.CreateEvent(None, True, False, None)
        handle = self._pending
        try:
            connected = False
            try:
                connected = (
                    _native_call(win32pipe, "ConnectNamedPipe", int(handle), overlapped) == _ERROR_PIPE_CONNECTED
                )
            except pywintypes.error as error:
                if error.winerror == _ERROR_PIPE_CONNECTED:
                    connected = True
                elif error.winerror != _ERROR_IO_PENDING:
                    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
            if not connected:
                _finish_io(handle, overlapped, deadline=time.monotonic() + timeout)
            self._pending = self._new_instance(first=False)
            return WindowsRuntimeChannel(handle, server=True)
        finally:
            win32api.CloseHandle(overlapped.hEvent)

    def close(self) -> None:
        """Close the waiting instance; accepted channels keep their own ownership."""
        if self._pending is not None:
            self._pending.Close()
            self._pending = None
