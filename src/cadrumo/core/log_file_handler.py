"""The diagnostic log file handler, which tells a following reader about each append.

Writers serialize rotation and append through one OS file lock and close the
log before releasing it. Retaining a handle between records prevents another
Windows process from rotating the file and loses its next record. After each
append the handler sets a session-local event named for the user and the log
directory. The desktop's log view waits on that event instead of reading the
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
from collections.abc import Callable
from functools import cache
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
        """Keep the standard handler configuration without retaining a file handle."""
        # Always open under the process lock, including the first record.
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay=True, errors=errors)

    @override
    def emit(self, record: logging.LogRecord) -> None:
        from .locks import exclusive_file_lock

        try:
            with exclusive_file_lock(Path(self.baseFilename), timeout=5.0, retry_backoff=0.005, log_events=False):
                try:
                    super().emit(record)
                finally:
                    if self.stream is not None:
                        self.stream.close()
                        self.stream = None
            announce_append(os.path.dirname(self.baseFilename))
        except Exception:
            self.handleError(record)
