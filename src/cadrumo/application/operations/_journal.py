"""Application ports for durable operation state, events, leases, and operands."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator

from ...core import (
    STRICT_FROZEN_CONFIG,
    Hex64Str,
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ...core.identity import ContentDigest
from ...core.time import validate_utc_aware
from ._events import OperationEvent, OperationEventCode, OperationPhaseEvent, OperationTerminalEvent
from ._models import OperationId, OperationIdentity, OperationRevision, OperationTerminalReceipt

OperationLeaseToken = Hex64Str
OperationEventCursor = Annotated[int, Field(ge=0)]
OperationReplayLimit = Annotated[int, Field(gt=0, le=1_000)]


class OperationReplayStatus(StrEnum):
    PAGE = "page"
    CAUGHT_UP = "caught_up"
    EXPIRED = "expired"
    COMPACTED = "compacted"
    UNKNOWN_OPERATION = "unknown_operation"


class OperationLeaseDisposition(StrEnum):
    ACQUIRED = "acquired"
    RENEWED = "renewed"
    RELEASED = "released"
    CONFLICT = "conflict"
    EXPIRED = "expired"
    TAKEN_OVER = "taken_over"
    OWNER_LOST = "owner_lost"


class OperationPersistedSnapshot(BaseModel):
    """Credential-free state and event batch written for one journal transition.

    The runtime :class:`OperationSnapshot` retains its concrete registered request
    payload. This record instead retains only the content digest that addresses
    that confidential operand in secure storage.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1] = 1
    identity: OperationIdentity
    request_reference: ContentDigest
    revision: OperationRevision
    lifecycle: OperationLifecycle
    terminal_condition: OperationTerminalCondition | None = None
    effect: OperationEffect = OperationEffect.NONE
    phase_code: OperationEventCode | None = None
    started_at: datetime
    updated_at: datetime
    event_cursor: OperationEventCursor = 0
    terminal_receipt: OperationTerminalReceipt | None = None
    events: tuple[OperationEvent, ...] = ()

    @model_validator(mode="after")
    def _validate_persisted_snapshot(self) -> OperationPersistedSnapshot:
        validate_utc_aware(self.started_at)
        validate_utc_aware(self.updated_at)
        if self.updated_at < self.started_at:
            raise ValueError("persisted operation snapshot cannot update before it starts")
        self._validate_terminal_state()
        self._validate_events()
        return self

    def _validate_terminal_state(self) -> None:
        terminal = self.lifecycle is OperationLifecycle.TERMINAL
        if terminal != (self.terminal_condition is not None):
            raise ValueError("terminal lifecycle requires exactly one terminal condition")
        if terminal != (self.terminal_receipt is not None):
            raise ValueError("terminal lifecycle requires exactly one terminal receipt")
        if self.terminal_receipt is None:
            return
        receipt = self.terminal_receipt
        if receipt.identity != self.identity:
            raise ValueError("terminal receipt identity does not match persisted operation snapshot")
        if receipt.revision != self.revision:
            raise ValueError("terminal receipt revision does not match persisted operation snapshot")
        if receipt.condition is not self.terminal_condition:
            raise ValueError("terminal receipt condition does not match persisted operation snapshot")
        if receipt.effect is not self.effect:
            raise ValueError("terminal receipt effect does not match persisted operation snapshot")
        if receipt.settled_at != self.updated_at:
            raise ValueError("terminal receipt settlement time does not match persisted operation snapshot")

    def _validate_events(self) -> None:
        if not self.events:
            if self.lifecycle is OperationLifecycle.TERMINAL:
                raise ValueError("terminal persisted operation snapshot requires one terminal event")
            if self.phase_code is not None:
                raise ValueError("persisted snapshot without phase events requires no phase code")
            return
        if any(event.identity != self.identity for event in self.events):
            raise ValueError("journal event identity does not match persisted operation snapshot")
        if any(event.revision != self.revision for event in self.events):
            raise ValueError("journal event revision does not match persisted operation snapshot")
        sequences = tuple(event.sequence for event in self.events)
        if any(current != previous + 1 for previous, current in pairwise(sequences)):
            raise ValueError("journal event sequences must be contiguous")
        if sequences[-1] != self.event_cursor:
            raise ValueError("persisted event cursor must equal the final journal event sequence")
        timestamps = tuple(event.timestamp for event in self.events)
        if any(current < previous for previous, current in pairwise(timestamps)):
            raise ValueError("journal event timestamps must be nondecreasing")
        if self.updated_at != timestamps[-1]:
            raise ValueError("persisted updated time must equal the final journal event timestamp")
        phase_events = tuple(event for event in self.events if isinstance(event, OperationPhaseEvent))
        latest_phase_code = phase_events[-1].phase_code if phase_events else None
        if self.phase_code != latest_phase_code:
            raise ValueError("persisted phase code must equal the latest journal phase event")
        terminal_events = tuple(event for event in self.events if isinstance(event, OperationTerminalEvent))
        if self.lifecycle is not OperationLifecycle.TERMINAL:
            if terminal_events:
                raise ValueError("non-terminal persisted operation snapshot forbids terminal events")
            return
        if len(terminal_events) != 1 or not isinstance(self.events[-1], OperationTerminalEvent):
            raise ValueError("terminal persisted operation snapshot requires exactly one final terminal event")
        if self.events[-1].receipt != self.terminal_receipt:
            raise ValueError("terminal journal event receipt does not match persisted operation snapshot")


class OperationOwnerLease(BaseModel):
    """Immutable proof that one supervisor currently owns an operation."""

    model_config = STRICT_FROZEN_CONFIG

    operation_id: OperationId
    owner_id: Hex64Str
    token: OperationLeaseToken
    acquired_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def _validate_window(self) -> OperationOwnerLease:
        validate_utc_aware(self.acquired_at)
        validate_utc_aware(self.expires_at)
        if self.expires_at <= self.acquired_at:
            raise ValueError("operation owner lease must expire after acquisition")
        return self


def _validate_lease_result_presence(
    disposition: OperationLeaseDisposition,
    predecessor: OperationOwnerLease | None,
    current: OperationOwnerLease | None,
) -> None:
    requires_current = {
        OperationLeaseDisposition.ACQUIRED,
        OperationLeaseDisposition.RENEWED,
        OperationLeaseDisposition.CONFLICT,
        OperationLeaseDisposition.TAKEN_OVER,
    }
    requires_predecessor = {
        OperationLeaseDisposition.RENEWED,
        OperationLeaseDisposition.RELEASED,
        OperationLeaseDisposition.EXPIRED,
        OperationLeaseDisposition.TAKEN_OVER,
        OperationLeaseDisposition.OWNER_LOST,
    }
    if disposition in requires_current and current is None:
        raise ValueError(f"{disposition.value} lease result requires the current lease")
    if disposition in requires_predecessor and predecessor is None:
        raise ValueError(f"{disposition.value} lease result requires predecessor evidence")
    if disposition in {OperationLeaseDisposition.ACQUIRED, OperationLeaseDisposition.CONFLICT} and predecessor:
        raise ValueError(f"{disposition.value} lease result forbids predecessor evidence")
    if (
        disposition
        in {
            OperationLeaseDisposition.RELEASED,
            OperationLeaseDisposition.EXPIRED,
            OperationLeaseDisposition.OWNER_LOST,
        }
        and current
    ):
        raise ValueError(f"{disposition.value} lease result forbids a current lease")


def _validate_lease_result_identity(
    predecessor: OperationOwnerLease | None,
    current: OperationOwnerLease | None,
) -> None:
    if predecessor and current and predecessor.operation_id != current.operation_id:
        raise ValueError("lease transition must preserve operation identity")


def _validate_lease_result_timing(
    observed_at: datetime,
    current: OperationOwnerLease | None,
) -> None:
    if current and current.acquired_at > observed_at:
        raise ValueError("current lease cannot be acquired after its evidence time")


def _validate_lease_renewal(
    predecessor: OperationOwnerLease,
    current: OperationOwnerLease,
) -> None:
    if (predecessor.owner_id, predecessor.token) != (current.owner_id, current.token):
        raise ValueError("lease renewal must preserve owner and token identity")
    if current.expires_at <= predecessor.expires_at:
        raise ValueError("lease renewal must extend the expiry")


def _validate_lease_takeover(
    observed_at: datetime,
    predecessor: OperationOwnerLease,
    current: OperationOwnerLease,
) -> None:
    if predecessor.owner_id == current.owner_id or predecessor.token == current.token:
        raise ValueError("lease takeover must change owner and token identity")
    if predecessor.expires_at > current.acquired_at or predecessor.expires_at > observed_at:
        raise ValueError("lease takeover requires an expired predecessor")


def _validate_lease_conflict(observed_at: datetime, current: OperationOwnerLease) -> None:
    if current.expires_at <= observed_at:
        raise ValueError("lease conflict requires an unexpired current lease")


def _validate_expired_lease_result(
    disposition: OperationLeaseDisposition,
    observed_at: datetime,
    predecessor: OperationOwnerLease,
) -> None:
    if predecessor.expires_at > observed_at:
        raise ValueError(f"{disposition.value} requires an expired predecessor")


def _validate_lease_result_transition(
    disposition: OperationLeaseDisposition,
    observed_at: datetime,
    predecessor: OperationOwnerLease | None,
    current: OperationOwnerLease | None,
) -> None:
    if disposition is OperationLeaseDisposition.RENEWED:
        assert predecessor is not None and current is not None
        _validate_lease_renewal(predecessor, current)
    if disposition is OperationLeaseDisposition.TAKEN_OVER:
        assert predecessor is not None and current is not None
        _validate_lease_takeover(observed_at, predecessor, current)
    if disposition is OperationLeaseDisposition.CONFLICT:
        assert current is not None
        _validate_lease_conflict(observed_at, current)
    if disposition in {OperationLeaseDisposition.EXPIRED, OperationLeaseDisposition.OWNER_LOST}:
        assert predecessor is not None
        _validate_expired_lease_result(disposition, observed_at, predecessor)


class OperationLeaseResult(BaseModel):
    """Stable evidence for every durable lease transition or refusal."""

    model_config = STRICT_FROZEN_CONFIG

    disposition: OperationLeaseDisposition
    observed_at: datetime
    evidence_ref: ContentDigest
    predecessor: OperationOwnerLease | None = None
    current: OperationOwnerLease | None = None

    @model_validator(mode="after")
    def _validate_shape(self) -> OperationLeaseResult:
        validate_utc_aware(self.observed_at)
        _validate_lease_result_presence(self.disposition, self.predecessor, self.current)
        _validate_lease_result_identity(self.predecessor, self.current)
        _validate_lease_result_timing(self.observed_at, self.current)
        _validate_lease_result_transition(self.disposition, self.observed_at, self.predecessor, self.current)
        return self


def _validate_replay_status_events(status: OperationReplayStatus, events: tuple[OperationEvent, ...]) -> None:
    if status is OperationReplayStatus.PAGE and not events:
        raise ValueError("replay page status requires at least one event")
    if status is not OperationReplayStatus.PAGE and events:
        raise ValueError("non-page replay status cannot carry events")


def _validate_replay_sequence(
    requested_cursor: OperationEventCursor,
    events: tuple[OperationEvent, ...],
    next_cursor: OperationEventCursor,
) -> None:
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
    _validate_replay_status_events(status, events)
    _validate_replay_sequence(requested_cursor, events, next_cursor)


def _validate_replay_cursor_state(
    status: OperationReplayStatus,
    requested_cursor: OperationEventCursor,
    next_cursor: OperationEventCursor,
    restart_cursor: OperationEventCursor | None,
) -> None:
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


@runtime_checkable
class OperationJournal(Protocol):
    """Atomic snapshot-plus-event persistence with optimistic revision checks."""

    async def load(self, operation_id: OperationId) -> OperationPersistedSnapshot: ...

    async def commit(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        expected_revision: OperationRevision,
        lease: OperationOwnerLease,
    ) -> None:
        """Atomically compare revision and append the snapshot and ordered events."""
        ...


@runtime_checkable
class OperationEventStream(Protocol):
    """Replay ordered operation events from an exclusive cursor."""

    async def read_after(
        self,
        operation_id: OperationId,
        cursor: OperationEventCursor,
        *,
        limit: OperationReplayLimit,
    ) -> OperationReplayPage: ...


@runtime_checkable
class OperationLeaseRepository(Protocol):
    """Acquire, renew, and release the durable owner lease."""

    async def acquire(
        self,
        operation_id: OperationId,
        owner_id: Hex64Str,
        *,
        expires_at: datetime,
    ) -> OperationLeaseResult: ...

    async def inspect(self, operation_id: OperationId) -> OperationLeaseResult: ...

    async def compare_and_swap(
        self,
        predecessor: OperationOwnerLease | None,
        *,
        owner_id: Hex64Str,
        expires_at: datetime,
    ) -> OperationLeaseResult: ...

    async def release(self, lease: OperationOwnerLease) -> OperationLeaseResult: ...


@runtime_checkable
class OperationSecureReferenceStore(Protocol):
    """Store and resolve confidential operands outside credential-free journals."""

    async def put(self, operand: BaseModel) -> ContentDigest: ...

    async def resolve[OperandT: BaseModel](
        self,
        reference: ContentDigest,
        operand_type: type[OperandT],
    ) -> OperandT: ...


__all__ = [
    "OperationEventCursor",
    "OperationEventStream",
    "OperationJournal",
    "OperationLeaseDisposition",
    "OperationLeaseRepository",
    "OperationLeaseResult",
    "OperationLeaseToken",
    "OperationOwnerLease",
    "OperationPersistedSnapshot",
    "OperationReplayLimit",
    "OperationReplayPage",
    "OperationReplayStatus",
    "OperationSecureReferenceStore",
]
