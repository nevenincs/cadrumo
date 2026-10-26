"""Private receipt-custody result schema for capital-goods operations."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.bienes_inversion.register import BienesInversionIvaRegister, BienInversionIvaRecord
from .registered_contracts import BienesInversionOperationId
from .registered_result_contracts import BienesInversionRefusalProjection


def _refused_execution_arm_is_closed(result: BienesInversionOperationExecutionResult) -> None:
    if (
        result.operation_id != "declare"
        or any(value is not None for value in (result.register_snapshot, result.record, result.count))
        or result.refusal is None
    ):
        raise ValueError("capital-goods refusal result has an incompatible payload")


def _successful_execution_arm_is_closed(result: BienesInversionOperationExecutionResult) -> None:
    if result.refusal is not None:
        raise ValueError("capital-goods success result contains a refusal")
    if result.operation_id == "list":
        if result.register_snapshot is None or result.record is not None or result.count is not None:
            raise ValueError("capital-goods list result arm is incomplete")
    elif result.register_snapshot is None or result.record is None or result.count is None:
        raise ValueError("capital-goods declaration result arm is incomplete")


class BienesInversionOperationExecutionResult(BaseModel):
    """Private result held in operation operand custody until projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operation_id: BienesInversionOperationId
    outcome: Literal["success", "refused"]
    profile_id: UUID
    register_snapshot: BienesInversionIvaRegister | None = None
    record: BienInversionIvaRecord | None = None
    count: int | None = None
    refusal: BienesInversionRefusalProjection | None = None

    @model_validator(mode="after")
    def _execution_arm_is_closed(self) -> BienesInversionOperationExecutionResult:
        if self.outcome == "refused":
            _refused_execution_arm_is_closed(self)
        else:
            _successful_execution_arm_is_closed(self)
        return self
