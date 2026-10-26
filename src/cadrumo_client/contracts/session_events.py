"""Nonsecret retirement frames on the connection that owned the retired lease."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, RootModel, model_validator

from cadrumo.application.user_profile.session_retirement import SessionRetirementKind
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

from .access_refusals import AccessDenialCode
from .model_runs import ModelRunRequested
from .presentation import presentation_refusal


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


class ProfileRecordsChanged(BaseModel):
    """Exact-session invalidation after a record effect; carries no values or authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["profile_records_changed"] = "profile_records_changed"
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


class AttendanceAnswered(BaseModel):
    """This connection's own attendance ask was decided or withdrawn; read its status again, which grants nothing."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["attendance_answered"] = "attendance_answered"
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID


class OperationChanged(BaseModel):
    """An operation this exact session observes may have advanced; observe it again, which grants nothing."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["operation_changed"] = "operation_changed"
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID
    session_id: UUID


class PresentationRequested(BaseModel):
    """The person asked, from another of their frontends, that this exact session show a page.

    It names a register view and the parameters that element declares, and
    nothing else: the receiver admits it against its own current projection,
    and it extends neither the session nor its authority.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["presentation_requested"] = "presentation_requested"
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID
    session_id: UUID
    destination: str
    params: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _a_tui_view(self) -> Self:
        refusal = presentation_refusal(self.destination, self.params)
        if refusal is not None:
            raise ValueError(f"destination is not a TUI view request: {refusal}")
        return self


type ConnectionEvent = (
    SessionEvent
    | LifecycleNotice
    | ProfileLanguageChanged
    | ProfileRecordsChanged
    | SignInChanged
    | ServiceLeaseChanged
    | AttendanceChanged
    | AttendanceAnswered
    | OperationChanged
    | PresentationRequested
    | ModelRunRequested
)

CONNECTION_EVENT_TYPES = (
    SessionEvent,
    LifecycleNotice,
    ProfileLanguageChanged,
    ProfileRecordsChanged,
    SignInChanged,
    ServiceLeaseChanged,
    AttendanceChanged,
    AttendanceAnswered,
    OperationChanged,
    PresentationRequested,
    ModelRunRequested,
)
"""Every frame the runtime may push between replies, for exhaustive transport checks."""


class EventFrame(RootModel[Annotated[ConnectionEvent, Field(discriminator="kind")]]):
    """Closed event variants on the existing verified connection stream."""
