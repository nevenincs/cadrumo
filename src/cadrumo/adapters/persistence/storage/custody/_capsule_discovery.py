"""Anchored discovery and retired-layout refusal for profile custody.

The discovery boundary deliberately has two, non-overlapping outcomes:

* only a final UUID directory with an authentic current commit marker is a
  discoverable capsule; and
* a member of the closed retired-layout inventory is an explicit refusal.

The latter is an existence-only detector.  It never opens, reads, parses, or
otherwise interprets a retired member.  Keeping that distinction here gives
every application projection the same rooted, no-follow inventory rather than
letting workflow code rediscover buckets or manifests independently.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from typing import Protocol
from uuid import UUID

from ._errors import (
    ProfileCustodyRecordError,
    ProfileCustodyRecoveryGuidance,
    ProfileCustodyRefusal,
    ProfileCustodyRefusedError,
)
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


PROFILE_CUSTODY_RETIRED_BUCKET_MEMBER_PATHS: tuple[str, ...] = ("manifest.toml",)
"""Closed, exact retired members checked below every bucket candidate.

``manifest.toml`` was the former plaintext profile authority.  Current
capsules have no manifest member: their only discovery authority is the
commit marker and their label is a non-authoritative current projection.
"""


def detect_retired_profile_custody_member_paths(capsules_root: Path) -> tuple[str, ...]:
    """Return exact retired member names found by the anchored, no-open detector."""
    if not os.path.lexists(capsules_root):
        return ()
    return _anchored_retired_bucket_member_paths(capsules_root)


def refuse_retired_profile_custody_paths(capsules_root: Path) -> None:
    """Raise the one destructive-reset refusal when a retired member exists.

    The detector intentionally reports no parsed attributes and no candidate
    identity.  A caller can act only on the stable refusal and its explicit
    reset/re-enrol guidance, never on an inferred retired profile.
    """
    detected = detect_retired_profile_custody_member_paths(capsules_root)
    if not detected:
        return
    raise ProfileCustodyRefusedError(
        ProfileCustodyRefusal.LEGACY_CUSTODY_DETECTED,
        context={
            "retired_member_paths": detected,
        },
        recovery_guidance=(
            ProfileCustodyRecoveryGuidance.DESTRUCTIVE_RESET,
            ProfileCustodyRecoveryGuidance.REENROLL_PROFILE,
        ),
    )


def _anchored_retired_bucket_member_paths(capsules_root: Path) -> tuple[str, ...]:
    if os.name != "nt":
        return _anchored_retired_bucket_member_paths_posix(capsules_root)
    return _anchored_retired_bucket_member_paths_windows(capsules_root)


def _anchored_retired_bucket_member_paths_posix(capsules_root: Path) -> tuple[str, ...]:
    detected: set[str] = set()
    with posix_directory_fd(capsules_root) as root_fd:
        for candidate_name in os.listdir(root_fd):
            if not _is_posix_directory(root_fd, candidate_name):
                continue
            candidate_fd = _open_posix_candidate(root_fd, candidate_name)
            if candidate_fd is None:
                continue
            try:
                for member_path in PROFILE_CUSTODY_RETIRED_BUCKET_MEMBER_PATHS:
                    if posix_child_exists(
                        candidate_fd,
                        member_path,
                        trace=None,
                        display_path=capsules_root / candidate_name / member_path,
                    ):
                        detected.add(member_path)
            finally:
                os.close(candidate_fd)
    return tuple(sorted(detected))


def _anchored_retired_bucket_member_paths_windows(capsules_root: Path) -> tuple[str, ...]:
    detected: set[str] = set()
    with ExitStack() as anchors:
        anchor_directory(anchors, capsules_root, final_access=0x80000000)
        try:
            with os.scandir(capsules_root) as entries:
                for entry in entries:
                    try:
                        if not entry.is_dir(follow_symlinks=False):
                            continue
                    except OSError:
                        continue
                    candidate = capsules_root / entry.name
                    try:
                        with ExitStack() as candidate_anchors:
                            anchor_directory(candidate_anchors, candidate, final_access=0x80000000)
                            for member_path in PROFILE_CUSTODY_RETIRED_BUCKET_MEMBER_PATHS:
                                if lexists(candidate / member_path, trace=None):
                                    detected.add(member_path)
                    except ProfileCustodyRecordError:
                        continue
        except OSError as exc:
            raise ProfileCustodyRecordError("profile capsule root cannot be safely enumerated") from exc
    return tuple(sorted(detected))


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
                # A final UUID candidate with a current marker is no longer an
                # ignorable directory once its marker fails validation.  It is
                # a malformed current format and must fail closed rather than
                # masquerade as an absent profile.
                raise
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
        # A link/reparse candidate or a concurrent removal is not a current
        # capsule.  The caller must never inspect children of that path.
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
    with ExitStack() as candidate_anchors:
        try:
            anchor_directory(candidate_anchors, candidate, final_access=0x80000000)
        except ProfileCustodyRecordError:
            # The candidate itself cannot be anchored, so it may not be
            # treated as a capsule and no child is inspected.
            return None
        profile_id = _canonical_profile_id(entry.name)
        if profile_id is None:
            return None
        marker_path = candidate / commit_filename
        if not lexists(marker_path, trace=None):
            return None
        commit = parse_commit(read_regular_file(marker_path, maximum_bytes=maximum_bytes, trace=None))
        if commit.profile_id != profile_id:
            raise ProfileCustodyRecordError("profile capsule commit UUID does not match its directory")
        return profile_id


def _canonical_profile_id(candidate_name: str) -> UUID | None:
    try:
        profile_id = UUID(candidate_name)
    except ValueError:
        return None
    return profile_id if str(profile_id) == candidate_name else None


__all__ = [
    "PROFILE_CUSTODY_RETIRED_BUCKET_MEMBER_PATHS",
    "anchored_current_capsule_ids",
    "detect_retired_profile_custody_member_paths",
    "refuse_retired_profile_custody_paths",
]
