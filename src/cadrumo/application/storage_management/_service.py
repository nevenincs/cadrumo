"""Read and reclaim operations over the declared storage tree.

Answers "where is my data", "does the tree on disk match its declaration", and
"what may safely be deleted" from the one typed declaration in
:data:`~cadrumo.core.STORAGE_TAXONOMY`, so no answer here can drift from the
resolver every writer already uses.

Nothing in this module moves data or relocates the root. Reporting where the
tree is and naming the variable that points at it is cheap and reversible;
copying an encrypted store is neither, and a copy that succeeds for the records
while failing for the key material that opens them is unrecoverable.

See Also:
    :func:`~cadrumo.core.storage_path`
        The resolver every row is built from.
    :func:`~cadrumo.core.config.ensure_storage_tree`
        The materialiser ``init`` delegates to rather than re-implementing.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Final

from ...core import (
    STORAGE_TAXONOMY,
    StorageCategory,
    StorageLifecycle,
    StorageNodeKind,
    StorageScope,
    bucket_scoped_storage_path,
    resolve_active_bucket_id,
    storage_location,
    storage_path,
)
from ...core.config import STORAGE_ROOT_MODE, ensure_storage_tree, load_settings
from ...core.logging import get_logger
from ._errors import StorageReclaimRefusedError, StorageReclaimUnconfirmedError
from ._models import (
    StorageInitReport,
    StorageInventoryReport,
    StorageInventoryRow,
    StorageOccupancy,
    StorageReclaimReport,
    StorageTreeCheckReport,
    StorageTreeIssue,
    StorageTreeIssueKind,
)

if TYPE_CHECKING:
    from ...core.config import Settings

_LOGGER = get_logger(__name__)

RECLAIMABLE_LIFECYCLES: Final[frozenset[StorageLifecycle]] = frozenset(
    {
        StorageLifecycle.RETENTION,
        StorageLifecycle.ROTATION,
        StorageLifecycle.TTL,
    },
)
"""Declared lifecycle classes whose contents ``reclaim`` may delete.

The complement is :attr:`~cadrumo.core.StorageLifecycle.UNBOUNDED_BY_DESIGN`,
which is the encrypted substrate, the key material, the audit trail, and the
durable filing outputs. Those are not caches that grew too large; their growth
is the record. Deriving the permitted set from the declared axis rather than
listing categories means a member reclassified in the taxonomy changes what
reclaim will touch at the same moment, with no second list to forget.
"""

_EXPECTED_ROOT_MODE: Final[int] = STORAGE_ROOT_MODE
"""Mode ``ensure_storage_tree`` requests on the root, read from it for the drift check.

Bound to the materialiser's own constant rather than restating the value: a
check defined as matching what was requested must not be able to keep
passing against a mode the materialiser no longer requests.
"""


def storage_lifecycle_permits_reclaim(lifecycle: StorageLifecycle) -> bool:
    """Return whether ``lifecycle`` declares contents a reclaim may delete."""
    return lifecycle in RECLAIMABLE_LIFECYCLES


def collect_storage_inventory(*, settings: Settings | None = None) -> StorageInventoryReport:
    """Return every declared location with its resolved path and occupancy.

    Bucket- and keystore-scoped members resolve against the active profile when
    one is pointed at, and report :attr:`StorageOccupancy.UNRESOLVED` otherwise:
    with no active profile there is no single path those members occupy, and
    reporting them absent would assert a fact nothing looked at.

    Args:
        settings: Settings to resolve against. Defaults to the effective
            settings for the calling context.

    Returns:
        One row per taxonomy member, in declaration order.
    """
    resolved = settings if settings is not None else load_settings()
    active_bucket = _active_bucket_id()
    rows = tuple(_inventory_row(category, resolved, active_bucket) for category in STORAGE_TAXONOMY)
    return StorageInventoryReport(
        storage_root=Path(resolved.cadrumo_local_storage_root),
        active_bucket_id=active_bucket,
        rows=rows,
    )


def inspect_storage_tree(*, settings: Settings | None = None) -> StorageTreeCheckReport:
    """Report where the materialised tree disagrees with its declaration.

    Read-only by contract: it names missing directories, nodes whose kind
    contradicts the declared :class:`~cadrumo.core.StorageNodeKind`, and root
    permission drift, and repairs none of them. ``init`` is the verb that acts.

    Only members the settings actually resolve are checked. A member whose
    opt-in field is unset names a location the operator has not asked for, and
    reporting it missing would turn every unused affordance into a finding.

    Two of these findings are unreachable from the CLI, and the reason is worth
    stating rather than leaving to be rediscovered. The command line materialises
    the declared tree during bootstrap, so by the time a command body runs a
    missing directory has been created and a directory occupied by a file has
    already been refused there, naming the same path this would have named. Both
    findings remain reachable in-process, and the ones the CLI genuinely leaves
    to this function are a directory sitting where a file-valued member's leaf
    belongs -- the materialiser creates that member's parent and deliberately
    not its leaf -- and root permission drift.
    """
    resolved = settings if settings is not None else load_settings()
    root = Path(resolved.cadrumo_local_storage_root)
    issues: list[StorageTreeIssue] = []
    checked = 0

    if not root.exists():
        issues.append(
            StorageTreeIssue(
                kind=StorageTreeIssueKind.MISSING_DIRECTORY,
                path=root,
                detail="the storage root itself does not exist",
            ),
        )
    elif not root.is_dir():
        issues.append(
            StorageTreeIssue(
                kind=StorageTreeIssueKind.FILE_WHERE_DIRECTORY_EXPECTED,
                path=root,
                detail="the storage root is occupied by a file",
            ),
        )

    for category, location in STORAGE_TAXONOMY.items():
        if location.scope is not StorageScope.ROOT or location.settings_field is None:
            continue
        if getattr(resolved, location.settings_field, None) is None:
            continue
        target = storage_path(category, settings=resolved)
        checked += 1
        # A file-valued member declares its own leaf; the tree materialiser
        # creates the PARENT and deliberately not the leaf, so an absent leaf is
        # the normal state of a document nothing has written yet. Only its
        # parent's absence is a gap in the tree.
        expected_directory = target if location.node_kind is StorageNodeKind.DIRECTORY else target.parent
        if not expected_directory.exists():
            issues.append(
                StorageTreeIssue(
                    kind=StorageTreeIssueKind.MISSING_DIRECTORY,
                    path=expected_directory,
                    category=category,
                    detail="declared directory has not been materialised",
                ),
            )
        elif not expected_directory.is_dir():
            issues.append(
                StorageTreeIssue(
                    kind=StorageTreeIssueKind.FILE_WHERE_DIRECTORY_EXPECTED,
                    path=expected_directory,
                    category=category,
                    detail="a file occupies a path the taxonomy declares a directory",
                ),
            )
        if location.node_kind is StorageNodeKind.FILE and target.is_dir():
            issues.append(
                StorageTreeIssue(
                    kind=StorageTreeIssueKind.DIRECTORY_WHERE_FILE_EXPECTED,
                    path=target,
                    category=category,
                    detail="a directory occupies a path the taxonomy declares a file",
                ),
            )

    mode_enforced = _root_mode_is_enforceable()
    if mode_enforced and root.is_dir():
        actual = root.stat().st_mode & 0o777
        if actual != _EXPECTED_ROOT_MODE:
            issues.append(
                StorageTreeIssue(
                    kind=StorageTreeIssueKind.ROOT_PERMISSIONS_DRIFTED,
                    path=root,
                    detail=f"root mode is {actual:04o}, expected {_EXPECTED_ROOT_MODE:04o}",
                ),
            )

    return StorageTreeCheckReport(
        storage_root=root,
        healthy=not issues,
        root_mode_enforced=mode_enforced,
        checked_locations=checked,
        issues=tuple(issues),
    )


def materialise_storage_tree(*, settings: Settings | None = None) -> StorageInitReport:
    """Create every declared directory, preserving whatever already exists.

    Delegates to :func:`~cadrumo.core.config.ensure_storage_tree` rather than
    walking the taxonomy again, so the operator verb and the runtime bootstrap
    cannot materialise different trees. It never removes and recreates a
    directory to reach a clean state: the tree holds the encrypted substrate,
    and "clean" would mean deleting it.
    """
    resolved = settings if settings is not None else load_settings()
    root = Path(resolved.cadrumo_local_storage_root)
    before = _existing_declared_directories(resolved, root)
    ensure_storage_tree(resolved)
    after = _existing_declared_directories(resolved, root)
    created = tuple(sorted(after - before))
    return StorageInitReport(
        storage_root=root,
        created=created,
        already_present=len(before),
    )


def reclaim_storage_category(
    category: StorageCategory,
    *,
    confirmed: bool = False,
    settings: Settings | None = None,
) -> StorageReclaimReport:
    """Delete the regenerable contents of ``category``, keeping the directory.

    The guard is the member's declared
    :class:`~cadrumo.core.StorageLifecycle`. A category declared unbounded by
    design is refused, and the refusal names the resolved path, the number of
    entries it holds, and the lifecycle that forbade the delete.

    The whole subtree beneath the category is removed, not only the parts the
    taxonomy declares. Production code nests locations beneath enrolled
    categories that the declaration does not enumerate, so a reclaim that
    deleted only declared children would silently leave the bulk behind.

    Args:
        category: The member to reclaim. Must be root-scoped and declared
            reclaimable.
        confirmed: Explicit acknowledgement that data will be deleted.
        settings: Settings to resolve against.

    Returns:
        What was removed, and what survived.

    Raises:
        StorageReclaimRefusedError: When the declared lifecycle forbids
            deletion, or the member is not root-scoped.
        StorageReclaimUnconfirmedError: When ``confirmed`` is false.
    """
    resolved = settings if settings is not None else load_settings()
    location = storage_location(category)

    if location.scope is not StorageScope.ROOT:
        # A per-bucket member is reached through its bucket's lifecycle, which
        # owns the ordering between a bucket's database, its blobs, and the
        # keystore that opens them. Reclaiming one of those in isolation would
        # strand the others.
        raise StorageReclaimRefusedError(
            category,
            lifecycle=location.lifecycle,
            path=None,
            entry_count=0,
            reason=f"{location.scope.value} members belong to a profile bucket's own lifecycle",
        )

    target = storage_path(category, settings=resolved)
    entry_count = _immediate_entry_count(target)

    if not storage_lifecycle_permits_reclaim(location.lifecycle):
        raise StorageReclaimRefusedError(
            category,
            lifecycle=location.lifecycle,
            path=target,
            entry_count=entry_count,
            reason=f"its declared lifecycle is {location.lifecycle.value}",
        )
    if not confirmed:
        raise StorageReclaimUnconfirmedError(category, path=target, entry_count=entry_count)

    if not target.exists():
        return StorageReclaimReport(category=category, path=target, removed_entries=0)

    if target.is_file():
        target.unlink()
        return StorageReclaimReport(category=category, path=target, removed_entries=1)

    removed = 0
    retained: list[Path] = []
    for entry in sorted(target.iterdir()):
        try:
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        except OSError:
            # A file held open by another process is a retained entry, not a
            # failed reclaim: the operator asked for space back and got what
            # could be released. The path is kept alongside the count so the
            # boundary can tell an expected retention from a real failure.
            retained.append(entry)
            _LOGGER.debug("reclaim could not remove %s", entry, exc_info=True)
        else:
            removed += 1

    return StorageReclaimReport(
        category=category,
        path=target,
        removed_entries=removed,
        retained_entries=len(retained),
        retained_paths=tuple(retained),
    )


def _inventory_row(
    category: StorageCategory,
    settings: Settings,
    active_bucket: str | None,
) -> StorageInventoryRow:
    """Build one inventory row for ``category``."""
    location = storage_location(category)
    path: Path | None = None
    bucket_id: str | None = None

    if location.scope is StorageScope.ROOT:
        path = storage_path(category, settings=settings)
    elif active_bucket is not None:
        path = bucket_scoped_storage_path(category, active_bucket, settings=settings)
        bucket_id = active_bucket

    occupancy, entry_count = _occupancy(path, location.node_kind)
    return StorageInventoryRow(
        category=category,
        subpath=location.subpath,
        node_kind=location.node_kind,
        scope=location.scope,
        grouping=location.grouping,
        lifecycle=location.lifecycle,
        override_policy=location.override_policy,
        fingerprint_participation=location.fingerprint_participation,
        settings_field=location.settings_field,
        path=path,
        bucket_id=bucket_id,
        occupancy=occupancy,
        entry_count=entry_count,
        reclaimable=location.scope is StorageScope.ROOT and storage_lifecycle_permits_reclaim(location.lifecycle),
    )


def _occupancy(path: Path | None, node_kind: StorageNodeKind) -> tuple[StorageOccupancy, int]:
    """Return what ``path`` holds and how many immediate entries it has.

    Deliberately answers "holds anything" rather than "how many bytes". The
    question the operator asks of an inventory is whether a location is in use;
    a byte total is a measurement of one profile's footprint, which the bucket
    maintenance surface already owns one layer down.
    """
    if path is None:
        return StorageOccupancy.UNRESOLVED, 0
    if not path.exists():
        return StorageOccupancy.ABSENT, 0
    if node_kind is StorageNodeKind.FILE or path.is_file():
        return (StorageOccupancy.POPULATED if path.stat().st_size > 0 else StorageOccupancy.EMPTY), 0
    count = _immediate_entry_count(path)
    return (StorageOccupancy.POPULATED if count else StorageOccupancy.EMPTY), count


def _immediate_entry_count(path: Path) -> int:
    """Return the number of immediate children of ``path``, or 0 when unreadable."""
    if not path.is_dir():
        return 0
    try:
        return sum(1 for _ in path.iterdir())
    except OSError:
        _LOGGER.debug("could not enumerate %s", path, exc_info=True)
        return 0


def _existing_declared_directories(settings: Settings, root: Path) -> frozenset[Path]:
    """Return the declared directories that currently exist on disk."""
    from ...core import storage_tree_targets

    present = {target for target in storage_tree_targets(settings) if target.is_dir()}
    if root.is_dir():
        present.add(root)
    return frozenset(present)


def _active_bucket_id() -> str | None:
    """Return the active profile bucket identifier, or None when none is pointed at."""
    return resolve_active_bucket_id()


def _root_mode_is_enforceable() -> bool:
    """Return whether this host implements the POSIX mode bits the root requests.

    Windows reports a mode that reflects the read-only attribute rather than the
    owner/group/other triple, so comparing it against ``0o700`` would manufacture
    a permission finding on every Windows machine. Where the check cannot mean
    anything, it is declared unenforced instead of silently passing.
    """
    return os.name != "nt"


__all__ = [
    "RECLAIMABLE_LIFECYCLES",
    "collect_storage_inventory",
    "inspect_storage_tree",
    "materialise_storage_tree",
    "reclaim_storage_category",
    "storage_lifecycle_permits_reclaim",
]
