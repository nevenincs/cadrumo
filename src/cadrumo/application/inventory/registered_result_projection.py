"""Profile-bound registered operations for the canonical inventory service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypeIs, get_args
from uuid import UUID

from pydantic import BaseModel

from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.models import OperationTerminalReceipt, require_succeeded_receipt_references
from ..operations.public_scalar import PublicDecimal
from .service import (
    InventoryLedgerResult,
    InventoryValuationPreviewResult,
)

if TYPE_CHECKING:
    pass

from .registered_execution_result import (
    InventoryOperationExecutionResult,
    InventoryOperationRefusalDetail,
)
from .registered_projections import (
    InventoryClosingAuthorityOperationProjection,
    InventoryClosingAuthorityRecordProjection,
    InventoryCreateProjection,
    InventoryInspectProjection,
    InventoryLedgerChangeProjection,
    InventoryLedgerProjection,
    InventoryListProjection,
    InventoryListRowProjection,
    InventoryMovementAddProjection,
    InventoryReasonFact,
    InventoryRefusalProjection,
    InventoryValuationOperationProjection,
    InventoryValuationPreviewProjection,
    inventory_advisories,
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

_OPERATION_IDS_BY_DEFINITION: dict[str, InventoryOperationId] = {
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


def _is_ledger_change_operation(operation_id: InventoryOperationId) -> TypeIs[InventoryLedgerChangeOperationId]:
    return operation_id in get_args(InventoryLedgerChangeOperationId)


def _profile_from_receipt(receipt: OperationTerminalReceipt, *, definition_id: str) -> UUID:
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


def _execution_result(result: BaseModel) -> InventoryOperationExecutionResult:
    if type(result) is not InventoryOperationExecutionResult:
        raise ValueError("inventory execution result has an incompatible type")
    return InventoryOperationExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)


def project_inventory_list_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> InventoryListProjection:
    """Release only a safe list projection correlated with its exact receipt."""
    private = _execution_result(result)
    profile_id = _profile_from_receipt(receipt, definition_id=INVENTORY_LIST_OPERATION_DEFINITION_ID)
    _require_inventory_list_execution(private, profile_id=profile_id)
    _require_inventory_list_receipt(receipt)
    return InventoryListProjection(
        profile_id=profile_id,
        rows=tuple(
            InventoryListRowProjection(
                actividad_id=row.actividad_id,
                year=row.year,
                valuation_method=row.valuation_method,
                opening_stock=PublicDecimal(decimal=str(row.opening_stock)),
                movement_count=row.movement_count,
                label=row.label,
                retired=row.retired,
                retirement_reason=row.retirement_reason,
                correction_count=row.correction_count,
                advisories=inventory_advisories(year=row.year, leaves_year_unresolved=row.leaves_year_unresolved),
            )
            for row in private.rows
        ),
    )


def _require_inventory_list_execution(
    private: InventoryOperationExecutionResult,
    *,
    profile_id: UUID,
) -> None:
    if private.operation_id != "list" or private.outcome != "success" or private.profile_id != profile_id:
        raise ValueError("inventory list result contradicts its terminal receipt")


def _require_inventory_list_receipt(receipt: OperationTerminalReceipt) -> None:
    message = "inventory list result contradicts its terminal receipt"
    if (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError(message)
    require_succeeded_receipt_references(receipt, message=message)


def _validate_refusal_receipt(
    *,
    private: InventoryOperationExecutionResult,
    receipt: OperationTerminalReceipt,
    profile_id: UUID,
    definition_id: str,
    operation_id: InventoryOperationId,
) -> InventoryRefusalProjection:
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
    if _OPERATION_IDS_BY_DEFINITION[definition_id] != operation_id:
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


def _validate_ledger_success(
    *,
    private: InventoryOperationExecutionResult,
    receipt: OperationTerminalReceipt,
    profile_id: UUID,
    operation_id: _LedgerResultOperationId,
    definition_id: str,
) -> InventoryLedgerResult:
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
    _require_inventory_ledger_receipt(
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


def _require_inventory_ledger_receipt(
    receipt: OperationTerminalReceipt,
    *,
    expected_effect: OperationEffect,
    definition_id: str,
) -> None:
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


def project_inventory_create_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> InventoryCreateProjection:
    """Release redacted ledger data or a typed create refusal."""
    private = _execution_result(result)
    profile_id = _profile_from_receipt(receipt, definition_id=INVENTORY_CREATE_OPERATION_DEFINITION_ID)
    if private.outcome == "refused":
        refusal = _validate_refusal_receipt(
            private=private,
            receipt=receipt,
            profile_id=profile_id,
            definition_id=INVENTORY_CREATE_OPERATION_DEFINITION_ID,
            operation_id="create",
        )
        return InventoryCreateProjection(outcome="refused", profile_id=profile_id, refusal=refusal)
    ledger_result = _validate_ledger_success(
        private=private,
        receipt=receipt,
        profile_id=profile_id,
        operation_id="create",
        definition_id=INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    )
    if not ledger_result.changed:
        raise ValueError("inventory create result reports no change")
    ledger = InventoryLedgerProjection.from_ledger(
        ledger_result.ledger,
        bucket_event_ids=ledger_result.bucket_event_ids,
    )
    return InventoryCreateProjection(
        outcome="created",
        profile_id=profile_id,
        ledger=ledger,
        bucket_event_ids=ledger_result.bucket_event_ids,
    )


def project_inventory_movement_add_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> InventoryMovementAddProjection:
    """Release redacted movement data or a typed movement refusal."""
    private = _execution_result(result)
    profile_id = _profile_from_receipt(receipt, definition_id=INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID)
    if private.outcome == "refused":
        refusal = _validate_refusal_receipt(
            private=private,
            receipt=receipt,
            profile_id=profile_id,
            definition_id=INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
            operation_id="movement.add",
        )
        return InventoryMovementAddProjection(outcome="refused", profile_id=profile_id, refusal=refusal)
    ledger_result = _validate_ledger_success(
        private=private,
        receipt=receipt,
        profile_id=profile_id,
        operation_id="movement.add",
        definition_id=INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
    )
    if not ledger_result.changed:
        raise ValueError("inventory movement result reports no change")
    ledger = InventoryLedgerProjection.from_ledger(
        ledger_result.ledger,
        bucket_event_ids=ledger_result.bucket_event_ids,
    )
    return InventoryMovementAddProjection(
        outcome="added",
        profile_id=profile_id,
        ledger=ledger,
        bucket_event_ids=ledger_result.bucket_event_ids,
    )


def project_inventory_inspect_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> InventoryInspectProjection:
    """Release one redacted ledger with its history, or the typed not-found refusal."""
    private = _execution_result(result)
    profile_id = _profile_from_receipt(receipt, definition_id=INVENTORY_INSPECT_OPERATION_DEFINITION_ID)
    if private.outcome == "refused":
        refusal = _validate_refusal_receipt(
            private=private,
            receipt=receipt,
            profile_id=profile_id,
            definition_id=INVENTORY_INSPECT_OPERATION_DEFINITION_ID,
            operation_id="inspect",
        )
        return InventoryInspectProjection(outcome="refused", profile_id=profile_id, refusal=refusal)
    ledger_result = private.ledger_result
    if private.operation_id != "inspect" or private.profile_id != profile_id or ledger_result is None:
        raise ValueError("inventory inspect result contradicts its terminal receipt")
    _require_inventory_ledger_receipt(
        receipt,
        expected_effect=OperationEffect.NONE,
        definition_id=INVENTORY_INSPECT_OPERATION_DEFINITION_ID,
    )
    return InventoryInspectProjection(
        outcome="found",
        profile_id=profile_id,
        ledger=InventoryLedgerProjection.from_ledger(ledger_result.ledger, with_acquisition_detail=True),
    )


def project_inventory_ledger_change_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> InventoryLedgerChangeProjection:
    """Release the ledger after one edit, rectification, retirement or restoration, or its refusal."""
    private = _execution_result(result)
    definition_id = receipt.identity.definition_id
    operation_id = private.operation_id
    if not _is_ledger_change_operation(operation_id) or _OPERATION_IDS_BY_DEFINITION.get(definition_id) != operation_id:
        raise ValueError("inventory change result contradicts its terminal receipt")
    profile_id = _profile_from_receipt(receipt, definition_id=definition_id)
    if private.outcome == "refused":
        refusal = _validate_refusal_receipt(
            private=private,
            receipt=receipt,
            profile_id=profile_id,
            definition_id=definition_id,
            operation_id=operation_id,
        )
        return InventoryLedgerChangeProjection(outcome="refused", profile_id=profile_id, refusal=refusal)
    ledger_result = _validate_ledger_success(
        private=private,
        receipt=receipt,
        profile_id=profile_id,
        operation_id=operation_id,
        definition_id=definition_id,
    )
    return InventoryLedgerChangeProjection(
        outcome="applied" if ledger_result.changed else "replayed",
        profile_id=profile_id,
        ledger=InventoryLedgerProjection.from_ledger(
            ledger_result.ledger,
            bucket_event_ids=ledger_result.bucket_event_ids,
        ),
        bucket_event_ids=ledger_result.bucket_event_ids,
    )


def project_inventory_valuation_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> InventoryValuationOperationProjection:
    """Release valuation facts only after the exact audited effect settles."""
    private = _execution_result(result)
    profile_id = _profile_from_receipt(receipt, definition_id=INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID)
    if private.outcome == "refused":
        refusal = _validate_refusal_receipt(
            private=private,
            receipt=receipt,
            profile_id=profile_id,
            definition_id=INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
            operation_id="valuation.preview",
        )
        return InventoryValuationOperationProjection(outcome="refused", refusal=refusal)
    preview_result = _require_inventory_valuation_execution(private, profile_id=profile_id)
    _require_inventory_valuation_receipt(receipt, preview_result=preview_result)
    preview = preview_result.preview
    return InventoryValuationOperationProjection(
        outcome="previewed",
        preview=InventoryValuationPreviewProjection(
            profile_id=profile_id,
            actividad_id=preview.actividad_id,
            year=preview.year,
            valuation_method=preview.valuation_method,
            derived_closing_value=PublicDecimal(decimal=str(preview.derived_closing_value)),
            cogs=PublicDecimal(decimal=str(preview.cogs)),
            bucket_event_ids=preview_result.bucket_event_ids,
        ),
    )


def _require_inventory_valuation_execution(
    private: InventoryOperationExecutionResult,
    *,
    profile_id: UUID,
) -> InventoryValuationPreviewResult:
    preview_result = private.valuation_result
    if (
        private.operation_id != "valuation.preview"
        or private.outcome != "success"
        or private.profile_id != profile_id
        or preview_result is None
    ):
        raise ValueError("inventory valuation result contradicts its terminal receipt")
    return preview_result


def _require_inventory_valuation_receipt(
    receipt: OperationTerminalReceipt,
    *,
    preview_result: InventoryValuationPreviewResult,
) -> None:
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


def project_inventory_closing_authority_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> InventoryClosingAuthorityOperationProjection:
    """Release only closing fingerprints and the repository's actual changed flag."""
    return _project_closing_record(
        result,
        receipt,
        definition_id=INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
        operation_id="closing-authority.record",
    )


def project_inventory_closing_value_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> InventoryClosingAuthorityOperationProjection:
    """Release the same closing fingerprints for a record derived from plain facts."""
    return _project_closing_record(
        result,
        receipt,
        definition_id=INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID,
        operation_id="closing-value.record",
    )


def _project_closing_record(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    operation_id: Literal["closing-authority.record", "closing-value.record"],
) -> InventoryClosingAuthorityOperationProjection:
    private = _execution_result(result)
    profile_id = _profile_from_receipt(receipt, definition_id=definition_id)
    if private.outcome == "refused":
        refusal = _validate_refusal_receipt(
            private=private,
            receipt=receipt,
            profile_id=profile_id,
            definition_id=definition_id,
            operation_id=operation_id,
        )
        return InventoryClosingAuthorityOperationProjection(outcome="refused", refusal=refusal)
    result_value = _validate_ledger_success(
        private=private,
        receipt=receipt,
        profile_id=profile_id,
        operation_id=operation_id,
        definition_id=definition_id,
    )
    record = result_value.ledger.closing_authority_record
    if record is None:
        raise ValueError("inventory closing-authority result contains no persisted authority")
    return InventoryClosingAuthorityOperationProjection(
        outcome="recorded",
        record=InventoryClosingAuthorityRecordProjection(
            profile_id=profile_id,
            actividad_id=result_value.ledger.actividad_id,
            year=result_value.ledger.year,
            authority_record_fingerprint=record.fingerprint,
            decision_fingerprint=record.decision.fingerprint,
            physical_observation_fingerprint=(
                record.physical_observation.fingerprint if record.physical_observation is not None else None
            ),
            prior_closing_link_fingerprint=record.prior_closing_link.fingerprint,
            changed=bool(private.closing_changed),
        ),
    )


__all__ = [
    "project_inventory_closing_authority_result",
    "project_inventory_closing_value_result",
    "project_inventory_create_result",
    "project_inventory_inspect_result",
    "project_inventory_ledger_change_result",
    "project_inventory_list_result",
    "project_inventory_movement_add_result",
    "project_inventory_valuation_result",
]
