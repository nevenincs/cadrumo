"""Canonical request, projection, and refusal shapes for inventory operations."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from .registered_projections import (
    InventoryClosingAuthorityOperationProjection,
    InventoryCreateProjection,
    InventoryInspectProjection,
    InventoryLedgerChangeProjection,
    InventoryListProjection,
    InventoryMovementAddProjection,
    InventoryValuationOperationProjection,
)
from .registered_requests import (
    INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CONFLICT_REFUSAL_CODE,
    INVENTORY_CORRECT_OPERATION_DEFINITION_ID,
    INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    INVENTORY_DESCRIBE_OPERATION_DEFINITION_ID,
    INVENTORY_INSPECT_OPERATION_DEFINITION_ID,
    INVENTORY_LIST_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_CORRECT_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_REVERSE_OPERATION_DEFINITION_ID,
    INVENTORY_NOT_FOUND_REFUSAL_CODE,
    INVENTORY_RESTORE_OPERATION_DEFINITION_ID,
    INVENTORY_RETIRE_OPERATION_DEFINITION_ID,
    INVENTORY_SERVICE_INPUT_REFUSAL_CODE,
    INVENTORY_VALIDATION_REFUSAL_CODE,
    INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
    InventoryClosingAuthorityRecordRequest,
    InventoryClosingValueRecordRequest,
    InventoryCorrectRequest,
    InventoryCreateRequest,
    InventoryDescribeRequest,
    InventoryInspectRequest,
    InventoryListRequest,
    InventoryMovementAddRequest,
    InventoryMovementCorrectRequest,
    InventoryMovementReverseRequest,
    InventoryRestoreRequest,
    InventoryRetireRequest,
    InventoryValuationPreviewRequest,
)


@dataclass(frozen=True, slots=True)
class InventoryOperationShape:
    """Bind one registered request to its public projection and refusal vocabulary."""

    request_type: type[BaseModel]
    projection_type: type[BaseModel]
    refusal_codes: frozenset[str]


_LEDGER_CHANGE_REFUSAL_CODES = frozenset(
    {INVENTORY_VALIDATION_REFUSAL_CODE, INVENTORY_SERVICE_INPUT_REFUSAL_CODE, INVENTORY_NOT_FOUND_REFUSAL_CODE}
)

INVENTORY_LEDGER_CHANGE_REQUEST_TYPES: dict[str, type[BaseModel]] = {
    INVENTORY_DESCRIBE_OPERATION_DEFINITION_ID: InventoryDescribeRequest,
    INVENTORY_CORRECT_OPERATION_DEFINITION_ID: InventoryCorrectRequest,
    INVENTORY_MOVEMENT_CORRECT_OPERATION_DEFINITION_ID: InventoryMovementCorrectRequest,
    INVENTORY_MOVEMENT_REVERSE_OPERATION_DEFINITION_ID: InventoryMovementReverseRequest,
    INVENTORY_RETIRE_OPERATION_DEFINITION_ID: InventoryRetireRequest,
    INVENTORY_RESTORE_OPERATION_DEFINITION_ID: InventoryRestoreRequest,
}
"""Every operation settling as an :class:`InventoryLedgerChangeProjection`."""

INVENTORY_OPERATION_SHAPES: dict[str, InventoryOperationShape] = {
    **{
        definition_id: InventoryOperationShape(
            request_type=request_type,
            projection_type=InventoryLedgerChangeProjection,
            refusal_codes=_LEDGER_CHANGE_REFUSAL_CODES,
        )
        for definition_id, request_type in INVENTORY_LEDGER_CHANGE_REQUEST_TYPES.items()
    },
    INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID: InventoryOperationShape(
        request_type=InventoryClosingValueRecordRequest,
        projection_type=InventoryClosingAuthorityOperationProjection,
        refusal_codes=_LEDGER_CHANGE_REFUSAL_CODES,
    ),
    INVENTORY_INSPECT_OPERATION_DEFINITION_ID: InventoryOperationShape(
        request_type=InventoryInspectRequest,
        projection_type=InventoryInspectProjection,
        refusal_codes=frozenset({INVENTORY_NOT_FOUND_REFUSAL_CODE}),
    ),
    INVENTORY_LIST_OPERATION_DEFINITION_ID: InventoryOperationShape(
        request_type=InventoryListRequest,
        projection_type=InventoryListProjection,
        refusal_codes=frozenset(),
    ),
    INVENTORY_CREATE_OPERATION_DEFINITION_ID: InventoryOperationShape(
        request_type=InventoryCreateRequest,
        projection_type=InventoryCreateProjection,
        refusal_codes=frozenset(
            {INVENTORY_VALIDATION_REFUSAL_CODE, INVENTORY_SERVICE_INPUT_REFUSAL_CODE, INVENTORY_CONFLICT_REFUSAL_CODE}
        ),
    ),
    INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID: InventoryOperationShape(
        request_type=InventoryMovementAddRequest,
        projection_type=InventoryMovementAddProjection,
        refusal_codes=frozenset(
            {INVENTORY_VALIDATION_REFUSAL_CODE, INVENTORY_SERVICE_INPUT_REFUSAL_CODE, INVENTORY_NOT_FOUND_REFUSAL_CODE}
        ),
    ),
    INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID: InventoryOperationShape(
        request_type=InventoryValuationPreviewRequest,
        projection_type=InventoryValuationOperationProjection,
        refusal_codes=frozenset({INVENTORY_VALIDATION_REFUSAL_CODE, INVENTORY_NOT_FOUND_REFUSAL_CODE}),
    ),
    INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID: InventoryOperationShape(
        request_type=InventoryClosingAuthorityRecordRequest,
        projection_type=InventoryClosingAuthorityOperationProjection,
        refusal_codes=frozenset(
            {INVENTORY_VALIDATION_REFUSAL_CODE, INVENTORY_SERVICE_INPUT_REFUSAL_CODE, INVENTORY_NOT_FOUND_REFUSAL_CODE}
        ),
    ),
}


__all__ = ["INVENTORY_LEDGER_CHANGE_REQUEST_TYPES", "INVENTORY_OPERATION_SHAPES", "InventoryOperationShape"]
