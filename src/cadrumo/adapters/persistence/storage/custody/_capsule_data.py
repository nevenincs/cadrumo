"""Bounded capsule data-tree writes and password-authority reads."""

from __future__ import annotations

import os
from collections.abc import Mapping
from contextlib import ExitStack, suppress
from pathlib import Path, PurePosixPath, PureWindowsPath
from uuid import uuid4

from .....core.hashing import prefixed_digest
from ._capsule_filesystem import fsync_directory
from .errors import ProfileCustodyRecordError
from .filesystem import (
    PROFILE_CUSTODY_DATA_FILE_MAX_BYTES,
    PROFILE_CUSTODY_DATA_MAX_ENTRIES,
    read_regular_file,
    read_regular_file_fd,
)
from .filesystem_primitives import (
    ProfileCustodyPasswordReadOperation,
    anchor_directory,
    posix_open_child_directory,
    write_exclusive_fsynced,
    write_exclusive_fsynced_fd,
)
from .records import ProfileCustodyEnvelope
from .sentinel import PROFILE_CUSTODY_SENTINEL_FILENAME, PROFILE_CUSTODY_SENTINEL_MAX_BYTES
from .sentinel_contract import ProfileCustodySentinelRecord, parse_profile_custody_sentinel_record


def write_data_files(data_root: Path, data_files: Mapping[str, bytes]) -> None:
    """Write one bounded portable data tree without following links."""
    validate_data_file_inventory(data_files)
    for relative_name, payload in sorted(data_files.items()):
        relative_path = validated_data_path(relative_name)
        if relative_path.as_posix() == PROFILE_CUSTODY_SENTINEL_FILENAME:
            raise ProfileCustodyRecordError("profile capsule data inventory tries to replace the DEK sentinel")
        target = data_root.joinpath(*relative_path.parts)
        with ExitStack() as anchors:
            current = data_root
            for component in relative_path.parts[:-1]:
                candidate = current / component
                with suppress(FileExistsError):
                    candidate.mkdir(mode=0o700)
                anchor_directory(anchors, candidate)
                current = candidate
            write_exclusive_fsynced(target, payload)
            fsync_directory(target.parent)


def validated_data_path(value: str) -> PurePosixPath:
    """Return ``value`` as a relative capsule path, or refuse it.

    "Portable" is the whole contract: the value is parsed as POSIX because that
    is the capsule's on-wire spelling, but it is JOINED onto a staging root on
    whatever platform is running -- and a drive-qualified value means something
    different to the two. ``"C:/x"`` is an ordinary two-component relative path
    to :class:`~pathlib.PurePosixPath`, so it is neither absolute nor dotted and
    clears the checks below; joined on Windows it discards the staging root
    entirely and resolves to ``C:x``. ``"C:x"`` is worse, resolving against the
    process's current directory on that drive.

    So the POSIX reading alone cannot decide this, and the Windows reading is
    the one that matters at the join. Both are consulted.

    The empty-parts check is not redundant with the component check below it.
    ``PurePosixPath`` normalises a lone ``.`` away, so ``"."`` and ``"./"``
    parse to NO components at all -- the ``{"", ".", ".."}`` membership test
    never sees the value it names, and the path resolves to the staging root
    itself, which is a directory rather than a file to write.
    """
    if not value or "\\" in value:
        raise ProfileCustodyRecordError("profile capsule data path must be a nonempty portable relative path")
    path = PurePosixPath(value)
    if not path.parts or path.is_absolute() or any(component in {"", ".", ".."} for component in path.parts):
        raise ProfileCustodyRecordError("profile capsule data path escapes its staging root")
    windows_reading = PureWindowsPath(value)
    if windows_reading.drive or windows_reading.root:
        raise ProfileCustodyRecordError("profile capsule data path escapes its staging root")
    return path


def validate_data_file_inventory(data_files: Mapping[str, bytes]) -> None:
    if len(data_files) > PROFILE_CUSTODY_DATA_MAX_ENTRIES:
        raise ProfileCustodyRecordError("profile capsule data inventory exceeds its entry limit")
    for relative_name, payload in data_files.items():
        validated_data_path(relative_name)
        if len(payload) > PROFILE_CUSTODY_DATA_FILE_MAX_BYTES:
            raise ProfileCustodyRecordError("profile capsule data file is outside its bounded write contract")


def read_password_envelope(
    path: Path,
    *,
    trace: list[ProfileCustodyPasswordReadOperation],
) -> ProfileCustodyEnvelope:
    from .records import PROFILE_CUSTODY_ENVELOPE_MAX_BYTES, parse_profile_custody_envelope

    return parse_profile_custody_envelope(
        read_regular_file(path, maximum_bytes=PROFILE_CUSTODY_ENVELOPE_MAX_BYTES, trace=trace)
    )


def read_password_envelope_fd(
    parent_fd: int,
    *,
    display_path: Path,
    trace: list[ProfileCustodyPasswordReadOperation],
) -> ProfileCustodyEnvelope:
    from .records import PROFILE_CUSTODY_ENVELOPE_MAX_BYTES, parse_profile_custody_envelope

    return parse_profile_custody_envelope(
        read_regular_file_fd(
            parent_fd,
            "envelope.v1.json",
            display_path=display_path,
            maximum_bytes=PROFILE_CUSTODY_ENVELOPE_MAX_BYTES,
            trace=trace,
        )
    )


def read_sentinel(
    path: Path,
    *,
    trace: list[ProfileCustodyPasswordReadOperation],
) -> ProfileCustodySentinelRecord:
    return parse_profile_custody_sentinel_record(
        read_regular_file(
            path,
            maximum_bytes=PROFILE_CUSTODY_SENTINEL_MAX_BYTES,
            trace=trace,
        )
    )


def read_sentinel_fd(
    parent_fd: int,
    *,
    display_path: Path,
    trace: list[ProfileCustodyPasswordReadOperation],
) -> ProfileCustodySentinelRecord:
    return parse_profile_custody_sentinel_record(
        read_regular_file_fd(
            parent_fd,
            PROFILE_CUSTODY_SENTINEL_FILENAME,
            display_path=display_path,
            maximum_bytes=PROFILE_CUSTODY_SENTINEL_MAX_BYTES,
            trace=trace,
        )
    )


def write_posix_data_files(data_fd: int, data_files: Mapping[str, bytes]) -> None:
    if len(data_files) > PROFILE_CUSTODY_DATA_MAX_ENTRIES:
        raise ProfileCustodyRecordError("profile capsule data inventory exceeds its entry limit")
    for relative_name, payload in sorted(data_files.items()):
        relative_path = validated_data_path(relative_name)
        if relative_path.as_posix() == PROFILE_CUSTODY_SENTINEL_FILENAME:
            raise ProfileCustodyRecordError("profile capsule data inventory tries to replace the DEK sentinel")
        if len(payload) > PROFILE_CUSTODY_DATA_FILE_MAX_BYTES:
            raise ProfileCustodyRecordError("profile capsule data file is outside its bounded write contract")
        current_fd = os.dup(data_fd)
        try:
            for component in relative_path.parts[:-1]:
                with suppress(FileExistsError):
                    os.mkdir(component, mode=0o700, dir_fd=current_fd)
                next_fd = posix_open_child_directory(current_fd, component)
                os.close(current_fd)
                current_fd = next_fd
            write_exclusive_fsynced_fd(current_fd, relative_path.name, payload)
            os.fsync(current_fd)
        finally:
            os.close(current_fd)


def replace_data_file(
    data_root: Path,
    relative_name: str,
    payload: bytes,
    *,
    expected_sha256: str,
) -> None:
    """Atomically replace one already-present regular capsule data member.

    Callers must hold their capsule lifecycle lock.  The expected digest is a
    compare-and-swap witness: the exact authenticated bytes read for a command
    must still be current at publication, otherwise no mutation is made.
    """
    relative_path = validated_data_path(relative_name)
    if relative_path.as_posix() == PROFILE_CUSTODY_SENTINEL_FILENAME:
        raise ProfileCustodyRecordError("profile record command cannot replace the DEK sentinel")
    if len(payload) > PROFILE_CUSTODY_DATA_FILE_MAX_BYTES:
        raise ProfileCustodyRecordError("profile record command exceeds the data-file byte limit")
    with ExitStack() as anchors:
        current = data_root
        for component in relative_path.parts[:-1]:
            current = current / component
            anchor_directory(anchors, current)
        replace_capsule_file(
            current,
            relative_path.name,
            payload,
            expected_sha256=expected_sha256,
            maximum_bytes=PROFILE_CUSTODY_DATA_FILE_MAX_BYTES,
        )


def replace_capsule_file(
    directory: Path,
    filename: str,
    payload: bytes,
    *,
    expected_sha256: str,
    maximum_bytes: int,
) -> None:
    """Compare-and-swap one already-present regular file inside a committed capsule.

    The single writer for every in-place capsule replacement, so the members of
    a published capsule cannot come to be mutated by two write paths with
    different guarantees. Callers hold their capsule lifecycle lock, anchor the
    directory's identity, and supply the digest of the exact authenticated
    bytes their command read.

    The digest is a compare-and-swap witness rather than a checksum: if the
    current bytes are not the ones the caller authenticated, the mutation is
    refused outright rather than overwriting a concurrent writer's work. The
    publication is a same-directory rename over a temporary the writer created
    exclusively, then a directory fsync -- so a crash leaves either the old
    member or the new one, never a torn file.

    Args:
        directory: The already-anchored directory holding the member.
        filename: The member's name within ``directory``. One component; path
            traversal is the caller's grammar to validate before arriving here.
        payload: The replacement bytes.
        expected_sha256: Prefixed digest of the bytes being replaced.
        maximum_bytes: The member's own bounded-read ceiling.

    Raises:
        ProfileCustodyRecordError: When the witness is stale or the replacement
            cannot be published.
    """
    target = directory / filename
    existing = read_regular_file(target, maximum_bytes=maximum_bytes, trace=[])
    if prefixed_digest(existing) != expected_sha256:
        raise ProfileCustodyRecordError("profile record compare-and-swap witness is stale")
    replacement = directory / f".{filename}.replace-{uuid4().hex}"
    write_exclusive_fsynced(replacement, payload)
    try:
        os.replace(replacement, target)
    except OSError as exc:
        raise ProfileCustodyRecordError("profile record replacement could not be published") from exc
    fsync_directory(directory)


__all__ = [
    "read_password_envelope",
    "read_password_envelope_fd",
    "read_sentinel",
    "read_sentinel_fd",
    "replace_data_file",
    "validate_data_file_inventory",
    "validated_data_path",
    "write_data_files",
    "write_posix_data_files",
]
