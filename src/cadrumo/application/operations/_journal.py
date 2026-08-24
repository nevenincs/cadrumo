"""Application ports for durable operation state, events, leases, and operands."""

from __future__ import annotations

from datetime import datetime
from itertools import pairwise
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, model_validator

from ...core import (
    STRICT_FROZEN_CONFIG,
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ...core.identity import ContentDigest
from ...core.time import validate_utc_aware
from ._capabilities import OperationRequestStoragePolicy
from ._events import (
    OperationEvent,
    OperationEventCode,
    OperationPhaseEvent,
    OperationProgressEvent,
    OperationTerminalEvent,
)
from ._interactions import OperationConsumedInteraction, OperationPendingInteraction
from ._leases import (
    OperationConflictScopeReference,
    OperationLeaseObservation,
    OperationLeaseResult,
    OperationOwnerLease,
)
from ._models import (
    OperationId,
    OperationIdempotencyClaim,
    OperationIdentity,
    OperationRevision,
    OperationTerminalReceipt,
)
from ._replay import (
    OperationEventCursor,
    OperationReplayLimit,
    OperationReplayPage,
    OperationReplayStatus,
)
from ._secret_submission import OperationSecretRequirement


class OperationPersistedSnapshot(BaseModel):
    """Credential-free state and event batch written for one journal transition.

    The runtime :class:`OperationSnapshot` retains its concrete registered request
    payload. This record instead retains only the content digest that addresses
    that confidential operand in secure storage.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[6] = 6
    identity: OperationIdentity
    definition_contract_digest: ContentDigest
    request_storage: OperationRequestStoragePolicy
    request_reference: ContentDigest
    credential_free_request_json: str | None = None
    secret_requirement: OperationSecretRequirement | None = None
    executor_entered_at: datetime | None = None
    revision: OperationRevision
    lifecycle: OperationLifecycle
    terminal_condition: OperationTerminalCondition | None = None
    effect: OperationEffect = OperationEffect.NONE
    phase_code: OperationEventCode | None = None
    started_at: datetime
    updated_at: datetime
    execution_deadline: datetime | None
    cleanup_deadline: datetime | None
    cancellation_requested_at: datetime | None
    cancellation_acknowledged_at: datetime | None
    cancellation_deferred: bool
    event_cursor: OperationEventCursor = 0
    terminal_receipt: OperationTerminalReceipt | None = None
    events: tuple[OperationEvent, ...] = ()
    idempotency_claim: OperationIdempotencyClaim | None = None
    pending_interaction: OperationPendingInteraction | None = None
    consumed_interactions: tuple[OperationConsumedInteraction, ...] = ()

    @property
    def operation_id(self) -> OperationId:
        """Return the filename identity consumed by the journal substrate."""
        return self.identity.operation_id

    @model_validator(mode="after")
    def _validate_persisted_snapshot(self) -> OperationPersistedSnapshot:
        validate_utc_aware(self.started_at)
        validate_utc_aware(self.updated_at)
        if self.updated_at < self.started_at:
            raise ValueError("persisted operation snapshot cannot update before it starts")
        _validate_deadline_and_cancellation_state(self)
        _validate_request_storage(self)
        _validate_secret_state(self)
        _validate_terminal_state(self)
        _validate_checkpoint_state(self)
        _validate_events(self)
        return self


class OperationProgressFoldCheckpoint(BaseModel):
    """Compaction-safe progress state through one authoritative event cursor."""

    model_config = STRICT_FROZEN_CONFIG

    identity: OperationIdentity
    through_cursor: OperationEventCursor
    phase_code: OperationEventCode | None = None
    progress_event: OperationProgressEvent | None = None

    @model_validator(mode="after")
    def _validate_checkpoint(self) -> OperationProgressFoldCheckpoint:
        progress = self.progress_event
        if progress is not None:
            if progress.identity != self.identity:
                raise ValueError("progress checkpoint event does not match operation identity")
            if progress.sequence > self.through_cursor:
                raise ValueError("progress checkpoint event cannot exceed its checkpoint cursor")
        return self


class OperationProgressFoldInput(BaseModel):
    """Exact checkpoint suffix needed to fold current progress through an anchor."""

    model_config = STRICT_FROZEN_CONFIG

    checkpoint: OperationProgressFoldCheckpoint | None = None
    events: tuple[OperationEvent, ...]


class OperationObservationMaterialization(BaseModel):
    """Snapshot, replay page, and progress input from one atomic journal read."""

    model_config = STRICT_FROZEN_CONFIG

    snapshot: OperationPersistedSnapshot
    anchor_cursor: OperationEventCursor
    replay: OperationReplayPage
    progress_fold: OperationProgressFoldInput

    @model_validator(mode="after")
    def _validate_materialization(self) -> OperationObservationMaterialization:
        if self.anchor_cursor != self.snapshot.event_cursor:
            raise ValueError("observation anchor must equal the current snapshot cursor")
        if self.replay.status is OperationReplayStatus.UNKNOWN_OPERATION:
            raise ValueError("an observation materialization cannot represent an unknown operation")
        if self.replay.requested_cursor > self.anchor_cursor:
            raise ValueError("observation replay cursor cannot exceed its anchor")
        if self.replay.next_cursor > self.anchor_cursor:
            raise ValueError("observation replay result cannot exceed its anchor")
        if (
            self.replay.status is OperationReplayStatus.CAUGHT_UP
            and self.replay.next_cursor != self.anchor_cursor
        ):
            raise ValueError("caught-up observation replay must reach its authoritative anchor")
        self._validate_event_set(self.replay.events, label="replay")
        self._validate_progress_fold()
        if self.replay.status in {OperationReplayStatus.EXPIRED, OperationReplayStatus.COMPACTED}:
            checkpoint = self.progress_fold.checkpoint
            if checkpoint is None or checkpoint.through_cursor != self.replay.restart_cursor:
                raise ValueError("resynchronizing observation replay requires its exact progress checkpoint")
        return self

    def _validate_event_set(self, events: tuple[OperationEvent, ...], *, label: str) -> None:
        if any(event.identity != self.snapshot.identity for event in events):
            raise ValueError(f"observation {label} event does not match operation identity")
        if any(event.revision > self.snapshot.revision for event in events):
            raise ValueError(f"observation {label} event revision cannot exceed its snapshot")
        if any(event.sequence > self.anchor_cursor for event in events):
            raise ValueError(f"observation {label} event cannot exceed its anchor")

    def _validate_progress_fold(self) -> None:
        fold = self.progress_fold
        checkpoint = fold.checkpoint
        start_cursor = checkpoint.through_cursor if checkpoint is not None else 0
        if checkpoint is not None:
            if checkpoint.identity != self.snapshot.identity:
                raise ValueError("progress checkpoint does not match operation identity")
            if checkpoint.through_cursor > self.anchor_cursor:
                raise ValueError("progress checkpoint cannot exceed the observation anchor")
            if (
                checkpoint.progress_event is not None
                and checkpoint.progress_event.revision > self.snapshot.revision
            ):
                raise ValueError("progress checkpoint revision cannot exceed its snapshot")
        self._validate_event_set(fold.events, label="progress-fold")
        sequences = tuple(event.sequence for event in fold.events)
        expected = tuple(range(start_cursor + 1, self.anchor_cursor + 1))
        if sequences != expected:
            raise ValueError("progress fold must cover every event after its checkpoint through the anchor")


class OperationObservationUnknownOperationError(LookupError):
    """The locked observation read found no journal for the requested operation."""

    def __init__(self, operation_id: OperationId) -> None:
        self.operation_id = operation_id
        super().__init__("operation observation requires an existing operation")


class OperationObservationCursorAheadError(ValueError):
    """The caller cursor is beyond the authoritative anchor read under the journal lock."""

    def __init__(self, *, requested_cursor: OperationEventCursor, anchor_cursor: OperationEventCursor) -> None:
        self.requested_cursor = requested_cursor
        self.anchor_cursor = anchor_cursor
        super().__init__("operation observation cursor exceeds its authoritative anchor")


def _validate_request_storage(snapshot: OperationPersistedSnapshot) -> None:
    journal_request = snapshot.credential_free_request_json
    if snapshot.request_storage is OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL:
        if journal_request is None or not journal_request:
            raise ValueError("credential-free request storage requires an inline canonical request")
    elif journal_request is not None:
        raise ValueError("secure-reference request storage forbids an inline journal request")


def _validate_secret_state(snapshot: OperationPersistedSnapshot) -> None:
    requirement = snapshot.secret_requirement
    entered_at = snapshot.executor_entered_at
    if entered_at is not None:
        validate_utc_aware(entered_at)
        if entered_at < snapshot.started_at or entered_at > snapshot.updated_at:
            raise ValueError("executor entry must fall within the persisted operation timeline")
        if snapshot.lifecycle in {OperationLifecycle.CREATED, OperationLifecycle.QUEUED}:
            raise ValueError("created or queued operation cannot record executor entry")
    if requirement is None:
        return
    if requirement.identity != snapshot.identity:
        raise ValueError("ephemeral secret requirement does not match operation identity")
    if requirement.revision != 0:
        raise ValueError("ephemeral secret requirement must bind the initial operation revision")
    if requirement.expires_at <= snapshot.started_at:
        raise ValueError("ephemeral secret requirement must expire after operation creation")
    if (
        snapshot.lifecycle is OperationLifecycle.TERMINAL
        and entered_at is None
        and snapshot.effect is not OperationEffect.NONE
    ):
        raise ValueError("pre-entry ephemeral secret settlement must retain none effect")


def _validate_deadline_and_cancellation_state(snapshot: OperationPersistedSnapshot) -> None:
    """Keep durable deadline and cooperative-stop facts ordered and correlated."""
    execution_deadline = snapshot.execution_deadline
    cleanup_deadline = snapshot.cleanup_deadline
    requested_at = snapshot.cancellation_requested_at
    acknowledged_at = snapshot.cancellation_acknowledged_at

    if snapshot.cancellation_deferred:
        if snapshot.executor_entered_at is None:
            raise ValueError("deferred cancellation requires executor entry")
        if snapshot.lifecycle is OperationLifecycle.TERMINAL:
            raise ValueError("terminal operation cannot defer cancellation")
        if acknowledged_at is not None:
            raise ValueError("acknowledged cancellation cannot remain deferred")

    for timestamp in (execution_deadline, cleanup_deadline, requested_at, acknowledged_at):
        if timestamp is not None:
            validate_utc_aware(timestamp)

    if execution_deadline is not None and execution_deadline < snapshot.started_at:
        raise ValueError("execution deadline cannot precede operation start")
    if requested_at is None:
        if cleanup_deadline is not None:
            raise ValueError("cleanup deadline requires a cancellation request")
        if acknowledged_at is not None:
            raise ValueError("cancellation acknowledgement requires a cancellation request")
        return
    if requested_at < snapshot.started_at or requested_at > snapshot.updated_at:
        raise ValueError("cancellation request must fall within the persisted operation timeline")
    if cleanup_deadline is None or cleanup_deadline <= requested_at:
        raise ValueError("cancellation request requires a later cleanup deadline")
    if snapshot.lifecycle in {
        OperationLifecycle.CREATED,
        OperationLifecycle.QUEUED,
        OperationLifecycle.RUNNING,
        OperationLifecycle.WAITING_FOR_INTERACTION,
        OperationLifecycle.WAITING_FOR_EXTERNAL,
    }:
        raise ValueError("cancellation request requires a cancellation or settlement lifecycle")
    if acknowledged_at is not None:
        if acknowledged_at < requested_at or acknowledged_at > snapshot.updated_at:
            raise ValueError("cancellation acknowledgement must follow the request within the operation timeline")
        if snapshot.lifecycle is OperationLifecycle.CANCELLATION_REQUESTED:
            raise ValueError("cancellation acknowledgement requires settlement lifecycle")
    if snapshot.terminal_condition is OperationTerminalCondition.CANCELLED and acknowledged_at is None:
        raise ValueError("cancelled operation requires a durable cancellation acknowledgement")


def _validate_checkpoint_state(snapshot: OperationPersistedSnapshot) -> None:
    _validate_idempotency_claim(snapshot)
    _validate_pending_interaction(snapshot)
    _validate_consumed_interactions(snapshot)


def _validate_idempotency_claim(snapshot: OperationPersistedSnapshot) -> None:
    claim = snapshot.idempotency_claim
    if claim is None:
        return
    if claim.operation_id != snapshot.operation_id or claim.definition_id != snapshot.identity.definition_id:
        raise ValueError("idempotency claim does not match persisted operation identity")
    if claim.subject_ref != snapshot.identity.subject_ref or claim.request_reference != snapshot.request_reference:
        raise ValueError("idempotency claim does not match persisted request identity")


def _validate_pending_interaction(snapshot: OperationPersistedSnapshot) -> None:
    pending = snapshot.pending_interaction
    if pending is None:
        return
    if snapshot.lifecycle is not OperationLifecycle.WAITING_FOR_INTERACTION:
        raise ValueError("pending interaction requires waiting-for-interaction lifecycle")
    if pending.request.identity != snapshot.identity or pending.request.revision != snapshot.revision:
        raise ValueError("pending interaction does not match persisted operation revision")


def _validate_consumed_interactions(snapshot: OperationPersistedSnapshot) -> None:
    consumed_ids = tuple(item.interaction_id for item in snapshot.consumed_interactions)
    if len(set(consumed_ids)) != len(consumed_ids):
        raise ValueError("consumed interaction identities must be unique")
    pending = snapshot.pending_interaction
    if pending is not None and pending.request.interaction_id in consumed_ids:
        raise ValueError("pending interaction cannot already be consumed")


def _validate_terminal_state(snapshot: OperationPersistedSnapshot) -> None:
    """Validate lifecycle markers and the optional terminal receipt."""
    terminal = snapshot.lifecycle is OperationLifecycle.TERMINAL
    if terminal != (snapshot.terminal_condition is not None):
        raise ValueError("terminal lifecycle requires exactly one terminal condition")
    if terminal != (snapshot.terminal_receipt is not None):
        raise ValueError("terminal lifecycle requires exactly one terminal receipt")
    if snapshot.terminal_receipt is not None:
        _validate_terminal_receipt(snapshot)


def _validate_terminal_receipt(snapshot: OperationPersistedSnapshot) -> None:
    """Validate that a terminal receipt agrees with its enclosing snapshot."""
    receipt = snapshot.terminal_receipt
    if receipt is None:
        return
    if receipt.identity != snapshot.identity:
        raise ValueError("terminal receipt identity does not match persisted operation snapshot")
    if receipt.revision != snapshot.revision:
        raise ValueError("terminal receipt revision does not match persisted operation snapshot")
    if receipt.condition is not snapshot.terminal_condition:
        raise ValueError("terminal receipt condition does not match persisted operation snapshot")
    if receipt.effect is not snapshot.effect:
        raise ValueError("terminal receipt effect does not match persisted operation snapshot")
    if receipt.settled_at != snapshot.updated_at:
        raise ValueError("terminal receipt settlement time does not match persisted operation snapshot")


def _validate_events(snapshot: OperationPersistedSnapshot) -> None:
    """Validate event identity, ordering, derived fields, and terminal shape."""
    if not snapshot.events:
        _validate_empty_events(snapshot)
        return
    _validate_event_identity_and_revision(snapshot)
    _validate_event_sequences(snapshot)
    _validate_event_timeline(snapshot)
    _validate_phase_code(snapshot)
    _validate_terminal_events(snapshot)


def _validate_empty_events(snapshot: OperationPersistedSnapshot) -> None:
    """Validate the only legal event-free snapshot states.

    A revision can intentionally advance without publishing a new event. That
    transition retains the prior cursor and phase projection; requiring a
    phase-less state here would make cancellation and other event-free
    compare-and-swap transitions impossible after a phase has been published.
    """
    if snapshot.lifecycle is OperationLifecycle.TERMINAL:
        raise ValueError("terminal persisted operation snapshot requires one terminal event")


def _validate_event_identity_and_revision(snapshot: OperationPersistedSnapshot) -> None:
    """Ensure every event belongs to the same operation revision."""
    if any(event.identity != snapshot.identity for event in snapshot.events):
        raise ValueError("journal event identity does not match persisted operation snapshot")
    if any(event.revision != snapshot.revision for event in snapshot.events):
        raise ValueError("journal event revision does not match persisted operation snapshot")


def _validate_event_sequences(snapshot: OperationPersistedSnapshot) -> None:
    """Ensure event sequence numbers are contiguous and cursor-aligned."""
    sequences = tuple(event.sequence for event in snapshot.events)
    if any(current != previous + 1 for previous, current in pairwise(sequences)):
        raise ValueError("journal event sequences must be contiguous")
    if sequences[-1] != snapshot.event_cursor:
        raise ValueError("persisted event cursor must equal the final journal event sequence")


def _validate_event_timeline(snapshot: OperationPersistedSnapshot) -> None:
    """Ensure event timestamps are monotonic and close the snapshot timeline."""
    timestamps = tuple(event.timestamp for event in snapshot.events)
    if any(current < previous for previous, current in pairwise(timestamps)):
        raise ValueError("journal event timestamps must be nondecreasing")
    if snapshot.updated_at != timestamps[-1]:
        raise ValueError("persisted updated time must equal the final journal event timestamp")


def _validate_phase_code(snapshot: OperationPersistedSnapshot) -> None:
    """Ensure the snapshot phase mirrors the latest phase event."""
    phase_events = tuple(event for event in snapshot.events if isinstance(event, OperationPhaseEvent))
    if phase_events and snapshot.phase_code != phase_events[-1].phase_code:
        raise ValueError("persisted phase code must equal the latest journal phase event")


def _validate_terminal_events(snapshot: OperationPersistedSnapshot) -> None:
    """Ensure terminal events agree with the snapshot lifecycle and receipt."""
    terminal_events = tuple(event for event in snapshot.events if isinstance(event, OperationTerminalEvent))
    if snapshot.lifecycle is not OperationLifecycle.TERMINAL:
        if terminal_events:
            raise ValueError("non-terminal persisted operation snapshot forbids terminal events")
        return
    last_event = snapshot.events[-1]
    if len(terminal_events) != 1 or not isinstance(last_event, OperationTerminalEvent):
        raise ValueError("terminal persisted operation snapshot requires exactly one final terminal event")
    if last_event.receipt != snapshot.terminal_receipt:
        raise ValueError("terminal journal event receipt does not match persisted operation snapshot")


@runtime_checkable
class OperationJournal(Protocol):
    """Atomic snapshot-plus-event persistence with optimistic revision checks."""

    async def load(self, operation_id: OperationId) -> OperationPersistedSnapshot: ...

    async def resolve_idempotency(self, claim: OperationIdempotencyClaim) -> OperationId | None:
        """Resolve a claim only when its matching operation journal exists."""
        ...

    async def create(self, snapshot: OperationPersistedSnapshot, *, lease: OperationOwnerLease) -> OperationId:
        """Atomically create one initial snapshot and its optional retry claim."""
        ...

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
class OperationObservationReader(Protocol):
    """Read one internally consistent operation observation from persistence.

    A missing operation raises :class:`OperationObservationUnknownOperationError`.
    A cursor beyond the read anchor raises :class:`OperationObservationCursorAheadError`.
    """

    async def read_observation(
        self,
        operation_id: OperationId,
        after_cursor: OperationEventCursor,
        *,
        limit: OperationReplayLimit,
    ) -> OperationObservationMaterialization: ...


@runtime_checkable
class OperationLeaseRepository(Protocol):
    """Observe and transition one durable owner lease against explicit evidence time."""

    async def inspect(
        self,
        scope_ref: OperationConflictScopeReference,
        operation_id: OperationId,
        *,
        observed_at: datetime,
    ) -> OperationLeaseObservation: ...

    async def acquire(self, candidate: OperationOwnerLease, *, observed_at: datetime) -> OperationLeaseResult: ...

    async def compare_and_swap(
        self,
        predecessor: OperationOwnerLease,
        successor: OperationOwnerLease,
        *,
        observed_at: datetime,
    ) -> OperationLeaseResult:
        del successor
        raise NotImplementedError

    async def release(self, predecessor: OperationOwnerLease, *, observed_at: datetime) -> OperationLeaseResult: ...


@runtime_checkable
class OperationSecureReferenceStore(Protocol):
    """Store and resolve confidential operands outside credential-free journals."""

    async def put(self, operand: BaseModel, *, written_at: datetime) -> ContentDigest: ...

    async def resolve[OperandT: BaseModel](
        self,
        reference: ContentDigest,
        operand_type: type[OperandT],
    ) -> OperandT:
        del operand_type
        raise NotImplementedError


__all__ = [
    "OperationEventStream",
    "OperationJournal",
    "OperationLeaseRepository",
    "OperationObservationCursorAheadError",
    "OperationObservationMaterialization",
    "OperationObservationReader",
    "OperationObservationUnknownOperationError",
    "OperationPersistedSnapshot",
    "OperationProgressFoldCheckpoint",
    "OperationProgressFoldInput",
    "OperationSecureReferenceStore",
]
