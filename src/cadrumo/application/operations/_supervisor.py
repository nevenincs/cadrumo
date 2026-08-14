"""Application-owned baseline operation supervision."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from pydantic import BaseModel

from ...core import Hex64Str, OperationCancellation, OperationEffect, OperationLifecycle, OperationTerminalCondition
from ...core.async_cleanup import AsyncCloseable, close_async_resources
from ._capabilities import OperationOwnedResource
from ._events import (
    OperationDiagnosticEvent,
    OperationDiagnosticReference,
    OperationEffectEvent,
    OperationEvent,
    OperationEventCode,
    OperationInteractionEvent,
    OperationLogRecord,
    OperationLogSeverity,
    OperationNoticeEvent,
    OperationPhaseEvent,
    OperationProgressEvent,
    OperationTerminalEvent,
)
from ._interactions import (
    OperationApplyResponse,
    OperationConsumedInteraction,
    OperationPendingInteraction,
    OperationRejectResponse,
)
from ._journal import (
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


class _Cancellation:
    def __init__(self) -> None:
        self.cancellation_requested = False

    async def acknowledge_cancellation(self) -> None:
        self.cancellation_requested = True


class _Deadlines:
    execution_deadline: datetime | None = None
    cleanup_deadline: datetime | None = None


class _DefinitionBoundContext:
    """One executor view whose declarations are checked before state mutation."""

    def __init__(
        self,
        *,
        snapshot: OperationPersistedSnapshot,
        registry: OperationRegistry,
        operands: OperationSecureReferenceStore,
        clock: Callable[[], datetime],
        resources: dict[OperationId, list[AsyncCloseable]],
        advance: Callable[..., Awaitable[OperationPersistedSnapshot]],
    ) -> None:
        self.registry = registry
        self.clock = clock
        self.resources = resources
        self.advance_transition = advance
        self.snapshot = snapshot
        self.identity = snapshot.identity
        self.cancellation = _Cancellation()
        self.deadlines = _Deadlines()
        self.events = _DefinitionBoundEvents(self)
        self.operands = operands
        self.cleanup = _DefinitionBoundCleanup(self)
        self.interactions = _DefinitionBoundInteractions(self)

    async def advance(
        self,
        *,
        lifecycle: OperationLifecycle,
        events: tuple[OperationEvent, ...] = (),
        pending: OperationPendingInteraction | None = None,
        effect: OperationEffect | None = None,
    ) -> None:
        self.snapshot = await self.advance_transition(
            self.snapshot,
            lifecycle=lifecycle,
            events=events,
            pending=pending,
            effect=effect,
        )


class _DefinitionBoundEvents:
    def __init__(self, context: _DefinitionBoundContext) -> None:
        self._context = context

    async def phase(self, phase_code: OperationEventCode) -> None:
        definition = self._context.registry.lookup(self._context.identity.definition_id)
        if phase_code not in definition.phase_codes:
            raise ValueError("operation phase is not declared by its definition")
        event = OperationPhaseEvent(
            identity=self._context.identity,
            revision=0,
            sequence=1,
            timestamp=self._context.clock(),
            code=phase_code,
            phase_code=phase_code,
        )
        await self._context.advance(lifecycle=OperationLifecycle.RUNNING, events=(event,))

    async def progress(self, *, completed: int, total: int, unit_code: OperationEventCode | None = None) -> None:
        event = OperationProgressEvent(
            identity=self._context.identity,
            revision=0,
            sequence=1,
            timestamp=self._context.clock(),
            code="operation.progress",
            completed=completed,
            total=total,
            unit_code=unit_code,
        )
        await self._context.advance(lifecycle=OperationLifecycle.RUNNING, events=(event,))

    async def log(
        self,
        *,
        code: OperationEventCode,
        severity: OperationLogSeverity,
        diagnostic_ref: OperationDiagnosticReference | None = None,
    ) -> None:
        event = OperationLogRecord(
            identity=self._context.identity,
            revision=0,
            sequence=1,
            timestamp=self._context.clock(),
            code=code,
            severity=severity,
            diagnostic_ref=diagnostic_ref,
        )
        await self._context.advance(lifecycle=OperationLifecycle.RUNNING, events=(event,))

    async def effect(self, effect: OperationEffect) -> None:
        definition = self._context.registry.lookup(self._context.identity.definition_id)
        if effect not in definition.capabilities.permitted_effects:
            raise ValueError("operation effect is not declared by its definition")
        event = OperationEffectEvent(
            identity=self._context.identity,
            revision=0,
            sequence=1,
            timestamp=self._context.clock(),
            code="operation.effect",
            effect=effect,
        )
        await self._context.advance(lifecycle=OperationLifecycle.RUNNING, events=(event,), effect=effect)

    async def notice(self, notice_code: OperationEventCode) -> None:
        event = OperationNoticeEvent(
            identity=self._context.identity,
            revision=0,
            sequence=1,
            timestamp=self._context.clock(),
            code=notice_code,
            notice_code=notice_code,
        )
        await self._context.advance(lifecycle=OperationLifecycle.RUNNING, events=(event,))

    async def diagnostic(self, diagnostic_ref: OperationDiagnosticReference) -> None:
        event = OperationDiagnosticEvent(
            identity=self._context.identity,
            revision=0,
            sequence=1,
            timestamp=self._context.clock(),
            code="operation.diagnostic",
            diagnostic_ref=diagnostic_ref,
        )
        await self._context.advance(lifecycle=OperationLifecycle.RUNNING, events=(event,))


class _DefinitionBoundCleanup:
    def __init__(self, context: _DefinitionBoundContext) -> None:
        self._context = context

    def own(self, resource: AsyncCloseable, *, family: OperationOwnedResource) -> None:
        definition = self._context.registry.lookup(self._context.identity.definition_id)
        if family not in definition.capabilities.owned_resources:
            raise ValueError("operation resource family is not declared by its definition")
        self._context.resources.setdefault(self._context.identity.operation_id, []).append(resource)


class _DefinitionBoundInteractions:
    def __init__(self, context: _DefinitionBoundContext) -> None:
        self._context = context

    async def request(self, pending: OperationPendingInteraction) -> None:
        definition = self._context.registry.lookup(self._context.identity.definition_id)
        if pending.request.kind not in definition.interaction_kinds:
            raise ValueError("operation interaction kind is not declared by its definition")
        if pending.request.identity != self._context.identity:
            raise ValueError("operation interaction identity does not match executor context")
        successor_revision = self._context.snapshot.revision + 1
        if pending.request.revision != successor_revision:
            raise ValueError("operation interaction revision does not match checkpoint revision")
        event = OperationInteractionEvent(
            identity=self._context.identity,
            revision=0,
            sequence=1,
            timestamp=self._context.clock(),
            code="operation.interaction.pending",
            interaction_id=pending.request.interaction_id,
        )
        await self._context.advance(
            lifecycle=OperationLifecycle.WAITING_FOR_INTERACTION,
            events=(event,),
            pending=pending,
        )


class OperationSupervisor:
    def __init__(
        self,
        *,
        registry: OperationRegistry,
        journal: OperationJournal,
        leases: OperationLeaseRepository,
        operands: OperationSecureReferenceStore,
        owner_id: Hex64Str,
        lease_token_factory: Callable[[], OperationLeaseToken],
        clock: Callable[[], datetime],
        lease_duration: timedelta,
    ) -> None:
        self._registry = registry
        self._journal = journal
        self._leases = leases
        self._operands = operands
        self._owner_id = owner_id
        self._lease_token = lease_token_factory()
        self._clock = clock
        self._lease_duration = lease_duration
        self._leases_by_operation: dict[OperationId, OperationOwnerLease] = {}
        self._resources: dict[OperationId, list[AsyncCloseable]] = {}

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

    async def _require_owned_lease(self, identity: OperationIdentity, now: datetime) -> OperationOwnerLease:
        scope_ref = operation_conflict_scope_reference(
            definition_id=identity.definition_id,
            subject_ref=identity.subject_ref,
        )
        observed = await self._leases.inspect(scope_ref, identity.operation_id, observed_at=now)
        if (
            observed.disposition is not OperationLeaseObservationDisposition.ACTIVE
            or observed.current is None
            or observed.current.owner_id != self._owner_id
            or observed.current.token != self._lease_token
        ):
            raise ValueError("operation is not owned by this supervisor")
        held = self._leases_by_operation.get(identity.operation_id)
        if held is not None and held != observed.current:
            raise ValueError("operation lease no longer matches this supervisor's exact held lease")
        self._leases_by_operation[identity.operation_id] = observed.current
        return observed.current

    async def _release_exact_lease(self, lease: OperationOwnerLease, *, observed_at: datetime) -> None:
        """Release one exact current lease and refuse any ownership loss."""
        released = await self._leases.release(lease, observed_at=observed_at)
        if released.disposition is not OperationLeaseDisposition.RELEASED:
            raise ValueError("operation exact lease release was refused")
        self._leases_by_operation.pop(lease.operation_id, None)

    async def submit(
        self, request: OperationRequest[BaseModel], *, operation_id: OperationId | None = None
    ) -> OperationId:
        definition = self._registry.lookup(request.definition_id)
        if not isinstance(request.payload, definition.request_type):
            raise ValueError("request payload does not match definition")
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
        if claim is not None:
            existing_operation_id = await self._journal.resolve_idempotency(claim)
            if existing_operation_id is not None:
                return existing_operation_id
        lease = self._candidate(identity, now)
        result = await self._leases.acquire(lease, observed_at=now)
        if result.disposition is not OperationLeaseDisposition.ACQUIRED:
            if claim is not None:
                existing_operation_id = await self._journal.resolve_idempotency(claim)
                if existing_operation_id is not None:
                    return existing_operation_id
            raise ValueError("operation conflict lease was not acquired")
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
        context = _DefinitionBoundContext(
            snapshot=running,
            registry=self._registry,
            operands=self._operands,
            clock=self._clock,
            resources=self._resources,
            advance=self._advance,
        )
        executor = definition.executor_factory.create()
        await executor.execute(request, context)
        return context.snapshot

    async def inspect(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        return await self._journal.load(operation_id)

    async def observe(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Return the latest durable operation observation."""
        return await self.inspect(operation_id)

    async def detach(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        return await self.inspect(operation_id)

    async def await_terminal(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        snapshot = await self.inspect(operation_id)
        if snapshot.lifecycle is not OperationLifecycle.TERMINAL:
            raise LookupError("operation is not terminal")
        return snapshot

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
        lease = await self._require_owned_lease(snapshot.identity, now)
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
        lease = await self._require_owned_lease(snapshot.identity, now)
        await close_async_resources(*self._resources.pop(operation_id, []), task_name="operation-settlement")
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
