"""Bounded success and refusal result schemas for ledger classification."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.buckets.event import BucketEventId
from ..review.filter import LedgerReviewStatus
from .classify_requests import LedgerClassifyShortText
from .transaction_projection import LedgerTransactionProjection

LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE = "REFUSED_CLI_VALIDATION_BOUNDARY"

_MAX_CLASSIFY_EVENT_IDS = 3

LEDGER_CLASSIFY_MAX_VALIDATION_MESSAGES = 32

LEDGER_CLASSIFY_MAX_RESULT_JSON_BYTES = 262_144

_ValidationMessage = Annotated[str, Field(min_length=1, max_length=2048)]

LedgerClassifyValidationMessages = Annotated[
    tuple[_ValidationMessage, ...], Field(max_length=LEDGER_CLASSIFY_MAX_VALIDATION_MESSAGES)
]

LedgerClassifyValidationKind = Literal["none", "input", "m210_incoming_only", "m210_required_options"]


def _classified_result_is_complete(result: LedgerClassifyOperationResult) -> None:
    if (
        result.transaction is None
        or result.review_status is None
        or result.validation_kind != "none"
        or result.validation_messages
    ):
        raise ValueError("classified result requires its transaction and review status")


def _validation_result_is_closed(result: LedgerClassifyOperationResult) -> None:
    if (
        result.transaction is not None
        or result.deduction_fact_kind is not None
        or result.investment_asset_id is not None
        or result.review_status is not None
        or result.bucket_event_ids
        or result.validation_kind == "none"
        or not result.validation_messages
    ):
        raise ValueError("validation refusal cannot carry transaction output or an effect")


class LedgerClassifyOperationResult(BaseModel):
    """Bounded success projection or field-safe classification refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["classified", "validation_error"]
    profile_id: UUID
    transaction: LedgerTransactionProjection | None = None
    deduction_fact_kind: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    investment_asset_id: LedgerClassifyShortText | None = None
    review_status: LedgerReviewStatus | None = None
    bucket_event_ids: Annotated[tuple[BucketEventId, ...], Field(max_length=_MAX_CLASSIFY_EVENT_IDS)] = ()
    validation_kind: LedgerClassifyValidationKind = "none"
    validation_messages: LedgerClassifyValidationMessages = ()

    @model_validator(mode="after")
    def _complete_selected_outcome(self) -> LedgerClassifyOperationResult:
        if self.outcome == "classified":
            _classified_result_is_complete(self)
        else:
            _validation_result_is_closed(self)
        return self


def _classified_execution_is_complete(result: LedgerClassifyExecutionResult) -> None:
    if (
        result.result is None
        or result.result.outcome != "classified"
        or result.validation_kind != "none"
        or result.validation_messages
    ):
        raise ValueError("classified execution requires its result projection")
    if result.result.profile_id != result.profile_id:
        raise ValueError("classified execution result belongs to another profile")


def _validation_execution_is_closed(result: LedgerClassifyExecutionResult) -> None:
    if result.result is not None or result.validation_kind == "none" or not result.validation_messages:
        raise ValueError("ledger classify validation refusal requires only bounded messages")


class LedgerClassifyExecutionResult(BaseModel):
    """Encrypted worker result for success or bounded input refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["classified", "validation_error"]
    profile_id: UUID
    result: LedgerClassifyOperationResult | None = None
    validation_kind: LedgerClassifyValidationKind = "none"
    validation_messages: LedgerClassifyValidationMessages = ()

    @model_validator(mode="after")
    def _complete_selected_outcome(self) -> LedgerClassifyExecutionResult:
        if self.outcome == "classified":
            _classified_execution_is_complete(self)
        else:
            _validation_execution_is_closed(self)
        return self
