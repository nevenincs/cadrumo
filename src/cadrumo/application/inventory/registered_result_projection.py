"""Profile-bound registered operations for the canonical inventory service."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from ...core.operations import OperationEffect
from ..operations.models import OperationTerminalReceipt
from ..operations.public_scalar import PublicDecimal
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
    InventoryValuationOperationProjection,
    InventoryValuationPreviewProjection,
    inventory_advisories,
)
from .registered_requests import (
    INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    INVENTORY_INSPECT_OPERATION_DEFINITION_ID,
    INVENTORY_LIST_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
    INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
)
from .registered_result_validation import (
    OPERATION_IDS_BY_DEFINITION,
    execution_result,
    is_ledger_change_operation,
    profile_from_receipt,
    require_inventory_ledger_receipt,
    require_inventory_list_execution,
    require_inventory_list_receipt,
    require_inventory_valuation_execution,
    require_inventory_valuation_receipt,
    validate_ledger_success,
    validate_refusal_receipt,
)


def project_inventory_list_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> InventoryListProjection:
    """Release only a safe list projection correlated with its exact receipt."""
    private = execution_result(result)
    profile_id = profile_from_receipt(receipt, definition_id=INVENTORY_LIST_OPERATION_DEFINITION_ID)
    require_inventory_list_execution(private, profile_id=profile_id)
    require_inventory_list_receipt(receipt)
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


def project_inventory_create_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> InventoryCreateProjection:
    """Release redacted ledger data or a typed create refusal."""
    private = execution_result(result)
    profile_id = profile_from_receipt(receipt, definition_id=INVENTORY_CREATE_OPERATION_DEFINITION_ID)
    if private.outcome == "refused":
        refusal = validate_refusal_receipt(
            private=private,
            receipt=receipt,
            profile_id=profile_id,
            definition_id=INVENTORY_CREATE_OPERATION_DEFINITION_ID,
            operation_id="create",
        )
        return InventoryCreateProjection(outcome="refused", profile_id=profile_id, refusal=refusal)
    ledger_result = validate_ledger_success(
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
    private = execution_result(result)
    profile_id = profile_from_receipt(receipt, definition_id=INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID)
    if private.outcome == "refused":
        refusal = validate_refusal_receipt(
            private=private,
            receipt=receipt,
            profile_id=profile_id,
            definition_id=INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
            operation_id="movement.add",
        )
        return InventoryMovementAddProjection(outcome="refused", profile_id=profile_id, refusal=refusal)
    ledger_result = validate_ledger_success(
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
    private = execution_result(result)
    profile_id = profile_from_receipt(receipt, definition_id=INVENTORY_INSPECT_OPERATION_DEFINITION_ID)
    if private.outcome == "refused":
        refusal = validate_refusal_receipt(
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
    require_inventory_ledger_receipt(
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
    private = execution_result(result)
    definition_id = receipt.identity.definition_id
    operation_id = private.operation_id
    if not is_ledger_change_operation(operation_id) or OPERATION_IDS_BY_DEFINITION.get(definition_id) != operation_id:
        raise ValueError("inventory change result contradicts its terminal receipt")
    profile_id = profile_from_receipt(receipt, definition_id=definition_id)
    if private.outcome == "refused":
        refusal = validate_refusal_receipt(
            private=private,
            receipt=receipt,
            profile_id=profile_id,
            definition_id=definition_id,
            operation_id=operation_id,
        )
        return InventoryLedgerChangeProjection(outcome="refused", profile_id=profile_id, refusal=refusal)
    ledger_result = validate_ledger_success(
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
    private = execution_result(result)
    profile_id = profile_from_receipt(receipt, definition_id=INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID)
    if private.outcome == "refused":
        refusal = validate_refusal_receipt(
            private=private,
            receipt=receipt,
            profile_id=profile_id,
            definition_id=INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
            operation_id="valuation.preview",
        )
        return InventoryValuationOperationProjection(outcome="refused", refusal=refusal)
    preview_result = require_inventory_valuation_execution(private, profile_id=profile_id)
    require_inventory_valuation_receipt(receipt, preview_result=preview_result)
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
    private = execution_result(result)
    profile_id = profile_from_receipt(receipt, definition_id=definition_id)
    if private.outcome == "refused":
        refusal = validate_refusal_receipt(
            private=private,
            receipt=receipt,
            profile_id=profile_id,
            definition_id=definition_id,
            operation_id=operation_id,
        )
        return InventoryClosingAuthorityOperationProjection(outcome="refused", refusal=refusal)
    result_value = validate_ledger_success(
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
