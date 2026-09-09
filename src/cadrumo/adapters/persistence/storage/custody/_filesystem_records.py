"""Atomic local custody-record transitions.

The public filesystem facade retains the custody locks, bounded primitive
read/write operations, and the public API names. This module owns the
compare-and-swap transition state machines so their Windows and POSIX
publication paths stay together.
"""

from __future__ import annotations

import os
import sys
from contextlib import ExitStack, suppress
from pathlib import Path
from uuid import uuid4

from . import filesystem as _filesystem
from ._capsule_filesystem import renameat2_noreplace, windows_mark_handle_for_deletion
from .errors import ProfileCustodyRecordError
from .filesystem_primitives import (
    anchor_directory,
    posix_directory_fd,
    windows_create_file_api,
    windows_file_information_type,
)

def compare_and_replace_profile_custody_local_record(
    path: Path,
    *,
    expected: bytes | None,
    replacement: bytes,
    maximum_bytes: int,
) -> None:
    """Atomically replace ``path`` only when its exact anchored bytes match.

    The comparison and mutation belong to one custody-owner operation.  A
    sibling that substitutes a different regular, canonical record after the
    comparison is detected at the exchange boundary; its bytes are restored
    before this function refuses.  ``expected=None`` is the one no-replace
    initial publication case.
    """
    if maximum_bytes < 1 or len(replacement) > maximum_bytes:
        raise ProfileCustodyRecordError("local custody record compare-and-replace payload exceeds its byte limit")
    if expected is None:
        _filesystem.write_profile_custody_local_record(path, replacement, publish_once=True)
        return
    if len(expected) < 1 or len(expected) > maximum_bytes:
        raise ProfileCustodyRecordError("local custody record compare-and-replace expectation is out of bounds")
    if os.name != "nt":
        _posix_compare_and_replace_local_record(
            path,
            expected=expected,
            replacement=replacement,
            maximum_bytes=maximum_bytes,
        )
        return
    _windows_compare_and_replace_local_record(
        path,
        expected=expected,
        replacement=replacement,
        maximum_bytes=maximum_bytes,
    )


def compare_and_replace_same_or_predecessor_profile_custody_local_record(
    path: Path,
    *,
    current: bytes,
    predecessor: bytes | None,
    maximum_bytes: int,
) -> None:
    """Idempotently publish ``current`` from only its exact predecessor.

    A durable retry whose requested bytes are already current is successful and
    performs no mutation.  Otherwise, one anchored compare-and-replace accepts
    only the exact predecessor (or a proven-absent first receipt); every other
    leaf is preserved and refused.
    """
    if len(current) < 1 or len(current) > maximum_bytes:
        raise ProfileCustodyRecordError("local custody record idempotent CAS payload is out of bounds")
    if predecessor is not None and (len(predecessor) < 1 or len(predecessor) > maximum_bytes):
        raise ProfileCustodyRecordError("local custody record idempotent CAS predecessor is out of bounds")
    if os.name != "nt":
        _posix_compare_and_replace_same_or_predecessor_local_record(
            path,
            current=current,
            predecessor=predecessor,
            maximum_bytes=maximum_bytes,
        )
        return
    _windows_compare_and_replace_same_or_predecessor_local_record(
        path,
        current=current,
        predecessor=predecessor,
        maximum_bytes=maximum_bytes,
    )


def _posix_compare_and_replace_same_or_predecessor_local_record(
    path: Path,
    *,
    current: bytes,
    predecessor: bytes | None,
    maximum_bytes: int,
) -> None:
    """Perform the idempotent receipt transition below one pinned POSIX parent."""
    if not sys.platform.startswith("linux"):
        raise ProfileCustodyRecordError(
            "atomic local custody record idempotent compare-and-replace is unavailable on this POSIX host"
        )
    with posix_directory_fd(path.parent) as parent_fd:
        observed = _read_optional_posix_local_record(parent_fd, path.name, maximum_bytes=maximum_bytes)
        if observed == current:
            _posix_clear_idempotent_backup_if_predecessor(
                parent_fd,
                path,
                predecessor=predecessor,
                maximum_bytes=maximum_bytes,
            )
            return
        if predecessor is None:
            if observed is not None:
                raise ProfileCustodyRecordError("local custody record idempotent CAS differs from first receipt")
            _posix_publish_current_or_confirm_existing(
                parent_fd,
                path,
                current=current,
                maximum_bytes=maximum_bytes,
            )
            return
        if observed != predecessor:
            raise ProfileCustodyRecordError("local custody record idempotent CAS predecessor differs")
        stage_name = _local_record_idempotent_backup_name(path)
        descriptor = _filesystem.posix_open_exclusive_file(parent_fd, stage_name)
        try:
            _filesystem.write_descriptor_fsynced(descriptor, current)
        finally:
            os.close(descriptor)
        exchanged = False
        try:
            _filesystem.renameat2_exchange(parent_fd=parent_fd, first_name=path.name, second_name=stage_name)
            exchanged = True
            displaced = _filesystem.read_regular_file_fd(
                parent_fd,
                stage_name,
                display_path=path.with_name(stage_name),
                maximum_bytes=maximum_bytes,
                trace=None,
            )
            if displaced == predecessor:
                # The exact predecessor remains as the deterministic recovery
                # sidecar until a same-receipt retry clears it.  A process can
                # therefore distinguish publication from cleanup without
                # making a new target mutation or trusting an arbitrary file.
                os.fsync(parent_fd)
                return
            _filesystem.renameat2_exchange(parent_fd=parent_fd, first_name=path.name, second_name=stage_name)
            exchanged = False
            if displaced == current:
                return
            raise ProfileCustodyRecordError("local custody record changed before idempotent CAS mutation")
        except OSError as exc:
            raise ProfileCustodyRecordError("local custody record cannot be idempotently compare-and-replaced") from exc
        finally:
            if not exchanged:
                with suppress(FileNotFoundError):
                    os.unlink(stage_name, dir_fd=parent_fd)


def _posix_clear_idempotent_backup_if_predecessor(
    parent_fd: int,
    path: Path,
    *,
    predecessor: bytes | None,
    maximum_bytes: int,
) -> None:
    """Clear only the exact predecessor sidecar left by a failed receipt cleanup."""
    backup_name = _local_record_idempotent_backup_name(path)
    observed_backup = _read_optional_posix_local_record(parent_fd, backup_name, maximum_bytes=maximum_bytes)
    if observed_backup is None:
        return
    if predecessor is None or observed_backup != predecessor:
        raise ProfileCustodyRecordError("local custody record idempotent CAS backup differs")
    _posix_compare_and_clear_local_record(
        path.with_name(backup_name),
        expected=predecessor,
        maximum_bytes=maximum_bytes,
    )


def _posix_publish_current_or_confirm_existing(
    parent_fd: int,
    path: Path,
    *,
    current: bytes,
    maximum_bytes: int,
) -> None:
    """No-replace publish the first receipt, accepting only a racing same receipt."""
    stage_name = _local_record_stage_name(path)
    descriptor = _filesystem.posix_open_exclusive_file(parent_fd, stage_name)
    try:
        _filesystem.write_descriptor_fsynced(descriptor, current)
    finally:
        os.close(descriptor)
    try:
        os.link(stage_name, path.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
    except FileExistsError:
        observed = _read_optional_posix_local_record(parent_fd, path.name, maximum_bytes=maximum_bytes)
        if observed != current:
            raise ProfileCustodyRecordError("local custody record idempotent first receipt now differs") from None
    except OSError as exc:
        raise ProfileCustodyRecordError("local custody record cannot publish its first idempotent receipt") from exc
    finally:
        with suppress(FileNotFoundError):
            os.unlink(stage_name, dir_fd=parent_fd)
    os.fsync(parent_fd)


def _read_optional_posix_local_record(parent_fd: int, name: str, *, maximum_bytes: int) -> bytes | None:
    return _filesystem.read_regular_file_open(
        Path(name),
        maximum_bytes=maximum_bytes,
        trace=None,
        parent_fd=parent_fd,
        missing_ok=True,
    )


def _windows_compare_and_replace_same_or_predecessor_local_record(
    path: Path,
    *,
    current: bytes,
    predecessor: bytes | None,
    maximum_bytes: int,
) -> None:
    """Use one ReplaceFileW transition, restoring a racing same receipt unchanged."""
    with ExitStack() as anchors:
        anchor_directory(anchors, path.parent, final_access=0x80000000)
        observed = _filesystem.read_optional_profile_custody_local_record(path, maximum_bytes=maximum_bytes)
        backup = path.with_name(_local_record_idempotent_backup_name(path))
        if observed == current:
            _windows_clear_idempotent_backup_if_predecessor(
                backup,
                predecessor=predecessor,
                maximum_bytes=maximum_bytes,
            )
            return
        if predecessor is None:
            if observed is not None:
                raise ProfileCustodyRecordError("local custody record idempotent CAS differs from first receipt")
            try:
                _filesystem.write_profile_custody_local_record(path, current, publish_once=True)
            except ProfileCustodyRecordError:
                if _filesystem.read_optional_profile_custody_local_record(path, maximum_bytes=maximum_bytes) == current:
                    return
                raise
            return
        if observed != predecessor:
            raise ProfileCustodyRecordError("local custody record idempotent CAS predecessor differs")
        stage = path.with_name(_local_record_stage_name(path))
        _filesystem.write_windows_local_stage(stage, current)
        try:
            _filesystem.windows_replace_file(target=path, replacement=stage, backup=backup)
            displaced = _filesystem.read_profile_custody_local_record(backup, maximum_bytes=maximum_bytes)
            if displaced == predecessor:
                # Retain the verified predecessor until a same-receipt retry
                # clears it.  This keeps post-publication cleanup recoverable
                # instead of turning a cleanup failure into an ambiguous
                # target rewrite.
                return
            _filesystem.windows_replace_file(target=path, replacement=backup, backup=stage)
            if displaced == current:
                _filesystem.clear_profile_custody_local_record(stage)
                return
            raise ProfileCustodyRecordError("local custody record changed before idempotent CAS mutation")
        except BaseException:
            with suppress(FileNotFoundError):
                _filesystem.clear_profile_custody_local_record(stage)
            raise


def _windows_clear_idempotent_backup_if_predecessor(
    backup: Path,
    *,
    predecessor: bytes | None,
    maximum_bytes: int,
) -> None:
    """Retire only the deterministic backup left by this exact receipt.

    A failed post-publication cleanup leaves the target already current and
    the predecessor in this sidecar.  A retry must neither replace the current
    target nor discard an unrelated sibling, so it removes the sidecar only
    through the anchored compare-and-clear operation after proving the exact
    predecessor bytes.
    """
    observed_backup = _filesystem.read_optional_profile_custody_local_record(backup, maximum_bytes=maximum_bytes)
    if observed_backup is None:
        return
    if predecessor is None or observed_backup != predecessor:
        raise ProfileCustodyRecordError("local custody record idempotent CAS backup differs")
    compare_and_clear_profile_custody_local_record(
        backup,
        expected=predecessor,
        maximum_bytes=maximum_bytes,
    )


def compare_and_clear_profile_custody_local_record(
    path: Path,
    *,
    expected: bytes,
    maximum_bytes: int,
) -> None:
    """Remove ``path`` only when its exact anchored bytes still match.

    Unlike a read followed by ``unlink``, this keeps the verified leaf pinned
    through the delete decision and refuses without deleting a substituted
    canonical record.
    """
    if len(expected) < 1 or len(expected) > maximum_bytes:
        raise ProfileCustodyRecordError("local custody record compare-and-clear expectation is out of bounds")
    if os.name != "nt":
        _posix_compare_and_clear_local_record(path, expected=expected, maximum_bytes=maximum_bytes)
        return
    _windows_compare_and_clear_local_record(path, expected=expected, maximum_bytes=maximum_bytes)


def _posix_compare_and_replace_local_record(
    path: Path,
    *,
    expected: bytes,
    replacement: bytes,
    maximum_bytes: int,
) -> None:
    """CAS through Linux ``renameat2(EXCHANGE)`` below one pinned directory."""
    if not sys.platform.startswith("linux"):
        raise ProfileCustodyRecordError(
            "atomic local custody record compare-and-replace is unavailable on this POSIX host"
        )
    with posix_directory_fd(path.parent) as parent_fd:
        _compare_posix_local_record(parent_fd, path.name, expected=expected, maximum_bytes=maximum_bytes)
        stage_name = _local_record_stage_name(path)
        descriptor = _filesystem.posix_open_exclusive_file(parent_fd, stage_name)
        try:
            _filesystem.write_descriptor_fsynced(descriptor, replacement)
        finally:
            os.close(descriptor)
        exchanged = False
        try:
            _filesystem.renameat2_exchange(parent_fd=parent_fd, first_name=path.name, second_name=stage_name)
            exchanged = True
            displaced = _filesystem.read_regular_file_fd(
                parent_fd,
                stage_name,
                display_path=path.with_name(stage_name),
                maximum_bytes=maximum_bytes,
                trace=None,
            )
            if displaced != expected:
                _filesystem.renameat2_exchange(parent_fd=parent_fd, first_name=path.name, second_name=stage_name)
                exchanged = False
                raise ProfileCustodyRecordError("local custody record changed before compare-and-replace mutation")
            os.unlink(stage_name, dir_fd=parent_fd)
            exchanged = False
            os.fsync(parent_fd)
        except OSError as exc:
            raise ProfileCustodyRecordError("local custody record cannot be compare-and-replaced") from exc
        finally:
            if not exchanged:
                with suppress(FileNotFoundError):
                    os.unlink(stage_name, dir_fd=parent_fd)


def _posix_compare_and_clear_local_record(path: Path, *, expected: bytes, maximum_bytes: int) -> None:
    """Move only the exact expected leaf aside, then delete that verified inode."""
    if not sys.platform.startswith("linux"):
        raise ProfileCustodyRecordError(
            "atomic local custody record compare-and-clear is unavailable on this POSIX host"
        )
    with posix_directory_fd(path.parent) as parent_fd:
        _compare_posix_local_record(parent_fd, path.name, expected=expected, maximum_bytes=maximum_bytes)
        stage_name = _local_record_stage_name(path)
        try:
            renameat2_noreplace(
                source_fd=parent_fd,
                source_name=path.name,
                destination_fd=parent_fd,
                destination_name=stage_name,
            )
            displaced = _filesystem.read_regular_file_fd(
                parent_fd,
                stage_name,
                display_path=path.with_name(stage_name),
                maximum_bytes=maximum_bytes,
                trace=None,
            )
            if displaced != expected:
                renameat2_noreplace(
                    source_fd=parent_fd,
                    source_name=stage_name,
                    destination_fd=parent_fd,
                    destination_name=path.name,
                )
                raise ProfileCustodyRecordError("local custody record changed before compare-and-clear mutation")
            os.unlink(stage_name, dir_fd=parent_fd)
            os.fsync(parent_fd)
        except OSError as exc:
            raise ProfileCustodyRecordError("local custody record cannot be compare-and-cleared") from exc


def _compare_posix_local_record(parent_fd: int, name: str, *, expected: bytes, maximum_bytes: int) -> None:
    """Read the no-follow leaf through its descriptor before a CAS mutation."""
    actual = _filesystem.read_regular_file_fd(
        parent_fd,
        name,
        display_path=Path(name),
        maximum_bytes=maximum_bytes,
        trace=None,
    )
    if actual != expected:
        raise ProfileCustodyRecordError("local custody record compare-and-swap expectation differs")


def _windows_compare_and_replace_local_record(
    path: Path,
    *,
    expected: bytes,
    replacement: bytes,
    maximum_bytes: int,
) -> None:
    """CAS with ``ReplaceFileW`` and a verified backup of the displaced leaf."""
    with ExitStack() as anchors:
        anchor_directory(anchors, path.parent, final_access=0x80000000)
        if _filesystem.read_profile_custody_local_record(path, maximum_bytes=maximum_bytes) != expected:
            raise ProfileCustodyRecordError("local custody record compare-and-swap expectation differs")
        stage = path.with_name(_local_record_stage_name(path))
        backup = path.with_name(_local_record_backup_name(path))
        _filesystem.write_windows_local_stage(stage, replacement)
        try:
            _filesystem.windows_replace_file(target=path, replacement=stage, backup=backup)
            displaced = _filesystem.read_profile_custody_local_record(backup, maximum_bytes=maximum_bytes)
            if displaced != expected:
                _filesystem.windows_replace_file(target=path, replacement=backup, backup=stage)
                raise ProfileCustodyRecordError("local custody record changed before compare-and-replace mutation")
            _filesystem.clear_profile_custody_local_record(backup)
        except BaseException:
            with suppress(FileNotFoundError):
                _filesystem.clear_profile_custody_local_record(stage)
            raise


def _windows_compare_and_clear_local_record(path: Path, *, expected: bytes, maximum_bytes: int) -> None:
    """Read and delete through one no-delete-shared Windows leaf handle."""
    with ExitStack() as anchors:
        anchor_directory(anchors, path.parent, final_access=0x80000000)
        ctypes, wintypes, kernel32, create_file = windows_create_file_api()
        file_information_type = windows_file_information_type()
        handle = create_file(
            str(path),
            0x80000000 | 0x00010000,  # GENERIC_READ | DELETE
            0x00000001,  # FILE_SHARE_READ only: pin contents and leaf name.
            None,
            3,  # OPEN_EXISTING
            0x00200000,  # FILE_FLAG_OPEN_REPARSE_POINT
            None,
        )
        if handle == wintypes.HANDLE(-1).value:
            raise ProfileCustodyRecordError("local custody record cannot be no-follow opened for compare-and-clear")
        try:
            info = file_information_type()
            if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
                raise ProfileCustodyRecordError(
                    "local custody record identity cannot be verified before compare-and-clear"
                )
            if info.dwFileAttributes & 0x400 or info.dwFileAttributes & 0x10:
                raise ProfileCustodyRecordError("local custody record must not be a reparse point or directory")
            payload = _filesystem.windows_read_handle_bounded(
                handle=int(handle), info=info, maximum_bytes=maximum_bytes
            )
            if payload != expected:
                raise ProfileCustodyRecordError("local custody record compare-and-swap expectation differs")
            windows_mark_handle_for_deletion(int(handle))
        finally:
            kernel32.CloseHandle(handle)


def _local_record_stage_name(path: Path) -> str:
    return f".{path.name}.cas-stage.{os.getpid()}.{uuid4().hex}.tmp"


def _local_record_backup_name(path: Path) -> str:
    return f".{path.name}.cas-backup.{os.getpid()}.{uuid4().hex}.tmp"


def _local_record_idempotent_backup_name(path: Path) -> str:
    """Return the sole recoverable backup name for one idempotent receipt."""
    return f".{path.name}.cas-idempotent-backup"
