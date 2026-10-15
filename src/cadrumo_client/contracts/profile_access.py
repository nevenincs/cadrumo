"""Closed local profile-admission messages; credentials use separate bounded frames."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, RootModel, model_validator

from cadrumo.application.operations.models import OperationId
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    AccessDenialCode,
    AccessScope,
    AuthorityState,
    DisclosurePage,
    DisclosurePageRequest,
    ProfileAccessStatus,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.application.user_profile.sign_in_refusals import SignInRefusal
from cadrumo.core.identity.digest import ContentDigest
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from cadrumo.core.profile_session import ProfileHumanLoginReceipt
from cadrumo.core.request_faults import MAX_REQUEST_FAULTS, RequestFault

from .access_management import (
    AccessManagementReply,
    AccessManagementRequest,
    SessionInventoryTransfer,
)
from .attendance import AttendanceAsk, AttendanceDecide, AttendanceDecided, AttendanceInventory, AttendancePending
from .bootstrap import (
    PasswordReset,
    PasswordResetCompleted,
    PasswordResetPrepare,
    PasswordResetPrepared,
    PasswordResetRefused,
)
from .bootstrap_delete import (
    ProfileDelete,
    ProfileDeleted,
    ProfileDeletePrepare,
    ProfileDeletePrepared,
    ProfileDeleteRefused,
)
from .contracts import RefusalCode
from .enrollment_access import EnrollmentReply, EnrollmentRequest
from .extension_records import ExtensionRecordReply, ExtensionRecordRequest
from .installation_requests import InstallationActRequest, InstallationReply, InstallationReplyTransfer
from .operation_access import OperationReply, OperationRequest
from .service_access import ServiceAdmission, ServiceConnect, ServiceConnected
from .sign_in import HumanSignedOut, SignInStatusReply, SignInStatusRequest

type HumanProofMethod = Literal["password", "receipt"]

# One cold profile admission can launch and prepare an isolated worker, then
# run its supervised password KDF, before its first reply; on a loaded host each
# takes many seconds. The same budget covers human proof and protected
# references, and uses the whole of the runtime's single-exchange maximum.
PROFILE_ADMISSION_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True, slots=True)
class HumanProof:
    """Borrowed secret and native login context, never a serialized credential."""

    method: HumanProofMethod
    secret: bytearray = field(repr=False)
    originating_login_id: str
    persist_receipt: bool = False


class ProfileLogin(BaseModel):
    """Name an exact profile and credential class, without asserting native identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["profile_login"] = "profile_login"
    request_id: UUID
    profile_id: UUID
    method: Literal["password", "receipt", "api_key"]
    frontend: OperationFrontendProjection
    scope: AccessScope | None = None
    persist_receipt: bool = False
    #: Omit the unset intent so older peers retain the ordinary login frame.
    activity_only: bool = Field(default=False, exclude_if=lambda value: value is False)

    @model_validator(mode="after")
    def _activity_resumes_existing_receipt(self) -> ProfileLogin:
        if self.activity_only and self.method != "receipt":
            raise ValueError("activity-only admission requires an existing receipt")
        return self


class SessionRequest(BaseModel):
    """Address one connection-bound lease; its identifier is never a bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["session_status", "session_refresh", "session_activity", "session_lock", "human_sign_out"]
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    target_session_id: UUID | None = None


class ProfileDisclosurePageRequest(BaseModel):
    """Read one page of the disclosures the caller's own status counts.

    It is a record of its own, apart from the session requests, because it
    reads and never changes a session.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["session_disclosures"] = "session_disclosures"
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    page: DisclosurePageRequest


class Request(
    RootModel[
        Annotated[
            ProfileLogin
            | ProfileDeletePrepare
            | ProfileDelete
            | PasswordResetPrepare
            | PasswordReset
            | SignInStatusRequest
            | SessionRequest
            | ProfileDisclosurePageRequest
            | AttendanceAsk
            | AttendanceDecide
            | OperationRequest
            | EnrollmentRequest
            | AccessManagementRequest
            | InstallationActRequest
            | ServiceConnect
            | ServiceAdmission
            | ExtensionRecordRequest,
            Field(discriminator="action"),
        ]
    ]
):
    """The exhaustive public request door, excluding arbitrary command dispatch."""


class SecretReady(BaseModel):
    """Authorize exactly one following secret frame after native/profile preflight."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["secret_ready"] = "secret_ready"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID


class ProfileStatus(BaseModel):
    """Release only the canonical nonsecret access projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["profile_status"] = "profile_status"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    status: ProfileAccessStatus
    human_login: ProfileHumanLoginReceipt | None = None


def status_admits_session(
    status: ProfileAccessStatus,
    *,
    profile_id: UUID,
    session_id: UUID,
    at: datetime,
    requires_automation_grant: bool,
) -> bool:
    """Whether ``status`` reports this exact lease as live and undenied at ``at``.

    Only API-key sessions carry an automation grant; a human session has none,
    so callers holding an API-key lease ask for the grant to be active too.
    """
    admitted = _session_is_live_for_profile(status, profile_id=profile_id, session_id=session_id, at=at)
    if not admitted or not requires_automation_grant:
        return admitted
    return _automation_grant_is_live(status, at=at)


def _session_is_live_for_profile(
    status: ProfileAccessStatus, *, profile_id: UUID, session_id: UUID, at: datetime
) -> bool:
    return (
        status.connected
        and status.credential_authenticated
        and status.profile_bound
        and status.profile_id == profile_id
        and status.session_id == session_id
        and status.session_expires_at is not None
        and status.session_expires_at > at
        and status.denial is None
    )


def _automation_grant_is_live(status: ProfileAccessStatus, *, at: datetime) -> bool:
    return (
        status.grant_valid
        and status.grant_state is AuthorityState.ACTIVE
        and status.grant_expires_at is not None
        and status.grant_expires_at > at
    )


class ProfileDisclosurePage(BaseModel):
    """One page of the effective disclosures the caller's own status counts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["disclosure_page"] = "disclosure_page"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    page: DisclosurePage


class ProfileStatusTransfer(BaseModel):
    """Bounded full-scope status transfer, correlated before its chunks are read."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["profile_status_transfer"] = "profile_status_transfer"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    byte_count: Annotated[int, Field(ge=2, le=1_048_576)]
    payload_digest: ContentDigest


class SessionsLocked(BaseModel):
    """Acknowledge precisely the sessions retired by the application authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["sessions_locked"] = "sessions_locked"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    session_ids: tuple[UUID, ...]


class AccessRefusal(BaseModel):
    """Allowlisted application or native refusal, with no input attached.

    ``request_faults`` says why an operation's request was refused before it
    became an operation, or why a read could not be served: where, what kind,
    and the validator's own message or a registered error's, the text the
    command line shows for the same refusal. A fault never attaches the
    refused input. Only a refusal whose code is ``invalid`` has any.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["access_refusal"] = "access_refusal"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    code: AccessDenialCode | AutomationCustodyCode | RefusalCode
    sign_in: SignInRefusal | None = None
    request_faults: Annotated[tuple[RequestFault, ...], Field(max_length=MAX_REQUEST_FAULTS)] = ()
    #: The unsettled operation that holds the subject of a ``subject_busy`` refusal.
    holder_operation_id: OperationId | None = None

    @model_validator(mode="after")
    def _only_an_invalid_request_has_faults(self) -> AccessRefusal:
        if self.request_faults and self.code is not AutomationCustodyCode.INVALID:
            raise ValueError("only an invalid request carries request faults")
        if self.holder_operation_id is not None and self.code is not AccessDenialCode.SUBJECT_BUSY:
            raise ValueError("only a busy subject names the operation that holds it")
        return self


class Reply(
    RootModel[
        Annotated[
            SecretReady
            | ProfileDeletePrepared
            | ProfileDeleted
            | ProfileDeleteRefused
            | PasswordResetPrepared
            | PasswordResetCompleted
            | PasswordResetRefused
            | HumanSignedOut
            | SignInStatusReply
            | ProfileStatus
            | ProfileStatusTransfer
            | ProfileDisclosurePage
            | SessionInventoryTransfer
            | SessionsLocked
            | AttendancePending
            | AttendanceInventory
            | AttendanceDecided
            | OperationReply
            | EnrollmentReply
            | AccessManagementReply
            | InstallationReply
            | InstallationReplyTransfer
            | ServiceConnected
            | ExtensionRecordReply
            | AccessRefusal,
            Field(discriminator="kind"),
        ]
    ]
):
    """Strict response union shared by local projections."""
