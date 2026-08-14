"""Bounded capsule data-tree writes and password-authority reads."""

from __future__ import annotations

import os
from collections.abc import Mapping
from contextlib import ExitStack, suppress
from pathlib import Path, PurePosixPath

from ._errors import ProfileCustodyRecordError
from ._filesystem import (
    PROFILE_CUSTODY_DATA_FILE_MAX_BYTES,
    PROFILE_CUSTODY_DATA_MAX_ENTRIES,
    ProfileCustodyPasswordReadOperation,
    anchor_directory,
    fsync_directory,
    posix_open_child_directory,
    read_regular_file,
    read_regular_file_fd,
    write_exclusive_fsynced,
    write_exclusive_fsynced_fd,
)
from ._records import ProfileCustodyEnvelope
from ._sentinel import PROFILE_CUSTODY_SENTINEL_FILENAME, PROFILE_CUSTODY_SENTINEL_MAX_BYTES
from ._sentinel_contract import ProfileCustodySentinelRecord, parse_profile_custody_sentinel_record


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
    if not value or "\\" in value:
        raise ProfileCustodyRecordError("profile capsule data path must be a nonempty portable relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(component in {"", ".", ".."} for component in path.parts):
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
    from ._records import PROFILE_CUSTODY_ENVELOPE_MAX_BYTES, parse_profile_custody_envelope

    return parse_profile_custody_envelope(
        read_regular_file(path, maximum_bytes=PROFILE_CUSTODY_ENVELOPE_MAX_BYTES, trace=trace)
    )


def read_password_envelope_fd(
    parent_fd: int,
    *,
    display_path: Path,
    trace: list[ProfileCustodyPasswordReadOperation],
) -> ProfileCustodyEnvelope:
    from ._records import PROFILE_CUSTODY_ENVELOPE_MAX_BYTES, parse_profile_custody_envelope

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


__all__ = [
    "read_password_envelope",
    "read_password_envelope_fd",
    "read_sentinel",
    "read_sentinel_fd",
    "validate_data_file_inventory",
    "validated_data_path",
    "write_data_files",
    "write_posix_data_files",
]
