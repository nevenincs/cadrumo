"""Public request and projection contracts for Modelo 100 borrador operations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from ...core.casilla_id import CasillaId
from ...core.filing_year import FilingYear
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import SnapshotId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.ids import BindingId
from ..operations.models import CredentialFreeOperationRequest
from ..operations.public_period import PublicPeriod
from ..operations.public_scalar import PublicDecimal, PublicNamedScalar
from .borrador_100 import (
    Borrador100CaptureOutcome,
    Borrador100RefusedSnapshot,
    Borrador100Snapshot,
    Borrador100SnapshotRefusalReason,
    BorradorSourceUrl,
)
from .borrador_100_operation_ports import Borrador100ArtefactKind
from .snapshot_base import SnapshotLifecycleState, SnapshotStateFilter

type Borrador100ReadKind = Literal["list", "view", "latest"]
_BINDING_ID: TypeAdapter[BindingId] = TypeAdapter(BindingId)


class Borrador100ReadRequest(CredentialFreeOperationRequest):
    """Canonical list, unique-prefix view and latest-year selectors."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: Borrador100ReadKind
    state: SnapshotStateFilter = SnapshotStateFilter.ACTIVE
    snapshot_id: Annotated[str, Field(min_length=1)] | None = None
    filing_year: FilingYear | None = None

    @model_validator(mode="after")
    def _selector(self) -> Self:
        if (self.snapshot_id is not None) != (self.kind == "view"):
            raise ValueError("snapshot id belongs only to a view request")
        if (self.filing_year is not None) != (self.kind == "latest"):
            raise ValueError("filing year belongs only to a latest request")
        if self.kind != "list" and self.state is not SnapshotStateFilter.ACTIVE:
            raise ValueError("state filter belongs only to list requests")
        return self


class Borrador100ImportRequest(BaseModel):
    """Protected local source reference; the worker captures its bytes once."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    source_path: Path
    filing_year: FilingYear
    period: PublicPeriod

    @model_validator(mode="after")
    def _coordinate(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("borrador import period differs from filing year")
        return self


class Borrador100QuerySummary(BaseModel):
    """Reviewed metadata without source URLs or printed evidence strings."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    snapshot_id: SnapshotId
    filing_year: FilingYear
    period: PublicPeriod
    captured_at: datetime
    binding_count: Annotated[int, Field(ge=0)]
    state: SnapshotLifecycleState

    @model_validator(mode="after")
    def _coordinate(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("borrador summary period differs from filing year")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("borrador capture time requires an explicit timezone")
        return self


class Borrador100SnapshotSummary(Borrador100QuerySummary):
    """Complete existing human summary, including capture provenance."""

    source_url: BorradorSourceUrl


class Borrador100RefusedSnapshotSummary(BaseModel):
    """One stored snapshot a read refused: its identity, coordinate and reason, never its values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    snapshot_id: SnapshotId
    filing_year: FilingYear
    period: PublicPeriod
    captured_at: datetime
    state: SnapshotLifecycleState
    reason: Borrador100SnapshotRefusalReason

    @model_validator(mode="after")
    def _coordinate(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("refused borrador period differs from filing year")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("borrador capture time requires an explicit timezone")
        return self


def _validate_bindings(values: tuple[PublicNamedScalar, ...], *, count: int) -> None:
    keys = tuple(row.key for row in values)
    if keys != tuple(sorted(set(keys))) or len(values) != count:
        raise ValueError("borrador bindings must be sorted, unique and complete")
    for row in values:
        _BINDING_ID.validate_python(row.key, strict=True)
        if not isinstance(row.value, (str, PublicDecimal)):
            raise ValueError("borrador bindings preserve only decimal or text values")


def _binding_map(values: tuple[PublicNamedScalar, ...]) -> dict[str, Decimal | str]:
    result: dict[str, Decimal | str] = {}
    for row in values:
        if isinstance(row.value, PublicDecimal):
            result[row.key] = Decimal(row.value.decimal)
        elif isinstance(row.value, str):
            result[row.key] = row.value
        else:
            raise ValueError("invalid borrador binding scalar")
    return result


class Borrador100SnapshotDetail(Borrador100SnapshotSummary):
    """Existing full human view with lossless immutable binding entries."""

    binding_values: tuple[PublicNamedScalar, ...]

    @model_validator(mode="after")
    def _bindings(self) -> Self:
        _validate_bindings(self.binding_values, count=self.binding_count)
        return self

    def binding_map(self) -> dict[str, Decimal | str]:
        """Restore canonical scalar values for existing human presenters."""
        return _binding_map(self.binding_values)


class Borrador100QueryDetail(Borrador100QuerySummary):
    """Authorized binding facts without raw source provenance."""

    binding_values: tuple[PublicNamedScalar, ...]

    @model_validator(mode="after")
    def _bindings(self) -> Self:
        _validate_bindings(self.binding_values, count=self.binding_count)
        return self

    def binding_map(self) -> dict[str, Decimal | str]:
        """Restore the canonical tax/profile binding values."""
        return _binding_map(self.binding_values)


def _validate_read_shape(
    kind: Borrador100ReadKind,
    rows: tuple[Borrador100QuerySummary, ...],
    snapshot: Borrador100QuerySummary | None,
    filing_year: int | None,
    refused: tuple[Borrador100RefusedSnapshotSummary, ...],
) -> None:
    _validate_refused_shape(kind, rows, refused, filing_year)
    if kind == "list":
        _require_list_shape(snapshot, filing_year)
    elif _has_incompatible_rows_or_view_selectors(kind, rows, snapshot, filing_year):
        raise ValueError("view/latest result has incompatible rows or selectors")
    elif _latest_result_disagrees(snapshot, filing_year, kind):
        raise ValueError("latest result differs from its active-year selector")


def _validate_refused_shape(
    kind: Borrador100ReadKind,
    rows: tuple[Borrador100QuerySummary, ...],
    refused: tuple[Borrador100RefusedSnapshotSummary, ...],
    filing_year: int | None,
) -> None:
    refused_ids = tuple(item.snapshot_id for item in refused)
    if refused_ids != tuple(sorted(set(refused_ids))):
        raise ValueError("refused borrador snapshots must be sorted and unique")
    if set(refused_ids) & {row.snapshot_id for row in rows}:
        raise ValueError("a borrador snapshot cannot be both listed and refused")
    _validate_refused_for_kind(kind, refused, filing_year)


def _validate_refused_for_kind(
    kind: Borrador100ReadKind,
    refused: tuple[Borrador100RefusedSnapshotSummary, ...],
    filing_year: int | None,
) -> None:
    if kind == "view" and refused:
        raise ValueError("a view refuses its snapshot rather than listing it")
    if kind == "latest" and any(
        item.filing_year != filing_year or item.state is not SnapshotLifecycleState.ACTIVE for item in refused
    ):
        raise ValueError("latest refused snapshots differ from the active-year selector")


def _require_list_shape(snapshot: Borrador100QuerySummary | None, filing_year: int | None) -> None:
    if snapshot is not None or filing_year is not None:
        raise ValueError("list result has incompatible snapshot selectors")


def _has_incompatible_rows_or_view_selectors(
    kind: Borrador100ReadKind,
    rows: tuple[Borrador100QuerySummary, ...],
    snapshot: Borrador100QuerySummary | None,
    filing_year: int | None,
) -> bool:
    return bool(rows) or (kind == "view" and (snapshot is None or filing_year is not None))


def _latest_result_disagrees(
    snapshot: Borrador100QuerySummary | None,
    filing_year: int | None,
    kind: Borrador100ReadKind,
) -> bool:
    return kind == "latest" and (
        filing_year is None
        or (
            snapshot is not None
            and (snapshot.filing_year != filing_year or snapshot.state is not SnapshotLifecycleState.ACTIVE)
        )
    )


class Borrador100ReadProjection(BaseModel):
    """Full human read contract; absent latest snapshot is explicitly retained.

    ``refused_snapshots`` lists each selected stored snapshot the pinned
    authority refuses, so a refused snapshot never reads as an absent one.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: Borrador100ReadKind
    rows: tuple[Borrador100SnapshotSummary, ...] = ()
    snapshot: Borrador100SnapshotDetail | None = None
    filing_year: FilingYear | None = None
    refused_snapshots: tuple[Borrador100RefusedSnapshotSummary, ...] = ()

    @model_validator(mode="after")
    def _shape(self) -> Self:
        _validate_read_shape(self.kind, self.rows, self.snapshot, self.filing_year, self.refused_snapshots)
        return self


class Borrador100QueryProjection(BaseModel):
    """external client-safe result schema with no provenance/document prose fields."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: Borrador100ReadKind
    rows: tuple[Borrador100QuerySummary, ...] = ()
    snapshot: Borrador100QueryDetail | None = None
    filing_year: FilingYear | None = None
    refused_snapshots: tuple[Borrador100RefusedSnapshotSummary, ...] = ()

    @model_validator(mode="after")
    def _shape(self) -> Self:
        _validate_read_shape(self.kind, self.rows, self.snapshot, self.filing_year, self.refused_snapshots)
        return self


class Borrador100ImportProjection(BaseModel):
    """Complete human import facts and canonical parser warnings.

    ``unowned_casillas`` lists printed casillas that no borrador-admitted binding
    of the pinned revision owns; their values were read but not stored.
    ``outcome`` says whether the document was stored or resolved to a snapshot
    already stored for it, including a superseded or discarded one.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    snapshot: Borrador100SnapshotSummary
    extraction_profile_id: str
    extraction_coverage: PublicDecimal
    artefact_kind: Borrador100ArtefactKind
    source_pdf_sha256: ContentDigest
    blank_casillas: tuple[CasillaId, ...]
    unowned_casillas: tuple[CasillaId, ...] = ()
    warnings: tuple[str, ...]
    outcome: Borrador100CaptureOutcome

    @model_validator(mode="after")
    def _source_receipt(self) -> Self:
        if self.snapshot.source_url != "file-import:sha256:" + self.source_pdf_sha256:
            raise ValueError("borrador capture differs from its source digest")
        if self.blank_casillas != tuple(sorted(set(self.blank_casillas))):
            raise ValueError("blank casillas must be sorted and unique")
        if self.unowned_casillas != tuple(sorted(set(self.unowned_casillas))):
            raise ValueError("unowned casillas must be sorted and unique")
        if set(self.unowned_casillas) & set(self.blank_casillas):
            raise ValueError("a casilla cannot be both blank and unowned")
        if not Decimal("0") <= Decimal(self.extraction_coverage.decimal) <= Decimal("1"):
            raise ValueError("borrador coverage must be a unit fraction")
        if _OUTCOME_STATES[self.outcome] is not self.snapshot.state:
            raise ValueError("borrador import outcome differs from the snapshot state")
        return self


_OUTCOME_STATES: dict[Borrador100CaptureOutcome, SnapshotLifecycleState] = {
    Borrador100CaptureOutcome.CAPTURED: SnapshotLifecycleState.ACTIVE,
    Borrador100CaptureOutcome.CAPTURED_SUPERSEDED: SnapshotLifecycleState.SUPERSEDED,
    Borrador100CaptureOutcome.ALREADY_ACTIVE: SnapshotLifecycleState.ACTIVE,
    Borrador100CaptureOutcome.RESOLVED_SUPERSEDED: SnapshotLifecycleState.SUPERSEDED,
    Borrador100CaptureOutcome.RESOLVED_DISCARDED: SnapshotLifecycleState.DISCARDED,
}


class Borrador100ReadExecutionResult(BaseModel):
    """Encrypted full human read retention."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: Borrador100ReadProjection


class Borrador100QueryExecutionResult(BaseModel):
    """Encrypted query retention already excludes source evidence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: Borrador100QueryProjection


class Borrador100ImportExecutionResult(BaseModel):
    """Encrypted import summary and authorized human-only warnings."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: Borrador100ImportProjection


def summarize_borrador_100(snapshot: Borrador100Snapshot) -> Borrador100QuerySummary:
    """Build reviewed metadata without source provenance or printed evidence."""
    return Borrador100QuerySummary(
        snapshot_id=snapshot.snapshot_id,
        filing_year=snapshot.filing_year,
        period=PublicPeriod.from_period(snapshot.period),
        captured_at=snapshot.captured_at,
        binding_count=len(snapshot.binding_values),
        state=snapshot.state,
    )


def summarize_refused_borrador_100_snapshots(
    refused: tuple[Borrador100RefusedSnapshot, ...],
) -> tuple[Borrador100RefusedSnapshotSummary, ...]:
    """Name each refused snapshot and its reason, in snapshot-id order, without any stored value."""
    return tuple(
        sorted(
            (
                Borrador100RefusedSnapshotSummary(
                    snapshot_id=item.snapshot.snapshot_id,
                    filing_year=item.snapshot.filing_year,
                    period=PublicPeriod.from_period(item.snapshot.period),
                    captured_at=item.snapshot.captured_at,
                    state=item.snapshot.state,
                    reason=item.reason,
                )
                for item in refused
            ),
            key=lambda summary: summary.snapshot_id,
        )
    )


def summarize_borrador_100_for_human(snapshot: Borrador100Snapshot) -> Borrador100SnapshotSummary:
    """Include the source provenance required by the existing human view."""
    return Borrador100SnapshotSummary(**summarize_borrador_100(snapshot).model_dump(), source_url=snapshot.source_url)


__all__ = [
    "Borrador100ImportExecutionResult",
    "Borrador100ImportProjection",
    "Borrador100ImportRequest",
    "Borrador100QueryDetail",
    "Borrador100QueryExecutionResult",
    "Borrador100QueryProjection",
    "Borrador100QuerySummary",
    "Borrador100ReadExecutionResult",
    "Borrador100ReadKind",
    "Borrador100ReadProjection",
    "Borrador100ReadRequest",
    "Borrador100RefusedSnapshotSummary",
    "Borrador100SnapshotDetail",
    "Borrador100SnapshotSummary",
    "summarize_borrador_100",
    "summarize_borrador_100_for_human",
    "summarize_refused_borrador_100_snapshots",
]
