"""Send each operation's journal, lease and observation calls to the store its durability names.

The supervisor registers an ``EPHEMERAL`` operation before it takes the
operation's lease; from then on every call for that operation reaches the
in-memory store. Every other operation, recovery inventory and idempotency
resolution stay on the durable journal, so a durable operation is journaled
exactly as before.
"""

from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import override

from pydantic import BaseModel

from ....application.operations.event_replay import OperationEventCursor
from ....application.operations.models import OperationId, OperationRevision
from ....application.operations.persistence.idempotency import OperationIdempotencyClaim
from ....application.operations.persistence.journal import (
    OperationEphemeralRouting,
    OperationEventStream,
    OperationInventoryLimit,
    OperationJournal,
    OperationLeaseRepository,
    OperationObservationMaterialization,
    OperationObservationReader,
    OperationPersistedSnapshot,
    OperationRecoveryInventoryPage,
    OperationSecureReferenceStore,
)
from ....application.operations.persistence.leases import (
    OperationConflictScopeReference,
    OperationLeaseObservation,
    OperationLeaseResult,
    OperationOwnerLease,
)
from ....application.operations.persistence.replay import OperationReplayLimit, OperationReplayPage
from ....core.identity.digest import ContentDigest
from .ephemeral_store import EphemeralOperationStore


class DurabilityRoutedOperationPersistence(
    OperationJournal,
    OperationEventStream,
    OperationObservationReader,
    OperationLeaseRepository,
    OperationSecureReferenceStore,
    OperationEphemeralRouting,
):
    """One set of operation ports that keeps ephemeral operations in process memory."""

    def __init__(
        self,
        *,
        journal: OperationJournal,
        event_stream: OperationEventStream,
        reader: OperationObservationReader,
        leases: OperationLeaseRepository,
        operands: OperationSecureReferenceStore,
        ephemeral: EphemeralOperationStore | None = None,
    ) -> None:
        """Wrap the durable ports; ephemeral operations go to ``ephemeral`` or a fresh store."""
        self._journal = journal
        self._event_stream = event_stream
        self._reader = reader
        self._leases = leases
        self._operands = operands
        self._ephemeral = EphemeralOperationStore() if ephemeral is None else ephemeral
        self._lock = Lock()
        self._registered: set[OperationId] = set()

    # Routing -------------------------------------------------------------

    @override
    def register_ephemeral(self, operation_id: OperationId) -> None:
        with self._lock:
            self._registered.add(operation_id)

    @override
    def routes_ephemeral(self, operation_id: OperationId) -> bool:
        with self._lock:
            registered = operation_id in self._registered
        return registered or self._ephemeral.holds(operation_id)

    @override
    def operands_for(self, operation_id: OperationId) -> OperationSecureReferenceStore:
        return self._ephemeral.operands_for(operation_id)

    # Journal -------------------------------------------------------------

    @override
    async def load(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        if self.routes_ephemeral(operation_id):
            return await self._ephemeral.load(operation_id)
        return await self._journal.load(operation_id)

    @override
    async def inventory_page(
        self, *, after: OperationId | None, limit: OperationInventoryLimit
    ) -> OperationRecoveryInventoryPage:
        return await self._journal.inventory_page(after=after, limit=limit)

    @override
    async def resolve_idempotency(self, claim: OperationIdempotencyClaim) -> OperationId | None:
        return await self._journal.resolve_idempotency(claim)

    @override
    async def create(self, snapshot: OperationPersistedSnapshot, *, lease: OperationOwnerLease) -> OperationId:
        if self.routes_ephemeral(snapshot.operation_id):
            return await self._ephemeral.create(snapshot, lease=lease)
        return await self._journal.create(snapshot, lease=lease)

    @override
    async def commit(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        expected_revision: OperationRevision,
        lease: OperationOwnerLease,
    ) -> None:
        if self.routes_ephemeral(snapshot.operation_id):
            await self._ephemeral.commit(snapshot, expected_revision=expected_revision, lease=lease)
        else:
            await self._journal.commit(snapshot, expected_revision=expected_revision, lease=lease)

    @override
    async def commit_settlement(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        expected_revision: OperationRevision,
        lease: OperationOwnerLease,
    ) -> None:
        if self.routes_ephemeral(snapshot.operation_id):
            await self._ephemeral.commit_settlement(snapshot, expected_revision=expected_revision, lease=lease)
            with self._lock:
                self._registered.discard(snapshot.operation_id)
        else:
            await self._journal.commit_settlement(snapshot, expected_revision=expected_revision, lease=lease)

    @override
    async def read_after(
        self,
        operation_id: OperationId,
        cursor: OperationEventCursor,
        *,
        limit: OperationReplayLimit,
    ) -> OperationReplayPage:
        if self.routes_ephemeral(operation_id):
            return await self._ephemeral.read_after(operation_id, cursor, limit=limit)
        return await self._event_stream.read_after(operation_id, cursor, limit=limit)

    @override
    async def read_observation(
        self,
        operation_id: OperationId,
        after_cursor: OperationEventCursor,
        *,
        limit: OperationReplayLimit,
    ) -> OperationObservationMaterialization:
        if self.routes_ephemeral(operation_id):
            return await self._ephemeral.read_observation(operation_id, after_cursor, limit=limit)
        return await self._reader.read_observation(operation_id, after_cursor, limit=limit)

    # Leases --------------------------------------------------------------

    @override
    async def inspect(
        self,
        scope_ref: OperationConflictScopeReference,
        operation_id: OperationId,
        *,
        observed_at: datetime,
    ) -> OperationLeaseObservation:
        if self.routes_ephemeral(operation_id):
            return await self._ephemeral.inspect(scope_ref, operation_id, observed_at=observed_at)
        return await self._leases.inspect(scope_ref, operation_id, observed_at=observed_at)

    @override
    async def acquire(self, candidate: OperationOwnerLease, *, observed_at: datetime) -> OperationLeaseResult:
        if self.routes_ephemeral(candidate.operation_id):
            return await self._ephemeral.acquire(candidate, observed_at=observed_at)
        return await self._leases.acquire(candidate, observed_at=observed_at)

    @override
    async def compare_and_swap(
        self,
        predecessor: OperationOwnerLease,
        successor: OperationOwnerLease,
        *,
        observed_at: datetime,
    ) -> OperationLeaseResult:
        if self.routes_ephemeral(predecessor.operation_id):
            return await self._ephemeral.compare_and_swap(predecessor, successor, observed_at=observed_at)
        return await self._leases.compare_and_swap(predecessor, successor, observed_at=observed_at)

    @override
    async def release(self, predecessor: OperationOwnerLease, *, observed_at: datetime) -> OperationLeaseResult:
        if self.routes_ephemeral(predecessor.operation_id):
            result = await self._ephemeral.release(predecessor, observed_at=observed_at)
            with self._lock:
                self._registered.discard(predecessor.operation_id)
            return result
        return await self._leases.release(predecessor, observed_at=observed_at)

    # Operands ------------------------------------------------------------

    @override
    async def put(self, operand: BaseModel, *, written_at: datetime) -> ContentDigest:
        return await self._operands.put(operand, written_at=written_at)

    @override
    async def resolve[OperandT: BaseModel](
        self,
        reference: ContentDigest,
        operand_type: type[OperandT],
    ) -> OperandT:
        if self._ephemeral.holds_operand(reference):
            return await self._ephemeral.resolve(reference, operand_type)
        return await self._operands.resolve(reference, operand_type)


__all__ = ["DurabilityRoutedOperationPersistence"]
