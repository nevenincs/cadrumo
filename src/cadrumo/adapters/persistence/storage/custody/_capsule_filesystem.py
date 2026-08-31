"""Capsule-publication filesystem primitives owned by the capsule boundary."""

from __future__ import annotations

import os
import stat
import sys
from collections.abc import Mapping
from pathlib import Path

from .errors import ProfileCustodyRecordError
from .filesystem_primitives import (
    PROFILE_CUSTODY_COMMIT_FILENAME,
    is_reparse_metadata,
    posix_directory_fd,
    posix_open_child_directory,
    windows_create_file_api,
    windows_file_information_type,
)


def remove_posix_staging_if_same(parent_fd: int, name: str, identity: os.stat_result) -> None:
    try:
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ProfileCustodyRecordError("unpublished profile capsule staging cannot be inspected") from exc
    if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
        raise ProfileCustodyRecordError("unpublished profile capsule staging identity changed before cleanup")
    remove_posix_tree(parent_fd, name)


def remove_posix_tree(parent_fd: int, name: str) -> None:
    target_fd = posix_open_child_directory(parent_fd, name)
    try:
        with os.scandir(target_fd) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    remove_posix_tree(target_fd, entry.name)
                else:
                    os.unlink(entry.name, dir_fd=target_fd)
    finally:
        os.close(target_fd)
    os.rmdir(name, dir_fd=parent_fd)


def fsync_directory(path: Path) -> None:
    if os.name == "nt":
        # Windows does not expose a directory FlushFileBuffers contract. Every
        # staged file is already fsynced; publication uses MoveFileEx
        # WRITE_THROUGH below as the mandatory metadata durability fence.
        return
    descriptor: int
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule directory cannot be opened for durability") from exc
    else:
        try:
            os.fsync(descriptor)
        except OSError as exc:
            raise ProfileCustodyRecordError("profile capsule directory could not be fsynced") from exc
        finally:
            os.close(descriptor)


def rename_directory_noreplace(
    staging: Path,
    destination: Path,
    *,
    root_handle: int | None,
    staging_handle: int | None = None,
) -> None:
    """Publish exactly once; fail closed where the platform has no no-replace rename."""
    if os.name == "nt":
        if root_handle is None:
            raise ProfileCustodyRecordError("profile capsule root is not identity-anchored")
        if staging_handle is None:
            raise ProfileCustodyRecordError("profile capsule staging is not identity-anchored")
        rename_windows_directory_by_handle(staging_handle, destination, root_handle=root_handle)
        return
    if sys.platform.startswith("linux"):
        if staging.parent != destination.parent:
            raise ProfileCustodyRecordError("profile capsule staging and destination roots must match")
        with posix_directory_fd(staging.parent) as parent_fd:
            renameat2_noreplace(
                source_fd=parent_fd,
                source_name=staging.name,
                destination_fd=parent_fd,
                destination_name=destination.name,
            )
        return
    raise ProfileCustodyRecordError("atomic no-replace profile capsule publication is unavailable on this platform")


def renameat2_noreplace(*, source_fd: int, source_name: str, destination_fd: int, destination_name: str) -> None:
    import ctypes
    import errno

    renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if renameat2 is None:
        raise ProfileCustodyRecordError("atomic no-replace profile capsule publication is unavailable")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(source_fd, os.fsencode(source_name), destination_fd, os.fsencode(destination_name), 1) == 0:
        return
    error = ctypes.get_errno()
    if error in {errno.EEXIST, errno.ENOTEMPTY}:
        raise ProfileCustodyRecordError("profile capsule destination already exists") from None
    raise ProfileCustodyRecordError("atomic no-replace profile capsule publication failed") from OSError(
        error, os.strerror(error)
    )


def rename_windows_directory_by_handle(staging_handle: int, destination: Path, *, root_handle: int) -> None:
    """Rename the exact open stage while the complete destination ancestry is locked."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _FileRenameInfo(ctypes.Structure):
        _fields_ = [
            ("replace_if_exists", wintypes.BOOLEAN),
            ("root_directory", wintypes.HANDLE),
            ("file_name_length", wintypes.DWORD),
            ("file_name", wintypes.WCHAR * 1),
        ]

    # A mapped/network volume may reject a non-null RootDirectory.  The source
    # is still renamed by its already-open handle, while the component-wise
    # root anchor makes this absolute destination immutable for the call.
    encoded_name = str(destination).encode("utf-16-le")
    name_offset = _FileRenameInfo.file_name.offset
    rename_buffer = ctypes.create_string_buffer(
        ctypes.sizeof(_FileRenameInfo) + len(encoded_name) - ctypes.sizeof(wintypes.WCHAR)
    )
    rename = _FileRenameInfo.from_buffer(rename_buffer)
    rename.replace_if_exists = False
    rename.root_directory = wintypes.HANDLE()
    rename.file_name_length = len(encoded_name)
    ctypes.memmove(ctypes.addressof(rename_buffer) + name_offset, encoded_name, len(encoded_name))
    set_information = kernel32.SetFileInformationByHandle
    set_information.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    set_information.restype = wintypes.BOOL
    if set_information(wintypes.HANDLE(staging_handle), 3, ctypes.byref(rename), len(rename_buffer)):
        return
    error = ctypes.get_last_error()
    if error in {80, 183}:
        raise ProfileCustodyRecordError("profile capsule destination already exists") from None
    raise ProfileCustodyRecordError("atomic no-replace profile capsule publication failed") from OSError(
        error, "SetFileInformationByHandle(FileRenameInfo)"
    )


def write_through_windows_publication_fence(destination: Path, *, root_handle: int | None) -> None:
    """Commit the prior handle-relative rename through Windows' supported fence."""
    if root_handle is None:
        raise ProfileCustodyRecordError("profile capsule root is not identity-anchored for durability")
    import ctypes
    from ctypes import wintypes

    move_file = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
    move_file.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, wintypes.DWORD]
    move_file.restype = wintypes.BOOL
    if not move_file(str(destination), str(destination), 0x00000008):
        error = ctypes.get_last_error()
        if error == 109:  # ERROR_BROKEN_PIPE from a mapped/server volume.
            fsync_windows_published_commit(destination)
            return
        raise ProfileCustodyRecordError("profile capsule root durability fence failed") from OSError(
            error, "MoveFileExW(MOVEFILE_WRITE_THROUGH)"
        )


def fsync_windows_published_commit(destination: Path) -> None:
    """Use the server-backed commit record as the remote-volume durability fence."""
    try:
        descriptor = os.open(
            destination / PROFILE_CUSTODY_COMMIT_FILENAME,
            os.O_RDWR | getattr(os, "O_BINARY", 0),
        )
    except OSError as exc:
        raise ProfileCustodyRecordError("published profile capsule commit cannot be durability-fenced") from exc
    try:
        import ctypes
        import msvcrt
        from ctypes import wintypes

        flush = ctypes.WinDLL("kernel32", use_last_error=True).FlushFileBuffers
        flush.argtypes = [wintypes.HANDLE]
        flush.restype = wintypes.BOOL
        if not flush(wintypes.HANDLE(msvcrt.get_osfhandle(descriptor))):
            raise OSError(ctypes.get_last_error(), "FlushFileBuffers")
    except OSError as exc:
        raise ProfileCustodyRecordError("published profile capsule commit durability fence failed") from exc
    finally:
        os.close(descriptor)


def windows_stage_snapshot(staging: Path) -> dict[str, tuple[int, int, bool]]:
    """Capture the exact transaction-owned tree before any cleanup can occur."""
    try:
        snapshot: dict[str, tuple[int, int, bool]] = {}
        for current, directories, files in os.walk(staging, topdown=True, followlinks=False):
            current_path = Path(current)
            relative = current_path.relative_to(staging).as_posix()
            metadata = current_path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or is_reparse_metadata(metadata):
                raise ProfileCustodyRecordError("unpublished profile capsule staging contains a reparse point")
            snapshot[relative] = (metadata.st_dev, metadata.st_ino, True)
            for name in [*directories, *files]:
                entry = current_path / name
                entry_metadata = entry.lstat()
                if stat.S_ISLNK(entry_metadata.st_mode) or is_reparse_metadata(entry_metadata):
                    raise ProfileCustodyRecordError("unpublished profile capsule staging contains a reparse point")
                snapshot[entry.relative_to(staging).as_posix()] = (
                    entry_metadata.st_dev,
                    entry_metadata.st_ino,
                    stat.S_ISDIR(entry_metadata.st_mode),
                )
        return snapshot
    except OSError as exc:
        raise ProfileCustodyRecordError("unpublished profile capsule staging cannot be identity-inventoried") from exc


def remove_windows_unpublished_staging(
    staging: Path,
    *,
    staging_handle: int | None,
    snapshot: Mapping[str, tuple[int, int, bool]],
) -> None:
    """Delete only entries proven unchanged while the exact stage is pinned."""
    if staging_handle is None:
        raise ProfileCustodyRecordError("unpublished profile capsule staging is not identity-anchored")
    current_snapshot = windows_stage_snapshot(staging)
    if current_snapshot != snapshot:
        raise ProfileCustodyRecordError("unpublished profile capsule staging changed before safe cleanup")
    for relative_name, expected in sorted(snapshot.items(), key=lambda item: item[0].count("/"), reverse=True):
        if relative_name == ".":
            continue
        target = staging.joinpath(*relative_name.split("/"))
        windows_delete_exact_entry(target, expected)
    windows_mark_handle_for_deletion(staging_handle)


def windows_delete_exact_entry(target: Path, expected: tuple[int, int, bool]) -> None:
    ctypes, wintypes, kernel32, create_file = windows_create_file_api()
    file_information_type = windows_file_information_type()
    handle = create_file(str(target), 0x00010000, 0x00000001 | 0x00000002, None, 3, 0x02000000 | 0x00200000, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ProfileCustodyRecordError("unpublished profile capsule entry cannot be identity-opened")
    try:
        info = file_information_type()
        if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise ProfileCustodyRecordError("unpublished profile capsule entry identity cannot be verified")
        metadata = target.lstat()
        actual = (metadata.st_dev, metadata.st_ino, stat.S_ISDIR(metadata.st_mode))
        if actual != expected or is_reparse_metadata(metadata) or stat.S_ISLNK(metadata.st_mode):
            raise ProfileCustodyRecordError("unpublished profile capsule entry changed before safe cleanup")
        windows_mark_handle_for_deletion(int(handle))
    finally:
        kernel32.CloseHandle(handle)


def windows_mark_handle_for_deletion(handle: int) -> None:
    import ctypes
    from ctypes import wintypes

    class _FileDispositionInfo(ctypes.Structure):
        _fields_ = [("delete_file", wintypes.BOOLEAN)]

    disposition = _FileDispositionInfo(True)
    set_information = ctypes.WinDLL("kernel32", use_last_error=True).SetFileInformationByHandle
    set_information.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    set_information.restype = wintypes.BOOL
    if not set_information(wintypes.HANDLE(handle), 4, ctypes.byref(disposition), ctypes.sizeof(disposition)):
        raise ProfileCustodyRecordError("unpublished profile capsule entry cannot be safely removed")
