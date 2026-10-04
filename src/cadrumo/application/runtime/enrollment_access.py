"""Credential-free native messages for pre-unlock enrollment and client delivery."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import UtcInstant
from ..operations.registry import OperationFrontendProjection
from ..user_profile.access_contracts import ProfileAccessBinding
from ..user_profile.automation_custody_port import AutomationCustodyCode
from ..user_profile.automation_enrollment import AutomationReceiptProjection


class RuntimeEnrollmentPrepare(BaseModel):
    """Ask the verified runtime to mint one request and recipient identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["enrollment_prepare"] = "enrollment_prepare"
    request_id: UUID
    profile_id: UUID
    frontend: OperationFrontendProjection
    session_id: UUID | None = None


class RuntimeEnrollmentSubmit(BaseModel):
    """Name a prepared request; proposal bytes follow a separate secret-ready frame."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["enrollment_submit"] = "enrollment_submit"
    request_id: UUID
    profile_id: UUID
    enrollment_request_id: UUID


class RuntimeEnrollmentInspect(BaseModel):
    """Inspect only the safe receipt for this exact prepared request."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["enrollment_inspect"] = "enrollment_inspect"
    request_id: UUID
    profile_id: UUID
    enrollment_request_id: UUID


class RuntimeEnrollmentPoll(BaseModel):
    """Poll delivery without advancing a human session or receiving a credential."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["enrollment_poll"] = "enrollment_poll"
    request_id: UUID
    profile_id: UUID
    enrollment_request_id: UUID


class RuntimeEnrollmentReconcile(BaseModel):
    """Recover one terminal own-grant receipt under a newly admitted root key."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["enrollment_reconcile"] = "enrollment_reconcile"
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    enrollment_request_id: UUID


type RuntimeEnrollmentRequest = Annotated[
    RuntimeEnrollmentPrepare
    | RuntimeEnrollmentSubmit
    | RuntimeEnrollmentInspect
    | RuntimeEnrollmentPoll
    | RuntimeEnrollmentReconcile,
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


class _RuntimeEnrollmentReplyIdentity(BaseModel):
    """Shared native reply coordinates, never a bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID


class RuntimeEnrollmentPrepared(_RuntimeEnrollmentReplyIdentity):
    """Server-minted request, recipient and exact profile custody identity."""

    kind: Literal["enrollment_prepared"] = "enrollment_prepared"
    enrollment_request_id: UUID
    client_id: UUID
    destination_id: UUID
    profile_binding: ProfileAccessBinding
    expires_at: UtcInstant


class RuntimeEnrollmentRecorded(_RuntimeEnrollmentReplyIdentity):
    """Safe registered request receipt; proposal and proof remain private."""

    kind: Literal["enrollment_recorded"] = "enrollment_recorded"
    receipt: AutomationReceiptProjection


class RuntimeEnrollmentIdle(_RuntimeEnrollmentReplyIdentity):
    """No approved delivery is ready for this requester."""

    kind: Literal["enrollment_idle"] = "enrollment_idle"


class RuntimeEnrollmentDelivery(_RuntimeEnrollmentReplyIdentity):
    """Ask the exact client to store or prove possession over a secret frame."""

    kind: Literal["enrollment_delivery"] = "enrollment_delivery"
    command_id: UUID
    action: Literal["store", "possession"]
    credential: EnrollmentCredentialBinding


type RuntimeEnrollmentReply = Annotated[
    RuntimeEnrollmentPrepared | RuntimeEnrollmentRecorded | RuntimeEnrollmentIdle | RuntimeEnrollmentDelivery,
    Field(discriminator="kind"),
]
"""Closed nonsecret reply union for the enrollment handshake."""


class RuntimeEnrollmentClientReply(BaseModel):
    """Acknowledge one command after the separate protected credential exchange."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["enrollment_client_reply"] = "enrollment_client_reply"
    command_id: UUID
    outcome: Literal["stored", "present", "missing", "refused"]
    code: AutomationCustodyCode | None = None

    @model_validator(mode="after")
    def _require_refusal_code_only_for_refusal(self) -> RuntimeEnrollmentClientReply:
        if (self.outcome == "refused") != (self.code is not None):
            raise ValueError("client refusal outcome and code must agree")
        return self
