"""Immutable modal view models derived solely from public operation projections.

Every field here is computed from :class:`OperationPublicProjectionV1` and its
public capability, response-control, and pending-interaction fields. Nothing
in this module imports a persisted snapshot, a journal record, or any
supervisor-private state; the modal renders from these view models alone, so
a lifecycle truth (cancellable, terminal, detachable) can never be
reclassified downstream of what the projection already declares.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from ....application.operations.frontend_contracts import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
    OperationUnsupportedInteractionV1,
)
from ....core.operations import (
    OperationClosePolicy,
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)

_VIEW_MODEL_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid")

type OperationModalInteractionAffordanceV1 = Literal["none", "review_available", "unsupported"]
"""Which interaction control the modal may render, taken from the projection's
pending-interaction discriminator without reinterpreting its meaning."""

type OperationModalTerminalCopyKeyV1 = Literal[
    "operation.modal.terminal.succeeded",
    "operation.modal.terminal.succeeded_partial",
    "operation.modal.terminal.refused",
    "operation.modal.terminal.failed",
    "operation.modal.terminal.cancelled",
    "operation.modal.terminal.timed_out",
    "operation.modal.terminal.interrupted",
]
"""Locale key naming the terminal copy; the modal resolves prose through it."""

_TERMINAL_COPY_KEYS: dict[OperationTerminalCondition, OperationModalTerminalCopyKeyV1] = {
    OperationTerminalCondition.SUCCEEDED: "operation.modal.terminal.succeeded",
    OperationTerminalCondition.REFUSED: "operation.modal.terminal.refused",
    OperationTerminalCondition.FAILED: "operation.modal.terminal.failed",
    OperationTerminalCondition.CANCELLED: "operation.modal.terminal.cancelled",
    OperationTerminalCondition.TIMED_OUT: "operation.modal.terminal.timed_out",
    OperationTerminalCondition.INTERRUPTED: "operation.modal.terminal.interrupted",
}


class OperationModalViewModelV1(BaseModel):
    """Renderer-neutral, pre-derived state the generic operation modal draws.

    Every derived field is a pure function of the source projection; none
    reclassifies lifecycle truth the projection itself does not already carry.
    """

    model_config = _VIEW_MODEL_CONFIG

    projection: OperationPublicProjectionV1
    spinner_visible: bool
    cancel_control_enabled: bool
    detach_control_enabled: bool
    close_policy: OperationClosePolicy
    interaction_affordance: OperationModalInteractionAffordanceV1
    terminal_copy_key: OperationModalTerminalCopyKeyV1 | None

    @model_validator(mode="after")
    def _validate_derivation(self) -> OperationModalViewModelV1:
        projection = self.projection
        terminal = projection.lifecycle is OperationLifecycle.TERMINAL
        if self.spinner_visible == terminal:
            raise ValueError("modal spinner visibility must disagree with terminal settlement")
        if self.cancel_control_enabled != projection.cancellable_now:
            raise ValueError("modal cancel affordance must match the projection's cancellable_now fact")
        detachable = projection.close_policy is OperationClosePolicy.DETACH_ALLOWED and not terminal
        if self.detach_control_enabled != detachable:
            raise ValueError("modal detach affordance must match the projection's close policy and settlement")
        if self.close_policy is not projection.close_policy:
            raise ValueError("modal close policy must mirror the projection's declared close policy")
        expected_affordance = _interaction_affordance(projection)
        if self.interaction_affordance != expected_affordance:
            raise ValueError("modal interaction affordance must mirror the pending-interaction discriminator")
        expected_copy = _terminal_copy_key(projection) if terminal else None
        if self.terminal_copy_key != expected_copy:
            raise ValueError("modal terminal copy key must mirror the projection's terminal settlement")
        return self


def build_operation_modal_view_model(projection: OperationPublicProjectionV1) -> OperationModalViewModelV1:
    """Derive the one immutable modal view model for a public projection."""
    terminal = projection.lifecycle is OperationLifecycle.TERMINAL
    return OperationModalViewModelV1(
        projection=projection,
        spinner_visible=not terminal,
        cancel_control_enabled=projection.cancellable_now,
        detach_control_enabled=projection.close_policy is OperationClosePolicy.DETACH_ALLOWED and not terminal,
        close_policy=projection.close_policy,
        interaction_affordance=_interaction_affordance(projection),
        terminal_copy_key=_terminal_copy_key(projection) if terminal else None,
    )


def _interaction_affordance(projection: OperationPublicProjectionV1) -> OperationModalInteractionAffordanceV1:
    pending = projection.pending_interaction
    if isinstance(pending, OperationReviewAvailableInteractionV1):
        return "review_available"
    if isinstance(pending, OperationUnsupportedInteractionV1):
        return "unsupported"
    if isinstance(pending, OperationNoPendingInteractionV1):
        return "none"
    raise TypeError("unknown public pending-interaction variant")


def _terminal_copy_key(projection: OperationPublicProjectionV1) -> OperationModalTerminalCopyKeyV1:
    condition = projection.terminal_condition
    if condition is None:
        raise ValueError("terminal copy requires a settled terminal condition")
    if condition is OperationTerminalCondition.SUCCEEDED and projection.effect is OperationEffect.PARTIAL:
        return "operation.modal.terminal.succeeded_partial"
    return _TERMINAL_COPY_KEYS[condition]


__all__ = [
    "OperationModalInteractionAffordanceV1",
    "OperationModalTerminalCopyKeyV1",
    "OperationModalViewModelV1",
    "build_operation_modal_view_model",
]
