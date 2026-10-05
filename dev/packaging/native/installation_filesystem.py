"""Remove receipt-owned program files through retained native filesystem identities.

Windows denies write/delete sharing while hashing and deleting the open file.
POSIX claims a name into a private no-replace namespace before verifying it;
changed claims are restored without replacing another name. This binds inode
and namespace, not arbitrary writes through previously opened external FDs.
"""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from uuid import uuid4

from cadrumo.adapters.persistence.storage.custody.errors import ProfileCustodyRecordError
from cadrumo.adapters.persistence.storage.custody.filesystem_primitives import (
    posix_directory_fd,
    posix_mkdir_child_directory,
    rename_noreplace_at,
)

from .installation_windows import remove_windows_owned_file


def file_identity(path: Path) -> tuple[int, int]:
    """Identify the no-follow file inspected during uninstall preflight."""
    value = path.lstat()
    return value.st_dev, value.st_ino


def _parent_still_bound(path: Path, descriptor: int) -> bool:
    for parent in (path.parent, *path.parent.parents):
        if parent.is_symlink() or parent.is_junction():
            return False
    current = path.parent.lstat()
    held = os.fstat(descriptor)
    return (current.st_dev, current.st_ino) == (held.st_dev, held.st_ino)


def _remove_posix(path: Path, checksum: str, expected: tuple[int, int]) -> bool:
    with posix_directory_fd(path.parent) as parent_fd:
        if not _parent_still_bound(path, parent_fd):
            raise ValueError("Installation parent changed before removal")
        try:
            os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return True
        quarantine = ".cadrumo-uninstall-" + uuid4().hex
        held = posix_mkdir_child_directory(parent_fd, quarantine)
        claimed = False
        try:
            try:
                rename_noreplace_at(
                    source_fd=parent_fd, source_name=path.name, destination_fd=held, destination_name="owned"
                )
            except FileNotFoundError:
                return True
            claimed = True
            nofollow = getattr(os, "O_NOFOLLOW", 0)
            nonblock = getattr(os, "O_NONBLOCK", 0)
            if not nofollow or not nonblock:
                raise ValueError("No-follow nonblocking installation file reads are unavailable")
            descriptor = os.open("owned", os.O_RDONLY | nofollow | nonblock, dir_fd=held)
            with os.fdopen(descriptor, "rb") as stream:
                metadata = os.fstat(stream.fileno())
                unchanged = (
                    stat.S_ISREG(metadata.st_mode)
                    and (metadata.st_dev, metadata.st_ino) == expected
                    and hashlib.file_digest(stream, "sha256").hexdigest() == checksum
                    and _parent_still_bound(path, parent_fd)
                )
                after = os.fstat(stream.fileno())
                unchanged = unchanged and (metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns) == (
                    after.st_size,
                    after.st_mtime_ns,
                    after.st_ctime_ns,
                )
                current = os.stat("owned", dir_fd=held, follow_symlinks=False)
                if not unchanged or (current.st_dev, current.st_ino) != expected:
                    return False
                os.unlink("owned", dir_fd=held)
                claimed = False
                return True
        finally:
            try:
                if claimed:
                    # Never replace a newly appeared original name. A failed restore
                    # leaves the claim preserved in quarantine and reports refusal.
                    try:
                        rename_noreplace_at(
                            source_fd=held,
                            source_name="owned",
                            destination_fd=parent_fd,
                            destination_name=path.name,
                        )
                    except (OSError, ProfileCustodyRecordError) as exc:
                        raise ValueError(f"Changed installation file retained in {quarantine}/owned") from exc
            finally:
                os.close(held)
            os.rmdir(quarantine, dir_fd=parent_fd)


def remove_owned_file(path: Path, checksum: str, expected: tuple[int, int]) -> bool:
    """Remove the unchanged preflight identity; return False to preserve a change."""
    if os.name == "nt":
        return remove_windows_owned_file(path, checksum, expected)
    return _remove_posix(path, checksum, expected)
