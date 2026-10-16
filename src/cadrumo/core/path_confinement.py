"""Confine a caller-supplied host path and prove where the opened handle is.

A request that names a host path lets its sender choose what this process
opens. Checking the path text and then opening it leaves two gaps: a link,
junction or alias can make the checked text name one object and the open
reach another, and anything that replaces the path between the check and the
open is never seen by the check at all. This module closes both by deciding
on the handle it has already opened.

The rule is the same in every mode. A path is split into an *anchor*, taken
as named, and the components beneath it. Nothing beneath the anchor may be
reached through a link:

* on POSIX each component is opened relative to the descriptor of its parent
  with ``O_NOFOLLOW``, so the descriptor chain cannot leave the anchor;
* on Windows the object is opened first and the kernel is then asked where
  that handle really is; the answer must equal the anchor's own real location
  joined with the requested components, which a link, a junction, a short
  name or a trailing-dot alias all fail.

With a ``root`` the anchor is that root and the path must lie beneath it. With
no root the anchor is the named file's own directory, so the file is the one
that directory holds rather than one a link in it points at.

Refusals are returned as :class:`HostPathRefusal` values rather than raised:
this layer owns no operator-facing error, and each caller turns a refusal into
the registered error of its own boundary. A refusal names a reason only and
never repeats or resolves the path it was given.
"""

from __future__ import annotations

import errno
import os
import re
import stat
import sys
from collections.abc import Generator
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path, PureWindowsPath
from typing import Final

from .link_safety import is_link_like

if sys.platform == "win32":
    import ctypes
    import msvcrt
    from ctypes import wintypes

__all__ = [
    "ConfinedFile",
    "HostPathRefusal",
    "confined_directory_refusal",
    "host_path_form_refusal",
    "opened_confined_file",
]

_READ_BLOCK_BYTES: Final = 1024 * 1024

_WINDOWS_VERBATIM_PREFIX: Final = "\\\\?\\"
_WINDOWS_VERBATIM_FILE_FORM: Final = re.compile(r"\\\\\?\\(?:[A-Za-z]:\\|UNC\\)")
_WINDOWS_DEVICE_PREFIXES: Final = ("\\\\.\\", "\\??\\")
_WINDOWS_DEVICE_NAMES: Final = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "CONIN$",
        "CONOUT$",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
)


class HostPathRefusal(StrEnum):
    """Why a caller-supplied host path was not opened or accepted."""

    RELATIVE = "relative_path"
    TRAVERSAL = "parent_traversal"
    UNSUPPORTED_FORM = "unsupported_path_form"
    OUTSIDE_ROOT = "outside_allowed_root"
    REDIRECTED = "redirected_by_link"
    NOT_FOUND = "not_found"
    NOT_REGULAR_FILE = "not_a_regular_file"
    NOT_DIRECTORY = "not_a_directory"
    TOO_LARGE = "too_large"
    UNREADABLE = "unreadable"


def _is_windows_device_form(text: str) -> bool:
    """Return whether the path text addresses a device namespace rather than a file.

    The verbatim prefix is accepted only in front of a drive letter or a
    network share, which is how a long file path is spelled.
    """
    if text.startswith(_WINDOWS_VERBATIM_PREFIX):
        return _WINDOWS_VERBATIM_FILE_FORM.match(text) is None
    return text.startswith(_WINDOWS_DEVICE_PREFIXES)


def _is_windows_alias(name: str) -> bool:
    """Return whether one component names a stream, a device or a padded alias."""
    return (
        ":" in name or name != name.rstrip(". ") or name.partition(".")[0].rstrip(" ").upper() in _WINDOWS_DEVICE_NAMES
    )


def host_path_form_refusal(path: Path) -> HostPathRefusal | None:
    """Refuse a path whose text alone makes its target ambiguous.

    Touches no filesystem. A relative path is refused rather than resolved,
    because the directory it would resolve against belongs to the process and
    not to the request. On Windows the device namespaces, alternate data
    streams, reserved device names and trailing-dot or trailing-space aliases
    are refused as well; a drive-relative or rootless form is relative. A
    network share is a file path and passes here; a root, when one applies,
    is what keeps it out.
    """
    text = str(path)
    if "\x00" in text:
        return HostPathRefusal.UNSUPPORTED_FORM
    if sys.platform == "win32" and _is_windows_device_form(text):
        return HostPathRefusal.UNSUPPORTED_FORM
    if not path.is_absolute():
        return HostPathRefusal.RELATIVE
    names = path.parts[1:]
    if ".." in names:
        return HostPathRefusal.TRAVERSAL
    if sys.platform == "win32" and any(_is_windows_alias(name) for name in names):
        return HostPathRefusal.UNSUPPORTED_FORM
    return None


def _parts_beneath(path: Path, root: Path) -> tuple[str, ...] | None:
    """Return ``path``'s components beneath ``root``, or ``None`` when it is not beneath it."""
    if not root.is_absolute():
        return None
    try:
        return path.relative_to(root).parts
    except ValueError:
        return None


if sys.platform == "win32":
    # Invariants of this block. Every handle CreateFileW returns is closed by
    # the function that opened it before that function returns. The handle
    # msvcrt hands back for a descriptor stays owned by the descriptor and is
    # never closed here. Prototypes are set on this module's own library
    # object, so a pointer-sized HANDLE is never truncated to a C int.
    _FILE_READ_ATTRIBUTES: Final = 0x0080
    _FILE_SHARE_ALL: Final = 0x0007
    _OPEN_EXISTING: Final = 3
    _FILE_FLAG_BACKUP_SEMANTICS: Final = 0x0200_0000
    _FILE_ATTRIBUTE_DIRECTORY: Final = 0x0010
    _FILE_ATTRIBUTE_TAG_INFO: Final = 9
    _ABSENT_ERRORS: Final = frozenset({2, 3})
    _INVALID_HANDLE: Final = ctypes.c_void_p(-1).value

    _KERNEL32: Final = ctypes.WinDLL("kernel32", use_last_error=True)
    _KERNEL32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    _KERNEL32.CreateFileW.restype = wintypes.HANDLE
    _KERNEL32.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    _KERNEL32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    _KERNEL32.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    _KERNEL32.GetFileInformationByHandleEx.restype = wintypes.BOOL
    _KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
    _KERNEL32.CloseHandle.restype = wintypes.BOOL

    def _real_path_of_handle(handle: int) -> PureWindowsPath | None:
        """Return where the kernel reports the opened object to be."""
        capacity = 512
        for _attempt in range(2):
            buffer = ctypes.create_unicode_buffer(capacity)
            length = int(_KERNEL32.GetFinalPathNameByHandleW(handle, buffer, capacity, 0))
            if length == 0:
                return None
            if length < capacity:
                return PureWindowsPath(buffer.value)
            capacity = length + 1
        return None

    def _real_directory(path: Path) -> PureWindowsPath | HostPathRefusal:
        """Open ``path`` following links and return the real location of that directory."""
        handle = _KERNEL32.CreateFileW(
            str(path),
            _FILE_READ_ATTRIBUTES,
            _FILE_SHARE_ALL,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if handle is None or handle == _INVALID_HANDLE:
            if ctypes.get_last_error() in _ABSENT_ERRORS:
                return HostPathRefusal.NOT_FOUND
            return HostPathRefusal.UNREADABLE
        try:
            attributes = (wintypes.DWORD * 2)()
            if not _KERNEL32.GetFileInformationByHandleEx(
                handle, _FILE_ATTRIBUTE_TAG_INFO, ctypes.byref(attributes), ctypes.sizeof(attributes)
            ):
                return HostPathRefusal.UNREADABLE
            if not int(attributes[0]) & _FILE_ATTRIBUTE_DIRECTORY:
                return HostPathRefusal.NOT_DIRECTORY
            real = _real_path_of_handle(int(handle))
            return real if real is not None else HostPathRefusal.UNREADABLE
        finally:
            _KERNEL32.CloseHandle(handle)

    def _open_verified_file(anchor: Path, parts: tuple[str, ...]) -> int | HostPathRefusal:
        """Open the file, then require its handle to be where the request said."""
        anchor_real = _real_directory(anchor)
        if isinstance(anchor_real, HostPathRefusal):
            return anchor_real
        path = anchor.joinpath(*parts)
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_BINARY | os.O_NOINHERIT)
        except FileNotFoundError:
            return HostPathRefusal.NOT_FOUND
        except PermissionError:
            return HostPathRefusal.NOT_REGULAR_FILE if path.is_dir() else HostPathRefusal.UNREADABLE
        except OSError:
            return HostPathRefusal.UNREADABLE
        real = _real_path_of_handle(msvcrt.get_osfhandle(descriptor))
        if real is None or real != anchor_real.joinpath(*parts):
            os.close(descriptor)
            return HostPathRefusal.UNREADABLE if real is None else HostPathRefusal.REDIRECTED
        return descriptor

    def _existing_directory_refusal(root: Path, parts: tuple[str, ...]) -> HostPathRefusal | None:
        """Require every existing component beneath ``root`` to be a real directory there."""
        root_real = _real_directory(root)
        if root_real is HostPathRefusal.NOT_FOUND:
            return None
        if isinstance(root_real, HostPathRefusal):
            return root_real
        for depth in range(1, len(parts) + 1):
            candidate = root.joinpath(*parts[:depth])
            real = _real_directory(candidate)
            if isinstance(real, HostPathRefusal):
                # A link whose target is missing still redirects whatever is created through it.
                if is_link_like(candidate):
                    return HostPathRefusal.REDIRECTED
                return None if real is HostPathRefusal.NOT_FOUND else real
            if real != root_real.joinpath(*parts[:depth]):
                return HostPathRefusal.REDIRECTED
        return None

else:
    _DIRECTORY_FLAGS: Final = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
    _FILE_FLAGS: Final = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
    _LINK_ERRNOS: Final = frozenset({errno.ELOOP, errno.EMLINK, errno.ENOTDIR})

    def _open_anchor(path: Path) -> int | HostPathRefusal:
        """Open the anchor directory as named, following links."""
        try:
            return os.open(path, _DIRECTORY_FLAGS)
        except FileNotFoundError:
            return HostPathRefusal.NOT_FOUND
        except NotADirectoryError:
            return HostPathRefusal.NOT_DIRECTORY
        except OSError:
            return HostPathRefusal.UNREADABLE

    def _open_child(parent: int, name: str, flags: int) -> int | HostPathRefusal:
        """Open one component relative to its parent's descriptor without following a link."""
        try:
            return os.open(name, flags | os.O_NOFOLLOW, dir_fd=parent)
        except FileNotFoundError:
            return HostPathRefusal.NOT_FOUND
        except OSError as error:
            if error.errno not in _LINK_ERRNOS:
                return HostPathRefusal.UNREADABLE
        try:
            is_link = stat.S_ISLNK(os.stat(name, dir_fd=parent, follow_symlinks=False).st_mode)
        except OSError:
            return HostPathRefusal.REDIRECTED
        return HostPathRefusal.REDIRECTED if is_link else HostPathRefusal.NOT_DIRECTORY

    def _descend(anchor: Path, names: tuple[str, ...]) -> int | HostPathRefusal:
        """Open ``names`` beneath ``anchor`` as directories, keeping only the last descriptor."""
        current = _open_anchor(anchor)
        for name in names:
            if isinstance(current, HostPathRefusal):
                return current
            child = _open_child(current, name, _DIRECTORY_FLAGS)
            os.close(current)
            current = child
        return current

    def _open_verified_file(anchor: Path, parts: tuple[str, ...]) -> int | HostPathRefusal:
        """Open the file through a descriptor chain that never leaves the anchor."""
        directory = _descend(anchor, parts[:-1])
        if isinstance(directory, HostPathRefusal):
            return directory
        try:
            # Deciding the kind before the open keeps a device node or a pipe from being opened at all.
            try:
                mode = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False).st_mode
            except FileNotFoundError:
                return HostPathRefusal.NOT_FOUND
            except OSError:
                return HostPathRefusal.UNREADABLE
            if stat.S_ISLNK(mode):
                return HostPathRefusal.REDIRECTED
            if not stat.S_ISREG(mode):
                return HostPathRefusal.NOT_REGULAR_FILE
            return _open_child(directory, parts[-1], _FILE_FLAGS)
        finally:
            os.close(directory)

    def _existing_directory_refusal(root: Path, parts: tuple[str, ...]) -> HostPathRefusal | None:
        """Require every existing component beneath ``root`` to be a real directory there."""
        reached = _descend(root, parts)
        if isinstance(reached, HostPathRefusal):
            return None if reached is HostPathRefusal.NOT_FOUND else reached
        os.close(reached)
        return None


class ConfinedFile:
    """A regular file whose location was established on its opened handle.

    Reading goes through that handle, so replacing the path afterwards cannot
    change which file is read.
    """

    __slots__ = ("_descriptor", "_max_bytes")

    def __init__(self, descriptor: int, max_bytes: int) -> None:
        """Bind the verified descriptor and the size ceiling of one read."""
        self._descriptor = descriptor
        self._max_bytes = max_bytes

    def read_bytes(self) -> bytes | HostPathRefusal:
        """Return the whole file, or a refusal when it is unreadable or over the ceiling.

        The ceiling is enforced on the bytes actually read, so a file that
        grows after it was opened is refused rather than read without bound.
        """
        content = bytearray()
        try:
            os.lseek(self._descriptor, 0, os.SEEK_SET)
            while len(content) <= self._max_bytes:
                block = os.read(self._descriptor, min(_READ_BLOCK_BYTES, self._max_bytes + 1 - len(content)))
                if not block:
                    return bytes(content)
                content += block
        except OSError:
            return HostPathRefusal.UNREADABLE
        return HostPathRefusal.TOO_LARGE

    def status(self) -> os.stat_result:
        """Return the opened file's own status, never that of whatever its path names now."""
        return os.fstat(self._descriptor)


def _opened_file_refusal(descriptor: int, max_bytes: int) -> HostPathRefusal | None:
    """Decide the kind and size of the opened object from its own handle."""
    try:
        status = os.fstat(descriptor)
    except OSError:
        return HostPathRefusal.UNREADABLE
    if not stat.S_ISREG(status.st_mode):
        return HostPathRefusal.NOT_REGULAR_FILE
    if status.st_size > max_bytes:
        return HostPathRefusal.TOO_LARGE
    return None


@contextmanager
def opened_confined_file(
    path: Path,
    *,
    max_bytes: int,
    root: Path | None = None,
) -> Generator[ConfinedFile | HostPathRefusal]:
    """Open one regular file and yield it only after its handle was verified.

    Args:
        path: The absolute file path the caller supplied.
        max_bytes: The largest file this open accepts.
        root: The directory the file must really be inside. When omitted the
            file is confined to its own named directory: it may not be a link
            and must be a regular file there.

    Yields:
        A :class:`ConfinedFile` open for the duration of the block, or the
        :class:`HostPathRefusal` that stopped the open.
    """
    refusal = host_path_form_refusal(path)
    if refusal is None and root is not None and _parts_beneath(path, root) is None:
        refusal = HostPathRefusal.OUTSIDE_ROOT
    anchor = path.parent if root is None else root
    parts = _parts_beneath(path, anchor) or ()
    if refusal is None and not parts:
        refusal = HostPathRefusal.NOT_REGULAR_FILE
    if refusal is not None:
        yield refusal
        return
    descriptor = _open_verified_file(anchor, parts)
    if isinstance(descriptor, HostPathRefusal):
        yield descriptor
        return
    try:
        refusal = _opened_file_refusal(descriptor, max_bytes)
        yield refusal if refusal is not None else ConfinedFile(descriptor, max_bytes)
    finally:
        os.close(descriptor)


def confined_directory_refusal(path: Path, *, root: Path) -> HostPathRefusal | None:
    """Refuse a directory path that is not really inside ``root``.

    The path must lie beneath ``root`` by its text, and every component that
    already exists must be a real directory there, reached through no link.
    Components that do not exist yet are accepted: nothing stands there to
    redirect them. Nothing is created, so a caller that later creates the
    missing part must establish again where its own handle landed.
    """
    refusal = host_path_form_refusal(path)
    if refusal is not None:
        return refusal
    parts = _parts_beneath(path, root)
    if parts is None:
        return HostPathRefusal.OUTSIDE_ROOT
    return _existing_directory_refusal(root, parts)
