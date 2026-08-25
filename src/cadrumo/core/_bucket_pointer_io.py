"""Atomic current-record IO for the active-profile pointer.

This module owns exactly one current-format record parser and atomic writer.
The application pointer transaction owns cross-process transition serialization
through the custody-root lock; this core boundary neither opens that lock nor
implements profile lifecycle policy.
"""

from __future__ import annotations

import os
import stat
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from ._bucket_pointer import BucketPointer
from ._fsync import fsync_parent_dir
from ._link_safety import is_link_like
from ._windows_contention import is_windows_contention

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable

    from .errors import CadrumoError


def pointer_path(root: Path) -> Path:
    """Return the active-profile record path beneath ``root``."""
    from ._storage_taxonomy import StorageCategory, storage_location

    return root / storage_location(StorageCategory.ACTIVE_PROFILE_POINTER).relative_path()


_POINTER_READ_RETRY_SECONDS = 1.0
_POINTER_READ_POLL_SECONDS = 0.02
_POINTER_READ_MAX_WAIT_SECONDS = 15.0
_POINTER_WRITE_RETRY_SECONDS = 1.0
_POINTER_MAXIMUM_BYTES = 1024


def _pointer_entry_signature(target: Path) -> tuple[str, int, int] | None:
    from .paths import path_stat_fingerprint

    try:
        return path_stat_fingerprint(target)
    except OSError:
        return None


def _read_pointer_bytes(target: Path) -> bytes | None:
    """Read one complete record, waiting out a Windows replacement race."""
    def read_once() -> bytes:
        # Refuse a discovered reparse point before open; O_NOFOLLOW and fstat
        # close the POSIX race and preserve the same no-follow boundary used by
        # destructive custody transitions.
        if is_link_like(target):
            raise OSError("active-profile pointer must not be link-like")
        descriptor = os.open(
            target,
            os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > _POINTER_MAXIMUM_BYTES:
                raise OSError("active-profile pointer must be a bounded regular file")
            payload = os.read(descriptor, _POINTER_MAXIMUM_BYTES + 1)
            if len(payload) != metadata.st_size or len(payload) > _POINTER_MAXIMUM_BYTES:
                raise OSError("active-profile pointer changed during read")
            return payload
        finally:
            os.close(descriptor)

    if sys.platform != "win32":
        try:
            return read_once()
        except FileNotFoundError:
            return None
    started = time.monotonic()
    deadline = started + _POINTER_READ_RETRY_SECONDS
    ceiling = started + _POINTER_READ_MAX_WAIT_SECONDS
    signature = _pointer_entry_signature(target)
    while True:
        try:
            return read_once()
        except FileNotFoundError:
            return None
        except PermissionError:
            now = time.monotonic()
            current = _pointer_entry_signature(target)
            if current != signature:
                signature = current
                deadline = now + _POINTER_READ_RETRY_SECONDS
            if now >= deadline or now >= ceiling:
                raise
            time.sleep(_POINTER_READ_POLL_SECONDS)


def read_pointer(root: Path) -> BucketPointer:
    """Observe the optional selection and durable current coordinate once.

    A fresh root has no record and therefore observes as the initial absent
    coordinate zero. Once a transition has occurred, absence is persisted as a
    strict tombstone rather than inferred from a deleted file.
    """
    raw = _read_pointer_bytes(pointer_path(root))
    if raw is None:
        return BucketPointer.absent(transition_revision=0)
    return BucketPointer.from_toml(raw.decode("utf-8"))


def _await_uncontended(operation: Callable[[], None]) -> None:
    deadline = time.monotonic() + _POINTER_WRITE_RETRY_SECONDS
    while True:
        try:
            operation()
        except PermissionError as exc:
            if not is_windows_contention(exc) or time.monotonic() >= deadline:
                raise
            time.sleep(_POINTER_READ_POLL_SECONDS)
            continue
        return


def write_pointer(root: Path, pointer: BucketPointer) -> None:
    """Atomically replace the one strict pointer record.

    The caller must hold the canonical custody-root transaction when changing
    a selection. This primitive deliberately persists exactly the supplied
    record so the transaction remains the only owner of revision succession.
    """
    from .atomic_write import atomic_write_hardened_bytes

    target = pointer_path(root)
    _await_uncontended(lambda: atomic_write_hardened_bytes(target, pointer.to_toml().encode("utf-8")))
    fsync_parent_dir(target)


def resolve_active_bucket_id() -> str | None:
    """Resolve a process override or the current persisted pointer selection."""
    from .config import load_settings

    settings = load_settings()
    override = (settings.cadrumo_active_profile or "").strip()
    if override:
        return override
    return read_pointer(settings.cadrumo_local_storage_root).bucket_id


def require_active_bucket_id() -> str:
    """Return the selected bucket or raise the canonical no-profile refusal."""
    from .errors import NoActiveProfileError

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        raise NoActiveProfileError(translated_message="application.workflow.errors.no_active_profile_bucket")
    return bucket_id


def resolve_repository_bucket_id(bucket_id: str | None, *, error_type: type[CadrumoError]) -> str:
    """Resolve an explicit bucket or the current pointer selection."""
    if bucket_id is not None:
        trimmed = bucket_id.strip()
        if trimmed:
            return trimmed
        raise error_type(
            translated_message="application.workflow.errors.no_active_profile_bucket",
            context={"reason": "blank_explicit_bucket_id"},
        )
    active = resolve_active_bucket_id()
    if active is None:
        raise error_type(
            translated_message="application.workflow.errors.no_active_profile_bucket",
            context={"reason": "missing_active_profile_bucket"},
        )
    return active


__all__ = [
    "pointer_path",
    "read_pointer",
    "require_active_bucket_id",
    "resolve_active_bucket_id",
    "resolve_repository_bucket_id",
    "write_pointer",
]
