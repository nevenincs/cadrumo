"""Validate inventory execution results against their terminal receipts."""

from __future__ import annotations

from typing import Literal, TypeIs, get_args
from uuid import UUID

from pydantic import BaseModel

from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.models import OperationTerminalReceipt, require_succeeded_receipt_references
from .registered_execution_result import (
    InventoryOperationExecutionResult,
    InventoryOperationRefusalDetail,
)
from .registered_projections import (
    InventoryReasonFact,
    InventoryRefusalProjection,
)
from .registered_requests import (
    INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CORRECT_OPERATION_DEFINITION_ID,
    INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    INVENTORY_DESCRIBE_OPERATION_DEFINITION_ID,
    INVENTORY_INSPECT_OPERATION_DEFINITION_ID,
    INVENTORY_LIST_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_CORRECT_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_REVERSE_OPERATION_DEFINITION_ID,
    INVENTORY_RESTORE_OPERATION_DEFINITION_ID,
    INVENTORY_RETIRE_OPERATION_DEFINITION_ID,
    INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
    InventoryLedgerChangeOperationId,
    InventoryOperationId,
)
from .registered_specs import INVENTORY_OPERATION_SHAPES
from .service import (
    InventoryLedgerResult,
    InventoryValuationPreviewResult,
)

OPERATION_IDS_BY_DEFINITION: dict[str, InventoryOperationId] = {
    INVENTORY_LIST_OPERATION_DEFINITION_ID: "list",
    INVENTORY_CREATE_OPERATION_DEFINITION_ID: "create",
    INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID: "movement.add",
    INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID: "valuation.preview",
    INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID: "closing-authority.record",
    INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID: "closing-value.record",
    INVENTORY_INSPECT_OPERATION_DEFINITION_ID: "inspect",
    INVENTORY_DESCRIBE_OPERATION_DEFINITION_ID: "describe",
    INVENTORY_CORRECT_OPERATION_DEFINITION_ID: "correct",
    INVENTORY_MOVEMENT_CORRECT_OPERATION_DEFINITION_ID: "movement.correct",
    INVENTORY_MOVEMENT_REVERSE_OPERATION_DEFINITION_ID: "movement.reverse",
    INVENTORY_RETIRE_OPERATION_DEFINITION_ID: "retire",
    INVENTORY_RESTORE_OPERATION_DEFINITION_ID: "restore",
}


_LedgerResultOperationId = Literal[
    InventoryLedgerChangeOperationId,
    "create",
    "movement.add",
    "closing-authority.record",
    "closing-value.record",
]


def is_ledger_change_operation(operation_id: InventoryOperationId) -> TypeIs[InventoryLedgerChangeOperationId]:
    """Identify inventory ledger change operations."""
    return operation_id in get_args(InventoryLedgerChangeOperationId)


def profile_from_receipt(receipt: OperationTerminalReceipt, *, definition_id: str) -> UUID:
    """Validate and return the profile identified by the receipt."""
    if receipt.identity.definition_id != definition_id:
        raise ValueError("inventory result definition differs from its terminal receipt")
    subject = receipt.identity.subject_ref
    try:
        profile_id = UUID(subject.removeprefix("profile:"))
    except ValueError:
        raise ValueError("inventory result has an invalid profile subject") from None
    if subject != profile_operation_subject(str(profile_id)):
        raise ValueError("inventory result has an invalid profile subject")
    return profile_id


def execution_result(result: BaseModel) -> InventoryOperationExecutionResult:
    """Validate the private execution result type and contents."""
    if type(result) is not InventoryOperationExecutionResult:
        raise ValueError("inventory execution result has an incompatible type")
    return InventoryOperationExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)


def require_inventory_list_execution(
    private: InventoryOperationExecutionResult,
    *,
    profile_id: UUID,
) -> None:
    """Validate the inventory list execution result."""
    if private.operation_id != "list" or private.outcome != "success" or private.profile_id != profile_id:
        raise ValueError("inventory list result contradicts its terminal receipt")


def require_inventory_list_receipt(receipt: OperationTerminalReceipt) -> None:
    """Validate the inventory list terminal receipt."""
    message = "inventory list result contradicts its terminal receipt"
    if (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError(message)
    require_succeeded_receipt_references(receipt, message=message)


def validate_refusal_receipt(
    *,
    private: InventoryOperationExecutionResult,
    receipt: OperationTerminalReceipt,
    profile_id: UUID,
    definition_id: str,
    operation_id: InventoryOperationId,
) -> InventoryRefusalProjection:
    """Validate a refusal against its terminal receipt."""
    refusal = private.refusal
    refusal = _require_inventory_refusal_execution(
        private,
        profile_id=profile_id,
        operation_id=operation_id,
        refusal=refusal,
    )
    _require_inventory_refusal_scope_receipt(
        receipt,
        refusal=refusal,
        definition_id=definition_id,
        operation_id=operation_id,
    )
    _require_inventory_refusal_terminal_receipt(receipt, definition_id=definition_id)
    return InventoryRefusalProjection(
        code=refusal.code,
        reason=refusal.reason,
        actividad_id=refusal.actividad_id,
        year=refusal.year,
        movement_id=refusal.movement_id,
        valuation_method=refusal.valuation_method,
        reason_key=refusal.reason_key,
        reason_facts=tuple(
            InventoryReasonFact(key=key, value=value) for key, value in sorted(refusal.reason_facts.items())
        ),
    )


def _require_inventory_refusal_execution(
    private: InventoryOperationExecutionResult,
    *,
    profile_id: UUID,
    operation_id: InventoryOperationId,
    refusal: InventoryOperationRefusalDetail | None,
) -> InventoryOperationRefusalDetail:
    if (
        private.outcome != "refused"
        or private.operation_id != operation_id
        or private.profile_id != profile_id
        or refusal is None
    ):
        raise ValueError("inventory refusal detail contradicts its terminal receipt")
    return refusal


def _require_inventory_refusal_scope_receipt(
    receipt: OperationTerminalReceipt,
    *,
    refusal: InventoryOperationRefusalDetail,
    definition_id: str,
    operation_id: InventoryOperationId,
) -> None:
    if (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.effect is not OperationEffect.NONE
        or receipt.refusal_ref != refusal.code
        or definition_id not in INVENTORY_OPERATION_SHAPES
    ):
        raise ValueError("inventory refusal detail contradicts its terminal receipt")
    if refusal.code not in INVENTORY_OPERATION_SHAPES[definition_id].refusal_codes:
        raise ValueError("inventory refusal detail contradicts its terminal receipt")
    if OPERATION_IDS_BY_DEFINITION[definition_id] != operation_id:
        raise ValueError("inventory refusal detail contradicts its terminal receipt")


def _require_inventory_refusal_terminal_receipt(receipt: OperationTerminalReceipt, *, definition_id: str) -> None:
    if (
        receipt.refusal_detail_ref is None
        or receipt.result_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or receipt.identity.definition_id != definition_id
    ):
        raise ValueError("inventory refusal detail contradicts its terminal receipt")


def validate_ledger_success(
    *,
    private: InventoryOperationExecutionResult,
    receipt: OperationTerminalReceipt,
    profile_id: UUID,
    operation_id: _LedgerResultOperationId,
    definition_id: str,
) -> InventoryLedgerResult:
    """Validate a successful ledger result against its receipt."""
    result = private.ledger_result
    expected_effect = (
        OperationEffect.UPDATED if result is not None and result.bucket_event_ids else OperationEffect.NONE
    )
    if operation_id in {"closing-authority.record", "closing-value.record"}:
        expected_effect = OperationEffect.UPDATED if (private.closing_changed is True) else OperationEffect.NONE
    result = _require_inventory_ledger_execution(
        private,
        result=result,
        profile_id=profile_id,
        operation_id=operation_id,
    )
    require_inventory_ledger_receipt(
        receipt,
        expected_effect=expected_effect,
        definition_id=definition_id,
    )
    _require_inventory_ledger_event_scope(result, operation_id=operation_id)
    return result


def _require_inventory_ledger_execution(
    private: InventoryOperationExecutionResult,
    *,
    result: InventoryLedgerResult | None,
    profile_id: UUID,
    operation_id: _LedgerResultOperationId,
) -> InventoryLedgerResult:
    if (
        private.operation_id != operation_id
        or private.outcome != "success"
        or private.profile_id != profile_id
        or result is None
    ):
        raise ValueError("inventory ledger result contradicts its terminal receipt")
    return result


def require_inventory_ledger_receipt(
    receipt: OperationTerminalReceipt,
    *,
    expected_effect: OperationEffect,
    definition_id: str,
) -> None:
    """Validate the inventory ledger terminal receipt."""
    message = "inventory ledger result contradicts its terminal receipt"
    if (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not expected_effect
        or receipt.diagnostic_ref is not None
        or receipt.identity.definition_id != definition_id
    ):
        raise ValueError(message)
    require_succeeded_receipt_references(receipt, message=message)


def _require_inventory_ledger_event_scope(
    result: InventoryLedgerResult,
    *,
    operation_id: _LedgerResultOperationId,
) -> None:
    if operation_id in {"closing-authority.record", "closing-value.record"} and result.bucket_event_ids:
        raise ValueError("inventory ledger result contradicts its terminal receipt")
    if operation_id in {"create", "movement.add"} and len(result.bucket_event_ids) != 1:
        raise ValueError("inventory ledger result contradicts its terminal receipt")
    is_change = operation_id in get_args(InventoryLedgerChangeOperationId)
    if is_change and len(result.bucket_event_ids) != int(result.changed):
        raise ValueError("inventory ledger result contradicts its terminal receipt")


def require_inventory_valuation_execution(
    private: InventoryOperationExecutionResult,
    *,
    profile_id: UUID,
) -> InventoryValuationPreviewResult:
    """Validate the inventory valuation execution result."""
    preview_result = private.valuation_result
    if (
        private.operation_id != "valuation.preview"
        or private.outcome != "success"
        or private.profile_id != profile_id
        or preview_result is None
    ):
        raise ValueError("inventory valuation result contradicts its terminal receipt")
    return preview_result


def require_inventory_valuation_receipt(
    receipt: OperationTerminalReceipt,
    *,
    preview_result: InventoryValuationPreviewResult,
) -> None:
    """Validate the inventory valuation terminal receipt."""
    if receipt.condition is not OperationTerminalCondition.SUCCEEDED or receipt.effect is not (
        OperationEffect.UPDATED if preview_result.bucket_event_ids else OperationEffect.NONE
    ):
        raise ValueError("inventory valuation result contradicts its terminal receipt")
    _require_inventory_valuation_receipt_references(receipt)
    if len(preview_result.bucket_event_ids) != 1:
        raise ValueError("inventory valuation result contradicts its terminal receipt")
    if receipt.identity.definition_id != INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID:
        raise ValueError("inventory valuation result contradicts its terminal receipt")


def _require_inventory_valuation_receipt_references(receipt: OperationTerminalReceipt) -> None:
    message = "inventory valuation result contradicts its terminal receipt"
    if receipt.diagnostic_ref is not None:
        raise ValueError(message)
    require_succeeded_receipt_references(receipt, message=message)
