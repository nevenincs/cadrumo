"""Immutable modal view models derived solely from public operation projections.

Every field here is computed from :class:`OperationPublicProjectionV1` and its
public capability, response-control, and pending-interaction fields. Nothing
in this module imports a persisted snapshot, a journal record, or any
supervisor-private state; the modal renders from these view models alone, so
a lifecycle truth (cancellable, terminal, detachable) can never be
reclassified downstream of what the projection already declares.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator

from ....application.operations.events import OperationEventCode
from ....application.operations.frontend_contracts import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
    OperationUnsupportedInteractionV1,
)
from ....application.operations.models import OperationDiagnosticReference, OperationReference
from ....core import STRICT_FROZEN_CONFIG
from ....core.operations import (
    OperationClosePolicy,
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)

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

type OperationModalReceiptKindV1 = Literal["result", "refusal"]
"""Which settled reference the modal is showing.

The projection refuses to carry a result and a refusal together, so a
settled operation has at most one receipt. Collapsing the two fields into
one reference plus this discriminator is the whole derivation: it makes
the mutual exclusion the contract already guarantees impossible to render
wrongly, rather than leaving two nullable fields for a renderer to show
side by side."""

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

    model_config = STRICT_FROZEN_CONFIG

    projection: OperationPublicProjectionV1
    spinner_visible: bool
    cancel_control_enabled: bool
    detach_control_enabled: bool
    close_policy: OperationClosePolicy
    interaction_affordance: OperationModalInteractionAffordanceV1
    terminal_copy_key: OperationModalTerminalCopyKeyV1 | None
    phase_code: OperationEventCode | None
    execution_deadline_at: datetime | None
    cleanup_deadline_at: datetime | None
    diagnostic_ref: OperationDiagnosticReference | None
    receipt_kind: OperationModalReceiptKindV1 | None
    receipt_ref: OperationReference | None

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
        if self.phase_code != projection.phase_code:
            raise ValueError("modal phase must mirror the projection's declared phase")
        if self.execution_deadline_at != projection.execution_deadline_at:
            raise ValueError("modal execution deadline must mirror the projection's execution deadline")
        if self.cleanup_deadline_at != projection.cleanup_deadline_at:
            raise ValueError("modal cleanup deadline must mirror the projection's cleanup deadline")
        if self.diagnostic_ref != projection.diagnostic_ref:
            raise ValueError("modal diagnostic reference must mirror the projection's diagnostic reference")
        # Read the settled reference straight off the projection rather than
        # through the builder's helper. Sharing that helper would make this
        # check agree with the builder by construction, so a defect inside
        # the helper itself would pass unseen.
        if projection.result_ref is not None:
            expected_kind, expected_ref = "result", projection.result_ref
        elif projection.refusal_ref is not None:
            expected_kind, expected_ref = "refusal", projection.refusal_ref
        else:
            expected_kind, expected_ref = None, None
        if self.receipt_kind != expected_kind:
            raise ValueError("modal receipt kind must mirror which settled reference the projection carries")
        if self.receipt_ref != expected_ref:
            raise ValueError("modal receipt reference must mirror the projection's settled reference")
        return self


def build_operation_modal_view_model(projection: OperationPublicProjectionV1) -> OperationModalViewModelV1:
    """Derive the one immutable modal view model for a public projection."""
    terminal = projection.lifecycle is OperationLifecycle.TERMINAL
    receipt_kind, receipt_ref = _terminal_receipt(projection)
    return OperationModalViewModelV1(
        projection=projection,
        spinner_visible=not terminal,
        cancel_control_enabled=projection.cancellable_now,
        detach_control_enabled=projection.close_policy is OperationClosePolicy.DETACH_ALLOWED and not terminal,
        close_policy=projection.close_policy,
        interaction_affordance=_interaction_affordance(projection),
        terminal_copy_key=_terminal_copy_key(projection) if terminal else None,
        phase_code=projection.phase_code,
        execution_deadline_at=projection.execution_deadline_at,
        cleanup_deadline_at=projection.cleanup_deadline_at,
        diagnostic_ref=projection.diagnostic_ref,
        receipt_kind=receipt_kind,
        receipt_ref=receipt_ref,
    )


def _terminal_receipt(
    projection: OperationPublicProjectionV1,
) -> tuple[OperationModalReceiptKindV1 | None, OperationReference | None]:
    """Return the one settled reference the projection carries, and its kind."""
    if projection.result_ref is not None:
        return "result", projection.result_ref
    if projection.refusal_ref is not None:
        return "refusal", projection.refusal_ref
    return None, None


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
    "OperationModalReceiptKindV1",
    "OperationModalTerminalCopyKeyV1",
    "OperationModalViewModelV1",
    "build_operation_modal_view_model",
]
