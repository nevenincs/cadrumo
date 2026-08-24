"""Lease and local-durability mechanics shared by the operation supervisor."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any

from ...core import Hex64Str
from ._journal import OperationJournal, OperationLeaseRepository, OperationPersistedSnapshot
from ._leases import (
    OperationLeaseDisposition,
    OperationLeaseObservationDisposition,
    OperationLeaseToken,
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from ._models import OperationId, OperationIdempotencyClaim, OperationIdentity


class OperationSupervisorLeaseMixin:
    """Own local guards and exact durable-lease transitions for a supervisor."""

    _journal: OperationJournal
    _leases: OperationLeaseRepository
    _owner_id: Hex64Str
    _lease_token: OperationLeaseToken
    _clock: Callable[[], datetime]
    _lease_duration: timedelta
    _leases_by_operation: dict[OperationId, OperationOwnerLease]
    _lease_locks: dict[OperationId, asyncio.Lock]
    _durable_change_events: dict[OperationId, asyncio.Event]
    _durable_revisions: dict[OperationId, int]

    def _candidate(self, identity: OperationIdentity, now: datetime) -> OperationOwnerLease:
        return OperationOwnerLease(
            operation_id=identity.operation_id,
            scope_ref=operation_conflict_scope_reference(
                definition_id=identity.definition_id,
                subject_ref=identity.subject_ref,
            ),
            owner_id=self._owner_id,
            token=self._lease_token,
            acquired_at=now,
            expires_at=now + self._lease_duration,
        )

    def _lease_lock(self, operation_id: OperationId) -> asyncio.Lock:
        """Return the supervisor-local guard for one durable owner lease."""
        return self._lease_locks.setdefault(operation_id, asyncio.Lock())

    def _renewal_interval_seconds(self) -> float:
        """Bound scheduler wakeups without making scheduler time lease authority."""
        return min(max(self._lease_duration.total_seconds() / 3, 0.001), 30.0)

    async def _require_owned_lease(self, identity: OperationIdentity, now: datetime) -> OperationOwnerLease:
        """Return this supervisor's exact live lease under its local CAS guard."""
        async with self._lease_lock(identity.operation_id):
            return await self._require_owned_lease_unlocked(identity, now)

    async def _require_owned_lease_unlocked(
        self,
        identity: OperationIdentity,
        now: datetime,
    ) -> OperationOwnerLease:
        """Return this supervisor's exact live lease, renewing it only by CAS."""
        scope_ref = operation_conflict_scope_reference(
            definition_id=identity.definition_id,
            subject_ref=identity.subject_ref,
        )
        held = await self._load_owned_lease(identity, scope_ref=scope_ref, now=now)
        if now >= held.expires_at:
            raise ValueError("operation exact lease expired before renewal")
        successor = OperationOwnerLease(
            operation_id=held.operation_id,
            scope_ref=held.scope_ref,
            owner_id=held.owner_id,
            token=held.token,
            acquired_at=held.acquired_at,
            expires_at=now + self._lease_duration,
        )
        if successor.expires_at <= held.expires_at:
            return await self._retain_owned_lease(identity, scope_ref=scope_ref, held=held, now=now)
        renewed = await self._leases.compare_and_swap(held, successor, observed_at=now)
        if renewed.disposition is not OperationLeaseDisposition.RENEWED or renewed.current != successor:
            raise ValueError("operation exact lease renewal was refused")
        self._leases_by_operation[identity.operation_id] = successor
        return successor

    async def _load_owned_lease(
        self,
        identity: OperationIdentity,
        *,
        scope_ref: str,
        now: datetime,
    ) -> OperationOwnerLease:
        held = self._leases_by_operation.get(identity.operation_id)
        if held is not None:
            if held.scope_ref != scope_ref:
                raise ValueError("operation lease no longer matches this supervisor's conflict scope")
            return held
        observed = await self._leases.inspect(scope_ref, identity.operation_id, observed_at=now)
        current = observed.current
        if (
            observed.disposition is not OperationLeaseObservationDisposition.ACTIVE
            or current is None
            or current.owner_id != self._owner_id
            or current.token != self._lease_token
        ):
            raise ValueError("operation is not owned by this supervisor")
        self._leases_by_operation[identity.operation_id] = current
        return current

    async def _retain_owned_lease(
        self,
        identity: OperationIdentity,
        *,
        scope_ref: str,
        held: OperationOwnerLease,
        now: datetime,
    ) -> OperationOwnerLease:
        observed = await self._leases.inspect(scope_ref, identity.operation_id, observed_at=now)
        if observed.disposition is not OperationLeaseObservationDisposition.ACTIVE or observed.current != held:
            raise ValueError("operation lease no longer matches this supervisor's exact held lease")
        return held

    async def _renew_while_executing(
        self,
        *,
        identity: OperationIdentity,
        executor: Coroutine[Any, Any, object],
    ) -> object:
        """Join one executor while renewing its exact durable lease on schedule."""
        executor_task = asyncio.create_task(executor, name=f"operation-executor-{identity.operation_id}")
        try:
            while not executor_task.done():
                done, pending = await asyncio.wait(
                    (executor_task,),
                    timeout=self._renewal_interval_seconds(),
                )
                if executor_task in done or not pending:
                    break
                await self._require_owned_lease(identity, self._clock())
            return await executor_task
        finally:
            if not executor_task.done():
                executor_task.cancel()
            with suppress(asyncio.CancelledError):
                await executor_task

    async def _release_exact_lease(self, lease: OperationOwnerLease, *, observed_at: datetime) -> None:
        """Release one exact current lease and refuse any ownership loss."""
        released = await self._leases.release(lease, observed_at=observed_at)
        if released.disposition is not OperationLeaseDisposition.RELEASED:
            raise ValueError("operation exact lease release was refused")
        self._leases_by_operation.pop(lease.operation_id, None)

    async def _resolve_idempotency(self, claim: OperationIdempotencyClaim | None) -> OperationId | None:
        if claim is None:
            return None
        return await self._journal.resolve_idempotency(claim)

    async def _resolve_conflict_submission(self, claim: OperationIdempotencyClaim | None) -> OperationId:
        existing_operation_id = await self._resolve_idempotency(claim)
        if existing_operation_id is not None:
            return existing_operation_id
        raise ValueError("operation conflict lease was not acquired")

    def _notify_durable_change(self, snapshot: OperationPersistedSnapshot) -> None:
        """Signal one local durable commit while leaving journal bytes authoritative."""
        operation_id = snapshot.identity.operation_id
        self._durable_revisions[operation_id] = snapshot.revision
        self._durable_change_events.setdefault(operation_id, asyncio.Event()).set()


__all__ = ["OperationSupervisorLeaseMixin"]
