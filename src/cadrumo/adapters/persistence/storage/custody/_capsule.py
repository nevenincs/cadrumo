"""Immutable current-format capsule marker and one-rename publication seam."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable, Mapping
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast
from uuid import UUID

from .....core import StorageCategory, is_link_like, storage_location
from .....core.paths import effective_storage_root
from ._capsule_data import (
    read_committed_data_file_posix as _read_committed_data_file_posix,
)
from ._capsule_data import (
    read_committed_data_file_windows as _read_committed_data_file_windows,
)
from ._capsule_data import (
    read_password_envelope as _read_password_envelope,
)
from ._capsule_data import (
    read_password_envelope_fd as _read_password_envelope_fd,
)
from ._capsule_data import (
    read_sentinel as _read_sentinel,
)
from ._capsule_data import (
    read_sentinel_fd as _read_sentinel_fd,
)
from ._capsule_data import (
    replace_capsule_file as _replace_capsule_file,
)
from ._capsule_data import (
    replace_data_file as _replace_data_file,
)
from ._capsule_data import (
    validate_committed_data_member as _validate_committed_data_member,
)
from ._capsule_data import (
    validate_data_file_inventory as _validate_data_file_inventory,
)
from ._capsule_data import (
    write_data_files as _write_data_files,
)
from ._capsule_data import (
    write_posix_data_files as _write_posix_data_files,
)
from ._capsule_discovery import (
    AnchoredCurrentCapsuleCommit,
    anchored_current_capsule_commits,
    refuse_retired_profile_custody_paths,
)
from ._capsule_records import (
    PROFILE_CUSTODY_COMMIT_MAX_BYTES,
    PROFILE_CUSTODY_COMMIT_SCHEMA_VERSION,
    PROFILE_CUSTODY_DELETION_FILENAME,
    PROFILE_CUSTODY_LABEL_FILENAME,
    PROFILE_CUSTODY_LABEL_MAX_BYTES,
    PROFILE_CUSTODY_LAYOUT_VERSION,
    ProfileCustodyCapsuleLabel,
    ProfileCustodyCommit,
    ProfileCustodyDeletionMarker,
    ProfileCustodyPasswordMaterial,
    parse_profile_custody_capsule_label,
    parse_profile_custody_commit,
)
from ._capsule_records import (
    parse_profile_custody_deletion_marker as _parse_profile_custody_deletion_marker,
)
from ._filesystem import (
    PROFILE_CUSTODY_COMMIT_FILENAME,
    ProfileCustodyPasswordReadOperation,
)
from ._filesystem import (
    anchor_directory as _anchor_directory,
)
from ._filesystem import (
    ensure_real_directory as _ensure_real_directory,
)
from ._filesystem import (
    fsync_directory as _fsync_directory,
)
from ._filesystem import (
    fsync_windows_published_commit as _fsync_windows_published_commit,
)
from ._filesystem import (
    lexists as _lexists,
)
from ._filesystem import (
    posix_child_exists as _posix_child_exists,
)
from ._filesystem import (
    posix_directory_fd as _posix_directory_fd,
)
from ._filesystem import (
    posix_mkdir_child_directory as _posix_mkdir_child_directory,
)
from ._filesystem import (
    posix_open_child_directory as _posix_open_child_directory,
)
from ._filesystem import (
    read_regular_file as _read_regular_file,
)
from ._filesystem import (
    read_regular_file_fd as _read_regular_file_fd,
)
from ._filesystem import (
    remove_posix_staging_if_same as _remove_posix_staging_if_same,
)
from ._filesystem import (
    remove_posix_tree as _remove_posix_tree,
)
from ._filesystem import (
    remove_windows_unpublished_staging as _remove_windows_unpublished_staging,
)
from ._filesystem import (
    rename_directory_noreplace as _rename_directory_noreplace,
)
from ._filesystem import (
    rename_windows_directory_by_handle as _rename_windows_directory_by_handle,
)
from ._filesystem import (
    renameat2_noreplace as _renameat2_noreplace,
)
from ._filesystem import (
    windows_stage_snapshot as _windows_stage_snapshot,
)
from ._filesystem import (
    write_exclusive_fsynced as _write_exclusive_fsynced,
)
from ._filesystem import (
    write_exclusive_fsynced_fd as _write_exclusive_fsynced_fd,
)
from ._filesystem import (
    write_through_windows_publication_fence as _write_through_windows_publication_fence,
)
from ._inventory import (
    PROFILE_CUSTODY_INVENTORY_MAX_ENTRIES as _INVENTORY_MAX_ENTRIES,
)
from ._inventory import (
    PROFILE_CUSTODY_INVENTORY_MAX_TOTAL_BYTES as _INVENTORY_MAX_TOTAL_BYTES,
)
from ._inventory import (
    ProfileCustodyInventory as _CanonicalProfileCustodyInventory,
)
from ._inventory import (
    ProfileCustodyInventoryEntry as _CanonicalProfileCustodyInventoryEntry,
)
from ._inventory import (
    inventory_profile_custody_capsule as _inventory_profile_custody_capsule,
)
from ._paths import profile_custody_path
from ._records import (
    PROFILE_CUSTODY_ENVELOPE_FILENAME,
    PROFILE_CUSTODY_ENVELOPE_MAX_BYTES,
    ProfileCustodyEnvelope,
    parse_profile_custody_envelope,
)
from ._recovery import (
    PROFILE_CUSTODY_RECOVERY_FILENAME,
    ProfileCustodyRecoveryEnvelope,
)
from ._sentinel import PROFILE_CUSTODY_SENTINEL_FILENAME, write_profile_custody_sentinel
from ._sentinel_contract import ProfileCustodySentinelRecord
from .errors import ProfileCustodyRecordError

if TYPE_CHECKING:
    from .....core.config import Settings


@dataclass(frozen=True, slots=True)
class ProfileCustodyCapsuleSummaryWitness:
    """One coherent, read-only observation of a committed capsule summary.

    Both records have already passed their canonical current-format and digest
    validation.  The constructor additionally binds their identities together,
    so callers cannot accidentally combine a commit observation with another
    capsule's label provenance.
    """

    capsule_path: Path
    commit: ProfileCustodyCommit
    label: ProfileCustodyCapsuleLabel

    def __post_init__(self) -> None:
        if self.commit.profile_id != self.label.profile_id:
            raise ProfileCustodyRecordError("profile capsule summary records name different UUIDs")

    @property
    def profile_id(self) -> UUID:
        """Return the UUID proven independently by both summary records."""
        return self.commit.profile_id


def inventory_committed_profile_custody_capsule(
    profile_id: UUID,
    *,
    settings: Settings | None = None,
    root: Path | None = None,
) -> ProfileCustodyInventory:
    """Return a bounded regular-file inventory without following any capsule link."""
    capsule_path = recognize_current_profile_capsule(profile_id, settings=settings, root=root)
    if capsule_path is None:
        raise ProfileCustodyRecordError("profile capsule is not committed")
    return _inventory_profile_custody_capsule(profile_id, capsule_path)


def write_profile_custody_deletion_marker(
    *,
    profile_id: UUID,
    transaction_id: UUID,
    inventory_digest: str,
    settings: Settings | None = None,
    root: Path | None = None,
) -> ProfileCustodyDeletionMarker:
    """Exclusively bind a prepared local deletion to its committed capsule."""
    capsule = recognize_current_profile_capsule(profile_id, settings=settings, root=root)
    if capsule is None:
        raise ProfileCustodyRecordError("profile capsule is not committed")
    marker = ProfileCustodyDeletionMarker.create(
        profile_id=profile_id,
        transaction_id=transaction_id,
        inventory_digest=inventory_digest,
    )
    marker_path = capsule / PROFILE_CUSTODY_DELETION_FILENAME
    if os.path.lexists(marker_path):
        raise ProfileCustodyRecordError("profile capsule already carries a deletion marker")
    _write_exclusive_fsynced(marker_path, marker.canonical_json_bytes())
    _fsync_directory(capsule)
    return marker


def verify_profile_custody_deletion_tombstone(
    *,
    profile_id: UUID,
    transaction_id: UUID,
    inventory_digest: str,
    settings: Settings | None = None,
    root: Path | None = None,
) -> Path:
    """Return only the exact transaction-owned tombstone proven safe to remove."""
    source = profile_custody_path(
        profile_id,
        StorageCategory.PROFILE_CAPSULE_COMMIT,
        settings=settings,
        root=root,
    ).parent
    tombstone = profile_custody_deletion_path(
        profile_id=profile_id,
        transaction_id=transaction_id,
        settings=settings,
        root=root,
    )
    source_exists = os.path.lexists(source)
    tombstone_exists = os.path.lexists(tombstone)
    if source_exists or not tombstone_exists:
        raise ProfileCustodyRecordError("profile deletion tombstone state is ambiguous")
    if is_link_like(tombstone) or not tombstone.is_dir():
        raise ProfileCustodyRecordError("profile deletion tombstone is unsafe")
    marker_path = tombstone / PROFILE_CUSTODY_DELETION_FILENAME
    marker = _parse_profile_custody_deletion_marker(
        _read_regular_file(marker_path, maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES)
    )
    if (
        marker.profile_id != profile_id
        or marker.transaction_id != transaction_id
        or marker.inventory_digest != inventory_digest
    ):
        raise ProfileCustodyRecordError("profile deletion tombstone marker does not bind this transaction")
    inventory = _inventory_profile_custody_capsule(profile_id, tombstone, ignore_deletion_marker=True)
    if inventory.digest != inventory_digest:
        raise ProfileCustodyRecordError("profile deletion tombstone inventory differs from its prepared transaction")
    return tombstone


def verify_profile_custody_deletion_marker(
    *,
    profile_id: UUID,
    transaction_id: UUID,
    inventory_digest: str,
    settings: Settings | None = None,
    root: Path | None = None,
) -> Path:
    """Verify the prepared deletion marker while the capsule retains its UUID name."""
    capsule = recognize_current_profile_capsule(profile_id, settings=settings, root=root)
    if capsule is None:
        raise ProfileCustodyRecordError("profile capsule is not committed")
    marker = _parse_profile_custody_deletion_marker(
        _read_regular_file(capsule / PROFILE_CUSTODY_DELETION_FILENAME, maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES)
    )
    if (
        marker.profile_id != profile_id
        or marker.transaction_id != transaction_id
        or marker.inventory_digest != inventory_digest
    ):
        raise ProfileCustodyRecordError("profile deletion marker does not bind this transaction")
    inventory = _inventory_profile_custody_capsule(profile_id, capsule, ignore_deletion_marker=True)
    if inventory.digest != inventory_digest:
        raise ProfileCustodyRecordError("profile deletion marker inventory differs from its prepared transaction")
    return capsule


def profile_custody_deletion_path(
    *,
    profile_id: UUID,
    transaction_id: UUID,
    settings: Settings | None = None,
    root: Path | None = None,
) -> Path:
    """Return the only transaction-owned tombstone path for one local deletion."""
    destination = profile_custody_path(
        profile_id,
        StorageCategory.PROFILE_CAPSULE_COMMIT,
        settings=settings,
        root=root,
    ).parent
    return destination.parent / f".{profile_id}.deleting-{transaction_id}"


def _release_bucket_file_handles(profile_id: UUID) -> None:
    """Release this bucket's cached SQLite handles before destroying its directory.

    A capsule directory holds the profile's own database, and an engine cached
    for that bucket keeps the file open. Windows refuses to rename or remove a
    directory whose files are open, so a reset running in a process that has
    touched the profile fails at the rename with an opaque OS error rather than
    completing.

    Called here rather than left to callers because the two functions below ARE
    the destruction path: putting it at the boundary means no caller can forget,
    and there is nothing to forget on the platforms that would have tolerated
    the open handle -- which is exactly what would have kept the defect hidden.

    Disposal is idempotent and bucket-scoped: engines cached for other buckets
    and for explicit database URLs are untouched, and disposing when nothing is
    cached does nothing. It is safe to call on both steps because a handle can
    be re-opened between the rename and the removal.

    The import is deferred to keep this module's import graph free of the SQL
    engine, mirroring the only other disposal owner, ``BucketSession.close``.
    """
    from ..sql import dispose_engines_for_bucket

    dispose_engines_for_bucket(str(profile_id))


def rename_profile_custody_capsule_for_deletion(
    *,
    profile_id: UUID,
    transaction_id: UUID,
    settings: Settings | None = None,
    root: Path | None = None,
) -> Path:
    """Atomically move one committed capsule to its unique deleting tombstone."""
    source = recognize_current_profile_capsule(profile_id, settings=settings, root=root)
    if source is None:
        raise ProfileCustodyRecordError("profile capsule is not committed")
    _release_bucket_file_handles(profile_id)
    destination = profile_custody_deletion_path(
        profile_id=profile_id,
        transaction_id=transaction_id,
        settings=settings,
        root=root,
    )
    if os.name != "nt":
        with _posix_directory_fd(source.parent) as parent_fd:
            _renameat2_noreplace(
                source_fd=parent_fd,
                source_name=source.name,
                destination_fd=parent_fd,
                destination_name=destination.name,
            )
            os.fsync(parent_fd)
        return destination
    with ExitStack() as anchors:
        root_handle = _anchor_directory(anchors, source.parent, final_access=0x80000000)
        source_handle = _anchor_directory(anchors, source, final_access=0x00010000)
        if root_handle is None or source_handle is None:
            raise ProfileCustodyRecordError("profile deletion rename requires Windows identity anchors")
        _rename_windows_directory_by_handle(source_handle, destination, root_handle=root_handle)
        # A deletion tombstone is already a complete committed capsule.  Its
        # durable fence is the existing marker; a no-op MoveFileEx fence is a
        # publication-only operation and fails on some local Windows volumes.
        _fsync_windows_published_commit(destination)
    return destination


def remove_profile_custody_deletion_tombstone(
    *,
    profile_id: UUID,
    transaction_id: UUID,
    settings: Settings | None = None,
    root: Path | None = None,
) -> None:
    """Remove only a matching transaction tombstone without following links."""
    _release_bucket_file_handles(profile_id)
    tombstone = profile_custody_deletion_path(
        profile_id=profile_id,
        transaction_id=transaction_id,
        settings=settings,
        root=root,
    )
    if os.name != "nt":
        with _posix_directory_fd(tombstone.parent) as parent_fd:
            try:
                metadata = os.stat(tombstone.name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                return
            except OSError as exc:
                raise ProfileCustodyRecordError("profile deletion tombstone cannot be inspected") from exc
            if not stat.S_ISDIR(metadata.st_mode):
                raise ProfileCustodyRecordError("profile deletion tombstone is not a real directory")
            _remove_posix_tree(parent_fd, tombstone.name)
            os.fsync(parent_fd)
        return
    with ExitStack() as anchors:
        _anchor_directory(anchors, tombstone.parent, final_access=0x80000000)
        if not os.path.lexists(tombstone):
            return
        tombstone_handle = _anchor_directory(anchors, tombstone, final_access=0x00010000)
        snapshot = _windows_stage_snapshot(tombstone)
        _remove_windows_unpublished_staging(
            tombstone,
            staging_handle=tombstone_handle,
            snapshot=snapshot,
        )


# The inventory owner was split into `_inventory`; retain these exports as the
# current public custody vocabulary and ensure all later staged helpers use it.
PROFILE_CUSTODY_INVENTORY_MAX_ENTRIES = _INVENTORY_MAX_ENTRIES
PROFILE_CUSTODY_INVENTORY_MAX_TOTAL_BYTES = _INVENTORY_MAX_TOTAL_BYTES
PROFILE_CUSTODY_PROFILE_RECORD_MAX_BYTES = 4 * 1024 * 1024
ProfileCustodyInventory = _CanonicalProfileCustodyInventory
ProfileCustodyInventoryEntry = _CanonicalProfileCustodyInventoryEntry


def publish_profile_custody_capsule(
    *,
    profile_id: UUID,
    transaction_id: UUID,
    publication_kind: Literal["enroll", "restore"],
    password_envelope: ProfileCustodyEnvelope,
    sentinel: ProfileCustodySentinelRecord,
    data_files: Mapping[str, bytes],
    recovery_envelope: ProfileCustodyRecoveryEnvelope | None = None,
    settings: Settings | None = None,
    root: Path | None = None,
    published_at: datetime | None = None,
    stage_only: bool = False,
    stage_initializer: Callable[[Path], None] | None = None,
) -> Path:
    """Build a complete sibling staging capsule and optionally publish it with one rename.

    ``stage_only`` is the transaction-owner seam: it leaves the exact durable,
    transaction-named sibling stage in place for journal verification before the
    sole final rename.  It is not a second publication API.
    """
    _validate_publication_identity(
        profile_id=profile_id,
        password_envelope=password_envelope,
        sentinel=sentinel,
        recovery_envelope=recovery_envelope,
    )
    _validate_data_file_inventory(data_files)
    destination = profile_custody_path(
        profile_id, StorageCategory.PROFILE_CAPSULE_COMMIT, settings=settings, root=root
    ).parent
    capsules_root = destination.parent
    _ensure_real_directory(capsules_root)
    if os.name != "nt":
        return _publish_profile_custody_capsule_posix(
            capsules_root=capsules_root,
            destination_name=destination.name,
            profile_id=profile_id,
            transaction_id=transaction_id,
            publication_kind=publication_kind,
            password_envelope=password_envelope,
            sentinel=sentinel,
            data_files=data_files,
            recovery_envelope=recovery_envelope,
            published_at=published_at,
            stage_only=stage_only,
            stage_initializer=stage_initializer,
        )
    staging = profile_custody_staging_path(
        profile_id=profile_id,
        transaction_id=transaction_id,
        settings=settings,
        root=root,
    )
    published = False
    retained_stage = False
    stage_snapshot: dict[str, tuple[int, int, bool]] | None = None
    staging_handle: int | None = None
    with ExitStack() as root_anchors:
        root_handle = _anchor_directory(root_anchors, capsules_root, final_access=0x80000000)
        staging_anchors = ExitStack()
        content_anchors = ExitStack()
        try:
            staging.mkdir(mode=0o700, exist_ok=False)
        except OSError as exc:
            raise ProfileCustodyRecordError("profile capsule staging directory cannot be created") from exc
        try:
            staging_handle = _anchor_directory(staging_anchors, staging, final_access=0x80010000)
            custody_root = staging / "custody"
            data_root = staging / "data"
            custody_root.mkdir(mode=0o700)
            data_root.mkdir(mode=0o700)
            _anchor_directory(content_anchors, custody_root)
            _anchor_directory(content_anchors, data_root)
            _write_exclusive_fsynced(
                custody_root / PROFILE_CUSTODY_ENVELOPE_FILENAME, password_envelope.canonical_json_bytes()
            )
            if recovery_envelope is not None:
                _write_exclusive_fsynced(
                    custody_root / PROFILE_CUSTODY_RECOVERY_FILENAME, recovery_envelope.canonical_json_bytes()
                )
            write_profile_custody_sentinel(data_root / PROFILE_CUSTODY_SENTINEL_FILENAME, sentinel)
            _write_data_files(data_root, data_files)
            if stage_initializer is not None:
                stage_initializer(staging)
            _fsync_directory(custody_root)
            _fsync_directory(data_root)
            commit = ProfileCustodyCommit.create(
                profile_id=profile_id,
                transaction_id=transaction_id,
                publication_kind=publication_kind,
                published_at=published_at,
            )
            _write_exclusive_fsynced(staging / PROFILE_CUSTODY_COMMIT_FILENAME, commit.canonical_json_bytes())
            _fsync_directory(staging)
            stage_snapshot = _windows_stage_snapshot(staging)
            if stage_only:
                retained_stage = True
                return staging
            # Child handles intentionally deny delete while staged.  They must
            # be released before Windows grants DELETE for the exact stage
            # handle's atomic rename, while the stage/root identities remain
            # anchored throughout.
            content_anchors.close()
            _rename_directory_noreplace(
                staging,
                destination,
                root_handle=root_handle,
                staging_handle=staging_handle,
            )
            staging_anchors.close()
            _write_through_windows_publication_fence(destination, root_handle=root_handle)
            published = True
            return destination
        except OSError as exc:
            raise ProfileCustodyRecordError("profile capsule could not be atomically published") from exc
        finally:
            content_anchors.close()
            if not published and not retained_stage and stage_snapshot is not None:
                _remove_windows_unpublished_staging(
                    staging,
                    staging_handle=staging_handle,
                    snapshot=stage_snapshot,
                )
            staging_anchors.close()


def _publish_profile_custody_capsule_posix(
    *,
    capsules_root: Path,
    destination_name: str,
    profile_id: UUID,
    transaction_id: UUID,
    publication_kind: Literal["enroll", "restore"],
    password_envelope: ProfileCustodyEnvelope,
    sentinel: ProfileCustodySentinelRecord,
    data_files: Mapping[str, bytes],
    recovery_envelope: ProfileCustodyRecoveryEnvelope | None,
    published_at: datetime | None,
    stage_only: bool,
    stage_initializer: Callable[[Path], None] | None,
) -> Path:
    """Publish through descriptor-relative POSIX operations only."""
    staging_name = f".{profile_id}.staging-{transaction_id}"
    with _posix_directory_fd(capsules_root) as root_fd:
        try:
            os.mkdir(staging_name, mode=0o700, dir_fd=root_fd)
        except FileExistsError as exc:
            raise ProfileCustodyRecordError("profile capsule staging directory already exists") from exc
        except OSError as exc:
            raise ProfileCustodyRecordError("profile capsule staging directory cannot be created") from exc
        stage_fd = _posix_open_child_directory(root_fd, staging_name)
        stage_identity = os.fstat(stage_fd)
        published = False
        retained_stage = False
        try:
            custody_fd = _posix_mkdir_child_directory(stage_fd, "custody")
            data_fd = _posix_mkdir_child_directory(stage_fd, "data")
            try:
                _write_exclusive_fsynced_fd(
                    custody_fd, PROFILE_CUSTODY_ENVELOPE_FILENAME, password_envelope.canonical_json_bytes()
                )
                if recovery_envelope is not None:
                    _write_exclusive_fsynced_fd(
                        custody_fd,
                        PROFILE_CUSTODY_RECOVERY_FILENAME,
                        recovery_envelope.canonical_json_bytes(),
                    )
                _write_exclusive_fsynced_fd(data_fd, PROFILE_CUSTODY_SENTINEL_FILENAME, sentinel.canonical_json_bytes())
                _write_posix_data_files(data_fd, data_files)
                if stage_initializer is not None:
                    stage_initializer(capsules_root / staging_name)
                os.fsync(custody_fd)
                os.fsync(data_fd)
            finally:
                os.close(custody_fd)
                os.close(data_fd)
            commit = ProfileCustodyCommit.create(
                profile_id=profile_id,
                transaction_id=transaction_id,
                publication_kind=publication_kind,
                published_at=published_at,
            )
            _write_exclusive_fsynced_fd(stage_fd, PROFILE_CUSTODY_COMMIT_FILENAME, commit.canonical_json_bytes())
            os.fsync(stage_fd)
            if stage_only:
                retained_stage = True
                return capsules_root / staging_name
            _renameat2_noreplace(
                source_fd=root_fd,
                source_name=staging_name,
                destination_fd=root_fd,
                destination_name=destination_name,
            )
            os.fsync(root_fd)
            published = True
            return capsules_root / destination_name
        except OSError as exc:
            raise ProfileCustodyRecordError("profile capsule could not be atomically published") from exc
        finally:
            os.close(stage_fd)
            if not published and not retained_stage:
                _remove_posix_staging_if_same(root_fd, staging_name, stage_identity)


def inventory_staged_profile_custody_capsule(
    *,
    profile_id: UUID,
    transaction_id: UUID,
    settings: Settings | None = None,
    root: Path | None = None,
) -> ProfileCustodyInventory:
    """Inventory only the canonical stage owned by a create transaction."""
    stage = profile_custody_staging_path(profile_id=profile_id, transaction_id=transaction_id, settings=settings)
    if root is not None:
        destination = profile_custody_path(profile_id, StorageCategory.PROFILE_CAPSULE_COMMIT, root=root).parent
        stage = destination.parent / stage.name
    if not os.path.lexists(stage) or is_link_like(stage) or not stage.is_dir():
        raise ProfileCustodyRecordError("profile custody transaction stage is absent or unsafe")
    commit = parse_profile_custody_commit(
        _read_regular_file(stage / PROFILE_CUSTODY_COMMIT_FILENAME, maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES)
    )
    if commit.profile_id != profile_id or commit.transaction_id != transaction_id:
        raise ProfileCustodyRecordError("profile custody transaction stage has another transaction identity")
    return _inventory_profile_custody_capsule(profile_id, stage)


def publish_staged_profile_custody_capsule(
    *,
    profile_id: UUID,
    transaction_id: UUID,
    settings: Settings | None = None,
    root: Path | None = None,
) -> Path:
    """Perform the sole no-replace rename for an already verified stage."""
    destination = profile_custody_path(
        profile_id, StorageCategory.PROFILE_CAPSULE_COMMIT, settings=settings, root=root
    ).parent
    stage = destination.parent / f".{profile_id}.staging-{transaction_id}"
    _ = inventory_staged_profile_custody_capsule(
        profile_id=profile_id, transaction_id=transaction_id, settings=settings, root=root
    )
    if os.name != "nt":
        with _posix_directory_fd(destination.parent) as parent_fd:
            _renameat2_noreplace(
                source_fd=parent_fd, source_name=stage.name, destination_fd=parent_fd, destination_name=destination.name
            )
            os.fsync(parent_fd)
        return destination
    with ExitStack() as anchors:
        root_handle = _anchor_directory(anchors, destination.parent, final_access=0x80000000)
        stage_handle = _anchor_directory(anchors, stage, final_access=0x00010000)
        if root_handle is None or stage_handle is None:
            raise ProfileCustodyRecordError("profile custody staged publication requires Windows identity anchors")
        _rename_directory_noreplace(stage, destination, root_handle=root_handle, staging_handle=stage_handle)
        _fsync_windows_published_commit(destination)
    return destination


def recognize_current_profile_capsule(
    profile_id: UUID,
    *,
    settings: Settings | None = None,
    root: Path | None = None,
    _trace: list[ProfileCustodyPasswordReadOperation] | None = None,
) -> Path | None:
    """Recognize an exact UUID capsule through its marker and nothing else."""
    marker_path = profile_custody_path(
        profile_id,
        StorageCategory.PROFILE_CAPSULE_COMMIT,
        settings=settings,
        root=root,
    )
    capsule_path = marker_path.parent
    if not _lexists(capsule_path, trace=_trace):
        return None
    if os.name != "nt":
        with _posix_directory_fd(capsule_path) as capsule_fd:
            if not _posix_child_exists(capsule_fd, marker_path.name, trace=_trace, display_path=marker_path):
                return None
            commit = parse_profile_custody_commit(
                _read_regular_file_fd(
                    capsule_fd,
                    marker_path.name,
                    display_path=marker_path,
                    maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
                    trace=_trace,
                )
            )
        if commit.profile_id != profile_id:
            raise ProfileCustodyRecordError("profile capsule commit UUID does not match its directory")
        return capsule_path
    with ExitStack() as anchors:
        _anchor_directory(anchors, capsule_path)
        if not _lexists(marker_path, trace=_trace):
            return None
        commit = parse_profile_custody_commit(
            _read_regular_file(marker_path, maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES, trace=_trace)
        )
    if commit.profile_id != profile_id:
        raise ProfileCustodyRecordError("profile capsule commit UUID does not match its directory")
    return capsule_path


def list_current_profile_custody_capsule_ids(
    *,
    settings: Settings | None = None,
    root: Path | None = None,
) -> tuple[UUID, ...]:
    """Project only UUIDs from current-marker observations.

    A directory name is merely a candidate: it becomes visible only after the
    exact current-format commit has been opened and bound back to that UUID.
    Staging directories, deletion tombstones, retired buckets, links and
    malformed names therefore never enter the lifecycle surface.  The summary
    inventory below consumes the same observations when label provenance is
    also required.
    """
    return tuple(observation.profile_id for observation in _current_capsule_commits(settings=settings, root=root))


def list_current_profile_custody_capsule_summary_witnesses(
    *,
    settings: Settings | None = None,
    root: Path | None = None,
) -> tuple[ProfileCustodyCapsuleSummaryWitness, ...]:
    """Observe each current capsule's commit and UUID-bound label exactly once.

    Discovery retains the bounded, anchored commit parse it performed instead of
    handing this reader a UUID that would require opening that marker again.
    The remaining read is only the label provenance required for the summary;
    no custody, recovery, session, encrypted-fact, or label-head authority is
    entered here.
    """
    return tuple(
        _summary_witness_from_anchored_commit(observation)
        for observation in _current_capsule_commits(settings=settings, root=root, include_label=True)
    )


def _summary_witness_from_anchored_commit(
    observation: AnchoredCurrentCapsuleCommit,
) -> ProfileCustodyCapsuleSummaryWitness:
    """Build the S22 witness from bytes the discovery anchor already observed."""
    if observation.label_payload is None:
        raise ProfileCustodyRecordError("summary discovery omitted the required label provenance")
    try:
        label = parse_profile_custody_capsule_label(observation.label_payload)
    except (ProfileCustodyRecordError, ValueError, TypeError) as exc:
        raise ProfileCustodyRecordError("profile capsule summary witness is invalid") from exc
    if label.profile_id != observation.profile_id:
        raise ProfileCustodyRecordError("profile capsule label UUID differs from its committed capsule")
    return ProfileCustodyCapsuleSummaryWitness(
        capsule_path=observation.capsule_path,
        commit=cast(ProfileCustodyCommit, observation.commit),
        label=label,
    )


def _current_capsule_commits(
    *,
    settings: Settings | None = None,
    root: Path | None = None,
    include_label: bool = False,
) -> tuple[AnchoredCurrentCapsuleCommit, ...]:
    """Return current observations after the one retired-layout refusal."""
    storage_root = effective_storage_root(root, settings=settings)
    capsules_root = storage_root / storage_location(StorageCategory.BUCKETS).relative_path()
    keystore_root = storage_root / storage_location(StorageCategory.BUCKET_KEYSTORE).relative_path()
    # The refusal precedes the empty-store shortcut deliberately: retired key
    # material lives outside the buckets tree, so a store whose buckets root is
    # absent can still be a retired store, and returning "no profiles" for it
    # would route the operator to enrol beside key material nothing can read.
    refuse_retired_profile_custody_paths(capsules_root, keystore_root=keystore_root)
    if not os.path.lexists(capsules_root):
        return ()
    return anchored_current_capsule_commits(
        capsules_root,
        parse_commit=parse_profile_custody_commit,
        commit_filename=PROFILE_CUSTODY_COMMIT_FILENAME,
        maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
        label_filename=PROFILE_CUSTODY_LABEL_FILENAME if include_label else None,
        label_maximum_bytes=PROFILE_CUSTODY_LABEL_MAX_BYTES if include_label else None,
    )


def profile_custody_staging_path(
    *,
    profile_id: UUID,
    transaction_id: UUID,
    settings: Settings | None = None,
    root: Path | None = None,
) -> Path:
    """Return the one journal-addressable, permanently undiscoverable stage path."""
    destination = profile_custody_path(
        profile_id, StorageCategory.PROFILE_CAPSULE_COMMIT, settings=settings, root=root
    ).parent
    return destination.parent / f".{profile_id}.staging-{transaction_id}"


def load_committed_profile_custody_label_record(
    profile_id: UUID,
    *,
    settings: Settings | None = None,
    root: Path | None = None,
) -> ProfileCustodyCapsuleLabel:
    """Load the provenance-authenticated label bound inside one committed capsule.

    The label is staged with the capsule and becomes visible only through the
    same commit proof as password material.  A malformed or rewritten label is
    never silently replaced with an inferred directory or retired-manifest
    value.
    """
    capsule_path = recognize_current_profile_capsule(profile_id, settings=settings, root=root)
    if capsule_path is None:
        raise ProfileCustodyRecordError("profile capsule is not committed")
    return _load_profile_custody_label_from_verified_capsule(capsule_path, profile_id=profile_id)


def load_committed_profile_custody_summary_witness(
    profile_id: UUID,
    *,
    settings: Settings | None = None,
    root: Path | None = None,
) -> ProfileCustodyCapsuleSummaryWitness:
    """Observe one validated commit and UUID-bound label without custody reads.

    The capsule directory stays identity-anchored while both bounded records are
    read.  This path deliberately never opens the password envelope, sentinel,
    recovery material, label head, session state, or encrypted profile facts.
    """
    marker_path = profile_custody_path(
        profile_id,
        StorageCategory.PROFILE_CAPSULE_COMMIT,
        settings=settings,
        root=root,
    )
    capsule_path = marker_path.parent
    if not _lexists(capsule_path, trace=[]):
        raise ProfileCustodyRecordError("profile capsule is not committed")
    label_path = capsule_path / "data" / PROFILE_CUSTODY_LABEL_FILENAME
    if os.name != "nt":
        with _posix_directory_fd(capsule_path) as capsule_fd:
            if not _posix_child_exists(capsule_fd, marker_path.name, display_path=marker_path):
                raise ProfileCustodyRecordError("profile capsule is not committed")
            commit_payload = _read_regular_file_fd(
                capsule_fd,
                marker_path.name,
                display_path=marker_path,
                maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
                trace=[],
            )
            data_fd = _posix_open_child_directory(capsule_fd, "data")
            try:
                label_payload = _read_regular_file_fd(
                    data_fd,
                    PROFILE_CUSTODY_LABEL_FILENAME,
                    display_path=label_path,
                    maximum_bytes=PROFILE_CUSTODY_LABEL_MAX_BYTES,
                    trace=[],
                )
            finally:
                os.close(data_fd)
    else:
        with ExitStack() as anchors:
            _anchor_directory(anchors, capsule_path)
            _anchor_directory(anchors, capsule_path / "data")
            if not _lexists(marker_path, trace=[]):
                raise ProfileCustodyRecordError("profile capsule is not committed")
            commit_payload = _read_regular_file(
                marker_path,
                maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
                trace=[],
            )
            label_payload = _read_regular_file(
                label_path,
                maximum_bytes=PROFILE_CUSTODY_LABEL_MAX_BYTES,
                trace=[],
            )
    try:
        commit = parse_profile_custody_commit(commit_payload)
        label = parse_profile_custody_capsule_label(label_payload)
    except (ProfileCustodyRecordError, ValueError, TypeError) as exc:
        raise ProfileCustodyRecordError("profile capsule summary witness is invalid") from exc
    if commit.profile_id != profile_id:
        raise ProfileCustodyRecordError("profile capsule commit UUID does not match its directory")
    if label.profile_id != profile_id:
        raise ProfileCustodyRecordError("profile capsule label UUID differs from its committed capsule")
    return ProfileCustodyCapsuleSummaryWitness(capsule_path=capsule_path, commit=commit, label=label)


def load_committed_profile_custody_data_file(
    profile_id: UUID,
    relative_name: str,
    *,
    maximum_bytes: int = PROFILE_CUSTODY_PROFILE_RECORD_MAX_BYTES,
    settings: Settings | None = None,
    root: Path | None = None,
) -> bytes:
    """Read one regular capsule ``data/`` member after current-marker proof."""
    parts = _validate_committed_data_member(relative_name, maximum_bytes=maximum_bytes)
    capsule_path = recognize_current_profile_capsule(profile_id, settings=settings, root=root)
    if capsule_path is None:
        raise ProfileCustodyRecordError("profile capsule is not committed")
    data_path = capsule_path / "data"
    member_path = data_path.joinpath(*parts)
    if os.name != "nt":
        return _read_committed_data_file_posix(
            capsule_path,
            parts,
            member_path=member_path,
            maximum_bytes=maximum_bytes,
        )
    return _read_committed_data_file_windows(
        capsule_path,
        parts,
        member_path=member_path,
        maximum_bytes=maximum_bytes,
    )


def replace_committed_profile_custody_data_file(
    profile_id: UUID,
    relative_name: str,
    payload: bytes,
    *,
    expected_sha256: str,
    settings: Settings | None = None,
    root: Path | None = None,
) -> None:
    """CAS-replace one physical record only after recognizing its capsule.

    This is deliberately not a generic filesystem write API.  The lifecycle
    passes the canonical current-record name, holds the profile transaction
    lock, and supplies the digest of the authenticated record it is replacing.
    """
    capsule_path = recognize_current_profile_capsule(profile_id, settings=settings, root=root)
    if capsule_path is None:
        raise ProfileCustodyRecordError("profile record command requires a committed capsule")
    data_path = capsule_path / "data"
    with ExitStack() as anchors:
        _anchor_directory(anchors, capsule_path)
        _anchor_directory(anchors, data_path)
        _replace_data_file(data_path, relative_name, payload, expected_sha256=expected_sha256)


def replace_committed_profile_custody_envelope(
    profile_id: UUID,
    payload: bytes,
    *,
    expected_sha256: str,
    settings: Settings | None = None,
    root: Path | None = None,
) -> None:
    """CAS-replace a committed capsule's password envelope, preserving its DEK epoch.

    The write a passphrase rotation makes. Rotation re-wraps the SAME data key
    under a key derived from the new password, so exactly one capsule member
    changes: ``custody/envelope.v1.json``. The caller holds the custody
    transaction lock and supplies the digest of the envelope it authenticated.

    **The DEK sentinel is deliberately not touched.** Its associated data binds
    only ``(profile_id, dek_epoch)``, so an envelope that preserves the epoch
    leaves the committed sentinel -- and every outstanding recovery artifact
    minted against that epoch -- valid. Rewriting the sentinel here would
    invalidate an operator's recovery mnemonic for a password change that never
    touched the key it protects.

    That is why the epoch is enforced rather than trusted. A payload carrying a
    different ``dek_epoch`` describes a re-key, not a rotation: it would leave a
    sentinel and recovery artifacts silently unopenable while every surface
    still reported success. It is refused here, at the write boundary, so the
    invariant cannot be lost by a caller that forgets it.

    Args:
        profile_id: The committed capsule's profile UUID.
        payload: Canonical JSON bytes of the re-wrapped envelope.
        expected_sha256: Prefixed digest of the envelope being replaced.
        settings: Optional settings override.
        root: Optional storage-root override.

    Raises:
        ProfileCustodyRecordError: When no committed capsule is recognized, the
            payload is not a valid envelope for this profile, the payload
            changes the DEK epoch, or the compare-and-swap witness is stale.
    """
    capsule_path = recognize_current_profile_capsule(profile_id, settings=settings, root=root)
    if capsule_path is None:
        raise ProfileCustodyRecordError("profile custody rotation requires a committed capsule")
    custody_path = capsule_path / "custody"
    with ExitStack() as anchors:
        _anchor_directory(anchors, capsule_path)
        _anchor_directory(anchors, custody_path)
        committed = _read_password_envelope(custody_path / PROFILE_CUSTODY_ENVELOPE_FILENAME, trace=[])
        try:
            replacement = parse_profile_custody_envelope(payload)
        except (ProfileCustodyRecordError, ValueError, TypeError) as exc:
            raise ProfileCustodyRecordError("profile custody rotation payload is not a valid envelope") from exc
        if replacement.profile_id != profile_id:
            raise ProfileCustodyRecordError("profile custody rotation envelope names a different profile")
        if replacement.dek_epoch != committed.dek_epoch:
            raise ProfileCustodyRecordError(
                "profile custody rotation envelope changes the DEK epoch; a rotation re-wraps the same "
                "data key, and a new epoch would leave the committed sentinel and every recovery "
                "artifact unopenable",
            )
        _replace_capsule_file(
            custody_path,
            PROFILE_CUSTODY_ENVELOPE_FILENAME,
            payload,
            expected_sha256=expected_sha256,
            maximum_bytes=PROFILE_CUSTODY_ENVELOPE_MAX_BYTES,
        )


def load_staged_profile_custody_label_record(
    profile_id: UUID,
    transaction_id: UUID,
    *,
    settings: Settings | None = None,
    root: Path | None = None,
) -> ProfileCustodyCapsuleLabel:
    """Load the provenance-authenticated label from a transaction-owned stage.

    Recovery consumes the same bytes that eventual publication exposes.  The
    inventory proof prevents a journal from binding a label that differs from
    the staged capsule it is about to publish.
    """
    _ = inventory_staged_profile_custody_capsule(
        profile_id=profile_id,
        transaction_id=transaction_id,
        settings=settings,
        root=root,
    )
    stage_path = profile_custody_staging_path(
        profile_id=profile_id,
        transaction_id=transaction_id,
        settings=settings,
        root=root,
    )
    return _load_profile_custody_label_from_verified_capsule(stage_path, profile_id=profile_id)


def _load_profile_custody_label_from_verified_capsule(
    capsule_path: Path,
    *,
    profile_id: UUID,
) -> ProfileCustodyCapsuleLabel:
    """Read the UUID-bound label record after capsule identity verification."""
    label_path = capsule_path / "data" / PROFILE_CUSTODY_LABEL_FILENAME
    if os.name != "nt":
        with _posix_directory_fd(capsule_path) as capsule_fd:
            data_fd = _posix_open_child_directory(capsule_fd, "data")
            try:
                payload = _read_regular_file_fd(
                    data_fd,
                    PROFILE_CUSTODY_LABEL_FILENAME,
                    display_path=label_path,
                    maximum_bytes=PROFILE_CUSTODY_LABEL_MAX_BYTES,
                    trace=[],
                )
            finally:
                os.close(data_fd)
    else:
        with ExitStack() as anchors:
            _anchor_directory(anchors, capsule_path)
            _anchor_directory(anchors, capsule_path / "data")
            payload = _read_regular_file(label_path, maximum_bytes=PROFILE_CUSTODY_LABEL_MAX_BYTES, trace=[])
    try:
        label = parse_profile_custody_capsule_label(payload)
    except (ProfileCustodyRecordError, ValueError, TypeError) as exc:
        raise ProfileCustodyRecordError("profile capsule label is invalid") from exc
    if label.profile_id != profile_id:
        raise ProfileCustodyRecordError("profile capsule label UUID differs from its committed capsule")
    return label


def load_committed_profile_password_material(
    profile_id: UUID,
    *,
    settings: Settings | None = None,
    root: Path | None = None,
) -> ProfileCustodyPasswordMaterial:
    """Read normal-password authority without resolving the separate recovery path."""
    trace: list[ProfileCustodyPasswordReadOperation] = []
    capsule_path = recognize_current_profile_capsule(profile_id, settings=settings, root=root, _trace=trace)
    if capsule_path is None:
        raise ProfileCustodyRecordError("profile capsule is not committed")
    marker_path = capsule_path / PROFILE_CUSTODY_COMMIT_FILENAME
    if os.name != "nt":
        with _posix_directory_fd(capsule_path) as capsule_fd:
            custody_fd = _posix_open_child_directory(capsule_fd, "custody")
            data_fd = _posix_open_child_directory(capsule_fd, "data")
            try:
                commit = parse_profile_custody_commit(
                    _read_regular_file_fd(
                        capsule_fd,
                        marker_path.name,
                        display_path=marker_path,
                        maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES,
                        trace=trace,
                    )
                )
                envelope = _read_password_envelope_fd(
                    custody_fd,
                    display_path=capsule_path / "custody" / PROFILE_CUSTODY_ENVELOPE_FILENAME,
                    trace=trace,
                )
                sentinel = _read_sentinel_fd(
                    data_fd,
                    display_path=capsule_path / "data" / PROFILE_CUSTODY_SENTINEL_FILENAME,
                    trace=trace,
                )
            finally:
                os.close(custody_fd)
                os.close(data_fd)
    else:
        with ExitStack() as anchors:
            _anchor_directory(anchors, capsule_path)
            _anchor_directory(anchors, capsule_path / "custody")
            _anchor_directory(anchors, capsule_path / "data")
            commit = parse_profile_custody_commit(
                _read_regular_file(marker_path, maximum_bytes=PROFILE_CUSTODY_COMMIT_MAX_BYTES, trace=trace)
            )
            envelope = _read_password_envelope(
                capsule_path / "custody" / PROFILE_CUSTODY_ENVELOPE_FILENAME, trace=trace
            )
            sentinel = _read_sentinel(capsule_path / "data" / PROFILE_CUSTODY_SENTINEL_FILENAME, trace=trace)
    if envelope.profile_id != profile_id or sentinel.profile_id != profile_id:
        raise ProfileCustodyRecordError("normal password custody identity does not match its committed capsule")
    if sentinel.dek_epoch != envelope.dek_epoch:
        raise ProfileCustodyRecordError("normal password custody DEK epoch does not match its sentinel")
    return ProfileCustodyPasswordMaterial(
        capsule_path=capsule_path,
        commit=commit,
        envelope=envelope,
        sentinel=sentinel,
        access_trace=tuple(trace),
    )


def _validate_publication_identity(
    *,
    profile_id: UUID,
    password_envelope: ProfileCustodyEnvelope,
    sentinel: ProfileCustodySentinelRecord,
    recovery_envelope: ProfileCustodyRecoveryEnvelope | None,
) -> None:
    if password_envelope.profile_id != profile_id or sentinel.profile_id != profile_id:
        raise ProfileCustodyRecordError("profile capsule custody identity does not match its immutable UUID")
    if sentinel.dek_epoch != password_envelope.dek_epoch:
        raise ProfileCustodyRecordError("profile capsule sentinel DEK epoch does not match password custody")
    if recovery_envelope is not None and (
        recovery_envelope.profile_id != profile_id or recovery_envelope.dek_epoch != password_envelope.dek_epoch
    ):
        raise ProfileCustodyRecordError("recovery identity does not match password custody")


__all__ = [
    "PROFILE_CUSTODY_COMMIT_MAX_BYTES",
    "PROFILE_CUSTODY_COMMIT_SCHEMA_VERSION",
    "PROFILE_CUSTODY_DELETION_FILENAME",
    "PROFILE_CUSTODY_INVENTORY_MAX_ENTRIES",
    "PROFILE_CUSTODY_INVENTORY_MAX_TOTAL_BYTES",
    "PROFILE_CUSTODY_LABEL_FILENAME",
    "PROFILE_CUSTODY_LABEL_MAX_BYTES",
    "PROFILE_CUSTODY_LAYOUT_VERSION",
    "PROFILE_CUSTODY_PROFILE_RECORD_MAX_BYTES",
    "ProfileCustodyCapsuleSummaryWitness",
    "ProfileCustodyCommit",
    "ProfileCustodyDeletionMarker",
    "ProfileCustodyInventory",
    "ProfileCustodyInventoryEntry",
    "ProfileCustodyPasswordMaterial",
    "inventory_committed_profile_custody_capsule",
    "list_current_profile_custody_capsule_ids",
    "list_current_profile_custody_capsule_summary_witnesses",
    "load_committed_profile_custody_data_file",
    "load_committed_profile_custody_label_record",
    "load_committed_profile_custody_summary_witness",
    "load_committed_profile_password_material",
    "load_staged_profile_custody_label_record",
    "parse_profile_custody_commit",
    "profile_custody_deletion_path",
    "profile_custody_staging_path",
    "publish_profile_custody_capsule",
    "recognize_current_profile_capsule",
    "remove_profile_custody_deletion_tombstone",
    "rename_profile_custody_capsule_for_deletion",
    "replace_committed_profile_custody_data_file",
    "verify_profile_custody_deletion_marker",
    "verify_profile_custody_deletion_tombstone",
    "write_profile_custody_deletion_marker",
]
