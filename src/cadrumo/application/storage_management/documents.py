"""The public documents of the storage verbs: what ``aeat config storage`` prints and what its acts reply.

Each document is a strict :class:`OutputSchema` describing the inner ``result``
of the shared envelope spine and nothing more: the outer ``schema_version`` /
``command`` / ``status`` / ``notices`` fields belong to
:class:`SchemaEnvelope`, and every non-blocking diagnostic this surface
produces rides the typed notice channel rather than a field of its own. The
runtime's storage acts reply with the same members, so a command and an act
print one document.

Paths are rendered as strings because the document is a wire contract; the
service returns real :class:`~pathlib.Path` values and ``from_report`` projects
them here, hiding the tree's internal topology.
"""

from __future__ import annotations

from typing import Self

from pydantic import NonNegativeInt

from ...core.i18n.render import tr
from ...core.json_contract import OutputSchema
from ...core.storage_taxonomy import StorageArea
from ...core.text_bounds import NonEmptyStr
from .models import (
    StorageAreaDisposition,
    StorageAreaInventoryReport,
    StorageAreaInventoryRow,
    StorageCheckIssueKind,
    StorageInitReport,
    StorageOccupancy,
    StorageReclaimReport,
    StorageTreeCheckReport,
    StorageTreeIssue,
)


class StorageAreaPayload(OutputSchema):
    """Aggregate footprint and lifecycle disposition for one public area."""

    area: StorageArea
    occupancy: StorageOccupancy
    disposition: StorageAreaDisposition
    resolved_paths: NonNegativeInt
    entry_count: NonNegativeInt = 0
    footprint_bytes: NonNegativeInt = 0
    reclaimable: bool

    @classmethod
    def from_row(cls, row: StorageAreaInventoryRow) -> Self:
        """Project one aggregate row onto its topology-neutral wire shape."""
        return cls(
            area=row.area,
            occupancy=row.occupancy,
            disposition=row.disposition,
            resolved_paths=row.resolved_paths,
            entry_count=row.entry_count,
            footprint_bytes=row.footprint_bytes,
            reclaimable=row.reclaimable,
        )


class ConfigStorageListResult(OutputSchema):
    """JSON envelope for ``aeat config storage list``.

    The operator's answer to "where is my data": every declared location, its
    resolved path, and whether it currently holds anything.
    """

    storage_root: NonEmptyStr
    areas: list[StorageAreaPayload] = []

    @classmethod
    def from_report(cls, report: StorageAreaInventoryReport) -> Self:
        """Project the whole inventory."""
        return cls(
            storage_root=str(report.storage_root),
            areas=[StorageAreaPayload.from_row(row) for row in report.rows],
        )


class ConfigStorageViewResult(OutputSchema):
    """JSON envelope for ``aeat config storage view AREA``."""

    storage_root: NonEmptyStr
    area: StorageAreaPayload

    @classmethod
    def from_report(cls, report: StorageAreaInventoryReport, area: StorageArea) -> Self:
        """Project the one row of ``area``."""
        return cls(storage_root=str(report.storage_root), area=StorageAreaPayload.from_row(report.row_for(area)))


def _public_issue_detail(kind: StorageCheckIssueKind) -> str:
    """Describe a check failure without revealing internal node topology."""
    if kind is StorageCheckIssueKind.MISSING_PATH:
        return tr("cli.config.storage.check.issue.missing_path")
    if kind is StorageCheckIssueKind.PERMISSIONS_DRIFTED:
        return tr("cli.config.storage.check.issue.permissions_drifted")
    return tr("cli.config.storage.check.issue.path_type_mismatch")


class StorageAreaIssuePayload(OutputSchema):
    """One disagreement between the declared tree and the tree on disk."""

    kind: StorageCheckIssueKind
    path: NonEmptyStr
    area: StorageArea | None = None
    detail: str = ""

    @classmethod
    def from_issue(cls, issue: StorageTreeIssue, *, storage_root: str) -> Self:
        """Describe a failure by its public kind and the root, never by internal node topology."""
        public = issue.kind.public_kind
        return cls(
            kind=public,
            path=storage_root,
            area=issue.area,
            detail=_public_issue_detail(public),
        )


class ConfigStorageCheckResult(OutputSchema):
    """JSON envelope for ``aeat config storage check``.

    ``root_mode_enforced`` is false on a host that does not implement the POSIX
    mode triple, so an empty ``issues`` list there means the permission axis was
    not checked rather than checked and found clean.
    """

    storage_root: NonEmptyStr
    healthy: bool
    root_mode_enforced: bool
    checked_areas: NonNegativeInt
    issues: list[StorageAreaIssuePayload] = []

    @classmethod
    def from_report(cls, report: StorageTreeCheckReport) -> Self:
        """Project the verdict on the materialised tree."""
        storage_root = str(report.storage_root)
        return cls(
            storage_root=storage_root,
            healthy=report.healthy,
            root_mode_enforced=report.root_mode_enforced,
            checked_areas=len(StorageArea),
            issues=[StorageAreaIssuePayload.from_issue(issue, storage_root=storage_root) for issue in report.issues],
        )


class ConfigStorageInitResult(OutputSchema):
    """JSON envelope for ``aeat config storage init``.

    ``created`` lists only what this run brought into existence, so a repeat run
    reports an empty list rather than restating the whole tree.
    """

    storage_root: NonEmptyStr
    created_count: NonNegativeInt = 0
    already_present: NonNegativeInt = 0

    @classmethod
    def from_report(cls, report: StorageInitReport) -> Self:
        """Project the outcome of materialising the tree."""
        return cls(
            storage_root=str(report.storage_root),
            created_count=len(report.created),
            already_present=report.already_present,
        )


class ConfigStorageReclaimResult(OutputSchema):
    """JSON envelope for ``aeat config storage reclaim AREA``.

    ``retained_entries`` is non-zero when an entry could not be removed — a file
    held open by another process, say. The shortfall is reported rather than
    folded into the removed count, because an operator who asked for space back
    needs to know they did not get all of it.
    """

    area: StorageArea
    target_count: NonNegativeInt
    removed_entries: NonNegativeInt
    retained_entries: NonNegativeInt = 0

    @classmethod
    def from_report(cls, report: StorageReclaimReport) -> Self:
        """Project the outcome of one confirmed reclaim."""
        return cls(
            area=report.area,
            target_count=report.target_count,
            removed_entries=report.removed_entries,
            retained_entries=report.retained_entries,
        )


__all__ = [
    "ConfigStorageCheckResult",
    "ConfigStorageInitResult",
    "ConfigStorageListResult",
    "ConfigStorageReclaimResult",
    "ConfigStorageViewResult",
    "StorageAreaIssuePayload",
    "StorageAreaPayload",
]
