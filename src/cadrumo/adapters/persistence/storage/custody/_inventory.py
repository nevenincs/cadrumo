"""Bounded no-follow inventory of current profile-custody capsules."""

from __future__ import annotations

import os
import stat
from contextlib import ExitStack
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from .....core import iter_directory
from .....core.hashing import CONTENT_DIGEST_PREFIX, canonical_json_bytes, prefixed_digest
from ._errors import ProfileCustodyRecordError
from ._filesystem import (
    anchor_directory,
    is_reparse_metadata,
    posix_directory_fd,
    posix_open_child_directory,
    windows_regular_file_anchor,
)

PROFILE_CUSTODY_INVENTORY_MAX_ENTRIES = 2048
PROFILE_CUSTODY_INVENTORY_MAX_TOTAL_BYTES = 512 * 1024 * 1024
PROFILE_CUSTODY_DATA_MAX_ENTRIES = 1024
PROFILE_CUSTODY_DATA_FILE_MAX_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ProfileCustodyInventoryEntry:
    """One regular file observed under a current committed capsule."""

    relative_path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ProfileCustodyInventory:
    """Bounded, no-follow exact inventory used by local custody transactions."""

    profile_id: UUID
    entries: tuple[ProfileCustodyInventoryEntry, ...]
    total_bytes: int
    digest: str


def inventory_profile_custody_capsule(
    profile_id: UUID,
    capsule_path: Path,
    *,
    ignore_deletion_marker: bool = False,
) -> ProfileCustodyInventory:
    """Inventory a known capsule path without following links or reparse points."""
    entries: list[ProfileCustodyInventoryEntry] = []
    if os.name != "nt":
        with posix_directory_fd(capsule_path) as capsule_fd:
            _inventory_posix_directory(capsule_fd, "", entries, ignore_deletion_marker=ignore_deletion_marker)
    else:
        with ExitStack() as anchors:
            anchor_directory(anchors, capsule_path)
            _inventory_windows_directory(capsule_path, "", entries, ignore_deletion_marker=ignore_deletion_marker)
    return _build_profile_custody_inventory(profile_id, entries)


def _build_profile_custody_inventory(
    profile_id: UUID,
    entries: list[ProfileCustodyInventoryEntry],
) -> ProfileCustodyInventory:
    if not entries:
        raise ProfileCustodyRecordError("profile custody inventory cannot be empty")
    ordered = tuple(sorted(entries, key=lambda entry: entry.relative_path))
    if len(ordered) != len({entry.relative_path for entry in ordered}):
        raise ProfileCustodyRecordError("profile custody inventory contains duplicate paths")
    total_bytes = sum(entry.size_bytes for entry in ordered)
    if total_bytes > PROFILE_CUSTODY_INVENTORY_MAX_TOTAL_BYTES:
        raise ProfileCustodyRecordError("profile custody inventory exceeds its total byte limit")
    canonical = canonical_json_bytes([[entry.relative_path, entry.size_bytes, entry.sha256] for entry in ordered])
    return ProfileCustodyInventory(
        profile_id=profile_id,
        entries=ordered,
        total_bytes=total_bytes,
        digest=prefixed_digest(canonical),
    )


def _inventory_posix_directory(
    directory_fd: int,
    prefix: str,
    entries: list[ProfileCustodyInventoryEntry],
    *,
    ignore_deletion_marker: bool,
) -> None:
    try:
        names = sorted(entry.name for entry in os.scandir(directory_fd))
    except OSError as exc:
        raise ProfileCustodyRecordError("profile custody inventory directory cannot be read") from exc
    for name in names:
        if _skip_inventory_entry(prefix, name, ignore_deletion_marker):
            continue
        _inventory_posix_entry(directory_fd, prefix, name, entries, ignore_deletion_marker)


def _skip_inventory_entry(prefix: str, name: str, ignore_deletion_marker: bool) -> bool:
    if prefix or name != "profile.deletion.v1.json":
        return False
    if ignore_deletion_marker:
        return True
    raise ProfileCustodyRecordError("committed profile capsule carries an unexpected deletion marker")


def _inventory_posix_entry(
    directory_fd: int,
    prefix: str,
    name: str,
    entries: list[ProfileCustodyInventoryEntry],
    ignore_deletion_marker: bool,
) -> None:
    relative = f"{prefix}/{name}" if prefix else name
    try:
        metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile custody inventory entry cannot be inspected") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise ProfileCustodyRecordError("profile custody inventory refuses a symbolic link")
    if stat.S_ISDIR(metadata.st_mode):
        child_fd = posix_open_child_directory(directory_fd, name)
        try:
            _inventory_posix_directory(child_fd, relative, entries, ignore_deletion_marker=ignore_deletion_marker)
        finally:
            os.close(child_fd)
        return
    if not stat.S_ISREG(metadata.st_mode):
        raise ProfileCustodyRecordError("profile custody inventory refuses a non-regular entry")
    entries.append(_inventory_posix_file(directory_fd, name, relative, metadata))
    _ensure_inventory_entry_limit(entries)


def _ensure_inventory_entry_limit(entries: list[ProfileCustodyInventoryEntry]) -> None:
    if len(entries) > PROFILE_CUSTODY_INVENTORY_MAX_ENTRIES:
        raise ProfileCustodyRecordError("profile custody inventory exceeds its entry limit")


def _inventory_posix_file(
    directory_fd: int,
    name: str,
    relative: str,
    observed: os.stat_result,
) -> ProfileCustodyInventoryEntry:
    try:
        descriptor = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=directory_fd)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile custody inventory file cannot be no-follow opened") from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or (metadata.st_dev, metadata.st_ino, metadata.st_size)
            != (observed.st_dev, observed.st_ino, observed.st_size)
            or metadata.st_size > PROFILE_CUSTODY_DATA_FILE_MAX_BYTES
        ):
            raise ProfileCustodyRecordError("profile custody inventory file changed before reading")
        digest = sha256()
        remaining = metadata.st_size
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                raise ProfileCustodyRecordError("profile custody inventory file changed during reading")
            digest.update(chunk)
            remaining -= len(chunk)
        if os.fstat(descriptor).st_size != metadata.st_size:
            raise ProfileCustodyRecordError("profile custody inventory file changed during reading")
        return ProfileCustodyInventoryEntry(relative, metadata.st_size, f"{CONTENT_DIGEST_PREFIX}{digest.hexdigest()}")
    finally:
        os.close(descriptor)


def _inventory_windows_directory(
    path: Path,
    prefix: str,
    entries: list[ProfileCustodyInventoryEntry],
    *,
    ignore_deletion_marker: bool,
) -> None:
    with ExitStack() as anchors:
        anchor_directory(anchors, path, final_access=0x80000000)
        try:
            children = sorted(iter_directory(path, require_root=True), key=lambda child: child.name)
        except OSError as exc:
            raise ProfileCustodyRecordError("profile custody inventory directory cannot be read") from exc
        for child in children:
            if _skip_inventory_entry(prefix, child.name, ignore_deletion_marker):
                continue
            _inventory_windows_entry(child, prefix, entries, ignore_deletion_marker)


def _inventory_windows_entry(
    child: Path,
    prefix: str,
    entries: list[ProfileCustodyInventoryEntry],
    ignore_deletion_marker: bool,
) -> None:
    relative = f"{prefix}/{child.name}" if prefix else child.name
    try:
        metadata = child.lstat()
    except OSError as exc:
        raise ProfileCustodyRecordError("profile custody inventory entry cannot be inspected") from exc
    if stat.S_ISLNK(metadata.st_mode) or is_reparse_metadata(metadata):
        raise ProfileCustodyRecordError("profile custody inventory refuses a link or reparse point")
    if stat.S_ISDIR(metadata.st_mode):
        _inventory_windows_directory(child, relative, entries, ignore_deletion_marker=ignore_deletion_marker)
        return
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > PROFILE_CUSTODY_DATA_FILE_MAX_BYTES:
        raise ProfileCustodyRecordError("profile custody inventory refuses a non-regular entry")
    with windows_regular_file_anchor(child):
        try:
            payload = child.read_bytes()
        except OSError as exc:
            raise ProfileCustodyRecordError("profile custody inventory file cannot be read") from exc
    after = child.lstat()
    if (after.st_dev, after.st_ino, after.st_size) != (metadata.st_dev, metadata.st_ino, metadata.st_size):
        raise ProfileCustodyRecordError("profile custody inventory file changed during reading")
    entries.append(ProfileCustodyInventoryEntry(relative, len(payload), prefixed_digest(payload)))
    _ensure_inventory_entry_limit(entries)


__all__ = [
    "PROFILE_CUSTODY_DATA_FILE_MAX_BYTES",
    "PROFILE_CUSTODY_DATA_MAX_ENTRIES",
    "PROFILE_CUSTODY_INVENTORY_MAX_ENTRIES",
    "PROFILE_CUSTODY_INVENTORY_MAX_TOTAL_BYTES",
    "ProfileCustodyInventory",
    "ProfileCustodyInventoryEntry",
    "inventory_profile_custody_capsule",
]
