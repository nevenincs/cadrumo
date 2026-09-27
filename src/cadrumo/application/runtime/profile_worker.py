"""Immutable identity of one profile worker owned by a runtime boot."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, RootModel

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationResultV1,
    OperationSubmissionReceiptV1,
)
from ..operations.models import OperationDefinitionId, OperationId, OperationReference
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionContractV1
from ..user_profile.access_contracts import AccessDenialCode, AccessSession, ProfileAccessBinding
from ..user_profile.automation_custody_port import AutomationCustodyCode
from ..user_profile.login_session import ProfileLoginOutcome
from .worker_authorization import WorkerAuthorizationRequest


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


class ProfileWorkerRetireRequest(BaseModel):
    """Release one runtime-authorized lineage, without changing the worker target."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["retire"] = "retire"
    request_id: UUID
    session_id: UUID


class ProfileWorkerControlRequest(BaseModel):
    """Credential-free internal observation or explicit worker shutdown."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["status", "stop", "password", "cancel_password"]
    request_id: UUID


class ProfileWorkerHumanBindingRequest(BaseModel):
    """Promote one exact password candidate after runtime human-session admission."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["bind_human"] = "bind_human"
    request_id: UUID
    candidate_id: UUID
    lease: AccessSession


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


class ProfileWorkerOperationRequest(BaseModel):
    """Internal lifecycle access to a previously session-bound invocation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["operation_start"] = "operation_start"
    request_id: UUID
    session_id: UUID
    frontend: OperationFrontendProjection
    operation_id: OperationId


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


class ProfileWorkerRequest(
    RootModel[
        Annotated[
            ProfileWorkerLeaseRequest
            | ProfileWorkerRetireRequest
            | ProfileWorkerControlRequest
            | ProfileWorkerHumanBindingRequest
            | ProfileWorkerContractRequest
            | ProfileWorkerSubmitRequest
            | ProfileWorkerOperationRequest
            | ProfileWorkerResumeRequest
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


class ProfileWorkerPasswordOutcome(BaseModel):
    """Password proof awaiting runtime admission; the candidate ID is not a bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["password"] = "password"
    identity: ProfileWorkerIdentity
    request_id: UUID
    candidate_id: UUID
    login: ProfileLoginOutcome


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


class ProfileWorkerSubmission(BaseModel):
    """Internal receipt only; response capabilities stay with their original owner."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["operation_submission"] = "operation_submission"
    identity: ProfileWorkerIdentity
    request_id: UUID
    receipt: OperationSubmissionReceiptV1
    release: WorkerAuthorizationRequest


class ProfileWorkerOperationReceipt(BaseModel):
    """Internal acknowledgement that claims neither successful commit nor private output."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["operation_receipt"] = "operation_receipt"
    identity: ProfileWorkerIdentity
    request_id: UUID
    operation_id: OperationId
    release: WorkerAuthorizationRequest


class ProfileWorkerObservation(BaseModel):
    """Canonical observation released under its own disclosure authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["operation_observation"] = "operation_observation"
    identity: ProfileWorkerIdentity
    request_id: UUID
    observation: OperationObservationResultV1
    release: WorkerAuthorizationRequest


class ProfileWorkerReply(
    RootModel[
        Annotated[
            ProfileWorkerStatus
            | ProfileWorkerPasswordOutcome
            | ProfileWorkerRefusal
            | ProfileWorkerOperationContract
            | ProfileWorkerSubmission
            | ProfileWorkerOperationReceipt
            | ProfileWorkerObservation,
            Field(discriminator="kind"),
        ]
    ]
):
    """The closed internal response set, including nonfatal authentication refusal."""
