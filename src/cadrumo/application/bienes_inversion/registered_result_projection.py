"""Receipt-checked public projections for capital-goods operations."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.bienes_inversion.register import BienesInversionIvaRegister, BienInversionIvaRecord
from ..operations.models import OperationTerminalReceipt
from .registered_contracts import (
    BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
    BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID,
    BIENES_INVERSION_VALIDATION_REFUSAL_CODE,
)
from .registered_execution_result import BienesInversionOperationExecutionResult
from .registered_result_contracts import (
    BienesInversionDeclareProjection,
    BienesInversionListProjection,
    BienesInversionRefusalProjection,
    BienInversionRecordProjection,
)


def _profile_from_receipt(receipt: OperationTerminalReceipt, *, definition_id: str) -> UUID:
    if receipt.identity.definition_id != definition_id:
        raise ValueError("capital-goods result definition differs from its terminal receipt")
    subject = receipt.identity.subject_ref
    try:
        profile_id = UUID(subject.removeprefix("profile:"))
    except ValueError:
        raise ValueError("capital-goods result has an invalid profile subject") from None
    if subject != profile_operation_subject(str(profile_id)):
        raise ValueError("capital-goods result has an invalid profile subject")
    return profile_id


def _execution_result(result: BaseModel) -> BienesInversionOperationExecutionResult:
    if type(result) is not BienesInversionOperationExecutionResult:
        raise ValueError("capital-goods execution result has an incompatible type")
    return BienesInversionOperationExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)


def _validate_refusal(
    *,
    result: BienesInversionOperationExecutionResult,
    receipt: OperationTerminalReceipt,
    profile_id: UUID,
) -> BienesInversionRefusalProjection:
    refusal = result.refusal
    if (
        result.operation_id != "declare"
        or result.outcome != "refused"
        or result.profile_id != profile_id
        or refusal is None
    ):
        raise ValueError("capital-goods refusal detail contradicts its terminal receipt")
    if not _refusal_receipt_matches(receipt, refusal):
        raise ValueError("capital-goods refusal detail contradicts its terminal receipt")
    return refusal


def _refusal_receipt_matches(
    receipt: OperationTerminalReceipt,
    refusal: BienesInversionRefusalProjection,
) -> bool:
    return (
        receipt.condition is OperationTerminalCondition.REFUSED
        and receipt.effect is OperationEffect.NONE
        and receipt.refusal_ref == refusal.code
        and receipt.refusal_detail_ref is not None
        and receipt.result_ref is None
        and receipt.failure_error_code is None
        and receipt.diagnostic_ref is None
        and receipt.identity.definition_id == BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID
        and refusal.code == BIENES_INVERSION_VALIDATION_REFUSAL_CODE
    )


def _success_receipt_matches_effect(receipt: OperationTerminalReceipt, effect: OperationEffect) -> bool:
    return (
        receipt.condition is OperationTerminalCondition.SUCCEEDED
        and receipt.effect is effect
        and receipt.result_ref is not None
        and receipt.refusal_ref is None
        and receipt.refusal_detail_ref is None
        and receipt.failure_error_code is None
        and receipt.diagnostic_ref is None
    )


def _declaration_receipt_matches(receipt: OperationTerminalReceipt) -> bool:
    return (
        _success_receipt_matches_effect(receipt, OperationEffect.UPDATED)
        and receipt.identity.definition_id == BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID
    )


def _require_list_result(
    result: BienesInversionOperationExecutionResult,
    receipt: OperationTerminalReceipt,
    profile_id: UUID,
) -> BienesInversionIvaRegister:
    register = result.register_snapshot
    if (
        result.operation_id != "list"
        or result.outcome != "success"
        or result.profile_id != profile_id
        or register is None
        or result.record is not None
        or result.refusal is not None
        or not _success_receipt_matches_effect(receipt, OperationEffect.NONE)
        or receipt.identity.definition_id != BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID
    ):
        raise ValueError("capital-goods list result contradicts its terminal receipt")
    return register


def _record_is_present(
    record: BienInversionIvaRecord,
    register: BienesInversionIvaRegister,
) -> bool:
    return any(row.identifier == record.identifier and row == record for row in register.records)


def _require_declaration_result(
    result: BienesInversionOperationExecutionResult,
    receipt: OperationTerminalReceipt,
    profile_id: UUID,
) -> tuple[BienInversionIvaRecord, BienesInversionIvaRegister]:
    record = result.record
    register = result.register_snapshot
    if (
        result.operation_id != "declare"
        or result.outcome != "success"
        or result.profile_id != profile_id
        or record is None
        or register is None
        or result.count != len(register.records)
        or result.refusal is not None
        or not _declaration_receipt_matches(receipt)
    ):
        raise ValueError("capital-goods declaration result contradicts its terminal receipt")
    if not _record_is_present(record, register):
        raise ValueError("capital-goods declaration result contradicts its terminal receipt")
    return record, register


def project_bienes_inversion_list_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> BienesInversionListProjection:
    """Release the complete profile register only against a read-only receipt."""
    private = _execution_result(result)
    profile_id = _profile_from_receipt(receipt, definition_id=BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID)
    register = _require_list_result(private, receipt, profile_id)
    return BienesInversionListProjection(
        profile_id=profile_id,
        rows=tuple(BienInversionRecordProjection.from_record(row) for row in register.records),
    )


def project_bienes_inversion_declare_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> BienesInversionDeclareProjection:
    """Release one complete new record or its typed pre-write refusal."""
    private = _execution_result(result)
    profile_id = _profile_from_receipt(receipt, definition_id=BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID)
    if private.outcome == "refused":
        refusal = _validate_refusal(result=private, receipt=receipt, profile_id=profile_id)
        return BienesInversionDeclareProjection(outcome="refused", profile_id=profile_id, refusal=refusal)
    record, register = _require_declaration_result(private, receipt, profile_id)
    return BienesInversionDeclareProjection(
        outcome="declared",
        profile_id=profile_id,
        record=BienInversionRecordProjection.from_record(record),
        count=len(register.records),
    )
