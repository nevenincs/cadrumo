"""Application-owned baseline operation supervision."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta

from pydantic import BaseModel

from ...core import Hex64Str, OperationCancellation, OperationEffect, OperationLifecycle, OperationTerminalCondition
from ...core.async_cleanup import AsyncCloseable, close_async_resources
from ._events import (
    OperationEvent,
    OperationInteractionEvent,
    OperationNoticeEvent,
    OperationPhaseEvent,
    OperationTerminalEvent,
)
from ._execution_context import DefinitionBoundContext
from ._interactions import (
    OperationApplyResponse,
    OperationConsumedInteraction,
    OperationPendingInteraction,
    OperationRejectResponse,
)
from ._journal import (
    OperationEventStream,
    OperationJournal,
    OperationLeaseRepository,
    OperationPersistedSnapshot,
    OperationSecureReferenceStore,
)
from ._leases import (
    OperationLeaseDisposition,
    OperationLeaseObservationDisposition,
    OperationLeaseToken,
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from ._models import (
    OperationId,
    OperationIdempotencyClaim,
    OperationIdentity,
    OperationRequest,
    OperationTerminalReceipt,
    new_operation_id,
)
from ._registry import OperationReconciliationPolicy, OperationRegistry
from ._replay import OperationEventCursor, OperationReplayLimit, OperationReplayPage
from ._supervisor_lease import OperationSupervisorLeaseMixin

_AWAIT_TERMINAL_INITIAL_BACKOFF_SECONDS = 0.025
_AWAIT_TERMINAL_MAX_BACKOFF_SECONDS = 0.25


class OperationSupervisor(OperationSupervisorLeaseMixin):
    def __init__(
        self,
        *,
        registry: OperationRegistry,
        journal: OperationJournal,
        event_stream: OperationEventStream,
        leases: OperationLeaseRepository,
        operands: OperationSecureReferenceStore,
        owner_id: Hex64Str,
        lease_token_factory: Callable[[], OperationLeaseToken],
        clock: Callable[[], datetime],
        lease_duration: timedelta,
    ) -> None:
        self._registry = registry
        self._journal = journal
        self._event_stream = event_stream
        self._leases = leases
        self._operands = operands
        self._owner_id = owner_id
        self._lease_token = lease_token_factory()
        self._clock = clock
        self._lease_duration = lease_duration
        self._leases_by_operation: dict[OperationId, OperationOwnerLease] = {}
        self._lease_locks: dict[OperationId, asyncio.Lock] = {}
        self._resources: dict[OperationId, list[AsyncCloseable]] = {}
        self._durable_change_events: dict[OperationId, asyncio.Event] = {}
        self._durable_revisions: dict[OperationId, int] = {}

        if lease_duration <= timedelta():
            raise ValueError("operation lease duration must be positive")

    async def submit(
        self, request: OperationRequest[BaseModel], *, operation_id: OperationId | None = None
    ) -> OperationId:
        definition = self._registry.lookup(request.definition_id)
        self._validate_request_payload(request, definition.request_type)
        now = self._clock()
        ref = await self._operands.put(request.payload, written_at=now)
        identity = OperationIdentity(
            operation_id=operation_id or new_operation_id(),
            definition_id=request.definition_id,
            subject_ref=request.subject_ref,
        )
        claim = (
            OperationIdempotencyClaim.bind(
                identity=identity, idempotency_key=request.idempotency_key, request_reference=ref
            )
            if request.idempotency_key
            else None
        )
        existing_operation_id = await self._resolve_idempotency(claim)
        if existing_operation_id is not None:
            return existing_operation_id
        lease = self._candidate(identity, now)
        result = await self._leases.acquire(lease, observed_at=now)
        if result.disposition is not OperationLeaseDisposition.ACQUIRED:
            return await self._resolve_conflict_submission(claim)
        self._leases_by_operation[identity.operation_id] = lease
        snapshot = OperationPersistedSnapshot(
            identity=identity,
            request_reference=ref,
            revision=0,
            lifecycle=OperationLifecycle.CREATED,
            started_at=now,
            updated_at=now,
            idempotency_claim=claim,
        )
        try:
            created_operation_id = await self._journal.create(snapshot, lease=lease)
        except BaseException:
            await self._release_exact_lease(lease, observed_at=self._clock())
            raise
        if created_operation_id != identity.operation_id:
            await self._release_exact_lease(lease, observed_at=self._clock())
        return created_operation_id

    @staticmethod
    def _validate_request_payload(request: OperationRequest[BaseModel], request_type: type[BaseModel]) -> None:
        if not isinstance(request.payload, request_type):
            raise ValueError("request payload does not match definition")

    async def start(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Start one owned registered executor from its durable secure operand."""
        snapshot = await self.inspect(operation_id)
        if snapshot.lifecycle is not OperationLifecycle.CREATED:
            raise ValueError("only a created operation may be started")
        definition = self._registry.lookup(snapshot.identity.definition_id)
        payload = await self._operands.resolve(snapshot.request_reference, definition.request_type)
        request = OperationRequest(
            definition_id=snapshot.identity.definition_id,
            subject_ref=snapshot.identity.subject_ref,
            payload=payload,
            idempotency_key=None,
        )
        started = OperationNoticeEvent(
            identity=snapshot.identity,
            revision=0,
            sequence=1,
            timestamp=self._clock(),
            code="operation.started",
            notice_code="operation.started",
        )
        running = await self._advance(snapshot, lifecycle=OperationLifecycle.RUNNING, events=(started,))
        context = DefinitionBoundContext(
            snapshot=running,
            registry=self._registry,
            operands=self._operands,
            clock=self._clock,
            resources=self._resources,
            advance=self._advance,
        )
        executor = definition.executor_factory.create()
        await self._renew_while_executing(
            identity=running.identity,
            executor=executor.execute(request, context),
        )
        return context.snapshot

    async def inspect(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        return await self._journal.load(operation_id)

    async def observe(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Return the latest durable operation observation."""
        return await self.inspect(operation_id)

    async def replay(
        self,
        operation_id: OperationId,
        cursor: OperationEventCursor,
        *,
        limit: OperationReplayLimit,
    ) -> OperationReplayPage:
        """Read one bounded authoritative event page after an exclusive cursor."""
        return await self._event_stream.read_after(operation_id, cursor, limit=limit)

    async def detach(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        return await self.inspect(operation_id)

    async def await_terminal(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Await local commits promptly and bounded durable rechecks after detachment."""
        backoff_seconds = _AWAIT_TERMINAL_INITIAL_BACKOFF_SECONDS
        while True:
            snapshot = await self.inspect(operation_id)
            if snapshot.lifecycle is OperationLifecycle.TERMINAL:
                return snapshot
            event = self._durable_change_events.setdefault(operation_id, asyncio.Event())
            observed_revision = snapshot.revision
            if self._durable_revisions.get(operation_id, observed_revision) > observed_revision:
                backoff_seconds = _AWAIT_TERMINAL_INITIAL_BACKOFF_SECONDS
                continue
            event.clear()
            if self._durable_revisions.get(operation_id, observed_revision) > observed_revision:
                backoff_seconds = _AWAIT_TERMINAL_INITIAL_BACKOFF_SECONDS
                continue
            try:
                async with asyncio.timeout(backoff_seconds):
                    await event.wait()
            except TimeoutError:
                backoff_seconds = min(backoff_seconds * 2, _AWAIT_TERMINAL_MAX_BACKOFF_SECONDS)
            else:
                backoff_seconds = _AWAIT_TERMINAL_INITIAL_BACKOFF_SECONDS

    async def _advance(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        lifecycle: OperationLifecycle,
        events: tuple[OperationEvent, ...] = (),
        pending: OperationPendingInteraction | None = None,
        consumed: tuple[OperationConsumedInteraction, ...] | None = None,
        effect: OperationEffect | None = None,
    ) -> OperationPersistedSnapshot:
        now = self._clock()
        async with self._lease_lock(snapshot.identity.operation_id):
            lease = await self._require_owned_lease_unlocked(snapshot.identity, now)
            revision = snapshot.revision + 1
            emitted = tuple(
                event.model_copy(
                    update={"revision": revision, "sequence": snapshot.event_cursor + index + 1, "timestamp": now}
                )
                for index, event in enumerate(events)
            )
            phase_events = tuple(event for event in emitted if isinstance(event, OperationPhaseEvent))
            successor = snapshot.model_copy(
                update={
                    "revision": revision,
                    "lifecycle": lifecycle,
                    "updated_at": now,
                    "event_cursor": snapshot.event_cursor + len(emitted),
                    "events": emitted,
                    "phase_code": snapshot.phase_code if not phase_events else phase_events[-1].phase_code,
                    "pending_interaction": pending,
                    "consumed_interactions": snapshot.consumed_interactions if consumed is None else consumed,
                    "effect": snapshot.effect if effect is None else effect,
                }
            )
            await self._journal.commit(successor, expected_revision=snapshot.revision, lease=lease)
        self._notify_durable_change(successor)
        return successor

    async def respond(self, response: OperationApplyResponse | OperationRejectResponse) -> OperationConsumedInteraction:
        snapshot = await self.inspect(response.operation_id)
        pending = snapshot.pending_interaction
        if pending is None or any(
            item.interaction_id == response.interaction_id for item in snapshot.consumed_interactions
        ):
            raise ValueError("interaction is not pending")
        consumed = pending.consume(response)
        event = OperationInteractionEvent(
            identity=snapshot.identity,
            revision=0,
            sequence=1,
            timestamp=self._clock(),
            code="operation.interaction.consumed",
            interaction_id=consumed.interaction_id,
        )
        await self._advance(
            snapshot,
            lifecycle=OperationLifecycle.RUNNING,
            events=(event,),
            consumed=(*snapshot.consumed_interactions, consumed),
        )
        return consumed

    async def reject(self, response: OperationRejectResponse) -> OperationConsumedInteraction:
        return await self.respond(response)

    async def request_cancel(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        snapshot = await self.inspect(operation_id)
        if (
            self._registry.lookup(snapshot.identity.definition_id).capabilities.cancellation
            is OperationCancellation.UNSUPPORTED
        ):
            raise ValueError("operation does not support cancellation")
        return await self._advance(snapshot, lifecycle=OperationLifecycle.CANCELLATION_REQUESTED)

    async def settle(self, operation_id: OperationId, receipt: OperationTerminalReceipt) -> OperationPersistedSnapshot:
        snapshot = await self.inspect(operation_id)
        if receipt.identity != snapshot.identity or receipt.revision != snapshot.revision + 1:
            raise ValueError("terminal receipt does not match successor revision")
        definition = self._registry.lookup(snapshot.identity.definition_id)
        if receipt.effect not in definition.capabilities.permitted_effects:
            raise ValueError("terminal receipt effect is not declared by its definition")
        now = receipt.settled_at
        async with self._lease_lock(snapshot.identity.operation_id):
            lease = await self._require_owned_lease_unlocked(snapshot.identity, now)
            resources = self._resources.get(operation_id, ())
            await close_async_resources(*resources, task_name="operation-settlement")
            self._resources.pop(operation_id, None)
            event = OperationTerminalEvent(
                identity=snapshot.identity,
                revision=receipt.revision,
                sequence=snapshot.event_cursor + 1,
                timestamp=now,
                code="operation.terminal",
                receipt=receipt,
            )
            successor = snapshot.model_copy(
                update={
                    "revision": receipt.revision,
                    "lifecycle": OperationLifecycle.TERMINAL,
                    "terminal_condition": receipt.condition,
                    "effect": receipt.effect,
                    "updated_at": now,
                    "event_cursor": event.sequence,
                    "events": (event,),
                    "terminal_receipt": receipt,
                    "pending_interaction": None,
                }
            )
            await self._journal.commit(successor, expected_revision=snapshot.revision, lease=lease)
            await self._release_exact_lease(lease, observed_at=now)
        self._notify_durable_change(successor)
        return successor

    async def reconcile(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        snapshot = await self.inspect(operation_id)
        if snapshot.lifecycle is OperationLifecycle.TERMINAL:
            return snapshot
        scope_ref = operation_conflict_scope_reference(
            definition_id=snapshot.identity.definition_id,
            subject_ref=snapshot.identity.subject_ref,
        )
        now = self._clock()
        observed = await self._leases.inspect(scope_ref, operation_id, observed_at=now)
        if observed.disposition is OperationLeaseObservationDisposition.ACTIVE:
            raise ValueError("operation has active owner")
        if observed.disposition is not OperationLeaseObservationDisposition.EXPIRED or observed.current is None:
            raise ValueError("operation has no expired owner lease to take over")
        takeover = self._candidate(snapshot.identity, now)
        taken_over = await self._leases.compare_and_swap(observed.current, takeover, observed_at=now)
        if taken_over.disposition is not OperationLeaseDisposition.TAKEN_OVER or taken_over.current != takeover:
            raise ValueError("operation expired owner lease takeover was refused")
        self._leases_by_operation[operation_id] = takeover
        if (
            self._registry.lookup(snapshot.identity.definition_id).reconciliation_policy
            is OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT
        ):
            return snapshot
        receipt = OperationTerminalReceipt(
            identity=snapshot.identity,
            revision=snapshot.revision + 1,
            condition=OperationTerminalCondition.INTERRUPTED,
            effect=OperationEffect.UNKNOWN,
            settled_at=now,
        )
        return await self.settle(operation_id, receipt)
