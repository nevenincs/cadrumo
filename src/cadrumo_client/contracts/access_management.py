"""Credential-free native messages for profile access lifecycle management."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_projections import PublicAccessSession
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind, AutomationDenialReceipt
from cadrumo.core.identity.digest import ContentDigest
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

from .automation_lifecycle import AutomationResumeReceipt


class AutomationDeny(BaseModel):
    """Request a reduction of authority for one live human profile session."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["automation_deny"] = "automation_deny"
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    kind: AutomationDenialKind
    target_id: UUID | None = None

    @model_validator(mode="after")
    def _target(self) -> AutomationDeny:
        if (self.kind in {AutomationDenialKind.KEY, AutomationDenialKind.GRANT}) != (self.target_id is not None):
            raise ValueError("denial target does not match action")
        return self


class ProfileRecoveryPrepare(BaseModel):
    """Capture one exact profile lock generation before separate human proof."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["profile_recovery_prepare"] = "profile_recovery_prepare"
    request_id: UUID
    profile_id: UUID
    frontend: OperationFrontendProjection


class ProfileResume(BaseModel):
    """Select exact grants after a human proof on a separate secret-ready frame."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["profile_resume"] = "profile_resume"
    request_id: UUID
    profile_id: UUID
    frontend: OperationFrontendProjection
    lock_generation: Annotated[int, Field(ge=0)]
    grants: frozenset[UUID]


class SessionInventory(BaseModel):
    """Request an authorized projection of sessions for one exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["session_inventory"] = "session_inventory"
    request_id: UUID
    profile_id: UUID
    session_id: UUID


type AccessManagementRequest = Annotated[
    AutomationDeny | ProfileRecoveryPrepare | ProfileResume | SessionInventory,
    Field(discriminator="action"),
]
"""Closed management request union; identifiers never prove human authority."""


class _AccessManagementReplyIdentity(BaseModel):
    """Common verified native reply coordinates without a bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID


class AutomationDenied(_AccessManagementReplyIdentity):
    """Durable reduction receipt, not a cleanup-completion claim."""

    kind: Literal["automation_denied"] = "automation_denied"
    receipt: AutomationDenialReceipt


class ProfileRecoveryPrepared(_AccessManagementReplyIdentity):
    """Nonsecret lock state captured for one profile on this native connection."""

    kind: Literal["profile_recovery_prepared"] = "profile_recovery_prepared"
    profile_id: UUID
    lock_generation: Annotated[int, Field(ge=0)]
    globally_locked: bool


class ProfileResumed(_AccessManagementReplyIdentity):
    """Exact selected-grant resume receipt after separate human proof."""

    kind: Literal["profile_resumed"] = "profile_resumed"
    receipt: AutomationResumeReceipt


class SessionInventoryReply(_AccessManagementReplyIdentity):
    """Allowlisted session inventory for an authorized human requester."""

    kind: Literal["session_inventory_reply"] = "session_inventory_reply"
    sessions: tuple[PublicAccessSession, ...]


class SessionInventoryTransfer(_AccessManagementReplyIdentity):
    """Bounded complete inventory, correlated before receiving any scope chunks."""

    kind: Literal["session_inventory_transfer"] = "session_inventory_transfer"
    byte_count: Annotated[int, Field(ge=2, le=1_048_576)]
    payload_digest: ContentDigest


type AccessManagementReply = Annotated[
    AutomationDenied | ProfileRecoveryPrepared | ProfileResumed | SessionInventoryReply,
    Field(discriminator="kind"),
]
"""Closed nonsecret management reply union."""
