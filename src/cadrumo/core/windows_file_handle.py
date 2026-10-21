"""Opening one existing Windows file by handle without following a link, declared once.

Two durable-state writers need the same Windows primitive: open an existing
file with every sharing mode (so the open never blocks a peer's replacement),
refuse a reparse point instead of following it, and hand the handle over as a
C runtime descriptor. :mod:`core.atomic_write` uses it to bind a hardened
publication to the exact staged file it reserved; :mod:`core.bucket_pointer`
uses it to read the active-profile pointer without blocking its replacement.
Each caller still owns its access rights, its refusal messages and every check
it makes on the returned descriptor.

This module imports only the standard library. :mod:`core.bucket_pointer` is
read during ``Settings()`` bootstrap and must not reach :mod:`core.logging`, so
nothing here may either.

The kernel32 declarations sit behind the module-level ``sys.platform ==
"win32"`` block because :mod:`ctypes.wintypes` raises on import elsewhere, and
that block is the guard shape every checker this project runs narrows on.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Final

if sys.platform == "win32":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    _FILE_SHARE_ALL: Final = 0x00000007
    _OPEN_EXISTING: Final = 3
    _FILE_FLAG_OPEN_REPARSE_POINT: Final = 0x00200000
    _FILE_ATTRIBUTE_TAG_INFO: Final = 9
    _FILE_ATTRIBUTE_DIRECTORY: Final = 0x00000010
    _FILE_ATTRIBUTE_REPARSE_POINT: Final = 0x00000400
    _INVALID_HANDLE: Final = ctypes.c_void_p(-1).value

    class _FileAttributeTagInfo(ctypes.Structure):
        _fields_ = [("file_attributes", wintypes.DWORD), ("reparse_tag", wintypes.DWORD)]

    _KERNEL32: Final = ctypes.WinDLL("kernel32", use_last_error=True)
    _CREATE_FILE = _KERNEL32.CreateFileW
    _CREATE_FILE.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    _CREATE_FILE.restype = wintypes.HANDLE
    _GET_FILE_INFORMATION_BY_HANDLE_EX = _KERNEL32.GetFileInformationByHandleEx
    _GET_FILE_INFORMATION_BY_HANDLE_EX.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    _GET_FILE_INFORMATION_BY_HANDLE_EX.restype = wintypes.BOOL
    _CLOSE_HANDLE = _KERNEL32.CloseHandle
    _CLOSE_HANDLE.argtypes = [wintypes.HANDLE]
    _CLOSE_HANDLE.restype = wintypes.BOOL

    def open_unfollowed_windows_descriptor(
        path: Path,
        access: int,
        *,
        link_like_message: str,
        directory_message: str | None = None,
    ) -> int:
        """Open ``path`` share-all without following a link and return a read-only descriptor.

        The handle is opened with ``FILE_FLAG_OPEN_REPARSE_POINT`` so a link is
        opened as itself, then refused by its reparse-point attribute before the
        handle is converted. ``directory_message``, when given, also refuses a
        directory before conversion. The returned descriptor owns the handle;
        the caller closes it with :func:`os.close`. On any failure the handle
        is closed here, exactly once.

        Args:
            path: Existing file to open.
            access: ``CreateFileW`` desired-access mask.
            link_like_message: :class:`OSError` message for a reparse point.
            directory_message: :class:`OSError` message for a directory, or
                ``None`` to leave directory refusal to the caller's own checks.

        Raises:
            OSError: When the open or the attribute query fails, or the file is
                refused as link-like or as a directory.
        """
        handle = _CREATE_FILE(
            str(path),
            access,
            _FILE_SHARE_ALL,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        handle_value = getattr(handle, "value", handle)
        if handle_value is None or handle_value == _INVALID_HANDLE:
            raise ctypes.WinError(ctypes.get_last_error())

        converted = False
        try:
            attributes = _FileAttributeTagInfo()
            if not _GET_FILE_INFORMATION_BY_HANDLE_EX(
                handle_value,
                _FILE_ATTRIBUTE_TAG_INFO,
                ctypes.byref(attributes),
                ctypes.sizeof(attributes),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            if attributes.file_attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
                raise OSError(link_like_message)
            if directory_message is not None and attributes.file_attributes & _FILE_ATTRIBUTE_DIRECTORY:
                raise OSError(directory_message)

            descriptor = msvcrt.open_osfhandle(handle_value, os.O_RDONLY | os.O_BINARY)
            converted = True
            return descriptor
        finally:
            if not converted:
                _CLOSE_HANDLE(handle_value)

    __all__ = ["open_unfollowed_windows_descriptor"]
else:
    __all__: list[str] = []
