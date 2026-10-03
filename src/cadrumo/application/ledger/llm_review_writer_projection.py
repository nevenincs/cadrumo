"""Recognize and project the exact result returned by an existing ledger writer."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.identity.digest import ContentDigest
from ...core.operations import OperationEffect
from ...domain.transactions.models import Transaction
from .actions_manual import ledger_transaction_result_payload
from .classify_operation import LedgerClassifyOperationResult
from .llm_classification_ports import LLMSplitApplyResult, LLMSuggestionRejectionResult
from .llm_review_contracts import bound_ledger_llm_projection
from .llm_review_operand import LedgerLlmReviewedOperand
from .llm_review_results import LedgerLlmOperationResult
from .llm_review_workflow import LlmReviewDecision
from .models import ManualLedgerTransactionResult
from .transaction_projection import LedgerTransactionProjection


def _classification_writer_effect(
    result: ManualLedgerTransactionResult,
    *,
    profile: str,
    transaction_id: str,
) -> OperationEffect:
    if (
        result.ref.bucket_id != profile
        or result.ref.transaction_id != transaction_id
        or result.transaction.transaction_id != transaction_id
    ):
        raise ValueError("classification writer returned another profile or transaction")
    return OperationEffect.UPDATED if result.bucket_event_ids else OperationEffect.NONE


def _split_writer_effect(
    result: LLMSplitApplyResult,
    *,
    profile: str,
    transaction_id: str,
    provenance: str,
) -> OperationEffect:
    if result.bucket_id != profile or result.parent_transaction_id != transaction_id or result.provenance != provenance:
        raise ValueError("split writer returned another profile, transaction, or proposal")
    return OperationEffect.UPDATED


def _expected_suggestion_kind(operand: LedgerLlmReviewedOperand) -> str:
    return "split" if operand.request.mode in {"split", "auto_split"} else "classification"


def _rejection_writer_effect(
    result: LLMSuggestionRejectionResult,
    *,
    operand: LedgerLlmReviewedOperand,
    profile: str,
    transaction_id: str,
) -> OperationEffect:
    if (
        result.bucket_id != profile
        or result.transaction_id != transaction_id
        or result.provenance != operand.suggestion.provenance
        or result.suggestion_kind != _expected_suggestion_kind(operand)
        or result.operator_reason != operand.request.reason
    ):
        raise ValueError("rejection writer returned another profile, transaction, or proposal")
    return OperationEffect.UPDATED


def validate_ledger_llm_writer_effect(
    result: BaseModel,
    *,
    operand: LedgerLlmReviewedOperand,
    baseline: Transaction,
    decision: LlmReviewDecision,
) -> OperationEffect:
    """Validate settled writer identity before publishing its truthful effect."""
    profile = str(operand.request.profile_id)
    transaction_id = baseline.transaction_id
    if isinstance(result, ManualLedgerTransactionResult) and decision is LlmReviewDecision.APPLY:
        return _classification_writer_effect(result, profile=profile, transaction_id=transaction_id)
    if isinstance(result, LLMSplitApplyResult) and decision is LlmReviewDecision.SPLIT:
        return _split_writer_effect(
            result,
            profile=profile,
            transaction_id=transaction_id,
            provenance=operand.suggestion.provenance,
        )
    if isinstance(result, LLMSuggestionRejectionResult) and decision is LlmReviewDecision.REJECT:
        return _rejection_writer_effect(
            result,
            operand=operand,
            profile=profile,
            transaction_id=transaction_id,
        )
    raise ValueError("ledger review writer returned an incompatible decision result")


def project_ledger_llm_writer_result(
    result: BaseModel,
    *,
    operand: LedgerLlmReviewedOperand,
    baseline: Transaction,
    digest: ContentDigest,
) -> LedgerLlmOperationResult:
    """Project after durable outcome recognition without resetting the effect on failure."""
    common = {
        "profile_id": operand.request.profile_id,
        "reviewed_proposal_digest": digest,
        "transaction_id": baseline.transaction_id,
        "provenance": operand.suggestion.provenance,
    }
    if isinstance(result, ManualLedgerTransactionResult):
        payload = ledger_transaction_result_payload(result)
        classification = LedgerClassifyOperationResult(
            outcome="classified",
            profile_id=operand.request.profile_id,
            transaction=LedgerTransactionProjection.from_payload(payload.transaction),
            deduction_fact_kind=result.transaction.deduction_fact_kind.value
            if result.transaction.deduction_fact_kind
            else None,
            investment_asset_id=result.transaction.investment_asset_id,
            review_status=payload.review_status,
            bucket_event_ids=result.bucket_event_ids,
        )
        return bound_ledger_llm_projection(
            LedgerLlmOperationResult.model_validate(
                {**common, "outcome": "classified", "classification": classification}
            )
        )
    if isinstance(result, LLMSplitApplyResult):
        return bound_ledger_llm_projection(
            LedgerLlmOperationResult.model_validate(
                {
                    **common,
                    "outcome": "split",
                    "split_group_id": result.split_group_id,
                    "child_transaction_ids": result.child_transaction_ids,
                    "classified_child_count": result.classified_child_count,
                }
            )
        )
    if isinstance(result, LLMSuggestionRejectionResult):
        return bound_ledger_llm_projection(
            LedgerLlmOperationResult.model_validate(
                {
                    **common,
                    "outcome": "rejected",
                    "bucket_event_id": result.bucket_event_id,
                    "suggestion_kind": result.suggestion_kind,
                    "operator_reason": result.operator_reason,
                }
            )
        )
    raise ValueError("ledger review writer returned an incompatible result")
