"""Anchored discovery of current profile-custody capsule directories."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from typing import Protocol
from uuid import UUID

from ._errors import ProfileCustodyRecordError
from ._filesystem import (
    anchor_directory,
    lexists,
    posix_child_exists,
    posix_directory_fd,
    posix_open_child_directory,
    read_regular_file,
    read_regular_file_fd,
)


class _CommitIdentity(Protocol):
    profile_id: UUID


def anchored_current_capsule_ids(
    capsules_root: Path,
    *,
    parse_commit: Callable[[bytes], _CommitIdentity],
    commit_filename: str,
    maximum_bytes: int,
) -> tuple[UUID, ...]:
    """Discover UUID capsules whose current commit validates while anchored."""
    if os.name != "nt":
        return _anchored_current_capsule_ids_posix(
            capsules_root,
            parse_commit=parse_commit,
            commit_filename=commit_filename,
            maximum_bytes=maximum_bytes,
        )
    return _anchored_current_capsule_ids_windows(
        capsules_root,
        parse_commit=parse_commit,
        commit_filename=commit_filename,
        maximum_bytes=maximum_bytes,
    )


def _anchored_current_capsule_ids_posix(
    capsules_root: Path,
    *,
    parse_commit: Callable[[bytes], _CommitIdentity],
    commit_filename: str,
    maximum_bytes: int,
) -> tuple[UUID, ...]:
    discovered: list[UUID] = []
    with posix_directory_fd(capsules_root) as root_fd:
        for candidate_name in os.listdir(root_fd):
            if not _is_posix_directory(root_fd, candidate_name):
                continue
            candidate_fd = _open_posix_candidate(root_fd, candidate_name)
            if candidate_fd is None:
                continue
            try:
                profile_id = _canonical_profile_id(candidate_name)
                if profile_id is None:
                    continue
                marker_path = capsules_root / candidate_name / commit_filename
                if not posix_child_exists(
                    candidate_fd,
                    commit_filename,
                    trace=None,
                    display_path=marker_path,
                ):
                    continue
                commit = parse_commit(
                    read_regular_file_fd(
                        candidate_fd,
                        commit_filename,
                        display_path=marker_path,
                        maximum_bytes=maximum_bytes,
                        trace=None,
                    )
                )
                if commit.profile_id == profile_id:
                    discovered.append(profile_id)
            except ProfileCustodyRecordError:
                continue
            finally:
                os.close(candidate_fd)
    return tuple(sorted(discovered, key=str))


def _is_posix_directory(root_fd: int, candidate_name: str) -> bool:
    try:
        metadata = os.stat(candidate_name, dir_fd=root_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ProfileCustodyRecordError("profile capsule root cannot be safely enumerated") from exc
    return stat.S_ISDIR(metadata.st_mode)


def _open_posix_candidate(root_fd: int, candidate_name: str) -> int | None:
    try:
        return posix_open_child_directory(root_fd, candidate_name)
    except ProfileCustodyRecordError:
        return None


def _anchored_current_capsule_ids_windows(
    capsules_root: Path,
    *,
    parse_commit: Callable[[bytes], _CommitIdentity],
    commit_filename: str,
    maximum_bytes: int,
) -> tuple[UUID, ...]:
    discovered: list[UUID] = []
    with ExitStack() as anchors:
        anchor_directory(anchors, capsules_root, final_access=0x80000000)
        try:
            with os.scandir(capsules_root) as entries:
                for entry in entries:
                    profile_id = _windows_candidate_profile_id(
                        capsules_root,
                        entry,
                        parse_commit=parse_commit,
                        commit_filename=commit_filename,
                        maximum_bytes=maximum_bytes,
                    )
                    if profile_id is not None:
                        discovered.append(profile_id)
        except OSError as exc:
            raise ProfileCustodyRecordError("profile capsule root cannot be safely enumerated") from exc
    return tuple(sorted(discovered, key=str))


def _windows_candidate_profile_id(
    capsules_root: Path,
    entry: os.DirEntry[str],
    *,
    parse_commit: Callable[[bytes], _CommitIdentity],
    commit_filename: str,
    maximum_bytes: int,
) -> UUID | None:
    try:
        if not entry.is_dir(follow_symlinks=False):
            return None
    except OSError:
        return None
    candidate = capsules_root / entry.name
    try:
        with ExitStack() as candidate_anchors:
            anchor_directory(candidate_anchors, candidate, final_access=0x80000000)
            profile_id = _canonical_profile_id(entry.name)
            if profile_id is None:
                return None
            marker_path = candidate / commit_filename
            if not lexists(marker_path, trace=None):
                return None
            commit = parse_commit(read_regular_file(marker_path, maximum_bytes=maximum_bytes, trace=None))
            return profile_id if commit.profile_id == profile_id else None
    except ProfileCustodyRecordError:
        return None


def _canonical_profile_id(candidate_name: str) -> UUID | None:
    try:
        profile_id = UUID(candidate_name)
    except ValueError:
        return None
    return profile_id if str(profile_id) == candidate_name else None


__all__ = ["anchored_current_capsule_ids"]
