"""Non-authoritative shared sign-in presence over the verified runtime transport."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, model_validator

from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from cadrumo.core.time.utc import UtcInstant


class SignInPresence(StrEnum):
    """Receipt metadata availability, never proof of authentication."""

    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class SignInStatus(BaseModel):
    """Read-only presence and deadlines; contains no secret or portable bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    presence: SignInPresence
    idle_deadline: UtcInstant | None = None
    absolute_deadline: UtcInstant | None = None

    @model_validator(mode="after")
    def _deadlines_follow_presence(self) -> SignInStatus:
        if self.presence is SignInPresence.PRESENT:
            if self.idle_deadline is None or self.absolute_deadline is None:
                raise ValueError("present sign-in requires both deadlines")
            if self.idle_deadline > self.absolute_deadline:
                raise ValueError("idle deadline exceeds the absolute deadline")
        elif self.idle_deadline is not None or self.absolute_deadline is not None:
            raise ValueError("unavailable sign-in carries no deadlines")
        return self


class SignInStatusRequest(BaseModel):
    """Observe one profile without admitting a session or opening a worker.

    ``watch`` also asks for a ``sign_in_changed`` cue on this connection whenever
    any sign-in may have changed, until the connection closes.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["sign_in_status"] = "sign_in_status"
    request_id: UUID
    profile_id: UUID
    watch: bool = False


class SignInStatusReply(BaseModel):
    """Correlated observation; the runtime connection remains unauthenticated."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["sign_in_status"] = "sign_in_status"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID
    status: SignInStatus


class HumanSignedOut(BaseModel):
    """Human revocation outcome, with deletion and remaining automation access explicit.

    ``automation_enabled`` is the profile's persisted automation setting. It is
    not access. ``automation_access_remains`` reports whether an external application can still
    reach the profile after the sign-out: a key the person issued is not tied to
    the sign-in, so it is true while automation is enabled and an active,
    unexpired key of an active unattended grant remains, false otherwise, and
    absent when the automation store could not be read.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["human_signed_out"] = "human_signed_out"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID
    session_ids: tuple[UUID, ...]
    receipt_removed: bool
    keychain_removed: bool
    automation_enabled: bool | None
    automation_access_remains: bool | None
