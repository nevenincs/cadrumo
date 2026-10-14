"""In-memory operation journal, leases and operands for ephemeral operations.

An operation declared ``EPHEMERAL`` has no effect that lost observation could
conceal, so its lifecycle lives only as long as the process that runs it. This
store keeps that lifecycle under the same ports and transition rules as the
durable journal, without a lock file, a journal file or an encrypted operand
row. Each operation's lease is its own: two ephemeral operations of one
definition and subject never contend. A record lost with its process, or
evicted once enough later operations have settled, reads as an unknown
operation.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from threading import Lock
from typing import override

from pydantic import BaseModel, ValidationError

from ....application.operations.event_replay import OperationEventCursor
from ....application.operations.models import OperationId, OperationRevision
from ....application.operations.persistence.idempotency import OperationIdempotencyClaim
from ....application.operations.persistence.journal import (
    OperationEventStream,
    OperationInventoryLimit,
    OperationJournal,
    OperationLeaseRepository,
    OperationObservationMaterialization,
    OperationObservationReader,
    OperationObservationUnknownOperationError,
    OperationPersistedSnapshot,
    OperationRecoveryInventoryPage,
    OperationSecureReferenceStore,
    serialize_operation_operand,
)
from ....application.operations.persistence.leases import (
    OperationConflictScopeReference,
    OperationLeaseDisposition,
    OperationLeaseObservation,
    OperationLeaseObservationDisposition,
    OperationLeaseResult,
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from ....application.operations.persistence.replay import (
    OperationReplayLimit,
    OperationReplayPage,
    OperationReplayStatus,
)
from ....core.hashing import sha256_hex
from ....core.identity.digest import ContentDigest
from ....core.operations import OperationLifecycle
from ....core.time.utc import validate_utc_aware
from ..storage.errors import RepositoryError
from ._journal_validation import OperationJournalRecord, validate_advance
from .journal import OperationReplayRequest, observation_materialization_from_record, replay_page_from_record

EPHEMERAL_SETTLED_RETENTION = 256
"""How many settled ephemeral operations stay readable before the oldest is forgotten."""


class EphemeralOperationStore(
    OperationJournal,
    OperationEventStream,
    OperationObservationReader,
    OperationLeaseRepository,
    OperationSecureReferenceStore,
):
    """Process-lifetime journal, lease and operand ports for ephemeral operations."""

    def __init__(self, *, settled_retention: int = EPHEMERAL_SETTLED_RETENTION) -> None:
        """Start empty; nothing here outlives the process."""
        if settled_retention < 1:
            raise ValueError("ephemeral settled retention must be positive")
        self._settled_retention = settled_retention
        self._lock = Lock()
        self._records: dict[OperationId, OperationJournalRecord] = {}
        self._settled: OrderedDict[OperationId, None] = OrderedDict()
        self._leases: dict[OperationId, OperationOwnerLease] = {}
        self._operands: dict[ContentDigest, bytes] = {}
        self._operand_owners: dict[OperationId, set[ContentDigest]] = {}

    def holds(self, operation_id: OperationId) -> bool:
        """Whether this store holds the operation's record or its lease."""
        with self._lock:
            return operation_id in self._records or operation_id in self._leases

    # Journal -------------------------------------------------------------

    @override
    async def load(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        with self._lock:
            return self._record(operation_id).snapshot

    @override
    async def inventory_page(
        self, *, after: OperationId | None, limit: OperationInventoryLimit
    ) -> OperationRecoveryInventoryPage:
        # An ephemeral operation is never recovered: it ends with its process.
        del limit
        return OperationRecoveryInventoryPage(entries=(), next_cursor=after, has_more=False)

    @override
    async def resolve_idempotency(self, claim: OperationIdempotencyClaim) -> OperationId | None:
        # Ephemeral operations promise no replay, so no claim resolves here.
        del claim
        return None

    @override
    async def create(self, snapshot: OperationPersistedSnapshot, *, lease: OperationOwnerLease) -> OperationId:
        _require_lease_matches(snapshot, lease)
        with self._lock:
            self._require_live_exact(lease, observed_at=snapshot.updated_at)
            if snapshot.operation_id in self._records:
                raise RepositoryError("initial operation journal create already exists")
            if snapshot.revision != 0:
                raise RepositoryError("initial operation journal create requires snapshot revision zero")
            if not snapshot.events and snapshot.event_cursor != 0:
                raise RepositoryError("initial operation journal create requires empty history cursor zero")
            if snapshot.events and snapshot.events[0].sequence != 1:
                raise RepositoryError("initial operation journal create event history must begin at sequence one")
            self._records[snapshot.operation_id] = _record(snapshot, snapshot.events)
        return snapshot.operation_id

    @override
    async def commit(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        expected_revision: OperationRevision,
        lease: OperationOwnerLease,
    ) -> None:
        if snapshot.lifecycle is OperationLifecycle.TERMINAL:
            raise RepositoryError("a terminal operation snapshot is committed only with its lease release")
        _require_lease_matches(snapshot, lease)
        with self._lock:
            self._advance(snapshot, expected_revision=expected_revision, lease=lease)

    @override
    async def commit_settlement(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        expected_revision: OperationRevision,
        lease: OperationOwnerLease,
    ) -> None:
        if snapshot.lifecycle is not OperationLifecycle.TERMINAL:
            raise RepositoryError("operation settlement commit requires a terminal snapshot")
        _require_lease_matches(snapshot, lease)
        with self._lock:
            self._advance(snapshot, expected_revision=expected_revision, lease=lease)
            del self._leases[snapshot.operation_id]
            self._settled[snapshot.operation_id] = None
            while len(self._settled) > self._settled_retention:
                forgotten, _ = self._settled.popitem(last=False)
                self._records.pop(forgotten, None)
                self._forget_operands(forgotten)

    def forget_unadmitted(self, operation_id: OperationId) -> None:
        """Drop the lease and operands of an operation whose record was never created."""
        with self._lock:
            if operation_id in self._records:
                return
            self._leases.pop(operation_id, None)
            self._forget_operands(operation_id)

    @override
    async def read_after(
        self,
        operation_id: OperationId,
        cursor: OperationEventCursor,
        *,
        limit: OperationReplayLimit,
    ) -> OperationReplayPage:
        request = OperationReplayRequest(cursor=cursor, limit=limit)
        with self._lock:
            record = self._records.get(operation_id)
        if record is None:
            return OperationReplayPage(
                status=OperationReplayStatus.UNKNOWN_OPERATION,
                requested_cursor=request.cursor,
                events=(),
                next_cursor=request.cursor,
            )
        return replay_page_from_record(record, request)

    @override
    async def read_observation(
        self,
        operation_id: OperationId,
        after_cursor: OperationEventCursor,
        *,
        limit: OperationReplayLimit,
    ) -> OperationObservationMaterialization:
        request = OperationReplayRequest(cursor=after_cursor, limit=limit)
        with self._lock:
            record = self._records.get(operation_id)
        if record is None:
            raise OperationObservationUnknownOperationError(operation_id)
        return observation_materialization_from_record(record, request)

    # Leases --------------------------------------------------------------

    @override
    async def inspect(
        self,
        scope_ref: OperationConflictScopeReference,
        operation_id: OperationId,
        *,
        observed_at: datetime,
    ) -> OperationLeaseObservation:
        validate_utc_aware(observed_at)
        with self._lock:
            current = self._leases.get(operation_id)
        if current is None or current.scope_ref != scope_ref:
            return OperationLeaseObservation(
                scope_ref=scope_ref,
                operation_id=operation_id,
                disposition=OperationLeaseObservationDisposition.ABSENT,
                observed_at=observed_at,
            )
        return OperationLeaseObservation(
            scope_ref=scope_ref,
            operation_id=operation_id,
            disposition=OperationLeaseObservationDisposition.ACTIVE
            if current.expires_at > observed_at
            else OperationLeaseObservationDisposition.EXPIRED,
            observed_at=observed_at,
            current=current,
        )

    @override
    async def acquire(self, candidate: OperationOwnerLease, *, observed_at: datetime) -> OperationLeaseResult:
        validate_utc_aware(observed_at)
        with self._lock:
            current = self._leases.get(candidate.operation_id)
            if current is None:
                self._leases[candidate.operation_id] = candidate
                return OperationLeaseResult(
                    scope_ref=candidate.scope_ref,
                    operation_id=candidate.operation_id,
                    disposition=OperationLeaseDisposition.ACQUIRED,
                    observed_at=observed_at,
                    current=candidate,
                )
        if current.expires_at > observed_at:
            return OperationLeaseResult(
                scope_ref=candidate.scope_ref,
                operation_id=candidate.operation_id,
                disposition=OperationLeaseDisposition.CONFLICT,
                observed_at=observed_at,
                current=current,
            )
        return OperationLeaseResult(
            scope_ref=candidate.scope_ref,
            operation_id=candidate.operation_id,
            disposition=OperationLeaseDisposition.EXPIRED,
            observed_at=observed_at,
            predecessor=current,
        )

    @override
    async def compare_and_swap(
        self,
        predecessor: OperationOwnerLease,
        successor: OperationOwnerLease,
        *,
        observed_at: datetime,
    ) -> OperationLeaseResult:
        if predecessor.scope_ref != successor.scope_ref or predecessor.operation_id != successor.operation_id:
            raise ValueError("operation lease compare-and-swap cannot change conflict scope or operation")
        validate_utc_aware(observed_at)
        with self._lock:
            current = self._leases.get(predecessor.operation_id)
            if current is None or current != predecessor:
                return OperationLeaseResult(
                    scope_ref=predecessor.scope_ref,
                    operation_id=predecessor.operation_id,
                    disposition=OperationLeaseDisposition.OWNER_LOST,
                    observed_at=observed_at,
                    predecessor=predecessor,
                    current=current,
                )
            self._leases[predecessor.operation_id] = successor
        return OperationLeaseResult(
            scope_ref=predecessor.scope_ref,
            operation_id=successor.operation_id,
            disposition=OperationLeaseDisposition.RENEWED
            if current.expires_at > observed_at
            else OperationLeaseDisposition.TAKEN_OVER,
            observed_at=observed_at,
            predecessor=predecessor,
            current=successor,
        )

    @override
    async def release(self, predecessor: OperationOwnerLease, *, observed_at: datetime) -> OperationLeaseResult:
        validate_utc_aware(observed_at)
        with self._lock:
            current = self._leases.get(predecessor.operation_id)
            if current is None or current != predecessor:
                return OperationLeaseResult(
                    scope_ref=predecessor.scope_ref,
                    operation_id=predecessor.operation_id,
                    disposition=OperationLeaseDisposition.OWNER_LOST,
                    observed_at=observed_at,
                    predecessor=predecessor,
                    current=current,
                )
            del self._leases[predecessor.operation_id]
        return OperationLeaseResult(
            scope_ref=predecessor.scope_ref,
            operation_id=predecessor.operation_id,
            disposition=OperationLeaseDisposition.RELEASED,
            observed_at=observed_at,
            predecessor=predecessor,
        )

    # Operands ------------------------------------------------------------

    @override
    async def put(self, operand: BaseModel, *, written_at: datetime) -> ContentDigest:
        validate_utc_aware(written_at)
        payload = serialize_operation_operand(operand)
        reference = sha256_hex(payload)
        with self._lock:
            self._operands.setdefault(reference, payload)
        return reference

    def operands_for(self, operation_id: OperationId) -> OperationSecureReferenceStore:
        """The operand store one ephemeral operation writes through; its operands go with its record."""
        return _OperationOperands(self, operation_id)

    def put_for(self, operation_id: OperationId, operand: BaseModel, *, written_at: datetime) -> ContentDigest:
        """Keep an operand of one ephemeral operation, forgotten with that operation's record."""
        validate_utc_aware(written_at)
        payload = serialize_operation_operand(operand)
        reference = sha256_hex(payload)
        with self._lock:
            self._operands.setdefault(reference, payload)
            self._operand_owners.setdefault(operation_id, set()).add(reference)
        return reference

    def holds_operand(self, reference: ContentDigest) -> bool:
        """Whether this store holds the operand at ``reference``."""
        with self._lock:
            return reference in self._operands

    @override
    async def resolve[OperandT: BaseModel](
        self,
        reference: ContentDigest,
        operand_type: type[OperandT],
    ) -> OperandT:
        with self._lock:
            payload = self._operands.get(reference)
        if payload is None:
            raise RepositoryError("operation secure reference is absent")
        if sha256_hex(payload) != reference:
            raise RepositoryError("operation secure reference payload does not match its digest")
        try:
            return operand_type.model_validate_json(payload, strict=True)
        except ValidationError as exc:
            raise RepositoryError("operation secure reference payload does not match requested operand type") from exc

    # Internals -----------------------------------------------------------

    def _forget_operands(self, operation_id: OperationId) -> None:
        for reference in self._operand_owners.pop(operation_id, set()):
            self._operands.pop(reference, None)

    def _record(self, operation_id: OperationId) -> OperationJournalRecord:
        record = self._records.get(operation_id)
        if record is None:
            raise RepositoryError("operation journal record is absent")
        return record

    def _require_live_exact(self, lease: OperationOwnerLease, *, observed_at: datetime) -> None:
        validate_utc_aware(observed_at)
        current = self._leases.get(lease.operation_id)
        if current is None:
            raise RepositoryError("operation journal commit requires a current operation lease")
        if current != lease:
            raise RepositoryError("operation journal commit lease is not the exact current operation lease")
        if current.acquired_at > observed_at:
            raise RepositoryError("operation journal commit lease is not yet active at the supplied evidence time")
        if current.expires_at <= observed_at:
            raise RepositoryError("operation journal commit lease is expired at the supplied evidence time")

    def _advance(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        expected_revision: OperationRevision,
        lease: OperationOwnerLease,
    ) -> None:
        self._require_live_exact(lease, observed_at=snapshot.updated_at)
        current = self._records.get(snapshot.operation_id)
        if current is None:
            raise RepositoryError("operation journal commit requires an existing snapshot created via create")
        validate_advance(current.snapshot, snapshot, expected_revision)
        self._records[snapshot.operation_id] = _record(snapshot, (*current.history, *snapshot.events))


class _OperationOperands(OperationSecureReferenceStore):
    """One ephemeral operation's view of the store's operands."""

    def __init__(self, store: EphemeralOperationStore, operation_id: OperationId) -> None:
        self._store = store
        self._operation_id = operation_id

    @override
    async def put(self, operand: BaseModel, *, written_at: datetime) -> ContentDigest:
        return self._store.put_for(self._operation_id, operand, written_at=written_at)

    @override
    async def resolve[OperandT: BaseModel](self, reference: ContentDigest, operand_type: type[OperandT]) -> OperandT:
        return await self._store.resolve(reference, operand_type)


def _record(snapshot: OperationPersistedSnapshot, history: tuple[object, ...]) -> OperationJournalRecord:
    try:
        return OperationJournalRecord.model_validate({"snapshot": snapshot, "history": history})
    except ValidationError as exc:
        raise RepositoryError("operation journal record is invalid") from exc


def _require_lease_matches(snapshot: OperationPersistedSnapshot, lease: OperationOwnerLease) -> None:
    if lease.operation_id != snapshot.operation_id:
        raise RepositoryError("operation lease does not match the persisted snapshot identity")
    expected_scope_ref = operation_conflict_scope_reference(
        definition_id=snapshot.identity.definition_id,
        subject_ref=snapshot.identity.subject_ref,
    )
    if lease.scope_ref != expected_scope_ref:
        raise RepositoryError("operation lease does not match the persisted snapshot conflict scope")


__all__ = ["EPHEMERAL_SETTLED_RETENTION", "EphemeralOperationStore"]
