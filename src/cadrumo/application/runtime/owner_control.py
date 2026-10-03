"""Connection-bound OS-owner consent for stopping the shared runtime."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, field_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import UtcInstant
from ..user_profile.access_contracts import Availability, LoginEligibility
from .contracts import RuntimeRefusalCode, RuntimeRefusalError
from .login import RuntimeLoginEvidence
from .transport import RuntimeConnectionContext


class RuntimeStopPreviewRequest(BaseModel):
    """Request explicit global scope on a dedicated local-owner connection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["runtime_stop_preview"] = "runtime_stop_preview"
    request_id: UUID


class RuntimeStopPreview(BaseModel):
    """One short-lived consent request; no private inventory or profile authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["runtime_stop_preview"] = "runtime_stop_preview"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    preview_id: UUID
    expires_at: UtcInstant
    scope: Literal["all_profiles_and_work"] = "all_profiles_and_work"


class RuntimeStopConfirm(BaseModel):
    """Acknowledge the exact boot and the entire shared runtime's stop scope."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["runtime_stop_confirm"] = "runtime_stop_confirm"
    request_id: UUID
    runtime_boot_id: UUID
    preview_id: UUID
    acknowledge_all_profiles_and_work: Literal[True]

    @field_validator("acknowledge_all_profiles_and_work", mode="before")
    @classmethod
    def _explicit_acknowledgement(cls, value: object) -> Literal[True]:
        if value is not True:
            raise ValueError("explicit global stop acknowledgement required")
        return True


class RuntimeStopAccepted(BaseModel):
    """The stop was accepted; this does not certify drain or domain settlement."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["runtime_stop_accepted"] = "runtime_stop_accepted"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    scope: Literal["all_profiles_and_work"] = "all_profiles_and_work"


@dataclass(frozen=True)
class _PendingConsent:
    preview: RuntimeStopPreview
    issued_at: datetime
    issued_monotonic: float


class RuntimeOwnerControl:
    """Verify native owner evidence independently of every profile credential.

    The transport creates this only on a connection that has never attempted
    profile admission or private work, and reserves that connection for owner
    control. This class never authenticates a profile or terminates a process.
    The existing server remains responsible for its bounded drain protocol.
    """

    CONSENT_SECONDS = 60

    def __init__(self, context: RuntimeConnectionContext, *, login: RuntimeLoginEvidence) -> None:
        """Retain transport-owned login evidence, not a caller-asserted identity."""
        self._context = context
        self._login = login
        self._login_id = login.login_id
        self._pending: _PendingConsent | None = None

    def _owner(self) -> None:
        observation = self._login.observe(credential_facilities=Availability.NOT_REQUIRED)
        if (
            observation.login_id != self._login_id
            or self._login.login_id != self._login_id
            or observation.os_owner_id != self._context.peer.os_owner_id
            or not observation.active
            or observation.locked
            or observation.unattended is not LoginEligibility.ELIGIBLE
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)

    def preview(self, request: RuntimeStopPreviewRequest, *, now: datetime, monotonic_now: float) -> RuntimeStopPreview:
        """Replace any prior consent, after freshly checking the originating login."""
        self._pending = None
        self._owner()
        if now.utcoffset() is None or not math.isfinite(monotonic_now) or monotonic_now < 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        preview = RuntimeStopPreview(
            request_id=request.request_id,
            runtime_boot_id=self._context.runtime_boot_id,
            connection_id=self._context.connection_id,
            preview_id=uuid4(),
            expires_at=now + timedelta(seconds=self.CONSENT_SECONDS),
        )
        self._pending = _PendingConsent(preview, now, monotonic_now)
        return preview

    def confirm(self, request: RuntimeStopConfirm, *, now: datetime, monotonic_now: float) -> RuntimeStopAccepted:
        """Consume once and recheck login, boot and both clocks before acceptance."""
        pending, self._pending = self._pending, None
        self._owner()
        if (
            pending is None
            or request.runtime_boot_id != self._context.runtime_boot_id
            or request.preview_id != pending.preview.preview_id
            or now.utcoffset() is None
            or not pending.issued_at <= now < pending.preview.expires_at
            or not math.isfinite(monotonic_now)
            or not 0 <= monotonic_now - pending.issued_monotonic < self.CONSENT_SECONDS
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return RuntimeStopAccepted(
            request_id=request.request_id,
            runtime_boot_id=self._context.runtime_boot_id,
            connection_id=self._context.connection_id,
        )
