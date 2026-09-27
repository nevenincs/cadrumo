"""Bounded authorization handshakes between an owned worker and its runtime."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, RootModel

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import UtcInstant
from ..operations.models import OperationId
from ..user_profile.access_contracts import AccessAllowed, OperationAccessPolicy, OperationAccessRequest
from .profile_access import RuntimeAccessRefusal

AUTHORITY_SECTION_MAXIMUM_SECONDS = 30.0


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


class WorkerAuthorizationPermit(BaseModel):
    """One held fence on this native connection, never a transferable capability."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["authorized"] = "authorized"
    request_id: UUID
    runtime_boot_id: UUID
    permit_id: UUID
    expires_at: UtcInstant


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


class WorkerAuthorizationAcknowledgement(BaseModel):
    """Confirm consumption before a native pipe server closes its reply buffer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["acknowledge"] = "acknowledge"
    request_id: UUID


class WorkerAuthorizationReply(
    RootModel[
        Annotated[
            WorkerAuthorizationPermit | WorkerAuthorizationReleased | RuntimeAccessRefusal, Field(discriminator="kind")
        ]
    ]
):
    """The closed internal reply union for authorization, refusal and release."""


class WorkerAuthorizationOwner(Protocol):
    """Thread-affine application guard called only for the exact owned worker."""

    def authorize(self, request: WorkerAuthorizationRequest) -> AbstractContextManager[AccessAllowed]:
        """Evaluate current authority and retain the fence until release or containment."""
        ...
