"""Application-owned baseline operation supervision."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from datetime import datetime, timedelta
from typing import cast

from pydantic import BaseModel

from ...core import (
    Hex64Str,
    OperationCancellation,
    OperationDeadline,
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    content_hash_hex,
)
from ...core.async_cleanup import AsyncCloseable, close_async_resources
from ...core.errors import ErrorCategory, get_registered_error_code
from ._capabilities import OperationRequestStoragePolicy
from ._events import (
    OperationDiagnosticEvent,
    OperationEvent,
    OperationInteractionEvent,
    OperationNoticeEvent,
    OperationPhaseEvent,
    OperationReconciliationEvent,
    OperationTerminalEvent,
)
from ._execution_context import DefinitionBoundContext, OperationDeclarationError
from ._executor import OperationResumableExecutor
from ._interactions import (
    OperationApplyResponse,
    OperationConsumedInteraction,
    OperationInteractionRequest,
    OperationPendingInteraction,
    OperationRejectResponse,
    OperationResponseToken,
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
    OperationReconciliationOutcome,
    OperationRequest,
    OperationTerminalReceipt,
    new_operation_id,
)
from ._registry import OperationDefinition, OperationReconciliationPolicy, OperationRegistry
from ._replay import OperationEventCursor, OperationReplayLimit, OperationReplayPage
from ._secret_submission import (
    BoundEphemeralSecretAccess,
    EphemeralSecretBroker,
    OperationSecretRequirement,
    zeroize_secret_buffer,
)
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
        operands: OperationSecureReferenceStore | None,
        owner_id: Hex64Str,
        lease_token_factory: Callable[[], OperationLeaseToken],
        clock: Callable[[], datetime],
        lease_duration: timedelta,
        execution_timeout: timedelta | None = None,
        cleanup_timeout: timedelta | None = None,
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
        self._execution_timeout = execution_timeout
        self._cleanup_timeout = cleanup_timeout
        self._leases_by_operation: dict[OperationId, OperationOwnerLease] = {}
        self._lease_locks: dict[OperationId, asyncio.Lock] = {}
        self._resources: dict[OperationId, list[AsyncCloseable]] = {}
        self._contexts: dict[OperationId, DefinitionBoundContext] = {}
        self._executor_tasks: dict[OperationId, asyncio.Task[object]] = {}
        self._cleanup_tasks: dict[OperationId, asyncio.Task[None]] = {}
        self._continuation_tasks: dict[OperationId, asyncio.Task[OperationPersistedSnapshot]] = {}
        self._durable_change_events: dict[OperationId, asyncio.Event] = {}
        self._durable_revisions: dict[OperationId, int] = {}
        self._ephemeral_secrets = EphemeralSecretBroker()

        if lease_duration <= timedelta():
            raise ValueError("operation lease duration must be positive")
        for name, duration in (
            ("operation execution timeout", execution_timeout),
            ("operation cleanup timeout", cleanup_timeout),
        ):
            if duration is not None and duration <= timedelta():
                raise ValueError(f"{name} must be positive when configured")
        for definition in registry.definitions:
            declaration = definition.ephemeral_secret
            if declaration is not None and declaration.lifetime >= lease_duration:
                raise ValueError("ephemeral secret lifetime must be shorter than the owner lease")

    async def submit(
        self, request: OperationRequest[BaseModel], *, operation_id: OperationId | None = None
    ) -> OperationId:
        definition = self._registry.lookup(request.definition_id)
        definition_contract = self._registry.lookup_public_contract(request.definition_id)
        self._validate_request_payload(request, definition.request_type)
        now = self._clock()
        identity = OperationIdentity(
            operation_id=operation_id or new_operation_id(),
            definition_id=request.definition_id,
            subject_ref=request.subject_ref,
        )
        request_storage = definition.capabilities.request_storage
        if request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE:
            if self._operands is None:
                raise ValueError("secure-reference request storage requires an operand store")
            ref = await self._operands.put(request.payload, written_at=now)
            credential_free_request_json = None
        else:
            credential_free_request_json = request.payload.model_dump_json()
            ref = content_hash_hex(request.payload.model_dump(mode="json"))
        secret_requirement = (
            OperationSecretRequirement(
                identity=identity,
                interaction_id=content_hash_hex(
                    {
                        "schema_version": 1,
                        "identity": identity.model_dump(mode="json"),
                        "revision": 0,
                        "secret_kind": definition.ephemeral_secret.secret_kind,
                    }
                ),
                revision=0,
                secret_kind=definition.ephemeral_secret.secret_kind,
                expires_at=now + definition.ephemeral_secret.lifetime,
            )
            if definition.ephemeral_secret is not None
            else None
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
            definition_contract_digest=definition_contract.definition_contract_digest,
            request_storage=request_storage,
            request_reference=ref,
            credential_free_request_json=credential_free_request_json,
            secret_requirement=secret_requirement,
            revision=0,
            lifecycle=OperationLifecycle.CREATED,
            started_at=now,
            updated_at=now,
            execution_deadline=None,
            cleanup_deadline=None,
            cancellation_requested_at=None,
            cancellation_acknowledged_at=None,
            cancellation_deferred=False,
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

    def _require_pinned_definition(self, snapshot: OperationPersistedSnapshot) -> OperationDefinition:
        definition_id = snapshot.identity.definition_id
        definition = self._registry.lookup(definition_id)
        current_contract = self._registry.lookup_public_contract(definition_id)
        if current_contract.definition_contract_digest != snapshot.definition_contract_digest:
            raise ValueError("operation definition contract no longer reproduces its invocation digest")
        return definition

    async def _load_pinned_snapshot(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Load one invocation only after its immutable registry contract reproduces."""
        snapshot = await self._journal.load(operation_id)
        self._require_pinned_definition(snapshot)
        return snapshot

    async def start(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Start one owned registered executor from its declared request storage."""
        snapshot = await self.inspect(operation_id)
        if snapshot.lifecycle is not OperationLifecycle.CREATED:
            raise ValueError("only a created operation may be started")
        definition = self._require_pinned_definition(snapshot)
        execution_deadline = self._execution_deadline_for(definition.capabilities.deadline)
        self._require_cleanup_timeout(definition.capabilities.cancellation)
        requirement = snapshot.secret_requirement
        now = self._clock()
        if requirement is not None:
            if now >= requirement.expires_at:
                self._ephemeral_secrets.discard(operation_id)
                return await self._settle_pre_entry_secret_wait(snapshot, OperationTerminalCondition.INTERRUPTED)
            if not self._ephemeral_secrets.has_exact(requirement, observed_at=now):
                raise ValueError("ephemeral secret requirement has no exact live submission")
        payload = await self._resolve_request_payload(snapshot, definition)
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
        running = await self._advance(
            snapshot,
            lifecycle=OperationLifecycle.RUNNING,
            events=(started,),
            execution_deadline=execution_deadline,
            executor_entered_at=now,
        )
        context = self._build_context(running)
        executor_context = _SupervisorExecutorContext(
            context=context,
            operands=self._operands,
            ephemeral_secret=BoundEphemeralSecretAccess(
                requirement=requirement,
                broker=self._ephemeral_secrets,
                clock=self._clock,
            ),
            clock=self._clock,
        )
        self._contexts[operation_id] = context
        executor = definition.executor_factory.create()
        try:
            result_ref = await self._execute_with_deadlines(
                identity=running.identity,
                context=context,
                executor=executor.execute(request, executor_context),
            )
        except OperationDeclarationError:
            raise
        except Exception as error:
            return await self._settle_executor_failure(context.snapshot, error)
        return await self._settle_returned_result(context.snapshot, result_ref)

    async def submit_ephemeral_secret(
        self,
        requirement: OperationSecretRequirement,
        secret: bytearray,
    ) -> None:
        """Accept one exact-bound mutable secret without serializing or digesting it."""
        try:
            expired_snapshot: OperationPersistedSnapshot | None = None
            async with self._lease_lock(requirement.identity.operation_id):
                snapshot = await self.inspect(requirement.identity.operation_id)
                if snapshot.secret_requirement != requirement:
                    raise ValueError("ephemeral secret submission does not match the durable requirement")
                if snapshot.lifecycle is not OperationLifecycle.CREATED or snapshot.executor_entered_at is not None:
                    raise ValueError("ephemeral secret requirement is no longer awaiting submission")
                observed_at = self._clock()
                if observed_at >= requirement.expires_at:
                    self._ephemeral_secrets.discard(requirement.identity.operation_id)
                    expired_snapshot = snapshot
                else:
                    self._ephemeral_secrets.submit(requirement, secret, observed_at=observed_at)
            if expired_snapshot is not None:
                await self._settle_pre_entry_secret_wait(expired_snapshot, OperationTerminalCondition.INTERRUPTED)
                raise ValueError("ephemeral secret requirement is expired")
        except BaseException:
            zeroize_secret_buffer(secret)
            raise

    async def _resolve_request_payload(
        self,
        snapshot: OperationPersistedSnapshot,
        definition: OperationDefinition,
    ) -> BaseModel:
        if snapshot.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE:
            if self._operands is None:
                raise ValueError("secure-reference request storage requires an operand store")
            return await self._operands.resolve(snapshot.request_reference, definition.request_type)
        raw = snapshot.credential_free_request_json
        if raw is None:
            raise ValueError("credential-free operation request is absent")
        payload = self._registry.resolve_credential_free_payload(definition.definition_id, raw)
        if content_hash_hex(payload.model_dump(mode="json")) != snapshot.request_reference:
            raise ValueError("credential-free operation request digest does not match durable content")
        return payload

    async def _settle_pre_entry_secret_wait(
        self,
        snapshot: OperationPersistedSnapshot,
        condition: OperationTerminalCondition,
    ) -> OperationPersistedSnapshot:
        if snapshot.executor_entered_at is not None:
            raise ValueError("pre-entry secret settlement cannot follow executor entry")
        return await self.settle(
            snapshot.identity.operation_id,
            OperationTerminalReceipt(
                identity=snapshot.identity,
                revision=snapshot.revision + 1,
                condition=condition,
                effect=OperationEffect.NONE,
                settled_at=self._clock(),
            ),
        )

    async def shutdown(self) -> None:
        """Wipe every runtime-only secret retained by this supervisor instance."""
        self._ephemeral_secrets.close()

    async def _settle_executor_failure(
        self,
        snapshot: OperationPersistedSnapshot,
        error: Exception,
    ) -> OperationPersistedSnapshot:
        """Settle one stopped executor without persisting its exception surface.

        Registered ``REFUSED`` errors retain their registry code as the
        canonical operator reference. Every other exception receives a stable
        opaque correlation digest over safe lifecycle facts only; exception
        message text, arguments, contexts, tracebacks, paths, and URLs never
        enter operation persistence.
        """
        try:
            registered = get_registered_error_code(error)
        except ValueError:
            registered = None
        if registered is not None and registered.category is ErrorCategory.REFUSED:
            receipt = OperationTerminalReceipt(
                identity=snapshot.identity,
                revision=snapshot.revision + 1,
                condition=OperationTerminalCondition.REFUSED,
                effect=snapshot.effect,
                settled_at=self._clock(),
                refusal_ref=registered.code,
            )
        else:
            receipt = OperationTerminalReceipt(
                identity=snapshot.identity,
                revision=snapshot.revision + 1,
                condition=OperationTerminalCondition.FAILED,
                effect=snapshot.effect,
                settled_at=self._clock(),
                diagnostic_ref=self._executor_failure_diagnostic_reference(snapshot, error),
            )
        return await self.settle(snapshot.identity.operation_id, receipt)

    @staticmethod
    def _executor_failure_diagnostic_reference(
        snapshot: OperationPersistedSnapshot,
        error: Exception,
    ) -> str:
        """Derive a non-reversing correlation key without absorbing error data.

        The correlation scope intentionally groups the same exception type for
        one operation terminal revision. It is not a message fingerprint, so
        its stable journal identity cannot reveal an operand, exception arg,
        filesystem path, URL, credential, or traceback fragment.
        """
        error_type = type(error)
        digest = content_hash_hex(
            {
                "schema_version": 1,
                "operation_id": snapshot.identity.operation_id,
                "definition_id": snapshot.identity.definition_id,
                "exception_type": f"{error_type.__module__}.{error_type.__qualname__}",
                "terminal_revision": snapshot.revision + 1,
            }
        )
        return f"sha256:{digest}"

    def _execution_deadline_for(self, deadline_capability: OperationDeadline) -> datetime | None:
        if deadline_capability is OperationDeadline.ABSENT:
            return None
        if self._execution_timeout is None:
            raise ValueError("deadline-capable operation requires a configured execution timeout")
        if self._cleanup_timeout is None:
            raise ValueError("deadline-capable operation requires a configured cleanup timeout")
        return self._clock() + self._execution_timeout

    def _require_cleanup_timeout(self, cancellation: OperationCancellation) -> None:
        if cancellation is not OperationCancellation.UNSUPPORTED and self._cleanup_timeout is None:
            raise ValueError("cancellable operation requires a configured cleanup timeout")

    async def _execute_with_deadlines(
        self,
        *,
        identity: OperationIdentity,
        context: DefinitionBoundContext,
        executor: Coroutine[object, object, object],
    ) -> object:
        """Await executor completion while aggregate and cleanup deadlines remain supervisor-owned."""
        executor_task = asyncio.create_task(
            self._renew_while_executing(identity=identity, executor=executor),
            name=f"operation-supervision-{identity.operation_id}",
        )
        self._executor_tasks[identity.operation_id] = executor_task
        while not executor_task.done():
            snapshot = context.snapshot
            now = self._clock()
            if snapshot.cancellation_requested_at is None:
                execution_deadline = snapshot.execution_deadline
                if execution_deadline is None:
                    await executor_task
                    break
                if now >= execution_deadline:
                    await self.request_cancel(identity.operation_id)
                    continue
                await self._wait_for_executor_or_deadline(executor_task, execution_deadline, now)
                continue
            cleanup_deadline = snapshot.cleanup_deadline
            if cleanup_deadline is not None and now >= cleanup_deadline:
                context.cancellation.record_request(await self._escalate_cleanup_deadline(identity.operation_id))
                await executor_task
                break
            if cleanup_deadline is None:
                raise ValueError("durable cancellation request is missing its cleanup deadline")
            await self._wait_for_executor_or_deadline(executor_task, cleanup_deadline, now)
        return await executor_task

    async def _settle_returned_result(
        self,
        snapshot: OperationPersistedSnapshot,
        result_ref: object,
    ) -> OperationPersistedSnapshot:
        """Join an executor's domain result to successful settlement after it stops."""
        if result_ref is None:
            return snapshot
        if not isinstance(result_ref, str):
            raise OperationDeclarationError("operation executor returned a non-reference result")
        if snapshot.lifecycle is not OperationLifecycle.RUNNING:
            raise OperationDeclarationError("operation executor returned a result outside running lifecycle")
        return await self.settle(
            snapshot.identity.operation_id,
            OperationTerminalReceipt(
                identity=snapshot.identity,
                revision=snapshot.revision + 1,
                condition=OperationTerminalCondition.SUCCEEDED,
                effect=snapshot.effect,
                settled_at=self._clock(),
                result_ref=result_ref,
            ),
        )

    @staticmethod
    async def _wait_for_executor_or_deadline(
        executor_task: asyncio.Task[object],
        deadline: datetime,
        now: datetime,
    ) -> None:
        """Yield until a real task ends or the supervisor-owned UTC deadline arrives."""
        remaining_seconds = max((deadline - now).total_seconds(), 0.0)
        await asyncio.wait((executor_task,), timeout=remaining_seconds)

    async def inspect(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        return await self._load_pinned_snapshot(operation_id)

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
        await self.inspect(operation_id)
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
        execution_deadline: datetime | None = None,
        cleanup_deadline: datetime | None = None,
        cancellation_requested_at: datetime | None = None,
        cancellation_acknowledged_at: datetime | None = None,
        cancellation_deferred: bool | None = None,
        executor_entered_at: datetime | None = None,
        discard_ephemeral_secret: bool = False,
    ) -> OperationPersistedSnapshot:
        self._require_pinned_definition(snapshot)
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
                    "execution_deadline": (
                        snapshot.execution_deadline if execution_deadline is None else execution_deadline
                    ),
                    "cleanup_deadline": snapshot.cleanup_deadline if cleanup_deadline is None else cleanup_deadline,
                    "cancellation_requested_at": (
                        snapshot.cancellation_requested_at
                        if cancellation_requested_at is None
                        else cancellation_requested_at
                    ),
                    "cancellation_acknowledged_at": (
                        snapshot.cancellation_acknowledged_at
                        if cancellation_acknowledged_at is None
                        else cancellation_acknowledged_at
                    ),
                    "cancellation_deferred": (
                        snapshot.cancellation_deferred
                        if cancellation_deferred is None
                        else cancellation_deferred
                    ),
                    "executor_entered_at": (
                        snapshot.executor_entered_at if executor_entered_at is None else executor_entered_at
                    ),
                }
            )
            await self._journal.commit(successor, expected_revision=snapshot.revision, lease=lease)
            if discard_ephemeral_secret:
                self._ephemeral_secrets.discard(snapshot.identity.operation_id)
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
        successor = await self._advance(
            snapshot,
            lifecycle=OperationLifecycle.RUNNING,
            events=(event,),
            consumed=(*snapshot.consumed_interactions, consumed),
        )
        definition = self._require_pinned_definition(snapshot)
        if definition.reconciliation_policy is OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT:
            self._schedule_continuation(successor, definition, consumed)
        return consumed

    def _schedule_continuation(
        self,
        snapshot: OperationPersistedSnapshot,
        definition: OperationDefinition,
        continuation: OperationConsumedInteraction,
    ) -> None:
        """Schedule one durably recorded response without weakening restart recovery."""
        operation_id = snapshot.identity.operation_id
        current = self._continuation_tasks.get(operation_id)
        if current is not None and not current.done():
            raise ValueError("operation continuation is already scheduled")
        task = asyncio.create_task(
            self._resume_from_checkpoint(snapshot, definition, continuation),
            name=f"operation-continuation-{operation_id}",
        )
        self._continuation_tasks[operation_id] = task
        task.add_done_callback(self._continuation_completed)

    def _continuation_completed(self, task: asyncio.Task[OperationPersistedSnapshot]) -> None:
        """Observe scheduled completion so task failures are never orphaned by asyncio."""
        if task.cancelled():
            return
        task.exception()

    async def reject(self, response: OperationRejectResponse) -> OperationConsumedInteraction:
        return await self.respond(response)

    async def request_cancel(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        snapshot = await self.inspect(operation_id)
        if snapshot.secret_requirement is not None and snapshot.executor_entered_at is None:
            requested_at = self._clock()
            event = OperationNoticeEvent(
                identity=snapshot.identity,
                revision=0,
                sequence=1,
                timestamp=requested_at,
                code="operation.secret.cancelled",
                notice_code="operation.secret.cancelled",
            )
            acknowledged = await self._advance(
                snapshot,
                lifecycle=OperationLifecycle.SETTLING,
                events=(event,),
                cleanup_deadline=requested_at + self._lease_duration,
                cancellation_requested_at=requested_at,
                cancellation_acknowledged_at=requested_at,
                discard_ephemeral_secret=True,
            )
            return await self._settle_pre_entry_secret_wait(acknowledged, OperationTerminalCondition.CANCELLED)
        cancellation = self._require_pinned_definition(snapshot).capabilities.cancellation
        if cancellation is OperationCancellation.UNSUPPORTED:
            raise ValueError("operation does not support cancellation")
        self._require_cleanup_timeout(cancellation)
        if snapshot.lifecycle is OperationLifecycle.TERMINAL:
            raise ValueError("terminal operation cannot receive a cancellation request")
        if snapshot.lifecycle in {OperationLifecycle.CREATED, OperationLifecycle.QUEUED}:
            raise ValueError("operation must be running before cancellation can be requested")
        if snapshot.cancellation_requested_at is not None:
            return snapshot
        cleanup_timeout = self._cleanup_timeout
        if cleanup_timeout is None:
            raise ValueError("cancellable operation requires a configured cleanup timeout")
        requested_at = self._clock()
        successor = await self._advance(
            snapshot,
            lifecycle=OperationLifecycle.CANCELLATION_REQUESTED,
            cleanup_deadline=requested_at + cleanup_timeout,
            cancellation_requested_at=requested_at,
        )
        context = self._contexts.get(operation_id)
        if context is not None:
            context.cancellation.record_request(successor)
        return successor

    async def _acknowledge_cancellation(
        self,
        context_snapshot: OperationPersistedSnapshot,
    ) -> OperationPersistedSnapshot:
        """Persist an executor's safe-stop acknowledgement after its request."""
        snapshot = await self.inspect(context_snapshot.identity.operation_id)
        if snapshot.identity != context_snapshot.identity:
            raise ValueError("cancellation acknowledgement identity does not match current operation")
        if snapshot.cancellation_requested_at is None:
            raise ValueError("cancellation acknowledgement requires a durable request")
        if snapshot.cancellation_acknowledged_at is not None:
            return snapshot
        if snapshot.lifecycle not in {OperationLifecycle.CANCELLATION_REQUESTED, OperationLifecycle.SETTLING}:
            raise ValueError("cancellation acknowledgement requires requested or settling lifecycle")
        return await self._advance(
            snapshot,
            lifecycle=OperationLifecycle.SETTLING,
            cancellation_acknowledged_at=self._clock(),
        )

    async def _set_cancellation_deferred(
        self,
        context_snapshot: OperationPersistedSnapshot,
        deferred: bool,
    ) -> OperationPersistedSnapshot:
        """Persist current cancellation availability across an irreversible section."""
        while True:
            current = await self.inspect(context_snapshot.identity.operation_id)
            if current.identity != context_snapshot.identity:
                raise ValueError("cancellation availability identity does not match current operation")
            if deferred and current.cancellation_requested_at is not None:
                raise ValueError("cancellation was requested before the irreversible section began")
            if current.cancellation_deferred is deferred:
                return current
            try:
                return await self._advance(
                    current,
                    lifecycle=current.lifecycle,
                    cancellation_deferred=deferred,
                )
            except Exception:
                latest = await self.inspect(current.identity.operation_id)
                if latest.revision == current.revision:
                    raise

    async def _escalate_cleanup_deadline(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Retain uncertainty after the cleanup window without publishing a false terminal state."""
        snapshot = await self.inspect(operation_id)
        if snapshot.lifecycle is OperationLifecycle.TERMINAL:
            return snapshot
        if snapshot.cancellation_requested_at is None or snapshot.cleanup_deadline is None:
            raise ValueError("cleanup escalation requires a durable cancellation deadline")
        if snapshot.lifecycle is OperationLifecycle.SETTLING:
            return snapshot
        return await self._advance(snapshot, lifecycle=OperationLifecycle.SETTLING)

    async def settle(self, operation_id: OperationId, receipt: OperationTerminalReceipt) -> OperationPersistedSnapshot:
        snapshot = await self.inspect(operation_id)
        if receipt.identity != snapshot.identity or receipt.revision != snapshot.revision + 1:
            raise ValueError("terminal receipt does not match successor revision")
        definition = self._require_pinned_definition(snapshot)
        if receipt.effect not in definition.capabilities.permitted_effects:
            raise OperationDeclarationError("terminal receipt effect is not declared by its definition")
        if (
            receipt.condition is not OperationTerminalCondition.INTERRUPTED
            or snapshot.identity.operation_id in self._executor_tasks
        ):
            self._validate_executor_stopped_for_settlement(snapshot, receipt.condition)
        if receipt.condition is OperationTerminalCondition.CANCELLED:
            self._validate_cancelled_settlement(snapshot)
        now = receipt.settled_at
        cleanup_deadline_elapsed = False
        successor: OperationPersistedSnapshot | None = None
        async with self._lease_lock(snapshot.identity.operation_id):
            lease = await self._require_owned_lease_unlocked(snapshot.identity, now)
            try:
                await self._complete_cleanup_before_settlement(snapshot)
            except TimeoutError:
                cleanup_deadline_elapsed = True
            if not cleanup_deadline_elapsed:
                diagnostic_event = (
                    OperationDiagnosticEvent(
                        identity=snapshot.identity,
                        revision=receipt.revision,
                        sequence=snapshot.event_cursor + 1,
                        timestamp=now,
                        code="operation.diagnostic",
                        diagnostic_ref=receipt.diagnostic_ref,
                    )
                    if receipt.diagnostic_ref is not None
                    else None
                )
                event = OperationTerminalEvent(
                    identity=snapshot.identity,
                    revision=receipt.revision,
                    sequence=snapshot.event_cursor + (2 if diagnostic_event is not None else 1),
                    timestamp=now,
                    code="operation.terminal",
                    receipt=receipt,
                )
                events: tuple[OperationEvent, ...] = (
                    (diagnostic_event, event) if diagnostic_event is not None else (event,)
                )
                successor = snapshot.model_copy(
                    update={
                        "revision": receipt.revision,
                        "lifecycle": OperationLifecycle.TERMINAL,
                        "terminal_condition": receipt.condition,
                        "effect": receipt.effect,
                        "updated_at": now,
                        "event_cursor": event.sequence,
                        "events": events,
                        "terminal_receipt": receipt,
                        "pending_interaction": None,
                    }
                )
                await self._journal.commit(successor, expected_revision=snapshot.revision, lease=lease)
                await self._release_exact_lease(lease, observed_at=now)
                self._ephemeral_secrets.discard(operation_id)
        if cleanup_deadline_elapsed:
            await self._escalate_cleanup_deadline(operation_id)
            raise TimeoutError("operation cleanup deadline elapsed before terminal settlement")
        if successor is None:
            raise RuntimeError("operation terminal settlement did not produce a successor snapshot")
        self._contexts.pop(operation_id, None)
        self._executor_tasks.pop(operation_id, None)
        self._cleanup_tasks.pop(operation_id, None)
        self._continuation_tasks.pop(operation_id, None)
        self._notify_durable_change(successor)
        return successor

    def _validate_executor_stopped_for_settlement(
        self,
        snapshot: OperationPersistedSnapshot,
        condition: OperationTerminalCondition,
    ) -> None:
        """Require local stop proof before a terminal condition claims work is over."""
        if snapshot.executor_entered_at is None or snapshot.lifecycle in {
            OperationLifecycle.CREATED,
            OperationLifecycle.QUEUED,
        }:
            return
        executor_task = self._executor_tasks.get(snapshot.identity.operation_id)
        if executor_task is None or not executor_task.done():
            raise ValueError(f"{condition.value} settlement requires completed executor work")

    def _validate_cancelled_settlement(self, snapshot: OperationPersistedSnapshot) -> None:
        """Reject a cancellation terminal claim until the executor's safe stop is proven."""
        if snapshot.cancellation_acknowledged_at is None:
            raise ValueError("cancelled settlement requires durable executor acknowledgement")
        cleanup_deadline = snapshot.cleanup_deadline
        if cleanup_deadline is None:
            raise ValueError("cancelled settlement requires a durable cleanup deadline")
        if self._clock() >= cleanup_deadline:
            raise ValueError("cleanup deadline elapsed; cancellation remains unsettled")

    async def _complete_cleanup_before_settlement(self, snapshot: OperationPersistedSnapshot) -> None:
        """Close owned resources within the durable cleanup window before any terminal commit."""
        operation_id = snapshot.identity.operation_id
        cleanup_task = self._cleanup_tasks.get(operation_id)
        if cleanup_task is None:
            cleanup_task = asyncio.create_task(
                close_async_resources(*self._resources.get(operation_id, ()), task_name="operation-settlement"),
                name=f"operation-cleanup-{operation_id}",
            )
            self._cleanup_tasks[operation_id] = cleanup_task
        cleanup_deadline = snapshot.cleanup_deadline
        if cleanup_deadline is not None:
            now = self._clock()
            if now >= cleanup_deadline:
                raise TimeoutError("operation cleanup deadline elapsed before terminal settlement")
            done, _ = await asyncio.wait(
                (cleanup_task,),
                timeout=(cleanup_deadline - now).total_seconds(),
            )
            if cleanup_task not in done:
                raise TimeoutError("operation cleanup deadline elapsed before terminal settlement")
        await cleanup_task
        self._resources.pop(operation_id, None)

    async def reconcile(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Recover one startup entry only through its durable owner evidence."""
        snapshot = await self.inspect(operation_id)
        if snapshot.lifecycle is OperationLifecycle.TERMINAL:
            return snapshot
        definition = self._require_pinned_definition(snapshot)
        scope_ref = operation_conflict_scope_reference(
            definition_id=snapshot.identity.definition_id,
            subject_ref=snapshot.identity.subject_ref,
        )
        now = self._clock()
        observed = await self._leases.inspect(scope_ref, operation_id, observed_at=now)
        if observed.disposition is OperationLeaseObservationDisposition.ACTIVE:
            raise ValueError("operation has active owner")
        if observed.disposition is OperationLeaseObservationDisposition.ABSENT:
            acquired = await self._leases.acquire(self._candidate(snapshot.identity, now), observed_at=now)
            if acquired.disposition is not OperationLeaseDisposition.ACQUIRED or acquired.current is None:
                raise ValueError("operation orphan lease acquisition was refused")
            self._leases_by_operation[operation_id] = acquired.current
            return await self._interrupt_reconciliation(
                snapshot,
                outcome=OperationReconciliationOutcome.ORPHANED,
                lease_evidence_ref=acquired.evidence_ref,
                effect=(
                    OperationEffect.NONE
                    if snapshot.secret_requirement is not None and snapshot.executor_entered_at is None
                    else OperationEffect.UNKNOWN
                ),
            )
        if observed.disposition is not OperationLeaseObservationDisposition.EXPIRED or observed.current is None:
            raise ValueError("operation lease observation cannot establish startup reconciliation ownership")
        checkpoint = snapshot.pending_interaction
        continuation = snapshot.consumed_interactions[-1] if snapshot.consumed_interactions else None
        may_resume_checkpoint = (
            definition.reconciliation_policy is OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT
            and self._is_valid_resume_checkpoint(snapshot, checkpoint, definition)
        )
        may_resume_continuation = (
            definition.reconciliation_policy is OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT
            and self._is_valid_resume_continuation(snapshot, continuation, definition)
        )
        takeover = self._candidate(snapshot.identity, now)
        taken_over = await self._leases.compare_and_swap(observed.current, takeover, observed_at=now)
        if taken_over.disposition is not OperationLeaseDisposition.TAKEN_OVER or taken_over.current != takeover:
            raise ValueError("operation expired owner lease takeover was refused")
        self._leases_by_operation[operation_id] = takeover
        if observed.current.operation_id != operation_id:
            return await self._interrupt_reconciliation(
                snapshot,
                outcome=OperationReconciliationOutcome.ORPHANED,
                lease_evidence_ref=taken_over.evidence_ref,
            )
        if snapshot.lifecycle is OperationLifecycle.CREATED:
            if snapshot.secret_requirement is not None and snapshot.executor_entered_at is None:
                return await self._interrupt_reconciliation(
                    snapshot,
                    outcome=OperationReconciliationOutcome.INTERRUPTED,
                    lease_evidence_ref=taken_over.evidence_ref,
                    effect=OperationEffect.NONE,
                )
            return await self._record_reconciliation(
                snapshot,
                outcome=OperationReconciliationOutcome.RECOVERED,
                lease_evidence_ref=taken_over.evidence_ref,
            )
        if may_resume_checkpoint:
            assert checkpoint is not None
            resumed = await self._record_reconciliation(
                snapshot,
                outcome=OperationReconciliationOutcome.RESUMED,
                lease_evidence_ref=taken_over.evidence_ref,
            )
            return await self._resume_from_checkpoint(resumed, definition, checkpoint)
        if may_resume_continuation:
            assert continuation is not None
            resumed = await self._record_reconciliation(
                snapshot,
                outcome=OperationReconciliationOutcome.RESUMED,
                lease_evidence_ref=taken_over.evidence_ref,
            )
            return await self._resume_from_checkpoint(resumed, definition, continuation)
        return await self._interrupt_reconciliation(
            snapshot,
            outcome=OperationReconciliationOutcome.INTERRUPTED,
            lease_evidence_ref=taken_over.evidence_ref,
        )

    @staticmethod
    def _is_valid_resume_checkpoint(
        snapshot: OperationPersistedSnapshot,
        checkpoint: OperationPendingInteraction | None,
        definition: OperationDefinition,
    ) -> bool:
        """Accept only the exact persisted interaction checkpoint contract."""
        return (
            snapshot.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
            and checkpoint is not None
            and checkpoint.request.identity == snapshot.identity
            and checkpoint.request.revision <= snapshot.revision
            and checkpoint.request.interaction_id
            not in {item.interaction_id for item in snapshot.consumed_interactions}
            and checkpoint.request.kind in definition.interaction_kinds
        )

    @staticmethod
    def _is_valid_resume_continuation(
        snapshot: OperationPersistedSnapshot,
        continuation: OperationConsumedInteraction | None,
        definition: OperationDefinition,
    ) -> bool:
        """Accept only the latest consumed-but-unsettled durable continuation."""
        return (
            snapshot.lifecycle is OperationLifecycle.RUNNING
            and snapshot.pending_interaction is None
            and continuation is not None
            and continuation.checkpoint.request.identity == snapshot.identity
            and continuation.checkpoint.request.interaction_id == continuation.interaction_id
            and continuation.checkpoint.request.kind in definition.interaction_kinds
        )

    async def _resume_from_checkpoint(
        self,
        snapshot: OperationPersistedSnapshot,
        definition: OperationDefinition,
        checkpoint: OperationPendingInteraction | OperationConsumedInteraction,
    ) -> OperationPersistedSnapshot:
        """Re-enter one registered executor from its declared durable checkpoint."""
        executor = definition.executor_factory.create()
        if not isinstance(executor, OperationResumableExecutor):
            raise ValueError("checkpoint reconciliation executor is not resumable")
        resumable_executor = cast(OperationResumableExecutor[BaseModel], executor)
        payload = await self._resolve_request_payload(snapshot, definition)
        request = OperationRequest(
            definition_id=snapshot.identity.definition_id,
            subject_ref=snapshot.identity.subject_ref,
            payload=payload,
            idempotency_key=None,
        )
        context = self._build_context(snapshot)
        executor_context = _SupervisorExecutorContext(
            context=context,
            operands=self._operands,
            ephemeral_secret=BoundEphemeralSecretAccess(
                requirement=snapshot.secret_requirement,
                broker=self._ephemeral_secrets,
                clock=self._clock,
            ),
            clock=self._clock,
        )
        self._contexts[snapshot.identity.operation_id] = context
        try:
            result_ref = await self._execute_with_deadlines(
                identity=snapshot.identity,
                context=context,
                executor=resumable_executor.resume(request, checkpoint, executor_context),
            )
        except OperationDeclarationError:
            raise
        except Exception as error:
            return await self._settle_executor_failure(context.snapshot, error)
        return await self._settle_returned_result(context.snapshot, result_ref)

    def _build_context(self, snapshot: OperationPersistedSnapshot) -> DefinitionBoundContext:
        return DefinitionBoundContext(
            snapshot=snapshot,
            registry=self._registry,
            operands=self._operands,
            clock=self._clock,
            resources=self._resources,
            advance=self._advance,
            acknowledge_cancellation=self._acknowledge_cancellation,
            set_cancellation_deferred=self._set_cancellation_deferred,
        )

    async def _record_reconciliation(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        outcome: OperationReconciliationOutcome,
        lease_evidence_ref: str,
    ) -> OperationPersistedSnapshot:
        event = OperationReconciliationEvent(
            identity=snapshot.identity,
            revision=0,
            sequence=1,
            timestamp=self._clock(),
            code="operation.reconciliation",
            outcome=outcome,
            lease_evidence_ref=lease_evidence_ref,
        )
        pending = snapshot.pending_interaction
        if pending is not None:
            pending = pending.model_copy(
                update={"request": pending.request.model_copy(update={"revision": snapshot.revision + 1})}
            )
        return await self._advance(
            snapshot,
            lifecycle=snapshot.lifecycle,
            events=(event,),
            pending=pending,
        )

    async def _interrupt_reconciliation(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        outcome: OperationReconciliationOutcome,
        lease_evidence_ref: str,
        effect: OperationEffect = OperationEffect.UNKNOWN,
    ) -> OperationPersistedSnapshot:
        classified = await self._record_reconciliation(
            snapshot,
            outcome=outcome,
            lease_evidence_ref=lease_evidence_ref,
        )
        receipt = OperationTerminalReceipt(
            identity=classified.identity,
            revision=classified.revision + 1,
            condition=OperationTerminalCondition.INTERRUPTED,
            effect=effect,
            settled_at=self._clock(),
        )
        return await self.settle(classified.identity.operation_id, receipt)


class _SupervisorInteractionAccess:
    """Publish reviewed operands through secure storage before journal visibility."""

    def __init__(
        self,
        *,
        request_pending: Callable[[OperationPendingInteraction], Awaitable[None]],
        operands: OperationSecureReferenceStore | None,
        clock: Callable[[], datetime],
    ) -> None:
        self._request_pending = request_pending
        self._operands = operands
        self._clock = clock

    async def request(self, pending: OperationPendingInteraction) -> None:
        await self._request_pending(pending)

    async def publish_review(
        self,
        *,
        request: OperationInteractionRequest,
        response_token: OperationResponseToken,
        reviewed_operand: BaseModel,
        baseline_digest: str | None = None,
        proposed_effect_digest: str | None = None,
    ) -> OperationPendingInteraction:
        if self._operands is None:
            raise ValueError("secure review publication requires an operand store")
        reference = await self._operands.put(reviewed_operand, written_at=self._clock())
        pending = OperationPendingInteraction.bind(
            request=request,
            response_token=response_token,
            reviewed_proposal_digest=reference,
            baseline_digest=baseline_digest,
            proposed_effect_digest=proposed_effect_digest,
        )
        await self._request_pending(pending)
        return pending


class _SupervisorExecutorContext:
    """Delegate definition checks while adding supervisor-owned secure publication."""

    def __init__(
        self,
        *,
        context: DefinitionBoundContext,
        operands: OperationSecureReferenceStore | None,
        ephemeral_secret: BoundEphemeralSecretAccess,
        clock: Callable[[], datetime],
    ) -> None:
        self.identity = context.identity
        self.cancellation = context.cancellation
        self.deadlines = context.deadlines
        self.events = context.events
        self._operands = operands
        self.ephemeral_secret = ephemeral_secret
        self.cleanup = context.cleanup
        self.interactions = _SupervisorInteractionAccess(
            request_pending=context.interactions.request,
            operands=operands,
            clock=clock,
        )
        self._context = context

    @property
    def operands(self) -> OperationSecureReferenceStore:
        """Expose secure storage only when the composition root supplied it."""
        if self._operands is None:
            raise ValueError("operation definition has no secure operand store")
        return self._operands

    @property
    def revision(self) -> int:
        """Return the current durable revision without exposing journal state."""
        return self._context.snapshot.revision

    @property
    def snapshot(self) -> OperationPersistedSnapshot:
        """Expose the current durable view retained by the definition-bound context."""
        return self._context.snapshot
