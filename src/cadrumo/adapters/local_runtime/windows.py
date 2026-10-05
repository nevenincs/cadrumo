"""Local-only first-instance Windows pipes bound to the native owner and physical root."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.hashing import sha256_hex
from .windows_channel import WindowsRuntimeChannel
from .windows_native_io import (
    CLIENT_PIPE_ACCESS,
    ERROR_IO_PENDING,
    ERROR_PIPE_CONNECTED,
    SECURITY_IDENTIFICATION,
    SECURITY_SQOS_PRESENT,
    SERVER_PIPE_ACCESS,
    NativeWindowsHandle,
    current_windows_owner_sid,
    finish_windows_io,
    native_windows_call,
    owned_windows_handle,
    require_windows,
    windows_deadline_milliseconds,
)

if TYPE_CHECKING:
    pass


class WindowsRuntimeEndpoint:
    """First-instance ownership held continuously across independent pipe clients."""

    def __init__(self, *, storage_root: Path, worker_namespace: UUID | None = None) -> None:
        """Derive a version-independent owner/root pipe name from physical identity."""
        require_windows()
        self._owner = current_windows_owner_sid()
        try:
            root = storage_root.resolve(strict=True)
            if not root.is_dir():
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED)
            metadata = root.stat()
        except (OSError, ValueError):
            raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None
        self.storage_identity = sha256_hex(f"{self._owner}:{metadata.st_dev}:{metadata.st_ino}".encode())
        self.pipe_name = "\\\\.\\pipe\\cadrumo-runtime-" + self.storage_identity
        if worker_namespace is not None:
            self.pipe_name += "-worker-" + worker_namespace.hex
        self._pending: NativeWindowsHandle | None = None

    @property
    def os_owner_id(self) -> str:
        """Return the native account identity used to derive this endpoint."""
        return self._owner

    def _new_instance(self, *, first: bool) -> NativeWindowsHandle:
        import pywintypes
        import win32file
        import win32pipe
        import win32security

        descriptor = native_windows_call(
            win32security,
            "ConvertStringSecurityDescriptorToSecurityDescriptor",
            f"O:{self._owner}D:P(A;;0x{SERVER_PIPE_ACCESS:08x};;;{self._owner})",
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
            handle = native_windows_call(
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
            return owned_windows_handle(handle)
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
            windows_deadline_milliseconds(deadline)
            try:
                handle = win32file.CreateFile(
                    self.pipe_name,
                    CLIENT_PIPE_ACCESS,
                    0,
                    None,
                    win32file.OPEN_EXISTING,
                    win32file.FILE_FLAG_OVERLAPPED | SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION,
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
                    native_windows_call(
                        win32pipe, "WaitNamedPipe", self.pipe_name, windows_deadline_milliseconds(deadline)
                    )
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
                    native_windows_call(win32pipe, "ConnectNamedPipe", int(handle), overlapped) == ERROR_PIPE_CONNECTED
                )
            except pywintypes.error as error:
                if error.winerror == ERROR_PIPE_CONNECTED:
                    connected = True
                elif error.winerror != ERROR_IO_PENDING:
                    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
            if not connected:
                finish_windows_io(handle, overlapped, deadline=time.monotonic() + timeout)
            self._pending = self._new_instance(first=False)
            return WindowsRuntimeChannel(handle, server=True)
        finally:
            win32api.CloseHandle(overlapped.hEvent)

    def close(self) -> None:
        """Close the waiting instance; accepted channels keep their own ownership."""
        if self._pending is not None:
            self._pending.Close()
            self._pending = None
