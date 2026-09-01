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
    :func:`~cadrumo.core.storage_materialization.ensure_storage_tree`
        The materialiser ``init`` delegates to rather than re-implementing.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Final

from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.config import load_settings
from ...core.directory_scan import iter_directory, scan_directory
from ...core.link_safety import is_link_like
from ...core.logging import get_logger
from ...core.storage_materialization import STORAGE_ROOT_MODE, ensure_storage_tree
from ...core.storage_taxonomy import (
    StorageArea,
    StorageCategory,
    StorageLifecycle,
    StorageLocation,
    StorageNodeKind,
    StorageScope,
)
from ...core.storage_taxonomy_locations import (
    STORAGE_TAXONOMY,
    bucket_scoped_storage_path,
    storage_location,
    storage_path,
)
from .errors import StorageReclaimRefusedError, StorageReclaimUnconfirmedError
from .models import (
    StorageAreaDisposition,
    StorageAreaInventoryReport,
    StorageAreaInventoryRow,
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


def collect_storage_area_inventory(*, settings: Settings | None = None) -> StorageAreaInventoryReport:
    """Aggregate the internal declaration into the four stable public areas."""
    resolved = settings if settings is not None else load_settings()
    active_bucket = _active_bucket_id()
    internal = tuple(_inventory_row(category, resolved, active_bucket) for category in STORAGE_TAXONOMY)
    rows = tuple(_area_inventory_row(area, internal) for area in StorageArea)
    return StorageAreaInventoryReport(
        storage_root=Path(resolved.cadrumo_local_storage_root),
        rows=rows,
    )


def _storage_tree_root_issues(root: Path) -> list[StorageTreeIssue]:
    """Describe a missing or file-occupied storage root."""
    if not root.exists():
        return [
            StorageTreeIssue(
                kind=StorageTreeIssueKind.MISSING_DIRECTORY,
                path=root,
                detail="the storage root itself does not exist",
            ),
        ]
    if not root.is_dir():
        return [
            StorageTreeIssue(
                kind=StorageTreeIssueKind.FILE_WHERE_DIRECTORY_EXPECTED,
                path=root,
                detail="the storage root is occupied by a file",
            ),
        ]
    return []


def _storage_location_issues(
    location: StorageLocation,
    target: Path,
) -> list[StorageTreeIssue]:
    """Describe filesystem kind drift for one resolved taxonomy member."""
    issues: list[StorageTreeIssue] = []
    expected_directory = target if location.node_kind is StorageNodeKind.DIRECTORY else target.parent
    area = StorageArea(location.grouping.value)
    if not expected_directory.exists():
        issues.append(
            StorageTreeIssue(
                kind=StorageTreeIssueKind.MISSING_DIRECTORY,
                path=expected_directory,
                area=area,
                detail="declared directory has not been materialised",
            ),
        )
    elif not expected_directory.is_dir():
        issues.append(
            StorageTreeIssue(
                kind=StorageTreeIssueKind.FILE_WHERE_DIRECTORY_EXPECTED,
                path=expected_directory,
                area=area,
                detail="a file occupies a path the taxonomy declares a directory",
            ),
        )
    if location.node_kind is StorageNodeKind.FILE and target.is_dir():
        issues.append(
            StorageTreeIssue(
                kind=StorageTreeIssueKind.DIRECTORY_WHERE_FILE_EXPECTED,
                path=target,
                area=area,
                detail="a directory occupies a path the taxonomy declares a file",
            ),
        )
    return issues


def _storage_root_permission_issues(root: Path, *, enforced: bool) -> list[StorageTreeIssue]:
    """Describe root mode drift when the platform enforces it."""
    if not enforced or not root.is_dir():
        return []
    actual = root.stat().st_mode & 0o777
    if actual == _EXPECTED_ROOT_MODE:
        return []
    return [
        StorageTreeIssue(
            kind=StorageTreeIssueKind.ROOT_PERMISSIONS_DRIFTED,
            path=root,
            detail=f"root mode is {actual:04o}, expected {_EXPECTED_ROOT_MODE:04o}",
        ),
    ]


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
    issues = _storage_tree_root_issues(root)
    checked = 0

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
        issues.extend(_storage_location_issues(location, target))

    mode_enforced = _root_mode_is_enforceable()
    issues.extend(_storage_root_permission_issues(root, enforced=mode_enforced))

    return StorageTreeCheckReport(
        storage_root=root,
        healthy=not issues,
        root_mode_enforced=mode_enforced,
        checked_locations=checked,
        issues=tuple(issues),
    )


def materialise_storage_tree(*, settings: Settings | None = None) -> StorageInitReport:
    """Create every declared directory, preserving whatever already exists.

    Delegates to :func:`~cadrumo.core.storage_materialization.ensure_storage_tree` rather than
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


def _reclaim_candidates(
    area: StorageArea,
    settings: Settings,
) -> tuple[tuple[StorageCategory, StorageLocation, Path], ...]:
    """Resolve the taxonomy members eligible for one reclaim area."""
    return tuple(
        (category, location, storage_path(category, settings=settings))
        for category, location in STORAGE_TAXONOMY.items()
        if location.grouping.value == area.value and location.lifecycle in RECLAIMABLE_LIFECYCLES
    )


def _remove_reclaim_targets(targets: Iterable[Path]) -> tuple[int, list[Path]]:
    """Remove entries under preflighted targets, retaining failures."""
    removed = 0
    retained: list[Path] = []
    for target in targets:
        if not target.exists():
            continue
        entries = (target,) if target.is_file() else scan_directory(target)
        for entry in entries:
            try:
                _remove_reclaim_entry(entry)
            except OSError:
                retained.append(entry)
                _LOGGER.debug("reclaim could not remove %s", entry, exc_info=True)
            else:
                removed += 1
    return removed, retained


def reclaim_storage_area(
    area: StorageArea,
    *,
    confirmed: bool = False,
    settings: Settings | None = None,
) -> StorageReclaimReport:
    """Reclaim all safe roots in ``area`` after one complete preflight.

    Selection, lifecycle admission, scope admission, and containment are all
    derived from the taxonomy. No target is touched until every target passes.
    """
    resolved = settings if settings is not None else load_settings()
    if area in {StorageArea.STATE, StorageArea.EXPORTS}:
        row = next(row for row in collect_storage_area_inventory(settings=resolved).rows if row.area is area)
        raise StorageReclaimRefusedError(
            area,
            entry_count=row.entry_count,
            reason="the area contains durable state",
        )

    candidates = _reclaim_candidates(area, resolved)
    _preflight_reclaim_targets(area, candidates, resolved)
    targets = _minimal_paths(path for _, _, path in candidates)
    storage_root = Path(resolved.cadrumo_local_storage_root).resolve(strict=False)
    for target in targets:
        _validate_reclaim_target(area, target, storage_root)
    entry_count = sum(_immediate_entry_count(path) for path in targets)
    if not confirmed:
        raise StorageReclaimUnconfirmedError(area, entry_count=entry_count)

    removed, retained = _remove_reclaim_targets(targets)

    return StorageReclaimReport(
        area=area,
        target_count=len(targets),
        removed_entries=removed,
        retained_entries=len(retained),
        retained_paths=tuple(retained),
    )


def _preflight_reclaim_targets(
    area: StorageArea,
    candidates: tuple[tuple[StorageCategory, StorageLocation, Path], ...],
    settings: Settings,
) -> None:
    """Prove every selected target safe before the caller deletes anything."""
    if not candidates:
        raise StorageReclaimRefusedError(
            area,
            entry_count=0,
            reason="the taxonomy declares no reclaimable targets",
        )

    root_members = tuple(
        (category, location, storage_path(category, settings=settings))
        for category, location in STORAGE_TAXONOMY.items()
        if location.scope is StorageScope.ROOT
    )
    storage_root = Path(settings.cadrumo_local_storage_root).resolve(strict=False)
    for category, location, target in candidates:
        if location.scope is not StorageScope.ROOT:
            raise StorageReclaimRefusedError(
                area,
                entry_count=0,
                reason="a selected target is not root-scoped",
            )
        if not storage_lifecycle_permits_reclaim(location.lifecycle):
            raise StorageReclaimRefusedError(
                area,
                entry_count=0,
                reason="a selected target has a durable lifecycle",
            )
        _validate_reclaim_target(area, target, storage_root)
        for other, other_location, other_path in root_members:
            if other is category or not other_path.is_relative_to(target):
                continue
            if not storage_lifecycle_permits_reclaim(other_location.lifecycle):
                raise StorageReclaimRefusedError(
                    area,
                    entry_count=_immediate_entry_count(target),
                    reason="a selected target contains protected declared data",
                )


def _validate_reclaim_target(area: StorageArea, target: Path, storage_root: Path) -> None:
    """Refuse a declared target whose live filesystem location is redirected.

    ``storage_path`` is memoized because settings construct the same paths many
    times. A target can therefore retain its lexical in-root path after that
    directory is replaced by a symlink or Windows junction. Resolve the live
    target independently at the destructive boundary and refuse link-like
    targets even when they redirect to another location beneath the root.
    """
    if is_link_like(target):
        raise StorageReclaimRefusedError(
            area,
            entry_count=0,
            reason="a selected target is not root-scoped",
        )
    try:
        resolved_target = target.resolve(strict=False)
    except OSError as exc:
        raise StorageReclaimRefusedError(
            area,
            entry_count=0,
            reason="a selected target is not root-scoped",
        ) from exc
    if not resolved_target.is_relative_to(storage_root):
        raise StorageReclaimRefusedError(
            area,
            entry_count=0,
            reason="a selected target is not root-scoped",
        )


def _remove_reclaim_entry(entry: Path) -> None:
    """Remove one selected entry without following a link-like directory."""
    if entry.is_junction():
        entry.rmdir()
    elif entry.is_symlink() or not entry.is_dir():
        entry.unlink()
    else:
        shutil.rmtree(entry)


def _area_inventory_row(
    area: StorageArea,
    rows: tuple[StorageInventoryRow, ...],
) -> StorageAreaInventoryRow:
    """Aggregate internal rows without projecting internal nouns to callers."""
    selected = tuple(row for row in rows if row.grouping.value == area.value)
    paths = _minimal_paths(row.path for row in selected if row.path is not None)
    occupancies = {row.occupancy for row in selected}
    if StorageOccupancy.POPULATED in occupancies:
        occupancy = StorageOccupancy.POPULATED
    elif StorageOccupancy.EMPTY in occupancies:
        occupancy = StorageOccupancy.EMPTY
    elif StorageOccupancy.ABSENT in occupancies:
        occupancy = StorageOccupancy.ABSENT
    else:
        occupancy = StorageOccupancy.UNRESOLVED

    permitted = [row.reclaimable for row in selected]
    if permitted and all(permitted):
        disposition = StorageAreaDisposition.RECLAIMABLE
    elif any(permitted):
        disposition = StorageAreaDisposition.MIXED
    else:
        disposition = StorageAreaDisposition.DURABLE

    return StorageAreaInventoryRow(
        area=area,
        occupancy=occupancy,
        disposition=disposition,
        reclaimable=area in {StorageArea.LOGS, StorageArea.CACHE} and any(permitted),
        resolved_paths=len(paths),
        entry_count=sum(_immediate_entry_count(path) for path in paths),
        footprint_bytes=sum(_path_size(path) for path in paths),
    )


def _minimal_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    """Return unique outermost paths so aggregates and deletes never double count."""
    ordered = sorted(set(paths), key=lambda path: (len(path.parts), str(path)))
    return tuple(
        path for path in ordered if not any(path.is_relative_to(parent) for parent in ordered if parent != path)
    )


def _path_size(path: Path) -> int:
    """Measure bytes beneath ``path`` without following links out of the tree."""
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    try:
        for entry in iter_directory(path, require_root=True):
            total += _path_size(entry)
    except OSError:
        _LOGGER.debug("could not measure %s", path, exc_info=True)
    return total


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
        return sum(1 for _ in iter_directory(path, require_root=True))
    except OSError:
        _LOGGER.debug("could not enumerate %s", path, exc_info=True)
        return 0


def _existing_declared_directories(settings: Settings, root: Path) -> frozenset[Path]:
    """Return the declared directories that currently exist on disk."""
    from ...core.storage_taxonomy_locations import storage_tree_targets

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
    "collect_storage_area_inventory",
    "collect_storage_inventory",
    "inspect_storage_tree",
    "materialise_storage_tree",
    "reclaim_storage_area",
    "storage_lifecycle_permits_reclaim",
]
