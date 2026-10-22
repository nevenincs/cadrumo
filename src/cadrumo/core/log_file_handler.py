"""The diagnostic log file handler, which tells a following reader about each append.

Writers serialize rotation and append through one OS file lock on a sidecar.
Each writer keeps its log and sidecar descriptors between records, because
reopening them for every record cost a directory creation and two opens, each
scanned on Windows. On Windows both are opened with delete sharing, so a
retained handle never stops another process renaming the log during rotation.
Under the lock a writer compares the files its descriptors hold with the ones
the paths name now. It reopens after another writer rotated the log or the
directory was replaced, so no record lands in a rotated backup and no writer
locks an unlinked sidecar. A forked child reopens both rather than share its
parent's lock. After each append the handler sets a session-local event named
for the user and the log directory. The desktop's log view waits on that event instead of reading the
files on a timer. The event belongs to this user alone: it is created
owner-only, and a name another account holds, or an object of another type,
is refused, which leaves the reader observing the files on its interval.
The same locking and rotation rules apply on every platform.
"""

from __future__ import annotations

import logging
import ntpath
import os
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from functools import cache
from io import TextIOWrapper
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import override

_FNV_OFFSET = 0xCBF29CE484222325
_FNV_PRIME = 0x100000001B3

_TOKEN_QUERY = 0x0008
_TOKEN_USER = 1
_SDDL_REVISION_1 = 1
_SE_KERNEL_OBJECT = 6
_OWNER_SECURITY_INFORMATION = 0x00000001
_ERROR_SUCCESS = 0

_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_SHARE_READ_WRITE_DELETE = 0x00000007
_OPEN_EXISTING = 3
_OPEN_ALWAYS = 4
_FILE_ATTRIBUTE_NORMAL = 0x00000080
_SIDECAR_REOPEN_ATTEMPTS = 3


def append_signal_name(directory: str, sid: str) -> str:
    r"""Name the event the user whose SID string is ``sid`` sets after an append in ``directory``.

    The desktop derives the same name: the absolute path without a ``\\?\``
    prefix, with ``\`` separators, no trailing separator and ASCII letters
    lowered, hashed with 64-bit FNV-1a over its UTF-8 bytes.
    """
    # Windows path rules on every platform: the signal only exists on Windows.
    text = ntpath.abspath(directory).removeprefix("\\\\?\\").replace("/", "\\").rstrip("\\")
    return f"Local\\cadrumo-log-append-{sid}-{_fnv1a(text.encode('utf-8').lower()):016x}"


def _fnv1a(data: bytes) -> int:
    """64-bit FNV-1a, which the desktop's platform crate computes alike."""
    digest = _FNV_OFFSET
    for byte in data:
        digest = ((digest ^ byte) * _FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return digest


@cache
def _append_signal(directory: str) -> Callable[[], object] | None:
    """Return what sets this user's owner-only event for ``directory``, opened once per process.

    ``None`` when the name is held by another account, by an object of
    another type, or by a descriptor this user cannot fully open.
    """
    if sys.platform == "win32":
        try:
            return _owner_only_event(directory)
        except Exception:
            # A reader that cannot be told must never cost a log record.
            return None
    return None


if sys.platform == "win32":

    def _owner_only_event(directory: str) -> Callable[[], object] | None:
        # Imported here: only a process that writes the diagnostic log file needs them.
        import ctypes
        from ctypes import byref, wintypes

        class _SecurityAttributes(ctypes.Structure):
            _fields_ = (
                ("length", wintypes.DWORD),
                ("descriptor", ctypes.c_void_p),
                ("inherit", wintypes.BOOL),
            )

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        current_process = kernel32.GetCurrentProcess
        current_process.argtypes = ()
        current_process.restype = wintypes.HANDLE
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL
        local_free = kernel32.LocalFree
        local_free.argtypes = (ctypes.c_void_p,)
        local_free.restype = ctypes.c_void_p
        create_event = kernel32.CreateEventW
        create_event.argtypes = (ctypes.POINTER(_SecurityAttributes), wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
        create_event.restype = wintypes.HANDLE
        set_event = kernel32.SetEvent
        set_event.argtypes = (wintypes.HANDLE,)
        set_event.restype = wintypes.BOOL
        open_token = advapi32.OpenProcessToken
        open_token.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE))
        open_token.restype = wintypes.BOOL
        token_information = advapi32.GetTokenInformation
        token_information.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        )
        token_information.restype = wintypes.BOOL
        sid_text = advapi32.ConvertSidToStringSidW
        sid_text.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
        sid_text.restype = wintypes.BOOL
        descriptor_from_text = advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW
        descriptor_from_text.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(wintypes.ULONG),
        )
        descriptor_from_text.restype = wintypes.BOOL
        security_info = advapi32.GetSecurityInfo
        security_info.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
        )
        security_info.restype = wintypes.DWORD
        equal_sid = advapi32.EqualSid
        equal_sid.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
        equal_sid.restype = wintypes.BOOL

        token = wintypes.HANDLE()
        if not open_token(current_process(), _TOKEN_QUERY, byref(token)):
            return None
        try:
            size = wintypes.DWORD(0)
            token_information(token, _TOKEN_USER, None, 0, byref(size))
            # TOKEN_USER begins with a pointer to the user's SID, inside this buffer.
            user = ctypes.create_string_buffer(size.value)
            if not token_information(token, _TOKEN_USER, user, size, byref(size)):
                return None
        finally:
            close_handle(token)
        user_sid = ctypes.c_void_p.from_buffer(user).value
        text = ctypes.c_void_p()
        if not sid_text(user_sid, byref(text)):
            return None
        try:
            sid = ctypes.wstring_at(text)
        finally:
            local_free(text)
        descriptor = ctypes.c_void_p()
        if not descriptor_from_text(f"O:{sid}D:P(A;;GA;;;{sid})", _SDDL_REVISION_1, byref(descriptor), None):
            return None
        try:
            attributes = _SecurityAttributes(ctypes.sizeof(_SecurityAttributes), descriptor, False)
            # An existing object is opened with full access, which another account's
            # descriptor refuses, and one of another type fails outright.
            handle = create_event(byref(attributes), True, False, append_signal_name(directory, sid))
        finally:
            local_free(descriptor)
        if not handle:
            return None
        owner, owner_descriptor = ctypes.c_void_p(), ctypes.c_void_p()
        status = security_info(
            handle,
            _SE_KERNEL_OBJECT,
            _OWNER_SECURITY_INFORMATION,
            byref(owner),
            None,
            None,
            None,
            byref(owner_descriptor),
        )
        try:
            ours = status == _ERROR_SUCCESS and bool(equal_sid(owner, user_sid))
        finally:
            local_free(owner_descriptor)
        if not ours:
            close_handle(handle)
            return None

        def signal() -> object:
            return set_event(handle)

        return signal


def announce_append(directory: str) -> None:
    """Set ``directory``'s append event on Windows; elsewhere, and on any refusal, do nothing."""
    if sys.platform == "win32":
        signal = _append_signal(os.path.abspath(directory))
        if signal is None:
            return
        try:
            signal()
        except Exception:
            # A reader that cannot be told must never cost a log record.
            return


def _shared_open(path: str, flags: int) -> int:
    """Open ``path`` like :func:`os.open`; on Windows also let other processes rename or delete it."""
    if sys.platform == "win32":
        import _winapi
        import msvcrt

        access = _GENERIC_READ | _GENERIC_WRITE if flags & os.O_RDWR else _GENERIC_WRITE
        disposition = _OPEN_ALWAYS if flags & os.O_CREAT else _OPEN_EXISTING
        handle = _winapi.CreateFile(path, access, _SHARE_READ_WRITE_DELETE, 0, disposition, _FILE_ATTRIBUTE_NORMAL, 0)
        try:
            # Without O_TEXT the descriptor is binary, and the handle was created non-inheritable.
            return msvcrt.open_osfhandle(handle, flags & os.O_APPEND)
        except BaseException:
            _winapi.CloseHandle(handle)
            raise
    else:
        return os.open(path, flags | os.O_CLOEXEC, 0o600)


def _names_descriptor(path: str, descriptor: int) -> bool:
    """Whether ``path`` still names the file open on ``descriptor``."""
    try:
        named = os.stat(path)
    except FileNotFoundError:
        return False
    held = os.fstat(descriptor)
    return (named.st_dev, named.st_ino) == (held.st_dev, held.st_ino)


class AnnouncingRotatingFileHandler(RotatingFileHandler):
    """Coordinate process writers before rotation and announce completed appends."""

    def __init__(
        self,
        filename: str | os.PathLike[str],
        mode: str = "a",
        maxBytes: int = 0,  # noqa: N803 -- logging.dictConfig uses the standard handler constructor.
        backupCount: int = 0,  # noqa: N803 -- logging.dictConfig uses the standard handler constructor.
        encoding: str | None = None,
        delay: bool = False,
        errors: str | None = None,
    ) -> None:
        """Keep the standard handler configuration and open nothing before the first record."""
        from .locks import sidecar_lock_path

        # The first open happens under the process lock, like every reopen.
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay=True, errors=errors)
        self._lock_path = sidecar_lock_path(Path(self.baseFilename))
        self._lock_descriptor: int | None = None
        self._descriptor_owner = os.getpid()

    @override
    def _open(self) -> TextIOWrapper:
        if sys.platform == "win32" and self.mode == "a":
            return open(self.baseFilename, "a", encoding=self.encoding, errors=self.errors, opener=_shared_open)
        return super()._open()

    @override
    def emit(self, record: logging.LogRecord) -> None:
        try:
            with self._exclusive_append():
                super().emit(record)
            announce_append(os.path.dirname(self.baseFilename))
        except Exception:
            self.handleError(record)

    @override
    def close(self) -> None:
        self.acquire()
        try:
            self._close_lock_descriptor()
        finally:
            self.release()
        super().close()

    @contextmanager
    def _exclusive_append(self) -> Generator[None]:
        """Hold the writers' lock with the stream, if any, on the file the log path names now."""
        from .locks import held_descriptor_lock

        if self._descriptor_owner != os.getpid():
            # Inherited across fork: the parent's lock description would admit both processes.
            self._close_lock_descriptor()
            self._close_stream()
            self._descriptor_owner = os.getpid()
        for _ in range(_SIDECAR_REOPEN_ATTEMPTS):
            descriptor = self._lock_descriptor
            if descriptor is None:
                descriptor = self._lock_descriptor = self._open_lock_descriptor()
            with held_descriptor_lock(descriptor, self._lock_path, timeout=5.0, retry_backoff=0.005, log_events=False):
                if _names_descriptor(str(self._lock_path), descriptor):
                    self._follow_rotation()
                    yield
                    return
            self._close_lock_descriptor()
        raise OSError(f"the log lock {self._lock_path} was replaced while it was being acquired")

    def _open_lock_descriptor(self) -> int:
        try:
            return _shared_open(str(self._lock_path), os.O_RDWR | os.O_CREAT)
        except FileNotFoundError:
            # The log directory was removed since this writer last opened it.
            self._lock_path.parent.mkdir(parents=True, exist_ok=True)
            return _shared_open(str(self._lock_path), os.O_RDWR | os.O_CREAT)

    def _follow_rotation(self) -> None:
        """Reopen after another writer rotated the log; otherwise measure the shared file's end."""
        if self.stream is None:
            return
        if _names_descriptor(self.baseFilename, self.stream.fileno()):
            # Other writers appended since this stream last wrote; rollover measures the whole file.
            self.stream.seek(0, os.SEEK_END)
        else:
            self._close_stream()

    def _close_stream(self) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None

    def _close_lock_descriptor(self) -> None:
        if self._lock_descriptor is not None:
            os.close(self._lock_descriptor)
            self._lock_descriptor = None
