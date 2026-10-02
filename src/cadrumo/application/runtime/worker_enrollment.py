"""Closed worker-only approval phases; passwords have a separate byte frame."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..user_profile.access_contracts import AccessAction, OperationAccessPolicy, OperationAccessRequest
from ..user_profile.automation_enrollment import EnrollmentReceipt
from ..user_profile.automation_operations import AUTOMATION_APPROVE_OPERATION_DEFINITION_ID
from .approval_binding import RuntimeApprovalBinding

type WorkerApprovalPublicationPhase = Literal["commit_review", "publish_candidate", "activate", "decline"]
"""A guarded reviewed enrollment decision, with or without fresh-key proof."""


class WorkerApprovalRequest(BaseModel):
    """A proof, recipient or cleanup phase on an owned worker's private channel."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["approval_phase"] = "approval_phase"
    request_id: UUID
    connection_id: UUID
    session_id: UUID
    binding: RuntimeApprovalBinding
    request: OperationAccessRequest
    policy: OperationAccessPolicy
    phase: Literal["prepare", "inspect_recipient", "deliver_and_verify", "close"]

    @model_validator(mode="after")
    def _require_exact_approval(self) -> WorkerApprovalRequest:
        if (
            self.connection_id != self.binding.connection_id
            or self.session_id != self.binding.session_id
            or self.request.profile_id != self.binding.profile_binding.profile_id
            or self.request.definition_id != AUTOMATION_APPROVE_OPERATION_DEFINITION_ID
            or self.policy.definition_id != self.request.definition_id
            or self.request.action is not AccessAction.START
            or not self.policy.requires_human
        ):
            raise ValueError("approval phase requires exact human invocation authority")
        return self


class WorkerApprovalReady(BaseModel):
    """One exact peer accepts a password frame after current authority preflight."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["approval_secret_ready"] = "approval_secret_ready"
    request_id: UUID
    runtime_boot_id: UUID


class WorkerApprovalPhaseResult(BaseModel):
    """Nonsecret completion; only recipient inspection returns a boolean."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["approval_phase_completed"] = "approval_phase_completed"
    request_id: UUID
    runtime_boot_id: UUID
    needs_candidate: bool | None = None


class WorkerApprovalPublication(BaseModel):
    """An instruction usable only on the exact currently held COMMIT channel."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["approval_publication"] = "approval_publication"
    request_id: UUID
    permit_id: UUID
    command_id: UUID
    binding: RuntimeApprovalBinding
    phase: WorkerApprovalPublicationPhase


class WorkerApprovalPublished(BaseModel):
    """A publication receipt says nothing about subsequent operation settlement."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["approval_published"] = "approval_published"
    request_id: UUID
    permit_id: UUID
    command_id: UUID
    runtime_boot_id: UUID
    receipt: EnrollmentReceipt | None
    published: bool

    @model_validator(mode="after")
    def _require_receipt_for_publication(self) -> WorkerApprovalPublished:
        if self.published and self.receipt is None:
            raise ValueError("publication requires its committed receipt")
        return self
