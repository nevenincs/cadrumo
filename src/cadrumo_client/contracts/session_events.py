"""Nonsecret retirement frames on the connection that owned the retired lease."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, RootModel, model_validator

from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.session_retirement import SessionRetirementKind
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class SessionEvent(BaseModel):
    """A committed retirement notice; absence or delivery never grants authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["session_event"] = "session_event"
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID
    session_id: UUID
    event: SessionRetirementKind
    reason: AccessDenialCode
    generation_lineage: UUID | None = None
    generation: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _generation_pair(self) -> "SessionEvent":
        if (self.generation_lineage is None) != (self.generation is None):
            raise ValueError("generation requires both lineage and counter")
        return self


class LifecycleNotice(BaseModel):
    """Nonsecret presentation information, never session or management authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["lifecycle_notice"] = "lifecycle_notice"
    runtime_boot_id: UUID
    connection_id: UUID
    notice_id: UUID
    event: Literal["upgrade_pending"] = "upgrade_pending"


class ProfileLanguageChanged(BaseModel):
    """Exact-session presentation invalidation; carries no private facts or authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["profile_language_changed"] = "profile_language_changed"
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID
    session_id: UUID


class SignInChanged(BaseModel):
    """A watched sign-in may have changed; the watcher re-reads its status, which grants nothing."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["sign_in_changed"] = "sign_in_changed"
    runtime_boot_id: UUID
    connection_id: UUID


class ServiceLeaseChanged(BaseModel):
    """The service connection's lease was issued or withdrawn; the service claims again to learn which."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["service_lease_changed"] = "service_lease_changed"
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID


class AttendanceChanged(BaseModel):
    """Pending attendance asks changed for the person holding this exact session; re-read the inventory."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["attendance_changed"] = "attendance_changed"
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID
    session_id: UUID


type ConnectionEvent = (
    SessionEvent | LifecycleNotice | ProfileLanguageChanged | SignInChanged | ServiceLeaseChanged | AttendanceChanged
)

CONNECTION_EVENT_TYPES = (
    SessionEvent,
    LifecycleNotice,
    ProfileLanguageChanged,
    SignInChanged,
    ServiceLeaseChanged,
    AttendanceChanged,
)
"""Every frame the runtime may push between replies, for exhaustive transport checks."""


class EventFrame(RootModel[Annotated[ConnectionEvent, Field(discriminator="kind")]]):
    """Closed event variants on the existing verified connection stream."""
