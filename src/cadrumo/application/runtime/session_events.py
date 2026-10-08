"""Nonsecret retirement frames on the connection that owned the retired lease."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, RootModel, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.session_retirement import SessionRetirementKind


class RuntimeSessionEvent(BaseModel):
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
    def _generation_pair(self) -> "RuntimeSessionEvent":
        if (self.generation_lineage is None) != (self.generation is None):
            raise ValueError("generation requires both lineage and counter")
        return self


class RuntimeLifecycleNotice(BaseModel):
    """Nonsecret presentation information, never session or management authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["lifecycle_notice"] = "lifecycle_notice"
    runtime_boot_id: UUID
    connection_id: UUID
    notice_id: UUID
    event: Literal["upgrade_pending"] = "upgrade_pending"


type RuntimeConnectionEvent = RuntimeSessionEvent | RuntimeLifecycleNotice


class RuntimeEventFrame(RootModel[Annotated[RuntimeConnectionEvent, Field(discriminator="kind")]]):
    """Closed event variants on the existing verified connection stream."""
