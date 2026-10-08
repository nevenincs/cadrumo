"""Private typed inventory executor results retained under operation custody."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .service import (
    InventoryActividadSummary,
    InventoryLedgerResult,
    InventoryValuationPreviewResult,
)

if TYPE_CHECKING:
    pass

from .registered_requests import InventoryOperationId, InventoryRefusalCode, InventoryRefusalReason


class InventoryOperationRefusalDetail(BaseModel):
    """Encrypted explanation details; never contains financial inputs or prose."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: InventoryRefusalCode
    reason: InventoryRefusalReason
    actividad_id: str | None = None
    year: int | None = None
    movement_id: str | None = None
    valuation_method: str | None = None


class InventoryOperationExecutionResult(BaseModel):
    """Private typed result arm persisted under secure operation custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operation_id: InventoryOperationId
    outcome: Literal["success", "refused"]
    profile_id: UUID
    rows: tuple[InventoryActividadSummary, ...] = ()
    ledger_result: InventoryLedgerResult | None = None
    valuation_result: InventoryValuationPreviewResult | None = None
    closing_changed: bool | None = None
    refusal: InventoryOperationRefusalDetail | None = None

    @model_validator(mode="after")
    def _result_arm_is_closed(self) -> InventoryOperationExecutionResult:
        _require_inventory_result_arm(self)
        return self


def _require_inventory_result_arm(result: InventoryOperationExecutionResult) -> None:
    if result.outcome == "refused":
        _require_inventory_refusal_arm(result)
        return
    _require_inventory_success_header(result)
    _require_inventory_success_payload(result)


def _require_inventory_refusal_arm(result: InventoryOperationExecutionResult) -> None:
    if result.refusal is None or result.rows or result.ledger_result is not None or result.valuation_result is not None:
        raise ValueError("inventory refusal result contains an incompatible payload")
    if result.closing_changed is not None:
        raise ValueError("inventory refusal result contains a mutation status")


def _require_inventory_success_header(result: InventoryOperationExecutionResult) -> None:
    if result.refusal is not None:
        raise ValueError("inventory success result contains refusal detail")
    if result.operation_id != "list" and result.rows:
        raise ValueError("non-list inventory result contains list rows")


def _require_inventory_success_payload(result: InventoryOperationExecutionResult) -> None:
    if result.operation_id == "list":
        _require_inventory_list_payload(result)
        return
    if result.operation_id in {"create", "movement.add"}:
        _require_inventory_ledger_payload(result)
        return
    if result.operation_id == "valuation.preview":
        _require_inventory_valuation_payload(result)
        return
    _require_inventory_closing_authority_payload(result)


def _require_inventory_list_payload(result: InventoryOperationExecutionResult) -> None:
    if result.ledger_result is not None or result.valuation_result is not None or result.closing_changed is not None:
        raise ValueError("inventory list result contains a mutation payload")


def _require_inventory_ledger_payload(result: InventoryOperationExecutionResult) -> None:
    if result.ledger_result is None or result.valuation_result is not None or result.closing_changed is not None:
        raise ValueError("inventory ledger result arm is incomplete")


def _require_inventory_valuation_payload(result: InventoryOperationExecutionResult) -> None:
    if result.valuation_result is None or result.ledger_result is not None or result.closing_changed is not None:
        raise ValueError("inventory valuation result arm is incomplete")


def _require_inventory_closing_authority_payload(result: InventoryOperationExecutionResult) -> None:
    if result.ledger_result is None or result.valuation_result is not None or result.closing_changed is None:
        raise ValueError("inventory closing-authority result arm is incomplete")


__all__ = [
    "InventoryOperationExecutionResult",
    "InventoryOperationRefusalDetail",
]
