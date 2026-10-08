"""Correlate operator IVA outcomes with their exact request and receipt."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.models import OperationTerminalReceipt
from .classify_result_contracts import (
    LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE,
)
from .operator_iva_contracts import (
    LEDGER_OPERATOR_IVA_DEFINITION_ID,
    LedgerOperatorIvaExecutionResult,
    LedgerOperatorIvaRequest,
    LedgerOperatorIvaResult,
)


def _expected_operator_iva_effect(projection: LedgerOperatorIvaResult) -> OperationEffect:
    return (
        OperationEffect.UPDATED
        if projection.classification is not None and projection.classification.bucket_event_ids
        else OperationEffect.NONE
    )


def _operator_iva_request_matches(
    receipt: OperationTerminalReceipt,
    payload: LedgerOperatorIvaRequest,
    projection: LedgerOperatorIvaResult,
    expected_effect: OperationEffect,
) -> bool:
    return (
        receipt.identity.definition_id == LEDGER_OPERATOR_IVA_DEFINITION_ID
        and receipt.identity.subject_ref == profile_operation_subject(str(payload.profile_id))
        and projection.profile_id == payload.profile_id
        and projection.transaction_id.startswith(payload.transaction_id)
        and projection.iva_category == payload.iva_category
        and receipt.effect is expected_effect
    )


def _operator_iva_refusal_receipt_matches(receipt: OperationTerminalReceipt) -> bool:
    return (
        receipt.condition is OperationTerminalCondition.REFUSED
        and receipt.refusal_ref == LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE
        and receipt.refusal_detail_ref is not None
        and receipt.diagnostic_ref is None
    )


def _operator_iva_success_receipt_matches(receipt: OperationTerminalReceipt) -> bool:
    return receipt.condition is OperationTerminalCondition.SUCCEEDED and receipt.diagnostic_ref is None


def project_operator_iva_result(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
    """Release one operator-selected IVA outcome against its correlated receipt."""
    if not isinstance(result, LedgerOperatorIvaExecutionResult):
        raise ValueError("invalid operator IVA execution result")
    payload, projection = result.request, result.result
    if not _operator_iva_request_matches(receipt, payload, projection, _expected_operator_iva_effect(projection)):
        raise ValueError("operator IVA result does not match its request and terminal receipt")
    if projection.outcome == "validation_error":
        if not _operator_iva_refusal_receipt_matches(receipt):
            raise ValueError("operator IVA validation detail has an incompatible terminal receipt")
    elif not _operator_iva_success_receipt_matches(receipt):
        raise ValueError("operator IVA success has an incompatible terminal receipt")
    return projection
