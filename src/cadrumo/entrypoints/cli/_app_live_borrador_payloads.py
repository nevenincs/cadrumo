"""Typed JSON transport schemas for the live borrador service."""

from __future__ import annotations

from typing import Literal

from pydantic import (
    Field,
    field_validator,
    model_validator,
)

from ...core.identity import (
    BucketId,
    SnapshotId,
)
from ...core.json_contract import OutputSchema
from cadrumo.domain.calculations.registry.ids import BindingId
from ._app_live_payloads_support import _canonical_borrador_period, _canonical_borrador_utc_timestamp


class Borrador100SnapshotSummaryPayload(OutputSchema):
    """Summary row for one persisted Modelo 100 borrador snapshot.

    Projects :class:`Borrador100Snapshot` for :class:`Borrador100ListResult`.
    ``state`` is the :class:`SnapshotLifecycleState` value that controls
    whether :class:`Borrador100SnapshotService` exposes the snapshot as active,
    superseded, discarded, or only through an explicit ``--state all`` listing.
    """

    snapshot_id: SnapshotId
    filing_year: int = Field(ge=1900, le=9999)
    period: str
    captured_at: str
    source_url: str = Field(min_length=1, max_length=2048)
    binding_count: int = Field(ge=0)
    state: Literal["active", "superseded", "discarded"]

    @field_validator("period")
    @classmethod
    def _validate_period(cls, value: str) -> str:
        return _canonical_borrador_period(value)

    @field_validator("captured_at")
    @classmethod
    def _validate_captured_at(cls, value: str) -> str:
        return _canonical_borrador_utc_timestamp(value)


class Borrador100ListResult(OutputSchema):
    """Typed listing of bucket-scoped Modelo 100 borrador snapshots.

    ``rows`` contains :class:`Borrador100SnapshotSummaryPayload` projections of
    :class:`Borrador100Snapshot` records returned by
    :class:`Borrador100SnapshotService`.
    """

    bucket_id: BucketId
    count: int = Field(ge=0)
    rows: list[Borrador100SnapshotSummaryPayload]

    @model_validator(mode="after")
    def _require_count_to_match_rows(self) -> Borrador100ListResult:
        if self.count != len(self.rows):
            raise ValueError("count must equal the number of Borrador snapshot rows")
        return self


class Borrador100ViewResult(Borrador100SnapshotSummaryPayload):
    """Typed detail view for one Modelo 100 borrador snapshot.

    ``binding_values`` is a ``{BindingId: string_value}`` mapping keyed by
    :data:`BindingId` from the persisted :class:`Borrador100Snapshot` resolved
    through :class:`Borrador100SnapshotService`. Decimal values are rendered as
    their canonical string form before they reach the envelope so the strict
    :class:`OutputSchema` never encounters a non-JSON-native scalar at
    validation time.
    """

    bucket_id: BucketId
    binding_values: dict[BindingId, str]


class Borrador100LatestResult(OutputSchema):
    """Typed newest-active response for Modelo 100 borrador snapshots.

    ``snapshot_id`` is ``None`` when :class:`Borrador100SnapshotService` finds
    no active :class:`Borrador100Snapshot` for the requested filing year; in
    that case every snapshot-derived field, including the
    :class:`SnapshotLifecycleState` value, is also ``None`` to keep the payload
    shape stable while still identifying the queried ``filing_year``.
    """

    bucket_id: BucketId
    filing_year: int = Field(ge=1900, le=9999)
    snapshot_id: SnapshotId | None
    captured_at: str | None = None
    period: str | None = None
    source_url: str | None = Field(default=None, min_length=1, max_length=2048)
    binding_count: int | None = Field(default=None, ge=0)
    state: Literal["active"] | None = None

    @field_validator("period")
    @classmethod
    def _validate_optional_period(cls, value: str | None) -> str | None:
        return _canonical_borrador_period(value) if value is not None else None

    @field_validator("captured_at")
    @classmethod
    def _validate_optional_captured_at(cls, value: str | None) -> str | None:
        return _canonical_borrador_utc_timestamp(value) if value is not None else None

    @model_validator(mode="after")
    def _enforce_latest_empty_or_active_shape(self) -> Borrador100LatestResult:
        snapshot_fields = (self.captured_at, self.period, self.source_url, self.binding_count, self.state)
        if self.snapshot_id is None:
            if any(value is not None for value in snapshot_fields):
                raise ValueError("empty latest results cannot carry snapshot-derived fields")
            return self
        if any(value is None for value in snapshot_fields):
            raise ValueError("latest results with a snapshot_id require every snapshot-derived field")
        return self


__all__ = [
    "Borrador100LatestResult",
    "Borrador100ListResult",
    "Borrador100SnapshotSummaryPayload",
    "Borrador100ViewResult",
]
