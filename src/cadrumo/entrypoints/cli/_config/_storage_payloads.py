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

from pydantic import NonNegativeInt

from ....application.storage_management._models import StorageAreaDisposition, StorageCheckIssueKind, StorageOccupancy
from ....core.json_contract import OutputSchema
from ....core.storage_taxonomy import StorageArea
from ....core.text_bounds import NonEmptyStr


class StorageAreaPayload(OutputSchema):
    """Aggregate footprint and lifecycle disposition for one public area."""

    area: StorageArea
    occupancy: StorageOccupancy
    disposition: StorageAreaDisposition
    resolved_paths: NonNegativeInt
    entry_count: NonNegativeInt = 0
    footprint_bytes: NonNegativeInt = 0
    reclaimable: bool


class ConfigStorageListResult(OutputSchema):
    """JSON envelope for ``aeat config storage list``.

    The operator's answer to "where is my data": every declared location, its
    resolved path, and whether it currently holds anything.
    """

    storage_root: NonEmptyStr
    areas: list[StorageAreaPayload] = []


class ConfigStorageViewResult(OutputSchema):
    """JSON envelope for ``aeat config storage view AREA``."""

    storage_root: NonEmptyStr
    area: StorageAreaPayload


class StorageAreaIssuePayload(OutputSchema):
    """One disagreement between the declared tree and the tree on disk."""

    kind: StorageCheckIssueKind
    path: NonEmptyStr
    area: StorageArea | None = None
    detail: str = ""


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


class ConfigStorageInitResult(OutputSchema):
    """JSON envelope for ``aeat config storage init``.

    ``created`` lists only what this run brought into existence, so a repeat run
    reports an empty list rather than restating the whole tree.
    """

    storage_root: NonEmptyStr
    created_count: NonNegativeInt = 0
    already_present: NonNegativeInt = 0


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


__all__ = [
    "ConfigStorageCheckResult",
    "ConfigStorageInitResult",
    "ConfigStorageListResult",
    "ConfigStorageReclaimResult",
    "ConfigStorageViewResult",
    "StorageAreaIssuePayload",
    "StorageAreaPayload",
]
