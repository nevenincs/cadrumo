"""Typed ``--json`` payload schemas for ``aeat config storage``.

Each schema is a strict :class:`OutputSchema` describing the inner ``result``
of the shared envelope spine and nothing more: the outer ``schema_version`` /
``command`` / ``status`` / ``notices`` fields belong to
:class:`SchemaEnvelope`, and every non-blocking diagnostic this surface
produces rides the typed notice channel rather than a field of its own.

Paths are rendered as strings because the envelope is a wire contract; the
service returns real :class:`~pathlib.Path` values and the command projects
them here at the boundary.
"""

from __future__ import annotations

from pydantic import Field

from ....application.storage_management import StorageOccupancy, StorageTreeIssueKind
from ....core import (
    FingerprintParticipation,
    StorageCategory,
    StorageGrouping,
    StorageLifecycle,
    StorageNodeKind,
    StorageOverridePolicy,
    StorageScope,
)
from ....core.json_contract import OutputSchema, register_schema


class StorageCategoryPayload(OutputSchema):
    """One declared location with its resolved path and current occupancy.

    ``path`` is null exactly when ``occupancy`` is ``unresolved`` — a
    bucket-scoped member read with no active profile. ``reclaimable`` mirrors
    the guard ``reclaim`` applies, so an operator can see which members that
    verb would accept before invoking it.
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
    path: str | None = None
    bucket_id: str | None = None
    occupancy: StorageOccupancy
    entry_count: int = Field(default=0, ge=0)
    reclaimable: bool


@register_schema("config.storage.list")
class ConfigStorageListResult(OutputSchema):
    """JSON envelope for ``aeat config storage list``.

    The operator's answer to "where is my data": every declared location, its
    resolved path, and whether it currently holds anything.
    """

    storage_root: str = Field(min_length=1)
    active_profile_bucket: str | None = None
    categories: list[StorageCategoryPayload] = []


@register_schema("config.storage.show")
class ConfigStorageShowResult(OutputSchema):
    """JSON envelope for ``aeat config storage show CATEGORY``."""

    storage_root: str = Field(min_length=1)
    active_profile_bucket: str | None = None
    category: StorageCategoryPayload


class StorageTreeIssuePayload(OutputSchema):
    """One disagreement between the declared tree and the tree on disk."""

    kind: StorageTreeIssueKind
    path: str = Field(min_length=1)
    category: StorageCategory | None = None
    detail: str = ""


@register_schema("config.storage.check")
class ConfigStorageCheckResult(OutputSchema):
    """JSON envelope for ``aeat config storage check``.

    ``root_mode_enforced`` is false on a host that does not implement the POSIX
    mode triple, so an empty ``issues`` list there means the permission axis was
    not checked rather than checked and found clean.
    """

    storage_root: str = Field(min_length=1)
    healthy: bool
    root_mode_enforced: bool
    checked_locations: int = Field(ge=0)
    issues: list[StorageTreeIssuePayload] = []


@register_schema("config.storage.init")
class ConfigStorageInitResult(OutputSchema):
    """JSON envelope for ``aeat config storage init``.

    ``created`` lists only what this run brought into existence, so a repeat run
    reports an empty list rather than restating the whole tree.
    """

    storage_root: str = Field(min_length=1)
    created: list[str] = []
    already_present: int = Field(default=0, ge=0)


@register_schema("config.storage.reclaim")
class ConfigStorageReclaimResult(OutputSchema):
    """JSON envelope for ``aeat config storage reclaim CATEGORY``.

    ``retained_entries`` is non-zero when an entry could not be removed — a file
    held open by another process, say. The shortfall is reported rather than
    folded into the removed count, because an operator who asked for space back
    needs to know they did not get all of it.
    """

    category: StorageCategory
    path: str = Field(min_length=1)
    removed_entries: int = Field(ge=0)
    retained_entries: int = Field(default=0, ge=0)


__all__ = [
    "ConfigStorageCheckResult",
    "ConfigStorageInitResult",
    "ConfigStorageListResult",
    "ConfigStorageReclaimResult",
    "ConfigStorageShowResult",
    "StorageCategoryPayload",
    "StorageTreeIssuePayload",
]
