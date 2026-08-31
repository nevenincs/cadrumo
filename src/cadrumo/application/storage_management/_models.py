"""Typed reports the storage-management service returns.

Every model here is a projection of the core storage taxonomy plus what the
filesystem currently holds. The taxonomy axes are carried through verbatim
rather than re-derived, so an operator reading a row sees the same declared
lifecycle and override policy the resolver and the reclaim guard read.

See Also:
    :data:`~cadrumo.core.STORAGE_TAXONOMY`
        The declaration these rows project.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, NonNegativeInt

from ...core.identity import BucketId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.storage_taxonomy import (
    FingerprintParticipation,
    StorageArea,
    StorageCategory,
    StorageGrouping,
    StorageLifecycle,
    StorageNodeKind,
    StorageOverridePolicy,
    StorageScope,
)


class StorageAreaDisposition(StrEnum):
    """Aggregate lifecycle character of an operator-facing storage area."""

    DURABLE = "durable"
    RECLAIMABLE = "reclaimable"
    MIXED = "mixed"


class StorageCheckIssueKind(StrEnum):
    """Public, topology-neutral storage check issue kinds."""

    MISSING_PATH = "missing_path"
    PATH_TYPE_MISMATCH = "path_type_mismatch"
    PERMISSIONS_DRIFTED = "permissions_drifted"


class _StorageReport(BaseModel):
    """Shared strict, frozen base for every report this package returns."""

    model_config = STRICT_FROZEN_CONFIG


class StorageOccupancy(StrEnum):
    """What a declared location currently holds on disk.

    ``UNRESOLVED`` is a distinct outcome from ``ABSENT`` and the distinction is
    load-bearing: a bucket-scoped member with no active profile has no single
    path to look at, which is not the same fact as a path that was looked at and
    found missing. Collapsing the two would report every per-bucket member as
    absent on a machine that simply has no profile logged in.
    """

    UNRESOLVED = "unresolved"
    ABSENT = "absent"
    EMPTY = "empty"
    POPULATED = "populated"


class StorageInventoryRow(_StorageReport):
    """One declared location, its resolved path, and what it holds.

    ``reclaimable`` is derived from :attr:`lifecycle` alone and is reported so
    the operator can see, before asking, which members ``reclaim`` would accept.
    It is a projection of the same predicate the reclaim guard applies, never a
    second opinion about it.
    """

    category: StorageCategory
    subpath: str = Field(min_length=1)
    node_kind: StorageNodeKind
    scope: StorageScope
    grouping: StorageGrouping
    lifecycle: StorageLifecycle
    override_policy: StorageOverridePolicy
    fingerprint_participation: FingerprintParticipation
    settings_field: str | None = None
    path: Path | None = None
    bucket_id: BucketId | None = None
    occupancy: StorageOccupancy
    entry_count: int = Field(default=0, ge=0)
    reclaimable: bool


class StorageInventoryReport(_StorageReport):
    """Every declared location resolved against the current settings."""

    storage_root: Path
    active_bucket_id: BucketId | None = None
    rows: tuple[StorageInventoryRow, ...]


class StorageAreaInventoryRow(_StorageReport):
    """Aggregate disk use and lifecycle disposition for one public area."""

    area: StorageArea
    occupancy: StorageOccupancy
    disposition: StorageAreaDisposition
    reclaimable: bool
    resolved_paths: NonNegativeInt
    entry_count: NonNegativeInt
    footprint_bytes: NonNegativeInt


class StorageAreaInventoryReport(_StorageReport):
    """One aggregate row for each stable operator-facing storage area."""

    storage_root: Path
    rows: tuple[StorageAreaInventoryRow, ...]


class StorageTreeIssueKind(StrEnum):
    """The ways the materialised tree can disagree with its declaration."""

    MISSING_DIRECTORY = "missing_directory"
    FILE_WHERE_DIRECTORY_EXPECTED = "file_where_directory_expected"
    DIRECTORY_WHERE_FILE_EXPECTED = "directory_where_file_expected"
    ROOT_PERMISSIONS_DRIFTED = "root_permissions_drifted"


class StorageTreeIssue(_StorageReport):
    """One disagreement between the declared tree and the tree on disk."""

    kind: StorageTreeIssueKind
    path: Path
    area: StorageArea | None = None
    detail: str = ""


class StorageTreeCheckReport(_StorageReport):
    """Read-only verdict on the materialised tree.

    ``root_mode_enforced`` records whether the host implements POSIX mode bits
    at all. A permission finding is only meaningful where it can be enforced, so
    the flag travels with the verdict instead of a silent absence of findings
    standing in for "checked and clean" on a platform that never checks.
    """

    storage_root: Path
    healthy: bool
    root_mode_enforced: bool
    checked_locations: NonNegativeInt
    issues: tuple[StorageTreeIssue, ...] = ()


class StorageInitReport(_StorageReport):
    """Outcome of materialising the declared tree.

    ``created`` names only the directories this call brought into existence, so
    a repeat run reports an empty tuple rather than restating the whole tree.
    """

    storage_root: Path
    created: tuple[Path, ...] = ()
    already_present: int = Field(default=0, ge=0)


class StorageReclaimReport(_StorageReport):
    """Outcome of reclaiming every regenerable target in one public area."""

    area: StorageArea
    target_count: NonNegativeInt
    removed_entries: NonNegativeInt
    retained_entries: int = Field(default=0, ge=0)

    retained_paths: tuple[Path, ...] = ()
    """The entries that survived, so a caller can say why rather than only how many.

    Deliberately not on the wire payload. A count is what the operator needs in
    the result; the paths exist so the boundary can identify a benign,
    every-time retention -- an open log file -- and word its warning
    accordingly, instead of raising the same alarm for a locked file and a
    failed delete.
    """


__all__ = [
    "StorageAreaDisposition",
    "StorageAreaInventoryReport",
    "StorageAreaInventoryRow",
    "StorageCheckIssueKind",
    "StorageInitReport",
    "StorageInventoryReport",
    "StorageInventoryRow",
    "StorageOccupancy",
    "StorageReclaimReport",
    "StorageTreeCheckReport",
    "StorageTreeIssue",
    "StorageTreeIssueKind",
]
