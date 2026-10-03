"""Canonical private contracts for the existing ledger LLM review workflow."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import profile_operation_subject
from ...domain.transactions.errors import TransactionValidationError
from ..operations.interactions import OperationResponseIntentValue
from ..operations.models import OperationIdentity
from .actions_common import display_decimal
from .id_resolution import normalise_transaction_id_prefix
from .llm_classification_ports import (
    LLMClassificationSuggestion,
    LLMSaturatedSuggestion,
    LLMSplitSuggestion,
)
from .llm_review_workflow import LlmReviewInvocationOrigin

LEDGER_CLASSIFY_REVIEW_DEFINITION_ID = "ledger.classify.review"
LEDGER_SPLIT_REVIEW_DEFINITION_ID = "ledger.split.review"
LEDGER_LLM_REVIEW_DEFINITION_IDS = frozenset({LEDGER_CLASSIFY_REVIEW_DEFINITION_ID, LEDGER_SPLIT_REVIEW_DEFINITION_ID})
LedgerLlmShortText = Annotated[str, Field(max_length=256)]
LedgerLlmLongText = Annotated[str, Field(max_length=8192)]
LedgerLlmDecimalText = Annotated[str, Field(min_length=1, max_length=128)]
LedgerLlmSuggestion = LLMSaturatedSuggestion | LLMClassificationSuggestion | LLMSplitSuggestion
_MAX_PROJECTION_BYTES = 262_144


class LedgerLlmReviewRequest(BaseModel):
    """Immutable profile and explicit options for one existing suggestion service."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: Annotated[str, Field(min_length=1, max_length=96)]
    mode: Literal["classification", "saturated", "auto_split", "split"]
    origin: LlmReviewInvocationOrigin
    business_pct: LedgerLlmDecimalText | None = None
    actor: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    read_evidence: bool = False
    vision_model: LedgerLlmShortText | None = None
    reason: LedgerLlmLongText = ""
    preview: bool = False

    @field_validator("transaction_id")
    @classmethod
    def _canonical_transaction_prefix(cls, value: str) -> str:
        return normalise_transaction_id_prefix(value)

    @field_validator("business_pct")
    @classmethod
    def _canonical_percentage(cls, value: str | None) -> str | None:
        if value is not None:
            parsed = try_parse_canonical_decimal(value, signed=False)
            if parsed is None or display_decimal(parsed) != value or not Decimal("0") <= parsed <= Decimal("1"):
                raise ValueError("business percentage must use canonical decimal text within 0..1")
        return value

    @model_validator(mode="after")
    def _matching_origin(self) -> LedgerLlmReviewRequest:
        allowed = {
            "classification": {
                LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
                LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT,
            },
            "saturated": {
                LlmReviewInvocationOrigin.CLASSIFY_LLM_SATURATE_APPLY,
                LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT,
            },
            "auto_split": {
                LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT,
                LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT,
            },
            "split": {LlmReviewInvocationOrigin.SPLIT_LLM},
        }
        if self.origin not in allowed[self.mode]:
            raise ValueError("review mode and invocation origin disagree")
        return self


class LedgerLlmChildProjection(BaseModel):
    """Bounded display facts copied from an existing grounded split proposal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    proportion: LedgerLlmDecimalText
    amount: LedgerLlmDecimalText
    description: LedgerLlmLongText
    category: LedgerLlmShortText | None
    iva_category: LedgerLlmShortText | None
    iva_rate: LedgerLlmDecimalText | None
    taxable_base: LedgerLlmDecimalText | None
    iva_amount: LedgerLlmDecimalText | None
    rate_derivable: bool
    derivation_note: LedgerLlmLongText
    evidence_citation: LedgerLlmLongText


class LedgerLlmSuggestionProjection(BaseModel):
    """JSON-stable review values without reconstructing domain authority in a frontend."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["classification", "saturated", "split"]
    transaction_id: Annotated[str, Field(min_length=1, max_length=96)]
    provenance: Annotated[str, Field(min_length=1, max_length=256)]
    reason: LedgerLlmLongText
    evidence_id: LedgerLlmShortText | None
    classification: LedgerLlmShortText | None = None
    category: LedgerLlmShortText | None = None
    confidence: LedgerLlmDecimalText | None = None
    multiple_components: bool | None = None
    business_pct: LedgerLlmDecimalText | None = None
    iva_category: LedgerLlmShortText | None = None
    iva_rate: LedgerLlmDecimalText | None = None
    taxable_base: LedgerLlmDecimalText | None = None
    iva_amount: LedgerLlmDecimalText | None = None
    rate_derivable: bool = False
    derivation_note: LedgerLlmLongText = ""
    evidence_advisory: LedgerLlmLongText = ""
    parent_amount: LedgerLlmDecimalText | None = None
    children: Annotated[tuple[LedgerLlmChildProjection, ...], Field(max_length=128)] = ()


class LedgerLlmReviewProjection(BaseModel):
    """Exact digest-bound private REVIEW projection released under disclosure policy."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection_version: Literal[1] = 1
    profile_id: UUID
    reviewed_proposal_digest: ContentDigest
    suggestion: LedgerLlmSuggestionProjection


class LedgerLlmReviewResponse(BaseModel):
    """Authority-free intent; the supervisor owns the bound response capability."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    response_version: Literal[1]
    intent: OperationResponseIntentValue


def ledger_llm_review_definition_id(request: LedgerLlmReviewRequest) -> str:
    """Bind the split-only request to its sole registered definition."""
    return LEDGER_SPLIT_REVIEW_DEFINITION_ID if request.mode == "split" else LEDGER_CLASSIFY_REVIEW_DEFINITION_ID


def require_ledger_llm_invocation(identity: OperationIdentity, request: LedgerLlmReviewRequest) -> None:
    """Refuse any invocation whose definition or profile differs from its operand."""
    expected_subject = profile_operation_subject(str(request.profile_id))
    if identity.definition_id != ledger_llm_review_definition_id(request) or identity.subject_ref != expected_subject:
        raise ValueError("ledger review invocation and request disagree")


def bound_ledger_llm_projection[ModelT: BaseModel](projection: ModelT) -> ModelT:
    """Refuse a public projection exceeding the declared serialized byte bound."""
    if len(projection.model_dump_json().encode("utf-8")) > _MAX_PROJECTION_BYTES:
        raise TransactionValidationError("ledger review projection exceeds its declared bound")
    return projection
