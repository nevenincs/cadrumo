"""Bounded authorization handshakes between an owned worker and its runtime."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, RootModel, SecretBytes, model_validator

from cadrumo.application.operations.models import OperationId
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.application.user_profile.automation_enrollment import AutomationInventory, EnrollmentTransition
from cadrumo.application.user_profile.automation_operations import AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
from cadrumo.core.identity.digest import ContentDigest
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from cadrumo.core.time.utc import UtcInstant
from cadrumo_client.contracts.access_refusals import AccessAllowed, OperationResponseScopeAllowed
from cadrumo_client.contracts.access_vocabulary import AccessAction, OperationAccessPolicy, OperationAccessRequest
from cadrumo_client.contracts.model_runs import MODEL_RUN_MAX_BODY_BYTES, ModelRunHeader, ModelRunOutcome
from cadrumo_client.contracts.profile_access import AccessRefusal

from .worker_enrollment import (
    WorkerApprovalPhaseResult,
    WorkerApprovalPublication,
    WorkerApprovalPublished,
    WorkerApprovalReady,
    WorkerApprovalRequest,
)

WORKER_AUTOMATION_INVENTORY_MAX_BYTES = 1024 * 1024
"""Largest complete inventory the runtime releases; its permit travels in bounded chunks."""

WORKER_AUTOMATION_INVENTORY_PERMIT_MAX_BYTES = WORKER_AUTOMATION_INVENTORY_MAX_BYTES + 1024
"""Largest inventory permit: the inventory plus its fixed permit fields."""


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


class RuntimeHumanReviewClaimAttestation(BaseModel):
    """Parent-issued person evidence carried only on its verified worker transport."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    worker_id: UUID
    profile_binding: ProfileAccessBinding
    runtime_boot_id: UUID
    connection_id: UUID
    session_id: UUID
    frontend: OperationFrontendProjection
    source_ref: Annotated[str, Field(min_length=1, max_length=256)]
    verified_at: UtcInstant


class WorkerHumanReviewScopeRequest(BaseModel):
    """One held fence for both the original invocation and its verified human responder."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["human_review_scope"] = "human_review_scope"
    request_id: UUID
    connection_id: UUID
    session_id: UUID
    operation_id: OperationId
    request: OperationAccessRequest
    policy: OperationAccessPolicy
    invocation: WorkerAuthorizationRequest
    review: WorkerAuthorizationRequest
    attestation: RuntimeHumanReviewClaimAttestation

    @model_validator(mode="after")
    def _require_review_scope(self) -> WorkerHumanReviewScopeRequest:
        if not self._invocation_matches() or not self._claimant_matches():
            raise ValueError("human review requires exact claimant and original invocation")
        return self

    def _invocation_matches(self) -> bool:
        """Require the original START invocation for the exact reviewed operation."""
        return (
            self.request.action is AccessAction.RESPOND
            and self.invocation.request.action is AccessAction.START
            and self.invocation.request.definition_id == self.request.definition_id
            and self.invocation.operation_id == self.operation_id
            and self.invocation.request.profile_id == self.request.profile_id
        )

    def _claimant_matches(self) -> bool:
        """Match review, response and native attestation to the same human claimant."""
        return (
            self.review.request.action is AccessAction.REVIEW
            and self.review.operation_id == self.operation_id
            and self.review.request.definition_id == self.request.definition_id
            and self.review.request.profile_id == self.request.profile_id
            and self.review.session_id == self.session_id
            and self.review.connection_id == self.connection_id
            and self._claimant_identity_matches()
        )

    def _claimant_identity_matches(self) -> bool:
        """Match frontend, destination and attested connection identity."""
        return (
            self.review.request.frontend == self.request.frontend
            and self.request.frontend == self.attestation.frontend
            and self.review.request.destination_id == self.request.destination_id
            and self.attestation.connection_id == self.connection_id
            and self.attestation.session_id == self.session_id
        )


WORKER_OPERATIONS_ADVANCED_MAX = 64
"""Operations one progress report may name; a busier worker sends another."""


class WorkerOperationsAdvanced(BaseModel):
    """Operations whose journal the worker has committed since its last report.

    It names operations only and grants nothing: the runtime cues the
    connections observing them, which then observe again under their own
    authority.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["operations_advanced"] = "operations_advanced"
    request_id: UUID
    operation_ids: Annotated[tuple[OperationId, ...], Field(min_length=1, max_length=WORKER_OPERATIONS_ADVANCED_MAX)]
    records_changed: bool = False


type WorkerAuthorityRequest = Annotated[
    WorkerAuthorizationRequest | WorkerResponseScopeRequest | WorkerHumanReviewScopeRequest, Field(discriminator="kind")
]


class WorkerAuthorityCheck(BaseModel):
    """Ask whether one stage is admitted now, for a caller that runs no body under the answer.

    The runtime evaluates admission and answers at once. It holds no fence and
    issues no permit, so a COMMIT, whose fence is what it asks for, is never
    checked this way.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["check"] = "check"
    authority: WorkerAuthorityRequest

    @model_validator(mode="after")
    def _refuse_commit(self) -> WorkerAuthorityCheck:
        if self.authority.request.action is AccessAction.COMMIT:
            raise ValueError("a COMMIT holds its fence and is never only checked")
        return self


type WorkerAuthorityEnvelopeRequest = Annotated[
    WorkerAuthorizationRequest
    | WorkerResponseScopeRequest
    | WorkerHumanReviewScopeRequest
    | WorkerAutomationInventoryRequest
    | WorkerApprovalRequest
    | WorkerOperationsAdvanced
    | WorkerAuthorityCheck,
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


class WorkerAuthorityChecked(BaseModel):
    """Admission held when the runtime answered; nothing is held once this is sent."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["checked"] = "checked"
    request_id: UUID
    runtime_boot_id: UUID
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


class WorkerAutomationInventoryTransfer(BaseModel):
    """Announce one inventory permit, which follows as ordered chunks of its canonical JSON.

    The worker accepts the permit only when the chunks reproduce this byte
    count and digest and the permit names this request, boot and permit.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["automation_inventory_transfer"] = "automation_inventory_transfer"
    request_id: UUID
    runtime_boot_id: UUID
    permit_id: UUID
    byte_count: Annotated[int, Field(ge=2, le=WORKER_AUTOMATION_INVENTORY_PERMIT_MAX_BYTES)]
    payload_digest: ContentDigest


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


class WorkerModelRun(BaseModel):
    """Ask the runtime to have the profile's agent service answer one lookup, selections read or run.

    Sent under a held START permit. A lookup names its role and carries no
    header and no body; a selections read names no role and carries neither;
    a run's body follows on secret frames. Nothing here, and nothing in the
    reply, is a credential.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["model_run"] = "model_run"
    request_id: UUID
    permit_id: UUID
    command_id: UUID
    role: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")] | None
    header: ModelRunHeader | None = None
    body_byte_count: Annotated[NonNegativeInt, Field(le=MODEL_RUN_MAX_BODY_BYTES)] = 0

    @model_validator(mode="after")
    def _run_carries_a_body(self) -> WorkerModelRun:
        if (self.header is None) != (self.body_byte_count == 0):
            raise ValueError("a run carries a body and a lookup carries none")
        if self.header is not None and self.header.role != self.role:
            raise ValueError("a run names the role its header names")
        return self


class WorkerModelRunResult(BaseModel):
    """The service's answer to one model-run instruction; served reply text follows on secret frames."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["model_run_result"] = "model_run_result"
    request_id: UUID
    permit_id: UUID
    command_id: UUID
    runtime_boot_id: UUID
    outcome: ModelRunOutcome


class WorkerAuthorizationInstruction(
    RootModel[
        Annotated[
            WorkerAuthorizationRelease | WorkerApprovalPublication | WorkerModelRun,
            Field(discriminator="kind"),
        ]
    ]
):
    """Only explicit release, an approval phase or a model run may use a held fence."""


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
            | WorkerAutomationInventoryTransfer
            | WorkerAuthorityChecked
            | WorkerAuthorizationReleased
            | WorkerApprovalReady
            | WorkerApprovalPhaseResult
            | WorkerApprovalPublished
            | AccessRefusal,
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

    def operations_advanced(self, operation_ids: tuple[OperationId, ...], *, records_changed: bool = False) -> None:
        """Cue the connections observing these operations of the worker's profile; never blocks."""
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

    def model_run(
        self, authority: WorkerAuthorizationRequest, command: WorkerModelRun, body: bytearray
    ) -> tuple[ModelRunOutcome, bytearray]:
        """Have the profile's admitted agent service answer one lookup or run; blocks until it does."""
        ...
