"""Credential-free native messages for profile access lifecycle management."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.registry import OperationFrontendProjection
from ..user_profile.access_projections import PublicAccessSession
from ..user_profile.automation_lifecycle import AutomationDenialKind, AutomationDenialReceipt
from ..user_profile.automation_lifecycle_service import AutomationResumeReceipt


class RuntimeAutomationDeny(BaseModel):
    """Request a reduction of authority for one live human profile session."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["automation_deny"] = "automation_deny"
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    kind: AutomationDenialKind
    target_id: UUID | None = None

    @model_validator(mode="after")
    def _target(self) -> RuntimeAutomationDeny:
        if (self.kind in {AutomationDenialKind.KEY, AutomationDenialKind.GRANT}) != (self.target_id is not None):
            raise ValueError("denial target does not match action")
        return self


class RuntimeProfileRecoveryPrepare(BaseModel):
    """Capture one exact profile lock generation before separate human proof."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["profile_recovery_prepare"] = "profile_recovery_prepare"
    request_id: UUID
    profile_id: UUID
    frontend: OperationFrontendProjection


class RuntimeProfileResume(BaseModel):
    """Select exact grants after a human proof on a separate secret-ready frame."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["profile_resume"] = "profile_resume"
    request_id: UUID
    profile_id: UUID
    frontend: OperationFrontendProjection
    lock_generation: Annotated[int, Field(ge=0)]
    grants: frozenset[UUID]


class RuntimeSessionInventory(BaseModel):
    """Request an authorized projection of sessions for one exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["session_inventory"] = "session_inventory"
    request_id: UUID
    profile_id: UUID
    session_id: UUID


type RuntimeAccessManagementRequest = Annotated[
    RuntimeAutomationDeny | RuntimeProfileRecoveryPrepare | RuntimeProfileResume | RuntimeSessionInventory,
    Field(discriminator="action"),
]
"""Closed management request union; identifiers never prove human authority."""


class _RuntimeAccessManagementReplyIdentity(BaseModel):
    """Common verified native reply coordinates without a bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID


class RuntimeAutomationDenied(_RuntimeAccessManagementReplyIdentity):
    """Durable reduction receipt, not a cleanup-completion claim."""

    kind: Literal["automation_denied"] = "automation_denied"
    receipt: AutomationDenialReceipt


class RuntimeProfileRecoveryPrepared(_RuntimeAccessManagementReplyIdentity):
    """Nonsecret lock state captured for one profile on this native connection."""

    kind: Literal["profile_recovery_prepared"] = "profile_recovery_prepared"
    profile_id: UUID
    lock_generation: Annotated[int, Field(ge=0)]
    globally_locked: bool


class RuntimeProfileResumed(_RuntimeAccessManagementReplyIdentity):
    """Exact selected-grant resume receipt after separate human proof."""

    kind: Literal["profile_resumed"] = "profile_resumed"
    receipt: AutomationResumeReceipt


class RuntimeSessionInventoryReply(_RuntimeAccessManagementReplyIdentity):
    """Allowlisted session inventory for an authorized human requester."""

    kind: Literal["session_inventory_reply"] = "session_inventory_reply"
    sessions: tuple[PublicAccessSession, ...]


class RuntimeSessionInventoryTransfer(_RuntimeAccessManagementReplyIdentity):
    """Bounded complete inventory, correlated before receiving any scope chunks."""

    kind: Literal["session_inventory_transfer"] = "session_inventory_transfer"
    byte_count: Annotated[int, Field(ge=2, le=1_048_576)]
    payload_digest: ContentDigest


type RuntimeAccessManagementReply = Annotated[
    RuntimeAutomationDenied | RuntimeProfileRecoveryPrepared | RuntimeProfileResumed | RuntimeSessionInventoryReply,
    Field(discriminator="kind"),
]
"""Closed nonsecret management reply union."""
