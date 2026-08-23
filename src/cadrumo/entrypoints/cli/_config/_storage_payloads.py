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

from ....application.storage_management import (
    StorageAreaDisposition,
    StorageCheckIssueKind,
    StorageOccupancy,
)
from ....core import StorageArea
from ....core.json_contract import OutputSchema


class StorageAreaPayload(OutputSchema):
    """Aggregate footprint and lifecycle disposition for one public area."""

    area: StorageArea
    occupancy: StorageOccupancy
    disposition: StorageAreaDisposition
    resolved_paths: int = Field(ge=0)
    entry_count: int = Field(default=0, ge=0)
    footprint_bytes: int = Field(default=0, ge=0)
    reclaimable: bool


class ConfigStorageListResult(OutputSchema):
    """JSON envelope for ``aeat config storage list``.

    The operator's answer to "where is my data": every declared location, its
    resolved path, and whether it currently holds anything.
    """

    storage_root: str = Field(min_length=1)
    areas: list[StorageAreaPayload] = []


class ConfigStorageShowResult(OutputSchema):
    """JSON envelope for ``aeat config storage show AREA``."""

    storage_root: str = Field(min_length=1)
    area: StorageAreaPayload


class StorageAreaIssuePayload(OutputSchema):
    """One disagreement between the declared tree and the tree on disk."""

    kind: StorageCheckIssueKind
    path: str = Field(min_length=1)
    area: StorageArea | None = None
    detail: str = ""


class ConfigStorageCheckResult(OutputSchema):
    """JSON envelope for ``aeat config storage check``.

    ``root_mode_enforced`` is false on a host that does not implement the POSIX
    mode triple, so an empty ``issues`` list there means the permission axis was
    not checked rather than checked and found clean.
    """

    storage_root: str = Field(min_length=1)
    healthy: bool
    root_mode_enforced: bool
    checked_areas: int = Field(ge=0)
    issues: list[StorageAreaIssuePayload] = []


class ConfigStorageInitResult(OutputSchema):
    """JSON envelope for ``aeat config storage init``.

    ``created`` lists only what this run brought into existence, so a repeat run
    reports an empty list rather than restating the whole tree.
    """

    storage_root: str = Field(min_length=1)
    created_count: int = Field(default=0, ge=0)
    already_present: int = Field(default=0, ge=0)


class ConfigStorageReclaimResult(OutputSchema):
    """JSON envelope for ``aeat config storage reclaim AREA``.

    ``retained_entries`` is non-zero when an entry could not be removed — a file
    held open by another process, say. The shortfall is reported rather than
    folded into the removed count, because an operator who asked for space back
    needs to know they did not get all of it.
    """

    area: StorageArea
    target_count: int = Field(ge=0)
    removed_entries: int = Field(ge=0)
    retained_entries: int = Field(default=0, ge=0)


__all__ = [
    "ConfigStorageCheckResult",
    "ConfigStorageInitResult",
    "ConfigStorageListResult",
    "ConfigStorageReclaimResult",
    "ConfigStorageShowResult",
    "StorageAreaIssuePayload",
    "StorageAreaPayload",
]
