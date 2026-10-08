"""Canonical request, projection, and refusal shapes for inventory operations."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from .registered_projections import (
    InventoryClosingAuthorityOperationProjection,
    InventoryCreateProjection,
    InventoryListProjection,
    InventoryMovementAddProjection,
    InventoryValuationOperationProjection,
)
from .registered_requests import (
    INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CONFLICT_REFUSAL_CODE,
    INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    INVENTORY_LIST_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
    INVENTORY_NOT_FOUND_REFUSAL_CODE,
    INVENTORY_SERVICE_INPUT_REFUSAL_CODE,
    INVENTORY_VALIDATION_REFUSAL_CODE,
    INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
    InventoryClosingAuthorityRecordRequest,
    InventoryCreateRequest,
    InventoryListRequest,
    InventoryMovementAddRequest,
    InventoryValuationPreviewRequest,
)


@dataclass(frozen=True, slots=True)
class InventoryOperationShape:
    """Bind one registered request to its public projection and refusal vocabulary."""

    request_type: type[BaseModel]
    projection_type: type[BaseModel]
    refusal_codes: frozenset[str]


INVENTORY_OPERATION_SHAPES: dict[str, InventoryOperationShape] = {
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


__all__ = ["INVENTORY_OPERATION_SHAPES", "InventoryOperationShape"]
