"""Canonical successful and refused result projection for manual ledger addition."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ValidationError

from ...core.errors.error_codes import resolve_error_message
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.transactions.errors import TransactionValidationError
from ..operations.models import OperationTerminalReceipt
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .actions_manual import ledger_transaction_result_payload
from .ledger_add_contracts import (
    LEDGER_ADD_OPERATION_DEFINITION_ID,
    LEDGER_ADD_VALIDATION_REFUSAL_CODE,
    MAX_LEDGER_ADD_EVENT_IDS,
    MAX_LEDGER_ADD_VALIDATION_MESSAGES,
    LedgerAddExecutionResult,
    LedgerAddOperationResult,
    LedgerAddValidationMessages,
)
from .models import LedgerTransactionResultPayload
from .transaction_projection import LedgerTransactionProjection


def build_ledger_add_validation_messages(error: Exception) -> LedgerAddValidationMessages:
    """Retain bounded validation locations and messages without error context."""
    if isinstance(error, ValidationError):
        messages: tuple[str, ...] = tuple(
            str(item.get("msg", "invalid value")).removeprefix("Value error, ").strip()
            for item in error.errors(include_input=False, include_context=False, include_url=False)[
                :MAX_LEDGER_ADD_VALIDATION_MESSAGES
            ]
        )
    else:
        messages = (resolve_error_message(error).strip() or "ledger add input is invalid",)
    bounded = tuple(message[:2048] for message in messages if message.strip())
    return bounded[:MAX_LEDGER_ADD_VALIDATION_MESSAGES] or ("ledger add input is invalid",)


def build_ledger_add_operation_result(
    profile_id: UUID,
    result: object,
    *,
    advisory_input_inert: bool,
    advisory_sector_unmatched: bool,
    advisory_input_classification: str | None,
    advisory_sector_id: str | None,
) -> LedgerAddOperationResult:
    """Project the canonical writer result with exact profile and advisory facts."""
    from .models import ManualLedgerTransactionResult

    if not isinstance(result, ManualLedgerTransactionResult):
        raise TransactionValidationError("ledger add returned no canonical transaction receipt")
    canonical: LedgerTransactionResultPayload = ledger_transaction_result_payload(result)
    if (
        canonical.bucket_id != str(profile_id)
        or result.ref.bucket_id != canonical.bucket_id
        or result.ref.transaction_id != canonical.transaction_id
        or result.transaction.transaction_id != canonical.transaction_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if len(result.bucket_event_ids) > MAX_LEDGER_ADD_EVENT_IDS:
        raise TransactionValidationError("ledger add returned too many event identifiers")
    return LedgerAddOperationResult.created(
        profile_id,
        transaction=LedgerTransactionProjection.from_payload(canonical.transaction),
        review_status=canonical.review_status,
        bucket_event_ids=result.bucket_event_ids,
        advisory_input_classification=advisory_input_classification,
        advisory_input_classification_inert=advisory_input_inert,
        advisory_sector_id=advisory_sector_id,
        advisory_sector_unmatched=advisory_sector_unmatched,
    )


def project_ledger_add_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release a matching successful add result or its bounded refusal detail."""
    if (
        type(result) is not LedgerAddExecutionResult
        or receipt.identity.definition_id != LEDGER_ADD_OPERATION_DEFINITION_ID
    ):
        raise ValueError("invalid ledger add result or terminal receipt")
    if receipt.identity.subject_ref != profile_operation_subject(str(result.profile_id)):
        raise ValueError("ledger add result belongs to another subject")
    if result.outcome == "created":
        return _project_created_ledger_add_result(result, receipt)
    return _project_refused_ledger_add_result(result, receipt)


def _project_created_ledger_add_result(
    result: LedgerAddExecutionResult,
    receipt: OperationTerminalReceipt,
) -> LedgerAddOperationResult:
    projected = result.result
    if (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.diagnostic_ref is not None
        or projected is None
        or receipt.effect is not (OperationEffect.UPDATED if projected.bucket_event_ids else OperationEffect.NONE)
    ):
        raise ValueError("ledger add success has an incompatible terminal receipt")
    return projected


def _project_refused_ledger_add_result(
    result: LedgerAddExecutionResult,
    receipt: OperationTerminalReceipt,
) -> LedgerAddOperationResult:
    if (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.refusal_ref != LEDGER_ADD_VALIDATION_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
        or receipt.diagnostic_ref is not None
        or receipt.effect is not OperationEffect.NONE
        or result.validation_code is None
    ):
        raise ValueError("ledger add validation refusal has an incompatible terminal receipt")
    return LedgerAddOperationResult.validation_refusal(
        result.profile_id,
        code=result.validation_code,
        messages=result.validation_messages,
    )
