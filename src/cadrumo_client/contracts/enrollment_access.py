"""Credential-free native messages for pre-unlock enrollment and client delivery."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.application.user_profile.automation_enrollment import AutomationReceiptProjection
from cadrumo.core.identity.digest import ContentDigest
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from cadrumo.core.time.utc import UtcInstant


class EnrollmentPrepare(BaseModel):
    """Ask the verified runtime to mint one request and recipient identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["enrollment_prepare"] = "enrollment_prepare"
    request_id: UUID
    profile_id: UUID
    frontend: OperationFrontendProjection
    session_id: UUID | None = None


class EnrollmentSubmit(BaseModel):
    """Name a prepared request; proposal bytes follow a separate secret-ready frame."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["enrollment_submit"] = "enrollment_submit"
    request_id: UUID
    profile_id: UUID
    enrollment_request_id: UUID


class EnrollmentInspect(BaseModel):
    """Inspect only the safe receipt for this exact prepared request."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["enrollment_inspect"] = "enrollment_inspect"
    request_id: UUID
    profile_id: UUID
    enrollment_request_id: UUID


class EnrollmentPoll(BaseModel):
    """Poll delivery without advancing a human session or receiving a credential."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["enrollment_poll"] = "enrollment_poll"
    request_id: UUID
    profile_id: UUID
    enrollment_request_id: UUID


class EnrollmentReconcile(BaseModel):
    """Recover one terminal own-grant receipt under a newly admitted root key."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["enrollment_reconcile"] = "enrollment_reconcile"
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    enrollment_request_id: UUID


type EnrollmentRequest = Annotated[
    EnrollmentPrepare | EnrollmentSubmit | EnrollmentInspect | EnrollmentPoll | EnrollmentReconcile,
    Field(discriminator="action"),
]
"""Closed pre-unlock request union; IDs alone grant no authority."""


class EnrollmentCredentialBinding(BaseModel):
    """Exact protected-client credential identity, excluding secret bytes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_binding: ProfileAccessBinding
    client_id: UUID
    destination_id: UUID
    credential_reference: UUID
    grant_id: UUID
    key_id: UUID
    review_digest: ContentDigest


class _EnrollmentReplyIdentity(BaseModel):
    """Shared native reply coordinates, never a bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID


class EnrollmentPrepared(_EnrollmentReplyIdentity):
    """Server-minted request, recipient and exact profile custody identity."""

    kind: Literal["enrollment_prepared"] = "enrollment_prepared"
    enrollment_request_id: UUID
    client_id: UUID
    destination_id: UUID
    profile_binding: ProfileAccessBinding
    expires_at: UtcInstant


class EnrollmentRecorded(_EnrollmentReplyIdentity):
    """Safe registered request receipt; proposal and proof remain private."""

    kind: Literal["enrollment_recorded"] = "enrollment_recorded"
    receipt: AutomationReceiptProjection


class EnrollmentIdle(_EnrollmentReplyIdentity):
    """No approved delivery is ready for this requester."""

    kind: Literal["enrollment_idle"] = "enrollment_idle"


class EnrollmentDelivery(_EnrollmentReplyIdentity):
    """Ask the exact client to store or prove possession over a secret frame."""

    kind: Literal["enrollment_delivery"] = "enrollment_delivery"
    command_id: UUID
    action: Literal["store", "possession"]
    credential: EnrollmentCredentialBinding


type EnrollmentReply = Annotated[
    EnrollmentPrepared | EnrollmentRecorded | EnrollmentIdle | EnrollmentDelivery,
    Field(discriminator="kind"),
]
"""Closed nonsecret reply union for the enrollment handshake."""


class EnrollmentClientReply(BaseModel):
    """Acknowledge one command after the separate protected credential exchange."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["enrollment_client_reply"] = "enrollment_client_reply"
    command_id: UUID
    outcome: Literal["stored", "present", "missing", "refused"]
    code: AutomationCustodyCode | None = None

    @model_validator(mode="after")
    def _require_refusal_code_only_for_refusal(self) -> EnrollmentClientReply:
        if (self.outcome == "refused") != (self.code is not None):
            raise ValueError("client refusal outcome and code must agree")
        return self
