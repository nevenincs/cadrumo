"""Application ports for durable operation state, events, leases, and operands."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG, Hex64Str
from ...core.identity import ContentDigest
from ...core.time import validate_utc_aware
from ._events import OperationEvent
from ._models import OperationId, OperationRevision, OperationSnapshot

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
        if self.disposition in requires_current and self.current is None:
            raise ValueError(f"{self.disposition.value} lease result requires the current lease")
        if self.disposition in requires_predecessor and self.predecessor is None:
            raise ValueError(f"{self.disposition.value} lease result requires predecessor evidence")
        if (
            self.disposition in {OperationLeaseDisposition.ACQUIRED, OperationLeaseDisposition.CONFLICT}
            and self.predecessor
        ):
            raise ValueError(f"{self.disposition.value} lease result forbids predecessor evidence")
        if (
            self.disposition
            in {
                OperationLeaseDisposition.RELEASED,
                OperationLeaseDisposition.EXPIRED,
                OperationLeaseDisposition.OWNER_LOST,
            }
            and self.current
        ):
            raise ValueError(f"{self.disposition.value} lease result forbids a current lease")
        if self.predecessor and self.current and self.predecessor.operation_id != self.current.operation_id:
            raise ValueError("lease transition must preserve operation identity")
        if self.current and self.current.acquired_at > self.observed_at:
            raise ValueError("current lease cannot be acquired after its evidence time")
        if self.disposition is OperationLeaseDisposition.RENEWED:
            assert self.predecessor is not None and self.current is not None
            if (self.predecessor.owner_id, self.predecessor.token) != (self.current.owner_id, self.current.token):
                raise ValueError("lease renewal must preserve owner and token identity")
            if self.current.expires_at <= self.predecessor.expires_at:
                raise ValueError("lease renewal must extend the expiry")
        if self.disposition is OperationLeaseDisposition.TAKEN_OVER:
            assert self.predecessor is not None and self.current is not None
            if self.predecessor.owner_id == self.current.owner_id or self.predecessor.token == self.current.token:
                raise ValueError("lease takeover must change owner and token identity")
            if self.predecessor.expires_at > self.current.acquired_at or self.predecessor.expires_at > self.observed_at:
                raise ValueError("lease takeover requires an expired predecessor")
        if self.disposition is OperationLeaseDisposition.CONFLICT:
            assert self.current is not None
            if self.current.expires_at <= self.observed_at:
                raise ValueError("lease conflict requires an unexpired current lease")
        if self.disposition in {OperationLeaseDisposition.EXPIRED, OperationLeaseDisposition.OWNER_LOST}:
            assert self.predecessor is not None
            if self.predecessor.expires_at > self.observed_at:
                raise ValueError(f"{self.disposition.value} requires an expired predecessor")
        return self


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
        if self.status is OperationReplayStatus.PAGE and not self.events:
            raise ValueError("replay page status requires at least one event")
        if self.status is not OperationReplayStatus.PAGE and self.events:
            raise ValueError("non-page replay status cannot carry events")
        if self.events:
            sequences = tuple(event.sequence for event in self.events)
            if sequences[0] != self.requested_cursor + 1 or any(
                current != previous + 1 for previous, current in pairwise(sequences)
            ):
                raise ValueError("replay events must be contiguous after the requested cursor")
            if self.next_cursor != sequences[-1]:
                raise ValueError("replay next cursor must equal the final event sequence")
        if self.status in {OperationReplayStatus.CAUGHT_UP, OperationReplayStatus.UNKNOWN_OPERATION}:
            if self.next_cursor != self.requested_cursor:
                raise ValueError(f"{self.status.value} replay must preserve the requested cursor")
            if self.restart_cursor is not None:
                raise ValueError(f"{self.status.value} replay forbids a restart cursor")
        elif self.status in {OperationReplayStatus.EXPIRED, OperationReplayStatus.COMPACTED}:
            if self.restart_cursor is None:
                raise ValueError(f"{self.status.value} replay requires a restart cursor")
            if self.next_cursor != self.restart_cursor:
                raise ValueError("replay next cursor must equal the authoritative restart cursor")
            if self.restart_cursor <= self.requested_cursor:
                raise ValueError("replay restart cursor must advance beyond the requested cursor")
        elif self.restart_cursor is not None:
            raise ValueError("event replay page forbids a restart cursor")
        return self


@runtime_checkable
class OperationJournal(Protocol):
    """Atomic snapshot-plus-event persistence with optimistic revision checks."""

    async def load(self, operation_id: OperationId) -> OperationSnapshot[BaseModel]: ...

    async def commit(
        self,
        snapshot: OperationSnapshot[BaseModel],
        events: tuple[OperationEvent, ...],
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
    "OperationReplayLimit",
    "OperationReplayPage",
    "OperationReplayStatus",
    "OperationSecureReferenceStore",
]
