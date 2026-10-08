"""Bounded authorization handshakes between an owned worker and its runtime."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, RootModel, SecretBytes, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import UtcInstant
from ..operations.models import OperationId
from ..user_profile.access_contracts import (
    AccessAction,
    AccessAllowed,
    OperationAccessPolicy,
    OperationAccessRequest,
    OperationResponseScopeAllowed,
)
from ..user_profile.automation_enrollment import AutomationInventory, EnrollmentTransition
from ..user_profile.automation_operations import AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
from .profile_access import RuntimeAccessRefusal
from .worker_enrollment import (
    WorkerApprovalPhaseResult,
    WorkerApprovalPublication,
    WorkerApprovalPublished,
    WorkerApprovalReady,
    WorkerApprovalRequest,
)

AUTHORITY_SECTION_MAXIMUM_SECONDS = 30.0
WORKER_AUTOMATION_INVENTORY_MAX_BYTES = 32 * 1024
"""Conservative complete-inventory IPC limit, below the native 64 KiB frame."""


class WorkerAuthorizationRequest(BaseModel):
    """Operation-owner coordinates supplied only over a kernel-verified worker connection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["authorize"] = "authorize"
    request_id: UUID
    connection_id: UUID
    session_id: UUID
    operation_id: OperationId
    request: OperationAccessRequest
    policy: OperationAccessPolicy


class WorkerResponseScopeRequest(BaseModel):
    """Profile scope for a response; no claim about the worker's transaction bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["response_scope"] = "response_scope"
    request_id: UUID
    connection_id: UUID
    session_id: UUID
    operation_id: OperationId
    request: OperationAccessRequest
    policy: OperationAccessPolicy

    @model_validator(mode="after")
    def _require_response(self) -> WorkerResponseScopeRequest:
        if self.request.action is not AccessAction.RESPOND:
            raise ValueError("response scope requires a response action")
        return self


class WorkerAutomationInventoryRequest(BaseModel):
    """Ask the runtime owner for one human-only inventory under a held fence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["automation_inventory"] = "automation_inventory"
    request_id: UUID
    connection_id: UUID
    session_id: UUID
    operation_id: OperationId
    request: OperationAccessRequest
    policy: OperationAccessPolicy

    @model_validator(mode="after")
    def _require_inventory_start(self) -> WorkerAutomationInventoryRequest:
        if (
            self.request.action is not AccessAction.START
            or self.request.definition_id != AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
            or self.policy.definition_id != self.request.definition_id
        ):
            raise ValueError("automation inventory requires its registered START action")
        return self


type WorkerAuthorityRequest = Annotated[
    WorkerAuthorizationRequest | WorkerResponseScopeRequest, Field(discriminator="kind")
]


type WorkerAuthorityEnvelopeRequest = Annotated[
    WorkerAuthorizationRequest | WorkerResponseScopeRequest | WorkerAutomationInventoryRequest | WorkerApprovalRequest,
    Field(discriminator="kind"),
]


class WorkerAuthorityEnvelope(RootModel[WorkerAuthorityEnvelopeRequest]):
    """Closed internal admission requests, accepted only from the owned worker."""


class WorkerAuthorizationPermit(BaseModel):
    """One held fence on this native connection, never a transferable capability."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["authorized"] = "authorized"
    request_id: UUID
    runtime_boot_id: UUID
    permit_id: UUID
    expires_at: UtcInstant


class WorkerResponseScopePermit(BaseModel):
    """Held profile scope only; never a response capability or an effect permit."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["response_scope_held"] = "response_scope_held"
    request_id: UUID
    runtime_boot_id: UUID
    permit_id: UUID
    expires_at: UtcInstant


class WorkerAutomationInventoryPermit(BaseModel):
    """Human inventory released only while this native authorization is held."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["automation_inventory_held"] = "automation_inventory_held"
    request_id: UUID
    runtime_boot_id: UUID
    permit_id: UUID
    expires_at: UtcInstant
    inventory: AutomationInventory


@dataclass(frozen=True, slots=True)
class WorkerAutomationInventoryAllowed:
    """Trusted parent result, scoped to one connection's live human authority."""

    expires_at: UtcInstant
    inventory: AutomationInventory


class WorkerAuthorizationRelease(BaseModel):
    """Release one exact held fence; this says nothing about rollback or domain outcome."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["release"] = "release"
    request_id: UUID
    permit_id: UUID


class WorkerAuthorizationReleased(BaseModel):
    """Acknowledge release only after the authority guard has exited."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["released"] = "released"
    request_id: UUID
    permit_id: UUID


class WorkerAuthorizationInstruction(
    RootModel[Annotated[WorkerAuthorizationRelease | WorkerApprovalPublication, Field(discriminator="kind")]]
):
    """Only explicit release or an exact approval phase may use a held fence."""


class WorkerAuthorizationAcknowledgement(BaseModel):
    """Confirm consumption before a native pipe server closes its reply buffer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["acknowledge"] = "acknowledge"
    request_id: UUID


class WorkerAuthorizationReply(
    RootModel[
        Annotated[
            WorkerAuthorizationPermit
            | WorkerResponseScopePermit
            | WorkerAutomationInventoryPermit
            | WorkerAuthorizationReleased
            | WorkerApprovalReady
            | WorkerApprovalPhaseResult
            | WorkerApprovalPublished
            | RuntimeAccessRefusal,
            Field(discriminator="kind"),
        ]
    ]
):
    """The closed internal reply union for authorization, refusal and release."""


class WorkerAuthorizationOwner(Protocol):
    """Thread-affine application guard called only for the exact owned worker."""

    def authorize(
        self, request: WorkerAuthorityRequest
    ) -> AbstractContextManager[AccessAllowed | OperationResponseScopeAllowed]:
        """Evaluate current authority and retain the fence until release or containment."""
        ...

    def automation_inventory(
        self, request: WorkerAutomationInventoryRequest
    ) -> AbstractContextManager[WorkerAutomationInventoryAllowed]:
        """Read inventory for the original human session while its fence is held."""
        ...

    def approval_preflight(self, request: WorkerApprovalRequest) -> None:
        """Validate current human authority before accepting any protected proof."""
        ...

    def approval_phase(self, request: WorkerApprovalRequest, password: SecretBytes | None) -> bool | None:
        """Run proof or delivery without holding the profile publication fence."""
        ...

    def approval_publication(
        self, authority: WorkerAuthorizationRequest, command: WorkerApprovalPublication
    ) -> EnrollmentTransition | None:
        """Run one canonical phase on the thread already holding COMMIT authority."""
        ...
