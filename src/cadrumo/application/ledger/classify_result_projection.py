"""Bounded manual classification result construction and receipt projection."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.transactions.errors import TransactionValidationError
from ..operations.models import OperationTerminalReceipt
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .actions_manual import ledger_transaction_result_payload
from .classify_requests import (
    LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
)
from .classify_result_contracts import (
    LEDGER_CLASSIFY_MAX_RESULT_JSON_BYTES,
    LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE,
    LedgerClassifyExecutionResult,
    LedgerClassifyOperationResult,
)
from .models import LedgerTransactionResultPayload, ManualLedgerTransactionResult
from .transaction_projection import LedgerTransactionProjection


def _classify_receipt_subject_matches(
    result: LedgerClassifyExecutionResult,
    receipt: OperationTerminalReceipt,
) -> bool:
    return receipt.identity.subject_ref == profile_operation_subject(str(result.profile_id))


def _classify_success_receipt_matches(
    receipt: OperationTerminalReceipt,
    projected: LedgerClassifyOperationResult | None,
) -> bool:
    return (
        receipt.condition is OperationTerminalCondition.SUCCEEDED
        and receipt.diagnostic_ref is None
        and projected is not None
        and receipt.effect is (OperationEffect.UPDATED if projected.bucket_event_ids else OperationEffect.NONE)
    )


def _classify_refusal_receipt_matches(receipt: OperationTerminalReceipt) -> bool:
    return (
        receipt.condition is OperationTerminalCondition.REFUSED
        and receipt.refusal_ref == LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE
        and receipt.refusal_detail_ref is not None
        and receipt.diagnostic_ref is None
        and receipt.effect is OperationEffect.NONE
    )


def classification_result_from_action(
    profile_id: UUID,
    result: ManualLedgerTransactionResult,
) -> LedgerClassifyOperationResult:
    """Validate exact identity, project canonical output, and enforce its byte bound."""
    canonical: LedgerTransactionResultPayload = ledger_transaction_result_payload(result)
    if (
        canonical.bucket_id != str(profile_id)
        or result.ref.bucket_id != canonical.bucket_id
        or result.ref.transaction_id != canonical.transaction_id
        or result.ref.transaction_id != result.transaction.transaction_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    projected = LedgerClassifyOperationResult(
        outcome="classified",
        profile_id=profile_id,
        transaction=LedgerTransactionProjection.from_payload(canonical.transaction),
        deduction_fact_kind=(
            result.transaction.deduction_fact_kind.value if result.transaction.deduction_fact_kind else None
        ),
        investment_asset_id=result.transaction.investment_asset_id,
        review_status=canonical.review_status,
        bucket_event_ids=result.bucket_event_ids,
    )
    if len(projected.model_dump_json().encode("utf-8")) > LEDGER_CLASSIFY_MAX_RESULT_JSON_BYTES:
        raise TransactionValidationError(
            "ledger classify result exceeds its registered projection bound",
            context={"max_result_bytes": str(LEDGER_CLASSIFY_MAX_RESULT_JSON_BYTES)},
        )
    return projected


def project_classify_operation_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release a matching success projection or bounded validation detail."""
    if (
        type(result) is not LedgerClassifyExecutionResult
        or receipt.identity.definition_id != LEDGER_CLASSIFY_OPERATION_DEFINITION_ID
    ):
        raise ValueError("invalid ledger classify result or terminal receipt")
    if not _classify_receipt_subject_matches(result, receipt):
        raise ValueError("ledger classify result belongs to another subject")
    if result.outcome == "classified":
        projected = result.result
        if projected is None or not _classify_success_receipt_matches(receipt, projected):
            raise ValueError("ledger classify success has an incompatible terminal receipt")
        return projected
    if not _classify_refusal_receipt_matches(receipt):
        raise ValueError("ledger classify validation refusal has an incompatible terminal receipt")
    return LedgerClassifyOperationResult(
        outcome="validation_error",
        profile_id=result.profile_id,
        validation_kind=result.validation_kind,
        validation_messages=result.validation_messages,
    )
