"""Attendance: a connection follows a person's live sign-in only on that person's exact decision.

An MCP connection that holds no key and has no stored sign-in to resume asks
to be attended. The ask carries no secret and grants nothing. A person's
connection that holds a live password sign-in for the same profile sees the
ask with the asking process's kernel-verified identity, and approves or
declines that one ask. An approved connection receives an attended child of
the person's session, which ends no later than that session does.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.registry import OperationFrontendProjection

ATTENDANCE_PENDING_SECONDS = 120
"""How long an ask waits for the person's decision before it lapses unanswered."""

ATTENDANCE_PENDING_LIMIT = 8
"""The most asks one profile keeps pending; a further ask is refused until one is decided or lapses."""


class RuntimeAttendanceAsk(BaseModel):
    """Ask, from a connection that holds no session, to be attended; or observe that ask.

    ``attendance_status`` names the ask this same connection made. Copying an
    attendance id to another connection confers nothing.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["attendance_request", "attendance_status"]
    request_id: UUID
    profile_id: UUID
    frontend: OperationFrontendProjection
    surface: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    attendance_id: UUID | None = None

    @model_validator(mode="after")
    def _status_names_its_ask(self) -> RuntimeAttendanceAsk:
        if (self.action == "attendance_status") != (self.attendance_id is not None):
            raise ValueError("only an attendance status names an attendance id")
        return self


class RuntimeAttendanceDecide(BaseModel):
    """List, or decide one of, the asks pending for the profile of this connection's own sign-in."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["attendance_inventory", "attendance_decision"]
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    attendance_id: UUID | None = None
    approve: bool | None = None

    @model_validator(mode="after")
    def _decision_names_its_ask(self) -> RuntimeAttendanceDecide:
        deciding = self.action == "attendance_decision"
        if deciding != (self.attendance_id is not None) or deciding != (self.approve is not None):
            raise ValueError("only an attendance decision names an ask and its answer")
        return self


class RuntimeAttendanceCandidate(BaseModel):
    """One pending ask, as the deciding person sees it: the asking process the kernel names, not a claim."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    attendance_id: UUID
    process_id: Annotated[int, Field(gt=0)] | None
    image_path: Annotated[str, Field(min_length=1, max_length=32767)] | None
    frontend: OperationFrontendProjection
    surface: Annotated[str, Field(min_length=1, max_length=64)] | None
    requested_at: datetime
    expires_at: datetime


class RuntimeAttendancePending(BaseModel):
    """An ask recorded for the person's decision; it admits nothing yet."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["attendance_pending"] = "attendance_pending"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    attendance_id: UUID
    expires_at: datetime


class RuntimeAttendanceInventory(BaseModel):
    """The asks pending for this person's profile, and when the person's own session ends."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["attendance_inventory"] = "attendance_inventory"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    profile_id: UUID
    session_expires_at: datetime
    candidates: Annotated[tuple[RuntimeAttendanceCandidate, ...], Field(max_length=ATTENDANCE_PENDING_LIMIT)]


class RuntimeAttendanceDecided(BaseModel):
    """The person's answer to one ask, as applied."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["attendance_decided"] = "attendance_decided"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    attendance_id: UUID
    approved: bool
