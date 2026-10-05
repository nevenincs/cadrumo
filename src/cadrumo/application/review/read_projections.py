"""Closed captured and public projections for review reads."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.identity.bucket import BucketId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.utc import validate_utc_aware
from ...domain.calculations.registry.ids import LegalRefId
from ..operations.models import OperationTerminalReceipt, require_terminal_receipt_match
from .enums import ReviewSeverity, ReviewState, severity_rank
from .operator import ReviewQueueRow
from .read_contracts import (
    REVIEW_QUEUE_OPERATION_DEFINITION_ID,
    REVIEW_VIEW_OPERATION_DEFINITION_ID,
    ReviewQueueReadRequest,
    ReviewViewReadRequest,
)

_QueueRows = Annotated[tuple["ReviewQueueRowProjection", ...], Field(max_length=4_096)]


class ReviewQueueRowProjection(BaseModel):
    """Closed wire snapshot of every operator-facing review-row fact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    item_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    source_kind: str | None = None
    affected_object_id: str = Field(min_length=1)
    bucket_id: BucketId
    modelo: str | None = None
    period: str | None = None
    severity: ReviewSeverity
    state: ReviewState
    blocking: bool
    reason: str = ""
    current_owner_surface: str = Field(min_length=1)
    canonical_next_command: str = Field(min_length=1)
    since: datetime
    summary: str = Field(min_length=1)
    legal_refs: tuple[LegalRefId, ...] = ()

    @field_validator("since")
    @classmethod
    def _utc_instant(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)


class ReviewQueueReadExecutionResult(BaseModel):
    """Worker-captured queue rows with their exact request provenance."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    request: ReviewQueueReadRequest
    rows: _QueueRows

    @model_validator(mode="after")
    def _scope(self) -> Self:
        _validate_queue_scope(self.profile_id, self.request, self.rows)
        return self


class ReviewQueueReadProjection(BaseModel):
    """Independent public projection of the successful worker capture."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    request: ReviewQueueReadRequest
    rows: _QueueRows

    @model_validator(mode="after")
    def _scope(self) -> Self:
        _validate_queue_scope(self.profile_id, self.request, self.rows)
        return self


class ReviewViewReadExecutionResult(BaseModel):
    """Worker-captured item with its exact lookup provenance."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    request: ReviewViewReadRequest
    row: ReviewQueueRowProjection

    @model_validator(mode="after")
    def _scope(self) -> Self:
        _validate_view_scope(self.profile_id, self.request, self.row)
        return self


class ReviewViewReadProjection(BaseModel):
    """Independent public projection of the successful exact-item read."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    request: ReviewViewReadRequest
    row: ReviewQueueRowProjection

    @model_validator(mode="after")
    def _scope(self) -> Self:
        _validate_view_scope(self.profile_id, self.request, self.row)
        return self


def _validate_queue_scope(
    profile_id: UUID,
    request: ReviewQueueReadRequest,
    rows: tuple[ReviewQueueRowProjection, ...],
) -> None:
    if request.profile_id != profile_id:
        raise ValueError("review queue result profile differs from its request")
    _require_queue_rows_match_scope(profile_id, request, rows)
    _require_unique_queue_items(rows)
    _require_queue_filters_match(request, rows)
    _require_canonical_queue_order(rows)


def _require_queue_rows_match_scope(
    profile_id: UUID,
    request: ReviewQueueReadRequest,
    rows: tuple[ReviewQueueRowProjection, ...],
) -> None:
    bucket_id = str(profile_id)
    if any(row.bucket_id != bucket_id or row.state is not request.state for row in rows):
        raise ValueError("review queue row scope differs from its request")


def _require_unique_queue_items(rows: tuple[ReviewQueueRowProjection, ...]) -> None:
    if len({row.item_id for row in rows}) != len(rows):
        raise ValueError("review queue contains duplicate item identities")


def _require_queue_filters_match(
    request: ReviewQueueReadRequest,
    rows: tuple[ReviewQueueRowProjection, ...],
) -> None:
    accepted_kinds = frozenset(value.strip() for value in request.kinds if value.strip())
    accepted_source_kinds = frozenset(value.strip() for value in request.source_kinds if value.strip())
    if any(not _review_queue_row_matches_filters(row, request, accepted_kinds, accepted_source_kinds) for row in rows):
        raise ValueError("review queue rows do not satisfy their request filters")


def _review_queue_row_matches_filters(
    row: ReviewQueueRowProjection,
    request: ReviewQueueReadRequest,
    accepted_kinds: frozenset[str],
    accepted_source_kinds: frozenset[str],
) -> bool:
    return not (
        (accepted_kinds and row.kind not in accepted_kinds)
        or (accepted_source_kinds and (row.source_kind is None or row.source_kind not in accepted_source_kinds))
        or (request.modelo is not None and row.modelo != request.modelo)
    )


def _require_canonical_queue_order(rows: tuple[ReviewQueueRowProjection, ...]) -> None:
    ordered = tuple(sorted(rows, key=lambda row: (-severity_rank(row.severity), row.since, row.item_id)))
    if ordered != rows:
        raise ValueError("review queue rows are not in canonical order")


def _validate_view_scope(
    profile_id: UUID,
    request: ReviewViewReadRequest,
    row: ReviewQueueRowProjection,
) -> None:
    if request.profile_id != profile_id or row.bucket_id != str(profile_id) or row.item_id != request.item_id:
        raise ValueError("review item result differs from its request")
    if row.state is not ReviewState.ALL:
        raise ValueError("review item result is not an all-state lookup")


def snapshot_review_row(row: ReviewQueueRow) -> ReviewQueueRowProjection:
    """Copy the canonical domain row into its closed wire projection."""
    return ReviewQueueRowProjection.model_validate(row.model_dump(mode="python"), strict=True)


def _check_receipt(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    *,
    expected_type: type[BaseModel],
    definition_id: str,
) -> UUID:
    if type(result) is not expected_type:
        raise ValueError("invalid review read result")
    profile_id = getattr(result, "profile_id", None)
    if not isinstance(profile_id, UUID):
        raise ValueError("invalid review read profile")
    require_terminal_receipt_match(
        receipt,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        message="review read result contradicts its terminal receipt",
    )
    return profile_id


def project_queue_read_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> ReviewQueueReadProjection:
    """Validate a terminal queue receipt before publishing its captured rows."""
    profile_id = _check_receipt(
        result,
        receipt,
        expected_type=ReviewQueueReadExecutionResult,
        definition_id=REVIEW_QUEUE_OPERATION_DEFINITION_ID,
    )
    private = ReviewQueueReadExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)
    if private.profile_id != profile_id:
        raise ValueError("review queue profile changed during projection")
    return ReviewQueueReadProjection(profile_id=profile_id, request=private.request, rows=private.rows)


def project_view_read_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> ReviewViewReadProjection:
    """Validate a terminal item receipt before publishing its captured row."""
    profile_id = _check_receipt(
        result,
        receipt,
        expected_type=ReviewViewReadExecutionResult,
        definition_id=REVIEW_VIEW_OPERATION_DEFINITION_ID,
    )
    private = ReviewViewReadExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)
    if private.profile_id != profile_id:
        raise ValueError("review item profile changed during projection")
    return ReviewViewReadProjection(profile_id=profile_id, request=private.request, row=private.row)


__all__ = [
    "ReviewQueueReadExecutionResult",
    "ReviewQueueReadProjection",
    "ReviewQueueRowProjection",
    "ReviewViewReadExecutionResult",
    "ReviewViewReadProjection",
    "project_queue_read_result",
    "project_view_read_result",
    "snapshot_review_row",
]
