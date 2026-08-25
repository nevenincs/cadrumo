"""Application-owned bounded operation-event replay contracts."""

from __future__ import annotations

from enum import StrEnum
from itertools import pairwise
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from ....core import STRICT_FROZEN_CONFIG
from ..event_replay import OperationEventCursor
from .events import OperationEvent

OperationReplayLimit = Annotated[int, Field(gt=0, le=1_000)]


class OperationReplayStatus(StrEnum):
    """Outcome category for one bounded event replay request."""

    PAGE = "page"
    CAUGHT_UP = "caught_up"
    EXPIRED = "expired"
    COMPACTED = "compacted"
    UNKNOWN_OPERATION = "unknown_operation"


def _validate_replay_status_events(status: OperationReplayStatus, events: tuple[OperationEvent, ...]) -> None:
    """Validate whether a replay status may carry event rows."""
    if status is OperationReplayStatus.PAGE and not events:
        raise ValueError("replay page status requires at least one event")
    if status is not OperationReplayStatus.PAGE and events:
        raise ValueError("non-page replay status cannot carry events")


def _validate_replay_sequence(
    requested_cursor: OperationEventCursor,
    events: tuple[OperationEvent, ...],
    next_cursor: OperationEventCursor,
) -> None:
    """Validate contiguous event sequence and resulting cursor."""
    if not events:
        return
    sequences = tuple(event.sequence for event in events)
    if sequences[0] != requested_cursor + 1 or any(
        current != previous + 1 for previous, current in pairwise(sequences)
    ):
        raise ValueError("replay events must be contiguous after the requested cursor")
    if next_cursor != sequences[-1]:
        raise ValueError("replay next cursor must equal the final event sequence")


def _validate_replay_events(
    status: OperationReplayStatus,
    requested_cursor: OperationEventCursor,
    events: tuple[OperationEvent, ...],
    next_cursor: OperationEventCursor,
) -> None:
    """Validate event payload and sequence rules for a replay page."""
    _validate_replay_status_events(status, events)
    _validate_replay_sequence(requested_cursor, events, next_cursor)


def _validate_replay_cursor_state(
    status: OperationReplayStatus,
    requested_cursor: OperationEventCursor,
    next_cursor: OperationEventCursor,
    restart_cursor: OperationEventCursor | None,
) -> None:
    """Validate status-specific next and restart cursor semantics."""
    if status in {OperationReplayStatus.CAUGHT_UP, OperationReplayStatus.UNKNOWN_OPERATION}:
        if next_cursor != requested_cursor:
            raise ValueError(f"{status.value} replay must preserve the requested cursor")
        if restart_cursor is not None:
            raise ValueError(f"{status.value} replay forbids a restart cursor")
        return
    if status in {OperationReplayStatus.EXPIRED, OperationReplayStatus.COMPACTED}:
        if restart_cursor is None:
            raise ValueError(f"{status.value} replay requires a restart cursor")
        if next_cursor != restart_cursor:
            raise ValueError("replay next cursor must equal the authoritative restart cursor")
        if restart_cursor <= requested_cursor:
            raise ValueError("replay restart cursor must advance beyond the requested cursor")
        return
    if restart_cursor is not None:
        raise ValueError("event replay page forbids a restart cursor")


class OperationReplayPage(BaseModel):
    """Authoritative bounded replay result and next exclusive cursor."""

    model_config = STRICT_FROZEN_CONFIG

    status: OperationReplayStatus
    requested_cursor: OperationEventCursor
    events: tuple[OperationEvent, ...]
    next_cursor: OperationEventCursor
    restart_cursor: OperationEventCursor | None = None

    @model_validator(mode="after")
    def _validate_status(self) -> OperationReplayPage:
        _validate_replay_events(self.status, self.requested_cursor, self.events, self.next_cursor)
        _validate_replay_cursor_state(self.status, self.requested_cursor, self.next_cursor, self.restart_cursor)
        return self


__all__ = [
    "OperationEventCursor",
    "OperationReplayLimit",
    "OperationReplayPage",
    "OperationReplayStatus",
]
