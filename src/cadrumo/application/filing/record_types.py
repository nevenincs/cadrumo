"""Shared value objects for canonical filing record rendering."""

from __future__ import annotations

from dataclasses import dataclass

from ...core.filing_projection_ref import FilingProjectionRef
from ...domain.calculations.registry.ids import BindingId, RecordId


@dataclass(frozen=True, slots=True)
class RecordRenderRow:
    """One record row's position and the binding ids active on it."""

    row_index: int | None
    active_binding_ids: frozenset[BindingId]


@dataclass(frozen=True, slots=True)
class RenderedRecordOccurrence:
    """One canonical resolver-produced fixed-width record occurrence."""

    record_id: RecordId
    occurrence: int
    payload: bytes


type ProjectionAddress = tuple[RecordId, int, FilingProjectionRef]
