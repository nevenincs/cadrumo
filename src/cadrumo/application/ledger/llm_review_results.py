"""Canonical terminal outcome contracts for ledger LLM review operations."""

from __future__ import annotations

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.interactions import OperationResponseIntentValue
from ..operations.models import OperationIdentity
from .classify_operation import LedgerClassifyOperationResult
from .id_resolution import resolve_transaction_id
from .llm_review_contracts import (
    LedgerLlmLongText,
    LedgerLlmReviewProjection,
    LedgerLlmReviewRequest,
    LedgerLlmShortText,
    require_ledger_llm_invocation,
)
from .llm_review_workflow import LlmReviewInvocationOrigin


class LedgerLlmOperationResult(BaseModel):
    """Settled preview or writer outcome and the exact captured proposal identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    reviewed_proposal_digest: ContentDigest
    outcome: Literal["preview", "classified", "split", "rejected"]
    transaction_id: Annotated[str, Field(min_length=1, max_length=96)]
    preview: LedgerLlmReviewProjection | None = None
    classification: LedgerClassifyOperationResult | None = None
    split_group_id: LedgerLlmShortText | None = None
    child_transaction_ids: Annotated[tuple[LedgerLlmShortText, ...], Field(max_length=128)] = ()
    classified_child_count: Annotated[int, Field(ge=0, le=128)] = 0
    bucket_event_id: LedgerLlmShortText | None = None
    suggestion_kind: LedgerLlmShortText | None = None
    provenance: LedgerLlmShortText
    operator_reason: LedgerLlmLongText = ""

    @model_validator(mode="after")
    def _complete_outcome(self) -> LedgerLlmOperationResult:
        return _validate_ledger_llm_operation_result(self)


class LedgerLlmExecutionResult(BaseModel):
    """Secure invocation binding for the distinct public terminal projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    identity: OperationIdentity
    request: LedgerLlmReviewRequest
    response: OperationResponseIntentValue | Literal["preview"]
    result: LedgerLlmOperationResult

    @model_validator(mode="after")
    def _matching_invocation(self) -> Self:
        _validate_ledger_llm_execution_result(self)
        return self


def _preview_has_exact_proposal(result: LedgerLlmOperationResult) -> bool:
    preview = result.preview
    return (
        preview is not None
        and preview.profile_id == result.profile_id
        and preview.reviewed_proposal_digest == result.reviewed_proposal_digest
        and preview.suggestion.transaction_id == result.transaction_id
        and preview.suggestion.provenance == result.provenance
    )


def _preview_has_no_writer_facts(result: LedgerLlmOperationResult) -> bool:
    return not (
        result.classification is not None
        or result.split_group_id is not None
        or result.child_transaction_ids
        or result.classified_child_count
        or result.bucket_event_id is not None
        or result.suggestion_kind is not None
        or result.operator_reason
    )


def _classified_result_is_exact(result: LedgerLlmOperationResult) -> bool:
    classification = result.classification
    return (
        classification is not None
        and classification.outcome == "classified"
        and classification.profile_id == result.profile_id
    )


def _classified_transaction_is_exact(result: LedgerLlmOperationResult) -> bool:
    classification = result.classification
    return (
        classification is not None
        and classification.transaction is not None
        and classification.transaction.transaction_id == result.transaction_id
    )


def _classified_has_no_other_facts(result: LedgerLlmOperationResult) -> bool:
    return not (
        result.split_group_id is not None
        or result.child_transaction_ids
        or result.classified_child_count
        or result.bucket_event_id is not None
        or result.suggestion_kind is not None
        or result.operator_reason
    )


def _split_children_are_exact(result: LedgerLlmOperationResult) -> bool:
    child_ids = result.child_transaction_ids
    return (
        bool(result.split_group_id)
        and len(child_ids) >= 2
        and len(set(child_ids)) == len(child_ids)
        and result.transaction_id not in child_ids
        and result.classified_child_count == len(child_ids)
    )


def _split_has_no_other_facts(result: LedgerLlmOperationResult) -> bool:
    return not (
        result.classification is not None
        or result.bucket_event_id is not None
        or result.suggestion_kind is not None
        or result.operator_reason
    )


def _rejection_audit_is_exact(result: LedgerLlmOperationResult) -> bool:
    return bool(result.bucket_event_id) and result.suggestion_kind in {"classification", "split"}


def _rejection_has_no_mutation_facts(result: LedgerLlmOperationResult) -> bool:
    return not (
        result.classification is not None
        or result.split_group_id is not None
        or result.child_transaction_ids
        or result.classified_child_count
    )


def _validate_preview_result(result: LedgerLlmOperationResult) -> LedgerLlmOperationResult:
    if not _preview_has_exact_proposal(result):
        raise ValueError("preview requires its exact captured proposal")
    if not _preview_has_no_writer_facts(result):
        raise ValueError("preview cannot carry mutation or rejection facts")
    return result


def _validate_classified_result(result: LedgerLlmOperationResult) -> None:
    if not _classified_result_is_exact(result):
        raise ValueError("classified review requires its exact-profile result")
    if not _classified_transaction_is_exact(result):
        raise ValueError("classified review result belongs to another row")
    if not _classified_has_no_other_facts(result):
        raise ValueError("classified review cannot carry split or rejection facts")


def _validate_split_result(result: LedgerLlmOperationResult) -> None:
    if not _split_children_are_exact(result):
        raise ValueError("split review requires its persisted children")
    if not _split_has_no_other_facts(result):
        raise ValueError("split review cannot carry classification or rejection facts")


def _validate_rejected_result(result: LedgerLlmOperationResult) -> None:
    if not _rejection_audit_is_exact(result):
        raise ValueError("rejected review requires its audit outcome")
    if not _rejection_has_no_mutation_facts(result):
        raise ValueError("rejected review cannot carry mutation facts")


def _validate_ledger_llm_operation_result(result: LedgerLlmOperationResult) -> LedgerLlmOperationResult:
    if result.outcome == "preview":
        return _validate_preview_result(result)
    if result.preview is not None:
        raise ValueError("writer outcome cannot carry a preview")
    if result.outcome == "classified":
        _validate_classified_result(result)
    elif result.outcome == "split":
        _validate_split_result(result)
    else:
        _validate_rejected_result(result)
    return result


def _validate_preview_binding(result: LedgerLlmExecutionResult) -> None:
    request = result.request
    if (result.response == "preview") != request.preview or (result.result.outcome == "preview") != request.preview:
        raise ValueError("ledger preview request and terminal outcome disagree")
    if request.preview:
        expected_kind = "split" if request.mode in {"split", "auto_split"} else request.mode
        if result.result.preview is None or result.result.preview.suggestion.kind != expected_kind:
            raise ValueError("preview result has another proposal kind")


def _validate_response_outcome(result: LedgerLlmExecutionResult) -> None:
    if (result.response == "reject") != (result.result.outcome == "rejected"):
        raise ValueError("ledger result disagrees with the reviewed decision")
    if result.response == "apply" and result.request.origin is LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT:
        raise ValueError("rejection invocation cannot publish a mutation")


def _validate_mode_outcome(result: LedgerLlmExecutionResult) -> None:
    if result.request.mode == "split" and result.result.outcome == "classified":
        raise ValueError("split invocation cannot publish an in-place classification")
    if result.request.mode not in {"split", "auto_split"} and result.result.outcome == "split":
        raise ValueError("classification invocation cannot publish a split")


def _validate_rejected_kind(result: LedgerLlmExecutionResult) -> None:
    expected_kind = "split" if result.request.mode in {"split", "auto_split"} else "classification"
    if result.result.outcome == "rejected" and result.result.suggestion_kind != expected_kind:
        raise ValueError("rejection result has another proposal kind")


def _validate_ledger_llm_execution_result(result: LedgerLlmExecutionResult) -> None:
    require_ledger_llm_invocation(result.identity, result.request)
    if result.result.profile_id != result.request.profile_id:
        raise ValueError("ledger result belongs to another profile")
    resolve_transaction_id(result.request.transaction_id, (result.result.transaction_id,))
    _validate_preview_binding(result)
    _validate_response_outcome(result)
    _validate_mode_outcome(result)
    _validate_rejected_kind(result)
