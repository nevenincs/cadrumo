"""Immutable identity of one profile worker owned by a runtime boot."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue, RootModel, model_validator

from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationResultV1,
    OperationResultProjectionRequestV1,
    OperationReviewProjectionRequestV1,
    OperationSubmissionReceiptV1,
)
from ..operations.models import OperationDefinitionId, OperationId, OperationIdentity, OperationReference
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionContractV1
from ..operations.secret_submission import OperationSecretRequirement
from ..user_profile.access_contracts import AccessDenialCode, AccessSession, ProfileAccessBinding
from ..user_profile.automation_custody_port import AutomationCustodyCode
from ..user_profile.login_session import ProfileHumanLoginReceipt, ProfileLoginOutcome
from .operation_access import OperationManagementRequest
from .projection_pages import ProjectionPage, ProjectionPageRequest
from .submission_payload import FinancialOperandInputDescriptor, SubmissionPayloadChunk, SubmissionPayloadDescriptor
from .worker_authorization import WorkerAuthorityRequest


class ProfileWorkerIdentity(BaseModel):
    """Nonsecret routing only; native ownership and custody proof remain required."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    worker_id: UUID
    runtime_boot_id: UUID
    binding: ProfileAccessBinding


class ProfileWorkerLeaseRequest(BaseModel):
    """Trusted runtime lease update; an install is followed by a separate DEK frame."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["install", "refresh", "share"]
    request_id: UUID
    lease: AccessSession


class ProfileWorkerLeaseTransferRequest(BaseModel):
    """Finite transfer of one complete lease command on the private control pipe."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["lease_transfer"] = "lease_transfer"
    request_id: UUID
    byte_count: Annotated[int, Field(ge=2, le=1_048_576)]
    payload_digest: ContentDigest


class ProfileWorkerRetireRequest(BaseModel):
    """Release one runtime-authorized lineage, without changing the worker target."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["retire"] = "retire"
    request_id: UUID
    session_id: UUID


class ProfileWorkerSettlementRequest(BaseModel):
    """Wait only for one worker-admitted rotation's canonical terminal state."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["operation_settlement"] = "operation_settlement"
    request_id: UUID
    operation_identity: OperationIdentity
    wait_seconds: Annotated[float, Field(gt=0, le=5, allow_inf_nan=False)]


class ProfileWorkerControlRequest(BaseModel):
    """Internal lifecycle control or a request for a following protected proof frame.

    A ``receipt`` request carries the originating OS login the runtime
    captured for the connection presenting the proof; the worker refuses the
    receipt unless it names that login. Other actions carry none.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["status", "stop", "password", "receipt", "cancel_human", "prepare_api"]
    request_id: UUID
    originating_login_id: Annotated[str, Field(min_length=1, max_length=256)] | None = None

    @model_validator(mode="after")
    def _login_only_for_receipt(self) -> ProfileWorkerControlRequest:
        if (self.action == "receipt") != (self.originating_login_id is not None):
            raise ValueError("only a receipt proof request carries its originating login")
        return self


class ProfileWorkerHumanBindingRequest(BaseModel):
    """Promote one exact human candidate after runtime human-session admission."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["bind_human"] = "bind_human"
    request_id: UUID
    candidate_id: UUID
    lease: AccessSession
    persist_receipt: bool = False


class ProfileWorkerHumanReceiptRequest(BaseModel):
    """Mint the receipt a bound human session left pending, after its publication.

    The runtime sends this only for a session it still publishes, under its
    admission guard, with the sign-in generation it captured at publication.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["mint_human_receipt"] = "mint_human_receipt"
    request_id: UUID
    session_id: UUID
    sign_in_lineage: UUID
    sign_in_generation: Annotated[int, Field(ge=1)]


class ProfileWorkerContractRequest(BaseModel):
    """Inspect one registered operation through a live exact-profile session."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["operation_contract"] = "operation_contract"
    request_id: UUID
    session_id: UUID
    definition_id: OperationDefinitionId


class ProfileWorkerSubmitRequest(BaseModel):
    """Private operands for exact registered decoding; policy is resolved in the worker."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["operation_submit"] = "operation_submit"
    request_id: UUID
    session_id: UUID
    frontend: OperationFrontendProjection
    definition_id: OperationDefinitionId
    subject_ref: OperationReference
    payload_json: str = Field(min_length=2, max_length=262144, repr=False)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=256, repr=False)


class ProfileWorkerSubmissionBeginRequest(BaseModel):
    """Bind a finite upload to its original runtime connection and live lease."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["operation_submit_begin"] = "operation_submit_begin"
    request_id: UUID
    upload_id: UUID
    connection_id: UUID
    session_id: UUID
    frontend: OperationFrontendProjection
    definition_id: OperationDefinitionId
    subject_ref: OperationReference
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=256, repr=False)
    descriptor: SubmissionPayloadDescriptor | FinancialOperandInputDescriptor


class ProfileWorkerSubmissionChunkRequest(BaseModel):
    """One bounded protected JSON-frame chunk for the bound upload."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["operation_submit_chunk"] = "operation_submit_chunk"
    request_id: UUID
    upload_id: UUID
    connection_id: UUID
    session_id: UUID
    chunk: SubmissionPayloadChunk


class ProfileWorkerSubmissionFinishRequest(BaseModel):
    """Verify exact staged bytes before canonical SUBMIT and fresh authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["operation_submit_finish"] = "operation_submit_finish"
    request_id: UUID
    upload_id: UUID
    connection_id: UUID
    session_id: UUID


class ProfileWorkerSubmissionAbortRequest(BaseModel):
    """Wipe only the matching upload, including after its lease was retired."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    action: Literal["operation_submit_abort"] = "operation_submit_abort"
    request_id: UUID
    upload_id: UUID
    connection_id: UUID
    session_id: UUID


class ProfileWorkerOperationRequest(BaseModel):
    """Internal lifecycle access to a previously session-bound invocation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["operation_start"] = "operation_start"
    request_id: UUID
    session_id: UUID
    frontend: OperationFrontendProjection
    operation_id: OperationId


class ProfileWorkerSecretRequest(BaseModel):
    """Preflight or deliver one original submission's runtime-only secret."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["operation_secret_ready", "operation_secret"]
    request_id: UUID
    session_id: UUID
    frontend: OperationFrontendProjection
    requirement: OperationSecretRequirement


class ProfileWorkerObserveRequest(BaseModel):
    """Bounded observation coordinates; the worker resolves disclosure permissions."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["operation_observe"] = "operation_observe"
    request_id: UUID
    session_id: UUID
    frontend: OperationFrontendProjection
    observation: OperationObservationRequestV1


class ProfileWorkerResumeRequest(BaseModel):
    """A fresh session requesting canonical recovery of exact persisted intent."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["operation_resume"] = "operation_resume"
    request_id: UUID
    session_id: UUID
    frontend: OperationFrontendProjection
    operation_id: OperationId


class ProfileWorkerProjectRequest(BaseModel):
    """Only canonical result/review coordinates, never an encrypted record reference."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["operation_project"] = "operation_project"
    request_id: UUID
    session_id: UUID
    frontend: OperationFrontendProjection
    projection: OperationResultProjectionRequestV1 | OperationReviewProjectionRequestV1


class ProfileWorkerProjectPageRequest(BaseModel):
    """Bounded output over the same canonical result and authorization owner."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["operation_project_page"] = "operation_project_page"
    request_id: UUID
    session_id: UUID
    frontend: OperationFrontendProjection
    projection: OperationResultProjectionRequestV1
    page: ProjectionPageRequest


class ProfileWorkerManageRequest(BaseModel):
    """Canonical control coordinates, with frontend and actor resolved by the worker."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["operation_manage"] = "operation_manage"
    request_id: UUID
    session_id: UUID
    frontend: OperationFrontendProjection
    management: OperationManagementRequest


class ProfileWorkerRequest(
    RootModel[
        Annotated[
            ProfileWorkerLeaseRequest
            | ProfileWorkerLeaseTransferRequest
            | ProfileWorkerRetireRequest
            | ProfileWorkerSettlementRequest
            | ProfileWorkerControlRequest
            | ProfileWorkerHumanBindingRequest
            | ProfileWorkerHumanReceiptRequest
            | ProfileWorkerContractRequest
            | ProfileWorkerSubmitRequest
            | ProfileWorkerSubmissionBeginRequest
            | ProfileWorkerSubmissionChunkRequest
            | ProfileWorkerSubmissionFinishRequest
            | ProfileWorkerSubmissionAbortRequest
            | ProfileWorkerOperationRequest
            | ProfileWorkerSecretRequest
            | ProfileWorkerResumeRequest
            | ProfileWorkerProjectRequest
            | ProfileWorkerProjectPageRequest
            | ProfileWorkerManageRequest
            | ProfileWorkerObserveRequest,
            Field(discriminator="action"),
        ]
    ]
):
    """Closed command set accepted only from the worker's verified runtime parent."""


class ProfileWorkerStatus(BaseModel):
    """Internal custody receipt with no password, DEK or authorization bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["status"] = "status"
    identity: ProfileWorkerIdentity
    request_id: UUID
    sessions: tuple[UUID, ...]


class ProfileWorkerDrained(BaseModel):
    """Bounded operation shutdown result, requiring native containment on return."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["drained"] = "drained"
    identity: ProfileWorkerIdentity
    request_id: UUID
    unresolved: tuple[OperationId, ...]
    recovery_required: tuple[OperationId, ...]


class ProfileWorkerSettlement(BaseModel):
    """Terminal completion only, without condition, result, or private reference."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["operation_settlement"] = "operation_settlement"
    identity: ProfileWorkerIdentity
    request_id: UUID
    operation_identity: OperationIdentity
    settled: bool


class ProfileWorkerHumanOutcome(BaseModel):
    """Human proof awaiting runtime admission; the candidate ID is not a bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["human_candidate"] = "human_candidate"
    identity: ProfileWorkerIdentity
    request_id: UUID
    candidate_id: UUID
    login: ProfileLoginOutcome


class ProfileWorkerHumanBound(BaseModel):
    """Acknowledge the exact admitted human session and acceleration outcome.

    ``receipt_pending`` means the worker holds the proof for a receipt that it
    mints only on a later request; ``receipt`` then reports nothing persisted.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["human_bound"] = "human_bound"
    identity: ProfileWorkerIdentity
    request_id: UUID
    session_id: UUID
    receipt: ProfileHumanLoginReceipt
    receipt_pending: bool = False


class ProfileWorkerRefusal(BaseModel):
    """An allowlisted application refusal that does not expose rejected input."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["refusal"] = "refusal"
    identity: ProfileWorkerIdentity
    request_id: UUID
    reason: AutomationCustodyCode | AccessDenialCode


class ProfileWorkerOperationContract(BaseModel):
    """The canonical operation contract from this worker's composed service graph."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["operation_contract"] = "operation_contract"
    identity: ProfileWorkerIdentity
    request_id: UUID
    contract: OperationPublicDefinitionContractV1
    request_json_schema: dict[str, JsonValue]


class ProfileWorkerSubmission(BaseModel):
    """Internal receipt only; response capabilities stay with their original owner."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["operation_submission"] = "operation_submission"
    identity: ProfileWorkerIdentity
    request_id: UUID
    receipt: OperationSubmissionReceiptV1
    release: WorkerAuthorityRequest


class ProfileWorkerUploadAccepted(BaseModel):
    """Acknowledge staging only; no operation exists until finish succeeds."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["operation_upload_accepted"] = "operation_upload_accepted"
    identity: ProfileWorkerIdentity
    request_id: UUID
    upload_id: UUID


class ProfileWorkerOperationReceipt(BaseModel):
    """Internal acknowledgement that claims neither successful commit nor private output."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["operation_receipt"] = "operation_receipt"
    identity: ProfileWorkerIdentity
    request_id: UUID
    operation_id: OperationId
    release: WorkerAuthorityRequest


class ProfileWorkerObservation(BaseModel):
    """Canonical observation released under its own disclosure authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["operation_observation"] = "operation_observation"
    identity: ProfileWorkerIdentity
    request_id: UUID
    observation: OperationObservationResultV1
    release: WorkerAuthorityRequest


class ProfileWorkerProjection(BaseModel):
    """Registered canonical public projection with fresh output policy coordinates."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["operation_projection"] = "operation_projection"
    identity: ProfileWorkerIdentity
    request_id: UUID
    document: dict[str, JsonValue]
    release: WorkerAuthorityRequest


class ProfileWorkerProjectionPage(BaseModel):
    """One bounded result page with its exact output policy coordinates."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["operation_projection_page"] = "operation_projection_page"
    identity: ProfileWorkerIdentity
    request_id: UUID
    page: ProjectionPage
    release: WorkerAuthorityRequest


class ProfileWorkerReply(
    RootModel[
        Annotated[
            ProfileWorkerStatus
            | ProfileWorkerDrained
            | ProfileWorkerSettlement
            | ProfileWorkerHumanOutcome
            | ProfileWorkerHumanBound
            | ProfileWorkerRefusal
            | ProfileWorkerOperationContract
            | ProfileWorkerSubmission
            | ProfileWorkerUploadAccepted
            | ProfileWorkerOperationReceipt
            | ProfileWorkerObservation
            | ProfileWorkerProjection
            | ProfileWorkerProjectionPage,
            Field(discriminator="kind"),
        ]
    ]
):
    """The closed internal response set, including nonfatal authentication refusal."""
