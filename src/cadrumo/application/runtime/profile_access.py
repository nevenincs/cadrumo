"""Closed local profile-admission messages; credentials use separate bounded frames."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, RootModel

from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.registry import OperationFrontendProjection
from ..user_profile.access_contracts import AccessDenialCode, AccessScope, AuthorityState, ProfileAccessStatus
from ..user_profile.automation_custody_port import AutomationCustodyCode
from ..user_profile.login_session import ProfileHumanLoginReceipt
from ..user_profile.sign_in_refusals import SignInRefusal
from .access_management import (
    RuntimeAccessManagementReply,
    RuntimeAccessManagementRequest,
    RuntimeAutomationDeny,
    RuntimeProfileRecoveryPrepare,
    RuntimeProfileResume,
    RuntimeSessionInventory,
    RuntimeSessionInventoryTransfer,
)
from .bootstrap import (
    RuntimePasswordReset,
    RuntimePasswordResetCompleted,
    RuntimePasswordResetPrepare,
    RuntimePasswordResetPrepared,
    RuntimePasswordResetRefused,
)
from .bootstrap_delete import (
    RuntimeProfileDelete,
    RuntimeProfileDeleted,
    RuntimeProfileDeletePrepare,
    RuntimeProfileDeletePrepared,
    RuntimeProfileDeleteRefused,
)
from .contracts import RuntimeByteChannel, RuntimeRefusalCode
from .enrollment_access import (
    RuntimeEnrollmentReply,
    RuntimeEnrollmentRequest,
)
from .operation_access import RuntimeOperationReply, RuntimeOperationRequest
from .session_events import RuntimeSessionEvent
from .sign_in import RuntimeHumanSignedOut, RuntimeSignInStatusReply, RuntimeSignInStatusRequest
from .transport import RuntimeConnectionContext

if TYPE_CHECKING:
    from .profile_worker import ProfileWorkerDrained


type RuntimeHumanProofMethod = Literal["password", "receipt"]

# One cold profile admission can launch and prepare an isolated worker before
# its first reply. The same budget covers human proof and protected references.
PROFILE_ADMISSION_TIMEOUT_SECONDS = 75.0


@dataclass(frozen=True, slots=True)
class RuntimeHumanProof:
    """Borrowed secret and native login context, never a serialized credential."""

    method: RuntimeHumanProofMethod
    secret: bytearray = field(repr=False)
    originating_login_id: str
    persist_receipt: bool = False


class RuntimeProfileLogin(BaseModel):
    """Name an exact profile and credential class, without asserting native identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["profile_login"] = "profile_login"
    request_id: UUID
    profile_id: UUID
    method: Literal["password", "receipt", "api_key"]
    frontend: OperationFrontendProjection
    scope: AccessScope | None = None
    persist_receipt: bool = False


class RuntimeSessionRequest(BaseModel):
    """Address one connection-bound lease; its identifier is never a bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["session_status", "session_refresh", "session_lock", "human_sign_out"]
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    target_session_id: UUID | None = None


class RuntimeRequest(
    RootModel[
        Annotated[
            RuntimeProfileLogin
            | RuntimeProfileDeletePrepare
            | RuntimeProfileDelete
            | RuntimePasswordResetPrepare
            | RuntimePasswordReset
            | RuntimeSignInStatusRequest
            | RuntimeSessionRequest
            | RuntimeOperationRequest
            | RuntimeEnrollmentRequest
            | RuntimeAccessManagementRequest,
            Field(discriminator="action"),
        ]
    ]
):
    """The exhaustive public request door, excluding arbitrary command dispatch."""


class RuntimeSecretReady(BaseModel):
    """Authorize exactly one following secret frame after native/profile preflight."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["secret_ready"] = "secret_ready"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID


class RuntimeProfileStatus(BaseModel):
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


class RuntimeProfileStatusTransfer(BaseModel):
    """Bounded full-scope status transfer, correlated before its chunks are read."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["profile_status_transfer"] = "profile_status_transfer"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    byte_count: Annotated[int, Field(ge=2, le=1_048_576)]
    payload_digest: ContentDigest


class RuntimeSessionsLocked(BaseModel):
    """Acknowledge precisely the sessions retired by the application authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["sessions_locked"] = "sessions_locked"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    session_ids: tuple[UUID, ...]


class RuntimeAccessRefusal(BaseModel):
    """Allowlisted application or native refusal, with no input or diagnostic text."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["access_refusal"] = "access_refusal"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    code: AccessDenialCode | AutomationCustodyCode | RuntimeRefusalCode
    sign_in: SignInRefusal | None = None


class RuntimeReply(
    RootModel[
        Annotated[
            RuntimeSecretReady
            | RuntimeProfileDeletePrepared
            | RuntimeProfileDeleted
            | RuntimeProfileDeleteRefused
            | RuntimePasswordResetPrepared
            | RuntimePasswordResetCompleted
            | RuntimePasswordResetRefused
            | RuntimeHumanSignedOut
            | RuntimeSignInStatusReply
            | RuntimeProfileStatus
            | RuntimeProfileStatusTransfer
            | RuntimeSessionInventoryTransfer
            | RuntimeSessionsLocked
            | RuntimeOperationReply
            | RuntimeEnrollmentReply
            | RuntimeAccessManagementReply
            | RuntimeAccessRefusal,
            Field(discriminator="kind"),
        ]
    ]
):
    """Strict response union shared by local projections."""


@dataclass(frozen=True)
class RuntimeProfileDrainResult:
    """Host-only proof of receipts and containment, never a public wire reply."""

    receipts: tuple[ProfileWorkerDrained, ...]
    missing_receipts: tuple[UUID, ...]
    uncontained: tuple[UUID, ...]
    unsettled: tuple[UUID, ...]
    parent_settled_profiles: tuple[UUID, ...] = ()

    @property
    def lacks_settlement_evidence(self) -> bool:
        """Keep missing worker receipts distinct from confirmed parent settlement."""
        return bool(set(self.missing_receipts) - set(self.parent_settled_profiles))


class RuntimeProfileHandler(Protocol):
    """Host-owned profile admission and lifetime hooks after the native handshake."""

    def connect_events(self, context: RuntimeConnectionContext) -> None:
        """Register an already verified stream for bounded retirement notices."""
        ...

    def take_events(self, context: RuntimeConnectionContext) -> tuple[RuntimeSessionEvent, ...]:
        """Take one bounded batch, or refuse an overflowed connection."""
        ...

    def handle(
        self,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeProfileLogin | RuntimeSessionRequest | RuntimeSignInStatusRequest,
    ) -> (
        RuntimeProfileStatus
        | RuntimeSessionsLocked
        | RuntimeSignInStatusReply
        | RuntimeHumanSignedOut
        | RuntimeAccessRefusal
    ):
        """Admit or observe only the exact current connection."""
        ...

    def disconnect(self, context: RuntimeConnectionContext) -> None:
        """Fence this connection without terminating other independently admitted work."""
        ...

    def operation(
        self, context: RuntimeConnectionContext, channel: RuntimeByteChannel, request: RuntimeOperationRequest
    ) -> None:
        """Resolve and write a canonical projection while holding current output authority."""
        ...

    def enrollment(
        self,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeEnrollmentRequest,
    ) -> None:
        """Complete one exact pre-unlock exchange on the verified native channel."""
        ...

    def manage_access(
        self,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeAutomationDeny | RuntimeProfileRecoveryPrepare | RuntimeProfileResume | RuntimeSessionInventory,
    ) -> None:
        """Complete one exact access-management exchange on the verified channel."""
        ...

    def bootstrap_delete(
        self,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeProfileDeletePrepare | RuntimeProfileDelete,
    ) -> None:
        """Host a confirmed existing deletion journal without profile admission."""
        ...

    def bootstrap(
        self,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimePasswordResetPrepare | RuntimePasswordReset,
    ) -> None:
        """Run an exact bootstrap custody transaction with separate proof."""
        ...

    def poll(self) -> None:
        """Revalidate leases without requiring a frontend call."""
        ...

    def close(self) -> None:
        """Fence and settle owned profile custody before runtime ownership is released."""
        ...

    def drain(self, *, deadline: float) -> RuntimeProfileDrainResult:
        """Fence admissions and drain all workers under one monotonic deadline."""
        ...
