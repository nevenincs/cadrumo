"""Non-sensitive custody checkpoints for one transient financial operand.

Custody of an operand moves through a fixed order: a wait is opened, an amount
is bound to it, delivery to the executor starts, the executor acknowledges, and
custody is released. Every step is journalled, and what is journalled is only
ever the shape of the wait - which requirement, which state, when - never the
amount. The operand contracts keep the value out of every record; this module
keeps it out of the durable record too.

The order matters because the interesting failures live between the steps. A
process that dies after delivery started but before acknowledgement cannot know
whether the executor saw the amount, so restart must classify that as uncertain
rather than guess. A wait that lapses must settle as expired even though no one
was watching. And release must happen exactly once however many supervisor
paths race for it, because a second release would clear a buffer another path
believes it still owns.

See Also:
    :class:`~cadrumo.application.operations.financial_operand.OperationTransientFinancialOperandRequirement`
        The durable, amount-free identity every checkpoint is written against.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time import validate_utc_aware
from .financial_operand import (
    OperationFinancialOperandKind,
    OperationFinancialOperandRefusalReason,
    OperationTransientFinancialOperandRequirement,
)


class OperationFinancialOperandCustodyState(StrEnum):
    """The fixed custody order one operand wait advances through."""

    AWAITING_SUBMISSION = "awaiting_submission"
    BOUND = "bound"
    DELIVERY_STARTED = "delivery_started"
    DELIVERY_ACKNOWLEDGED = "delivery_acknowledged"
    RELEASED = "released"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class OperationFinancialOperandCrashClassification(StrEnum):
    """What a restart may conclude about a wait interrupted mid-flight."""

    NOT_DELIVERED = "not_delivered"
    DELIVERY_UNCERTAIN = "delivery_uncertain"
    DELIVERED = "delivered"


_TERMINAL_STATES = frozenset(
    {
        OperationFinancialOperandCustodyState.RELEASED,
        OperationFinancialOperandCustodyState.EXPIRED,
        OperationFinancialOperandCustodyState.CANCELLED,
    }
)

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

_CRASH_CLASSIFICATION: dict[
    OperationFinancialOperandCustodyState,
    OperationFinancialOperandCrashClassification,
] = {
    OperationFinancialOperandCustodyState.AWAITING_SUBMISSION: (
        OperationFinancialOperandCrashClassification.NOT_DELIVERED
    ),
    OperationFinancialOperandCustodyState.BOUND: OperationFinancialOperandCrashClassification.NOT_DELIVERED,
    OperationFinancialOperandCustodyState.DELIVERY_STARTED: (
        OperationFinancialOperandCrashClassification.DELIVERY_UNCERTAIN
    ),
    OperationFinancialOperandCustodyState.DELIVERY_ACKNOWLEDGED: (
        OperationFinancialOperandCrashClassification.DELIVERED
    ),
}


class OperationFinancialOperandCustodyError(ValueError):
    """Raised when a custody advance would break the fixed transition order."""


class OperationFinancialOperandCustodyCheckpoint(BaseModel):
    """One journalled custody position, carrying no operand material.

    The checkpoint names the wait and its state. It deliberately has no field
    for an amount, a digest, or any other derivative, so a journal replay can
    reconstruct what happened without reconstructing what was supplied.
    """

    model_config = STRICT_FROZEN_CONFIG

    operand_kind: OperationFinancialOperandKind
    interaction_id: Annotated[str, Field(min_length=1, max_length=128)]
    sequence: Annotated[int, Field(ge=1)]
    state: OperationFinancialOperandCustodyState
    recorded_at: datetime
    refusal_reason: OperationFinancialOperandRefusalReason | None = None
    crash_classification: OperationFinancialOperandCrashClassification | None = None

    @model_validator(mode="after")
    def _validate_checkpoint(self) -> OperationFinancialOperandCustodyCheckpoint:
        validate_utc_aware(self.recorded_at)
        settled_without_delivery = self.state in {
            OperationFinancialOperandCustodyState.EXPIRED,
            OperationFinancialOperandCustodyState.CANCELLED,
        }
        if self.refusal_reason is not None and not settled_without_delivery:
            raise ValueError("only an expired or cancelled custody checkpoint may carry a refusal reason")
        return self

    @property
    def is_terminal(self) -> bool:
        """Report whether this checkpoint settles the wait for good."""
        return self.state in _TERMINAL_STATES


def open_custody(
    requirement: OperationTransientFinancialOperandRequirement,
    *,
    now: datetime,
) -> OperationFinancialOperandCustodyCheckpoint:
    """Journal the opening of one bounded wait, before any amount exists."""
    return OperationFinancialOperandCustodyCheckpoint(
        operand_kind=requirement.operand_kind,
        interaction_id=str(requirement.interaction_id),
        sequence=1,
        state=OperationFinancialOperandCustodyState.AWAITING_SUBMISSION,
        recorded_at=now,
    )


def advance_custody(
    current: OperationFinancialOperandCustodyCheckpoint,
    target: OperationFinancialOperandCustodyState,
    *,
    now: datetime,
    refusal_reason: OperationFinancialOperandRefusalReason | None = None,
) -> OperationFinancialOperandCustodyCheckpoint:
    """Advance one wait along the fixed order, refusing every other move.

    A terminal checkpoint refuses every advance, which is what makes release
    exactly-once: the second racing path to arrive finds a released checkpoint
    and is refused rather than clearing a buffer twice.
    """
    permitted = _LEGAL_TRANSITIONS[current.state]
    if target not in permitted:
        raise OperationFinancialOperandCustodyError(
            f"custody cannot advance from {current.state.value} to {target.value}"
        )
    if now < current.recorded_at:
        raise OperationFinancialOperandCustodyError("custody checkpoints cannot move backwards in time")
    return OperationFinancialOperandCustodyCheckpoint(
        operand_kind=current.operand_kind,
        interaction_id=current.interaction_id,
        sequence=current.sequence + 1,
        state=target,
        recorded_at=now,
        refusal_reason=refusal_reason,
    )


def classify_interrupted_custody(
    checkpoint: OperationFinancialOperandCustodyCheckpoint,
) -> OperationFinancialOperandCrashClassification | None:
    """Say what a restart may conclude about a wait that was cut off.

    ``None`` means the wait was already settled and needs no conclusion. A wait
    cut off between delivery starting and its acknowledgement is reported as
    uncertain, never as delivered or as not delivered, because the record
    genuinely does not say.
    """
    if checkpoint.is_terminal:
        return None
    return _CRASH_CLASSIFICATION[checkpoint.state]


def reconcile_on_restart(
    checkpoint: OperationFinancialOperandCustodyCheckpoint,
    *,
    now: datetime,
) -> OperationFinancialOperandCustodyCheckpoint:
    """Settle one interrupted wait so no custody position survives a restart.

    An unsettled wait cannot be resumed: the amount lived only in the memory of
    a process that is gone, so custody has in fact ended either way. What
    reconciliation must not do is decide what it cannot know. A wait cut off
    between delivery starting and its acknowledgement settles as released
    because the buffer is gone, and carries ``DELIVERY_UNCERTAIN`` forever
    after. Recording it as acknowledged would manufacture evidence that the
    executor saw the amount; recording it as not delivered would manufacture
    the opposite.

    This is deliberately not an :func:`advance_custody` call. The fixed order
    governs a live wait; a restart settles a wait whose owner no longer exists,
    and forcing it through the live transitions is what would tempt a caller to
    invent the missing acknowledgement.
    """
    classification = classify_interrupted_custody(checkpoint)
    if classification is None:
        return checkpoint
    settles_released = classification in {
        OperationFinancialOperandCrashClassification.DELIVERED,
        OperationFinancialOperandCrashClassification.DELIVERY_UNCERTAIN,
    }
    state = (
        OperationFinancialOperandCustodyState.RELEASED
        if settles_released
        else OperationFinancialOperandCustodyState.CANCELLED
    )
    if now < checkpoint.recorded_at:
        raise OperationFinancialOperandCustodyError("custody checkpoints cannot move backwards in time")
    return OperationFinancialOperandCustodyCheckpoint(
        operand_kind=checkpoint.operand_kind,
        interaction_id=checkpoint.interaction_id,
        sequence=checkpoint.sequence + 1,
        state=state,
        recorded_at=now,
        refusal_reason=(None if settles_released else OperationFinancialOperandRefusalReason.CANCELLED),
        crash_classification=classification,
    )


__all__ = [
    "OperationFinancialOperandCrashClassification",
    "OperationFinancialOperandCustodyCheckpoint",
    "OperationFinancialOperandCustodyError",
    "OperationFinancialOperandCustodyState",
    "advance_custody",
    "classify_interrupted_custody",
    "open_custody",
    "reconcile_on_restart",
]
