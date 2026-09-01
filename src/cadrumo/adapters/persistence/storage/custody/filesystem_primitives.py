"""Identity-anchored directory primitives for profile custody storage."""

from __future__ import annotations

import os
import stat
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from .errors import ProfileCustodyRecordError

PROFILE_CUSTODY_COMMIT_FILENAME: Final = "profile.commit.v1.json"


@dataclass(frozen=True, slots=True)
class WindowsDirectoryAnchorErrors:
    """Operator-facing refusals emitted while anchoring a Windows directory."""

    cannot_open: str
    cannot_verify: str
    invalid_entry: str
    empty_path: str


_PROFILE_CUSTODY_DIRECTORY_ANCHOR_ERRORS = WindowsDirectoryAnchorErrors(
    cannot_open="profile capsule directory cannot be identity-anchored",
    cannot_verify="profile capsule directory identity cannot be verified",
    invalid_entry="profile capsule directory must not be a reparse point or non-directory",
    empty_path="profile capsule directory cannot be identity-anchored",
)


@dataclass(frozen=True, slots=True)
class ProfileCustodyPasswordReadOperation:
    """One actual filesystem operation in the normal-password read set."""

    operation: Literal["stat", "open", "read"]
    path: Path


def is_real_directory(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode) and not bool(attributes & reparse)


def ensure_real_directory(path: Path) -> None:
    if os.path.lexists(path) and not is_real_directory(path):
        raise ProfileCustodyRecordError("profile capsule root must not be a link or non-directory")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule root cannot be created") from exc
    if not is_real_directory(path):
        raise ProfileCustodyRecordError("profile capsule root was not created as a real directory")


def anchor_directory(stack: ExitStack, path: Path, *, final_access: int = 0) -> int | None:
    """Keep a verified directory identity non-deletable for a path operation."""
    if os.name == "nt":
        return stack.enter_context(windows_directory_anchor(path, final_access=final_access))
    return stack.enter_context(posix_directory_fd(path))


def ensure_profile_custody_local_directory(path: Path) -> None:
    """Create one custody-owned directory while its parent identity is pinned.

    The caller supplies a single child of an existing storage root.  This is
    intentionally not a recursive convenience function: recursive path walks
    reintroduce a check-then-create window on Windows and POSIX alike.
    """
    if path.name in {"", ".", ".."}:
        raise ProfileCustodyRecordError("local custody directory must name one child")
    if os.name != "nt":
        with posix_directory_fd(path.parent) as parent_fd:
            try:
                os.mkdir(path.name, 0o700, dir_fd=parent_fd)
            except FileExistsError:
                pass
            except OSError as exc:
                raise ProfileCustodyRecordError("local custody directory cannot be created") from exc
            descriptor = posix_open_child_directory(parent_fd, path.name)
            os.close(descriptor)
            return
    with ExitStack() as anchors:
        anchor_directory(anchors, path.parent, final_access=0x80000000)
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
        except OSError as exc:
            raise ProfileCustodyRecordError("local custody directory cannot be created") from exc
        anchor_directory(anchors, path, final_access=0x80000000)


def windows_file_information_type() -> type[Any]:
    """Return the one Win32 identity structure shared by custody operations."""
    import ctypes
    from ctypes import wintypes

    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTimeLow", wintypes.DWORD),
            ("ftCreationTimeHigh", wintypes.DWORD),
            ("ftLastAccessTimeLow", wintypes.DWORD),
            ("ftLastAccessTimeHigh", wintypes.DWORD),
            ("ftLastWriteTimeLow", wintypes.DWORD),
            ("ftLastWriteTimeHigh", wintypes.DWORD),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    return _ByHandleFileInformation


def windows_create_file_api() -> tuple[Any, Any, Any, Any]:
    """Return configured ``CreateFileW`` bindings for identity-anchored calls."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    return ctypes, wintypes, kernel32, create_file


@contextmanager
def windows_directory_anchor(
    path: Path,
    *,
    final_access: int = 0,
    errors: WindowsDirectoryAnchorErrors = _PROFILE_CUSTODY_DIRECTORY_ANCHOR_ERRORS,
) -> Generator[int]:
    """Lock every real component against reparse and delete substitution."""
    ctypes, wintypes, kernel32, create_file = windows_create_file_api()
    file_information_type = windows_file_information_type()
    handles: list[int] = []
    try:
        current = Path(path.anchor)
        components = path.parts[1:] if path.anchor else path.parts
        for index, component in enumerate(components):
            current /= component
            handle = create_file(
                str(current),
                final_access if index == len(components) - 1 else 0,
                0x00000001 | 0x00000002,
                None,
                3,
                0x02000000 | 0x00200000,
                None,
            )
            if handle == wintypes.HANDLE(-1).value:
                raise ProfileCustodyRecordError(errors.cannot_open)
            handles.append(int(handle))
            info = file_information_type()
            if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
                raise ProfileCustodyRecordError(errors.cannot_verify)
            if not info.dwFileAttributes & 0x10 or info.dwFileAttributes & 0x400:
                raise ProfileCustodyRecordError(errors.invalid_entry)
        if not handles:
            raise ProfileCustodyRecordError(errors.empty_path)
        yield handles[-1]
    finally:
        for handle in reversed(handles):
            kernel32.CloseHandle(handle)


@contextmanager
def posix_directory_fd(path: Path) -> Generator[int]:
    """Walk an absolute directory a component at a time without following links."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path.anchor or "/", flags)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule root cannot be no-follow opened") from exc
    try:
        components = path.parts[1:] if path.anchor else path.parts
        for component in components:
            try:
                next_descriptor = os.open(component, flags, dir_fd=descriptor)
            except OSError as exc:
                raise ProfileCustodyRecordError("profile capsule directory component is unsafe") from exc
            os.close(descriptor)
            descriptor = next_descriptor
        yield descriptor
    finally:
        os.close(descriptor)


def posix_open_child_directory(parent_fd: int, name: str) -> int:
    try:
        return os.open(
            name,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule directory component is unsafe") from exc


def posix_mkdir_child_directory(parent_fd: int, name: str) -> int:
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule staging directory cannot be created") from exc
    return posix_open_child_directory(parent_fd, name)


def is_reparse_metadata(metadata: os.stat_result) -> bool:
    return bool(getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def write_exclusive_fsynced(path: Path, payload: bytes) -> None:
    """Create and fsync one capsule staging record at an anchored path."""
    if os.name != "nt" and not is_real_directory(path.parent):
        raise ProfileCustodyRecordError("profile capsule staging parent must not be a link or reparse directory")
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule staging record cannot be exclusively created") from exc
    try:
        _write_exclusive_descriptor_fsynced(descriptor, payload)
    finally:
        os.close(descriptor)


def write_exclusive_fsynced_fd(parent_fd: int, name: str, payload: bytes) -> None:
    """Create and fsync one capsule staging record below an anchored descriptor."""
    try:
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule staging record cannot be exclusively created") from exc
    try:
        _write_exclusive_descriptor_fsynced(descriptor, payload)
    finally:
        os.close(descriptor)


def _write_exclusive_descriptor_fsynced(descriptor: int, payload: bytes) -> None:
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise OSError("profile capsule staging short write")
            offset += written
        os.fsync(descriptor)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule staging record could not be fsynced") from exc


__all__ = [
    "PROFILE_CUSTODY_COMMIT_FILENAME",
    "ProfileCustodyPasswordReadOperation",
    "WindowsDirectoryAnchorErrors",
    "anchor_directory",
    "ensure_profile_custody_local_directory",
    "ensure_real_directory",
    "is_real_directory",
    "is_reparse_metadata",
    "posix_directory_fd",
    "posix_mkdir_child_directory",
    "posix_open_child_directory",
    "windows_create_file_api",
    "windows_directory_anchor",
    "windows_file_information_type",
    "write_exclusive_fsynced",
    "write_exclusive_fsynced_fd",
]
