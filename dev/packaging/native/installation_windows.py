"""Inspect native installation paths and remove files through exact Windows handles."""

from __future__ import annotations

import ctypes
import hashlib
import os
import sys
from collections.abc import Callable
from contextlib import ExitStack
from functools import cache
from pathlib import Path
from typing import cast

from cadrumo.adapters.persistence.storage.custody.filesystem_primitives import (
    WindowsDirectoryAnchorErrors,
    windows_create_file_api,
    windows_directory_anchor,
    windows_file_information_type,
)


@cache
def _file_attributes_api() -> Callable[[str], int]:
    if sys.platform == "win32":
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        attributes = kernel32.GetFileAttributesW
        attributes.argtypes = [wintypes.LPCWSTR]
        attributes.restype = wintypes.DWORD
        return cast(Callable[[str], int], attributes)
    raise ValueError("Native Windows attributes are unavailable")


def windows_path_redirects(path: Path) -> bool:
    """Inspect fresh no-follow attributes without opening a metadata handle.

    Cache only the API binding, never a path's attributes. GetFileAttributesW
    describes the link itself, so every reparse point is refused, including a
    dangling junction. Missing names are valid for not-yet-created members.
    """
    if sys.platform == "win32":
        attributes = _file_attributes_api()(str(path))
        if attributes == 0xFFFFFFFF:
            error = ctypes.get_last_error()
            if error in (2, 3):
                return False
            if error == 53 and path == Path(path.anchor):
                # GetFileAttributes cannot inspect a bare UNC share. Keep the
                # previous no-follow metadata inspection for that ancestor.
                return bool(path.lstat().st_file_attributes & 0x400)
            raise ctypes.WinError(error)
        return bool(attributes & 0x400)
    raise ValueError("Native Windows attributes are unavailable")


def remove_windows_owned_file(path: Path, checksum: str, expected: tuple[int, int]) -> bool:
    """Delete only the unchanged preflight identity while native handles deny replacement."""
    if sys.platform == "win32":
        import msvcrt
        from ctypes import wintypes

        errors = WindowsDirectoryAnchorErrors(
            cannot_open="Installation parent cannot be locked",
            cannot_verify="Installation parent identity cannot be verified",
            invalid_entry="Installation parent redirects through a link",
            empty_path="Installation parent is absent",
        )
        with ExitStack() as stack:
            stack.enter_context(windows_directory_anchor(path.parent, errors=errors))
            _, _, kernel32, create_file = windows_create_file_api()
            # GENERIC_READ | DELETE, FILE_SHARE_READ only, OPEN_EXISTING and
            # FILE_FLAG_OPEN_REPARSE_POINT: no concurrent writer/name replacement.
            handle = create_file(str(path), 0x80000000 | 0x00010000, 1, None, 3, 0x00200000, None)
            if handle == wintypes.HANDLE(-1).value:
                error = ctypes.get_last_error()
                if error in (2, 3):
                    return True
                raise OSError(error, "Installation file cannot be exclusively inspected")
            try:
                info = windows_file_information_type()()
                if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
                    raise ctypes.WinError(ctypes.get_last_error())
                if info.dwFileAttributes & (0x400 | 0x10):
                    raise ValueError("Installation file is a directory or reparse point")
                descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
            except BaseException:
                kernel32.CloseHandle(handle)
                raise
            with os.fdopen(descriptor, "rb") as stream:
                metadata = os.fstat(stream.fileno())
                if (metadata.st_dev, metadata.st_ino) != expected:
                    return False
                if hashlib.file_digest(stream, "sha256").hexdigest() != checksum:
                    return False

                class FileDispositionInfo(ctypes.Structure):
                    _fields_ = [("delete_file", wintypes.BOOLEAN)]

                disposition = FileDispositionInfo(True)
                delete = kernel32.SetFileInformationByHandle
                delete.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
                delete.restype = wintypes.BOOL
                if not delete(handle, 4, ctypes.byref(disposition), ctypes.sizeof(disposition)):
                    raise ctypes.WinError(ctypes.get_last_error())
            return True
    raise ValueError("Native handle removal is unavailable")
