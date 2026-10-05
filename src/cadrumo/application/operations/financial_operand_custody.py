"""Amount-free typed custody checkpoints and their fixed transition order."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import CadrumoError, pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.utc import validate_utc_aware
from .financial_operand_contract import OperationTransientFinancialOperandRequirementV1


class OperationFinancialOperandCustodyState(StrEnum):
    """The fixed custody order one operand wait advances through."""

    AWAITING_SUBMISSION = "awaiting_submission"
    BOUND = "bound"
    DELIVERY_STARTED = "delivery_started"
    DELIVERY_ACKNOWLEDGED = "delivery_acknowledged"
    RELEASED = "released"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


_LEGAL_TRANSITIONS: dict[
    OperationFinancialOperandCustodyState,
    frozenset[OperationFinancialOperandCustodyState],
] = {
    OperationFinancialOperandCustodyState.AWAITING_SUBMISSION: frozenset(
        {
            OperationFinancialOperandCustodyState.BOUND,
            OperationFinancialOperandCustodyState.EXPIRED,
            OperationFinancialOperandCustodyState.CANCELLED,
        }
    ),
    OperationFinancialOperandCustodyState.BOUND: frozenset(
        {
            OperationFinancialOperandCustodyState.DELIVERY_STARTED,
            OperationFinancialOperandCustodyState.EXPIRED,
            OperationFinancialOperandCustodyState.CANCELLED,
        }
    ),
    OperationFinancialOperandCustodyState.DELIVERY_STARTED: frozenset(
        {OperationFinancialOperandCustodyState.DELIVERY_ACKNOWLEDGED}
    ),
    OperationFinancialOperandCustodyState.DELIVERY_ACKNOWLEDGED: frozenset(
        {OperationFinancialOperandCustodyState.RELEASED}
    ),
    OperationFinancialOperandCustodyState.RELEASED: frozenset(),
    OperationFinancialOperandCustodyState.EXPIRED: frozenset(),
    OperationFinancialOperandCustodyState.CANCELLED: frozenset(),
}


class OperationFinancialOperandCustodyError(CadrumoError):
    """Raised when a custody advance would break the fixed transition order."""


class OperationFinancialOperandCustodyCheckpointV1(BaseModel):
    """Exact current typed handoff position, with no operand or content digest."""

    model_config = STRICT_FROZEN_CONFIG

    requirement: OperationTransientFinancialOperandRequirementV1
    sequence: Annotated[int, Field(ge=1)]
    state: OperationFinancialOperandCustodyState
    recorded_at: datetime

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_recorded_at(self) -> OperationFinancialOperandCustodyCheckpointV1:
        validate_utc_aware(self.recorded_at)
        return self

    def successor(
        self, state: OperationFinancialOperandCustodyState, *, now: datetime
    ) -> OperationFinancialOperandCustodyCheckpointV1:
        """Advance only through the fixed custody order without changing its binding."""
        if state not in _LEGAL_TRANSITIONS[self.state] or now < self.recorded_at:
            raise OperationFinancialOperandCustodyError("typed financial custody transition refused")
        return OperationFinancialOperandCustodyCheckpointV1(
            requirement=self.requirement,
            sequence=self.sequence + 1,
            state=state,
            recorded_at=now,
        )
