"""Closed local profile-admission messages; credentials use separate bounded frames."""

from __future__ import annotations

from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, RootModel

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.registry import OperationFrontendProjection
from ..user_profile.access_contracts import AccessDenialCode, AccessScope, ProfileAccessStatus
from ..user_profile.automation_custody_port import AutomationCustodyCode
from .contracts import RuntimeByteChannel, RuntimeRefusalCode
from .operation_access import RuntimeOperationReply, RuntimeOperationRequest
from .transport import RuntimeConnectionContext, RuntimeStatusRequest, RuntimeTransportStatus


class RuntimeProfileLogin(BaseModel):
    """Name an exact profile and credential class, without asserting native identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["profile_login"] = "profile_login"
    request_id: UUID
    profile_id: UUID
    method: Literal["password", "api_key"]
    frontend: OperationFrontendProjection
    scope: AccessScope | None = None


class RuntimeSessionRequest(BaseModel):
    """Address one connection-bound lease; its identifier is never a bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["session_status", "session_refresh", "session_lock"]
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    target_session_id: UUID | None = None


class RuntimeRequest(
    RootModel[
        Annotated[
            RuntimeStatusRequest | RuntimeProfileLogin | RuntimeSessionRequest | RuntimeOperationRequest,
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


class RuntimeReply(
    RootModel[
        Annotated[
            RuntimeTransportStatus
            | RuntimeSecretReady
            | RuntimeProfileStatus
            | RuntimeSessionsLocked
            | RuntimeOperationReply
            | RuntimeAccessRefusal,
            Field(discriminator="kind"),
        ]
    ]
):
    """Strict response union shared by local projections."""


class RuntimeProfileHandler(Protocol):
    """Host-owned profile admission and lifetime hooks after the native handshake."""

    def handle(
        self,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeProfileLogin | RuntimeSessionRequest,
    ) -> RuntimeProfileStatus | RuntimeSessionsLocked | RuntimeAccessRefusal:
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

    def poll(self) -> None:
        """Revalidate leases without requiring a frontend call."""
        ...

    def close(self) -> None:
        """Fence and settle owned profile custody before runtime ownership is released."""
        ...
