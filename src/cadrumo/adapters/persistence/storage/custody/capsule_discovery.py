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
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_location
from .errors import (
    ProfileCustodyRecordError,
    ProfileCustodyRecoveryGuidance,
    ProfileCustodyRefusal,
    ProfileCustodyRefusedError,
)
from .filesystem import (
    lexists,
    posix_child_exists,
    read_regular_file,
    read_regular_file_fd,
)
from .filesystem_primitives import anchor_directory, posix_directory_fd, posix_open_child_directory
from .paths import profile_custody_directory_name


class _CommitIdentity(Protocol):
    profile_id: UUID


@dataclass(frozen=True, slots=True)
class AnchoredCurrentCapsuleCommit:
    """One current-marker observation, optionally carrying its anchored label bytes."""

    capsule_path: Path
    commit: _CommitIdentity
    label_payload: bytes | None = None
    label_requested: bool = False
    """Whether the caller asked for label provenance at all.

    Separating "not asked for" from "asked for and absent" is what lets a
    summary reader tell a programming error from a capsule that changed
    generation between the marker parse and the label read.
    """

    @property
    def profile_id(self) -> UUID:
        """Return the UUID proved by the canonical directory and parsed marker."""
        return self.commit.profile_id


PROFILE_CUSTODY_RETIRED_BUCKET_MEMBER_PATHS: tuple[str, ...] = (
    storage_location(StorageCategory.BUCKET_MANIFEST).subpath,
)
"""Closed, exact retired members checked below every bucket candidate.

The former plaintext profile authority.  Current capsules have no manifest
member: their only discovery authority is the commit marker and their label
is a non-authoritative current projection.

The name is read from the core storage taxonomy rather than re-typed, because
this detector is the load-bearing reader of it and a second literal here could
drift silently -- recognising nothing while still looking correct.  If the
taxonomy member is ever deleted outright, this import fails loudly at module
load, which is the right failure for a refusal path.
"""

PROFILE_CUSTODY_RETIRED_KEYSTORE_MEMBER_PATHS: tuple[str, ...] = ("bucket.dek.json",)
"""Closed, exact retired members checked below every keystore candidate.

``bucket.dek.json`` was the shared-master-wrapped bucket data-encryption key.
Its writer is gone, so no current-format store can produce one, and a store
still carrying it holds ciphertext whose only key route is the retired
shared-master schedule.  That is a re-enrolment case, never a read: the
detector recognises the name and nothing else.

The keystore root is a SIBLING of the buckets root, never nested inside a
bucket, so a store can carry retired key material with an entirely current
buckets tree.  Checking only below the buckets root left exactly that store
undetected.
"""


_RETIRED_MEMBER_CANDIDATE_GLOB = "*"
"""Stands in for the candidate directory a retired member was found inside.

The scan shape is fixed: a retired member sits exactly one level below a
scanned root, inside a candidate directory whose name the detector refuses to
disclose because naming it would assert that the directory IS a retired
profile -- an identity inferred from retired custody, which this boundary does
not do.  Substituting the wildcard keeps the operator's search pattern
directly usable against the named root while disclosing exactly the same
nothing.  A literal candidate name would not survive the operator envelope in
any case: it is a UUID, and the redaction funnel rewrites a bare UUID to its
profile-id placeholder.
"""


def detect_retired_profile_custody_member_paths(capsules_root: Path, *, keystore_root: Path) -> tuple[str, ...]:
    """Return exact retired member names found by the anchored, no-open detector.

    Both stores that can hold retired material are scanned: the buckets root
    for the retired plaintext manifest, and the sibling keystore root for
    retired shared-master key material.  Either root may be absent; an absent
    root simply contributes nothing.
    """
    capsule_members, keystore_members = _retired_members_by_root(capsules_root, keystore_root=keystore_root)
    return _merged_member_paths(capsule_members, keystore_members)


def refuse_retired_profile_custody_paths(capsules_root: Path, *, keystore_root: Path) -> None:
    """Raise the one destructive-reset refusal when a retired member exists.

    The detector intentionally reports no parsed attributes and no candidate
    identity.  A caller can act only on the stable refusal and its explicit
    reset/re-enrol guidance, never on an inferred retired profile.

    Both scanned roots are reported alongside the member names because the only
    sanctioned remedy is a destructive reset of that store, and an operator
    cannot reset a location the refusal withholds.  Retired key material lives
    outside the buckets tree, so naming only the buckets root would point the
    operator at a directory whose removal leaves the refusal standing.  Each
    names a directory, never a bucket or an identity, so the refusal discloses
    nothing the detector declined to infer and requires reading no retired
    content.

    Those two roots are the REMEDY, and both are always named for that reason.
    Which root each member was found under is a separate question -- the CAUSE
    -- and a flat union of member names across both roots answers it only by
    accident, when a single member is detected.  A store carrying both members
    reported two names and two roots with no pairing, and a store carrying only
    retired key material reported a buckets root that has nothing wrong with
    it.  So each firing arm additionally contributes a root-relative search
    pattern under its own key, and an arm that did not fire contributes none.
    Both facts are pure existence: which member name matched, below which
    named root, at the one depth the scan looks.
    """
    capsule_members, keystore_members = _retired_members_by_root(capsules_root, keystore_root=keystore_root)
    if not capsule_members and not keystore_members:
        return
    context: dict[str, object] = {
        "capsules_root": str(capsules_root),
        "keystore_root": str(keystore_root),
        "retired_member_paths": _merged_member_paths(capsule_members, keystore_members),
    }
    if capsule_members:
        context["capsules_root_retired_matches"] = _root_relative_matches(capsule_members)
    if keystore_members:
        context["keystore_root_retired_matches"] = _root_relative_matches(keystore_members)
    raise ProfileCustodyRefusedError(
        ProfileCustodyRefusal.LEGACY_CUSTODY_DETECTED,
        context=context,
        translated_message="errors.refused.refused_profile_custody_legacy",
        recovery_guidance=(
            ProfileCustodyRecoveryGuidance.DESTRUCTIVE_RESET,
            ProfileCustodyRecoveryGuidance.REENROLL_PROFILE,
        ),
    )


def _retired_members_by_root(capsules_root: Path, *, keystore_root: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (
        _anchored_retired_member_paths(capsules_root, PROFILE_CUSTODY_RETIRED_BUCKET_MEMBER_PATHS),
        _anchored_retired_member_paths(keystore_root, PROFILE_CUSTODY_RETIRED_KEYSTORE_MEMBER_PATHS),
    )


def _merged_member_paths(capsule_members: tuple[str, ...], keystore_members: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({*capsule_members, *keystore_members}))


def _root_relative_matches(member_paths: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"{_RETIRED_MEMBER_CANDIDATE_GLOB}/{member_path}" for member_path in member_paths)


def _anchored_retired_member_paths(scan_root: Path, member_paths: tuple[str, ...]) -> tuple[str, ...]:
    if not os.path.lexists(scan_root):
        return ()
    if os.name != "nt":
        return _anchored_retired_member_paths_posix(scan_root, member_paths)
    return _anchored_retired_member_paths_windows(scan_root, member_paths)


def _anchored_retired_member_paths_posix(scan_root: Path, member_paths: tuple[str, ...]) -> tuple[str, ...]:
    detected: set[str] = set()
    with posix_directory_fd(scan_root) as root_fd:
        for candidate_name in os.listdir(root_fd):
            if not _is_posix_directory(root_fd, candidate_name):
                continue
            candidate_fd = _open_posix_candidate(root_fd, candidate_name)
            if candidate_fd is None:
                continue
            try:
                for member_path in member_paths:
                    if posix_child_exists(
                        candidate_fd,
                        member_path,
                        trace=None,
                        display_path=scan_root / candidate_name / member_path,
                    ):
                        detected.add(member_path)
            finally:
                os.close(candidate_fd)
    return tuple(sorted(detected))


def _anchored_retired_member_paths_windows(scan_root: Path, member_paths: tuple[str, ...]) -> tuple[str, ...]:
    detected: set[str] = set()
    with ExitStack() as anchors:
        anchor_directory(anchors, scan_root, final_access=0x80000000)
        try:
            with os.scandir(scan_root) as entries:
                for entry in entries:
                    try:
                        if not entry.is_dir(follow_symlinks=False):
                            continue
                    except OSError:
                        continue
                    candidate = scan_root / entry.name
                    try:
                        with ExitStack() as candidate_anchors:
                            anchor_directory(candidate_anchors, candidate, final_access=0x80000000)
                            for member_path in member_paths:
                                if lexists(candidate / member_path, trace=None):
                                    detected.add(member_path)
                    except ProfileCustodyRecordError:
                        continue
        except OSError as exc:
            raise ProfileCustodyRecordError("profile capsule root cannot be safely enumerated") from exc
    return tuple(sorted(detected))


def anchored_current_capsule_commits(
    capsules_root: Path,
    *,
    parse_commit: Callable[[bytes], _CommitIdentity],
    commit_filename: str,
    maximum_bytes: int,
    label_filename: str | None = None,
    label_maximum_bytes: int | None = None,
) -> tuple[AnchoredCurrentCapsuleCommit, ...]:
    """Discover current capsules while retaining anchored marker observations.

    An identity-only caller leaves the label arguments absent.  A summary
    caller supplies both and receives the label's bounded bytes from the same
    candidate anchor as the parsed commit, so a directory replacement cannot
    splice one generation's marker to another generation's provenance.
    """
    if (label_filename is None) is not (label_maximum_bytes is None):
        raise ValueError("summary discovery requires both label filename and byte ceiling")
    if os.name != "nt":
        return _anchored_current_capsule_commits_posix(
            capsules_root,
            parse_commit=parse_commit,
            commit_filename=commit_filename,
            maximum_bytes=maximum_bytes,
            label_filename=label_filename,
            label_maximum_bytes=label_maximum_bytes,
        )
    return _anchored_current_capsule_commits_windows(
        capsules_root,
        parse_commit=parse_commit,
        commit_filename=commit_filename,
        maximum_bytes=maximum_bytes,
        label_filename=label_filename,
        label_maximum_bytes=label_maximum_bytes,
    )


def _anchored_current_capsule_commits_posix(
    capsules_root: Path,
    *,
    parse_commit: Callable[[bytes], _CommitIdentity],
    commit_filename: str,
    maximum_bytes: int,
    label_filename: str | None,
    label_maximum_bytes: int | None,
) -> tuple[AnchoredCurrentCapsuleCommit, ...]:
    discovered: list[AnchoredCurrentCapsuleCommit] = []
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
                    label_payload = None
                    if label_filename is not None:
                        assert label_maximum_bytes is not None
                        label_payload = _posix_label_payload(
                            candidate_fd,
                            display_root=capsules_root / candidate_name,
                            label_filename=label_filename,
                            label_maximum_bytes=label_maximum_bytes,
                        )
                    discovered.append(
                        AnchoredCurrentCapsuleCommit(
                            capsule_path=capsules_root / candidate_name,
                            commit=commit,
                            label_payload=label_payload,
                            label_requested=label_filename is not None,
                        )
                    )
            except ProfileCustodyRecordError:
                # A final UUID candidate with a current marker is no longer an
                # ignorable directory once its marker fails validation.  It is
                # a malformed current format and must fail closed rather than
                # masquerade as an absent profile.
                raise
            finally:
                os.close(candidate_fd)
    return tuple(sorted(discovered, key=lambda observation: str(observation.profile_id)))


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


def _posix_label_payload(
    candidate_fd: int,
    *,
    display_root: Path,
    label_filename: str,
    label_maximum_bytes: int,
) -> bytes | None:
    """Read the anchored label beside a parsed marker, or report its absence.

    The data directory and the label member are both probed for existence
    before being read.  Either one missing means the capsule is mid-publication
    or mid-deletion, not malformed, so the absence is reported as ``None``
    rather than raised.
    """
    try:
        data_fd = posix_open_child_directory(candidate_fd, "data")
    except ProfileCustodyRecordError:
        return None
    try:
        display_path = display_root / "data" / label_filename
        if not posix_child_exists(data_fd, label_filename, trace=None, display_path=display_path):
            return None
        return read_regular_file_fd(
            data_fd,
            label_filename,
            display_path=display_path,
            maximum_bytes=label_maximum_bytes,
            trace=None,
        )
    finally:
        os.close(data_fd)


def _anchored_current_capsule_commits_windows(
    capsules_root: Path,
    *,
    parse_commit: Callable[[bytes], _CommitIdentity],
    commit_filename: str,
    maximum_bytes: int,
    label_filename: str | None,
    label_maximum_bytes: int | None,
) -> tuple[AnchoredCurrentCapsuleCommit, ...]:
    discovered: list[AnchoredCurrentCapsuleCommit] = []
    with ExitStack() as anchors:
        anchor_directory(anchors, capsules_root, final_access=0x80000000)
        try:
            with os.scandir(capsules_root) as entries:
                for entry in entries:
                    observation = _windows_candidate_commit(
                        capsules_root,
                        entry,
                        parse_commit=parse_commit,
                        commit_filename=commit_filename,
                        maximum_bytes=maximum_bytes,
                        label_filename=label_filename,
                        label_maximum_bytes=label_maximum_bytes,
                    )
                    if observation is not None:
                        discovered.append(observation)
        except OSError as exc:
            raise ProfileCustodyRecordError("profile capsule root cannot be safely enumerated") from exc
    return tuple(sorted(discovered, key=lambda observation: str(observation.profile_id)))


def _windows_candidate_commit(
    capsules_root: Path,
    entry: os.DirEntry[str],
    *,
    parse_commit: Callable[[bytes], _CommitIdentity],
    commit_filename: str,
    maximum_bytes: int,
    label_filename: str | None,
    label_maximum_bytes: int | None,
) -> AnchoredCurrentCapsuleCommit | None:
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
        label_path = candidate / "data" / label_filename if label_filename is not None else None
        label_anchored = False
        if label_path is not None:
            try:
                anchor_directory(candidate_anchors, label_path.parent, final_access=0x80000000)
                label_anchored = True
            except ProfileCustodyRecordError:
                label_anchored = False
        marker_path = candidate / commit_filename
        if not lexists(marker_path, trace=None):
            return None
        commit = parse_commit(read_regular_file(marker_path, maximum_bytes=maximum_bytes, trace=None))
        if commit.profile_id != profile_id:
            raise ProfileCustodyRecordError("profile capsule commit UUID does not match its directory")
        label_payload = None
        if label_path is not None and label_anchored and lexists(label_path, trace=None):
            assert label_maximum_bytes is not None
            label_payload = read_regular_file(label_path, maximum_bytes=label_maximum_bytes, trace=None)
        return AnchoredCurrentCapsuleCommit(
            capsule_path=candidate,
            commit=commit,
            label_payload=label_payload,
            label_requested=label_path is not None,
        )


def _canonical_profile_id(candidate_name: str) -> UUID | None:
    """Recognize only a name the custody path builder itself could have written.

    Recognition is expressed as the exact inverse of
    :func:`profile_custody_directory_name` rather than as a second spelling of
    the same canonicality rule.  Two independent spellings can disagree, and
    the disagreement is silent in the worst direction: a capsule the writer
    published under a name this reader rejects is undiscoverable while its
    material sits on disk.
    """
    try:
        profile_id = UUID(candidate_name)
    except ValueError:
        return None
    try:
        canonical = profile_custody_directory_name(profile_id)
    except ValueError:
        return None
    return profile_id if canonical == candidate_name else None


__all__ = [
    "PROFILE_CUSTODY_RETIRED_BUCKET_MEMBER_PATHS",
    "PROFILE_CUSTODY_RETIRED_KEYSTORE_MEMBER_PATHS",
    "AnchoredCurrentCapsuleCommit",
    "anchored_current_capsule_commits",
    "detect_retired_profile_custody_member_paths",
    "refuse_retired_profile_custody_paths",
]
