"""Execution and invocation stages for the durable operation supervisor."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel

from ...core.errors.error_codes import ErrorCategory, get_registered_error_code
from ...core.hashing import content_hash_hex
from ...core.operations import OperationDeadline, OperationEffect, OperationLifecycle, OperationTerminalCondition
from . import supervisor_context as _supervisor_context
from ._execution_context import DefinitionBoundContext
from .capabilities import OperationRequestStoragePolicy
from .errors import OperationDeclarationError
from .financial_operand import (
    OperationTransientFinancialOperandDelivery,
    OperationTransientFinancialOperandRequirement,
)
from .interactions import (
    OperationApplyResponse,
    OperationConsumedInteraction,
    OperationPendingInteraction,
    OperationRejectResponse,
)
from .models import OperationId, OperationIdentity, OperationRequest, OperationTerminalReceipt, new_operation_id
from .persistence.events import (
    OperationEvent,
    OperationInteractionEvent,
    OperationNoticeEvent,
    OperationPhaseEvent,
)
from .persistence.idempotency import OperationIdempotencyClaim
from .persistence.journal import OperationPersistedSnapshot
from .persistence.leases import OperationLeaseDisposition
from .registry import OperationDefinition, OperationReconciliationPolicy
from .secret_submission import BoundEphemeralSecretAccess, OperationSecretRequirement, zeroize_secret_buffer


class SupervisorHost(Protocol):
    if TYPE_CHECKING:

        def __getattr__(self, name: str) -> Any: ...


_AWAIT_TERMINAL_INITIAL_BACKOFF_SECONDS = 0.025
_AWAIT_TERMINAL_MAX_BACKOFF_SECONDS = 0.25


def _advance_events(
    snapshot: OperationPersistedSnapshot,
    events: tuple[OperationEvent, ...],
    revision: int,
    now: datetime,
) -> tuple[OperationEvent, ...]:
    return tuple(
        event.model_copy(update={"revision": revision, "sequence": snapshot.event_cursor + index + 1, "timestamp": now})
        for index, event in enumerate(events)
    )


def _advance_phase_code(snapshot: OperationPersistedSnapshot, emitted: tuple[OperationEvent, ...]) -> str | None:
    phase_events = tuple(event for event in emitted if isinstance(event, OperationPhaseEvent))
    return snapshot.phase_code if not phase_events else phase_events[-1].phase_code


def _advance_value[T](current: T, requested: T | None) -> T:
    return current if requested is None else requested


def _advanced_snapshot(
    snapshot: OperationPersistedSnapshot,
    *,
    revision: int,
    lifecycle: OperationLifecycle,
    now: datetime,
    emitted: tuple[OperationEvent, ...],
    pending: OperationPendingInteraction | None,
    consumed: tuple[OperationConsumedInteraction, ...] | None,
    effect: OperationEffect | None,
    execution_deadline: datetime | None,
    cleanup_deadline: datetime | None,
    cancellation_requested_at: datetime | None,
    cancellation_acknowledged_at: datetime | None,
    cancellation_deferred: bool | None,
    executor_entered_at: datetime | None,
) -> OperationPersistedSnapshot:
    return snapshot.model_copy(
        update={
            "revision": revision,
            "lifecycle": lifecycle,
            "updated_at": now,
            "event_cursor": snapshot.event_cursor + len(emitted),
            "events": emitted,
            "phase_code": _advance_phase_code(snapshot, emitted),
            "pending_interaction": pending,
            "consumed_interactions": _advance_value(snapshot.consumed_interactions, consumed),
            "effect": _advance_value(snapshot.effect, effect),
            "execution_deadline": _advance_value(snapshot.execution_deadline, execution_deadline),
            "cleanup_deadline": _advance_value(snapshot.cleanup_deadline, cleanup_deadline),
            "cancellation_requested_at": _advance_value(
                snapshot.cancellation_requested_at,
                cancellation_requested_at,
            ),
            "cancellation_acknowledged_at": _advance_value(
                snapshot.cancellation_acknowledged_at,
                cancellation_acknowledged_at,
            ),
            "cancellation_deferred": _advance_value(snapshot.cancellation_deferred, cancellation_deferred),
            "executor_entered_at": _advance_value(snapshot.executor_entered_at, executor_entered_at),
        }
    )


class SupervisorExecutionMixin(SupervisorHost):
    """Own request binding, executor execution, and durable interaction stages."""

    async def submit[RequestPayloadT: BaseModel](
        self,
        request: OperationRequest[RequestPayloadT],
        *,
        operation_id: OperationId | None = None,
    ) -> OperationId:
        """Persist one validated operation request without starting execution."""
        definition = self.registry.lookup(request.definition_id)
        definition_contract = self.registry.lookup_public_contract(request.definition_id)
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

    def _require_pinned_definition(self, snapshot: OperationPersistedSnapshot) -> OperationDefinition:
        definition_id = snapshot.identity.definition_id
        definition = self.registry.lookup(definition_id)
        current_contract = self.registry.lookup_public_contract(definition_id)
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
        executor_context = _supervisor_context.SupervisorExecutorContext(
            context=context,
            operands=self._operands,
            ephemeral_secret=BoundEphemeralSecretAccess(
                requirement=requirement,
                broker=self._ephemeral_secrets,
                clock=self._clock,
            ),
            financial_operand=self._bound_financial_operand(running.identity, definition),
            clock=self._clock,
            response_authority_issuer=self._response_authority_issuer,
            response_token_factory=self._response_token_factory,
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
        finally:
            await self._settle_financial_operand_custody(operation_id)
        return await self._settle_returned_result(context.snapshot, result_ref)

    async def submit_transient_financial_operand(
        self,
        requirement: OperationTransientFinancialOperandRequirement,
        amount: Decimal,
    ) -> OperationTransientFinancialOperandDelivery:
        """Answer one running invocation's declared operand wait with an amount.

        The amount is a parameter and is never written to the journal: the
        broker settles it against the declaration that opened the wait and
        records only where custody stands.
        """
        if self._financial_operands is None:
            raise ValueError("this supervisor has no transient financial operand custody")
        snapshot = await self.inspect(requirement.identity.operation_id)
        if snapshot.lifecycle is not OperationLifecycle.RUNNING:
            raise ValueError("a transient financial operand may only answer a running invocation")
        return await self._financial_operands.deliver(requirement, amount, observed_at=self._clock())

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
        payload = self.registry.resolve_credential_free_payload(definition.definition_id, raw)
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
                failure_error_code=None if registered is None else registered.code,
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
            returned = await self.inspect(snapshot.identity.operation_id)
            if returned.cancellation_acknowledged_at is None:
                return returned
            condition = self._acknowledged_cancellation_condition(returned)
            if condition is OperationTerminalCondition.TIMED_OUT:
                self._validate_cancelled_settlement(returned)
            return await self.settle(
                returned.identity.operation_id,
                OperationTerminalReceipt(
                    identity=returned.identity,
                    revision=returned.revision + 1,
                    condition=condition,
                    effect=returned.effect,
                    settled_at=self._clock(),
                ),
            )
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
            emitted = _advance_events(snapshot, events, revision, now)
            successor = _advanced_snapshot(
                snapshot,
                revision=revision,
                lifecycle=lifecycle,
                now=now,
                emitted=emitted,
                pending=pending,
                consumed=consumed,
                effect=effect,
                execution_deadline=execution_deadline,
                cleanup_deadline=cleanup_deadline,
                cancellation_requested_at=cancellation_requested_at,
                cancellation_acknowledged_at=cancellation_acknowledged_at,
                cancellation_deferred=cancellation_deferred,
                executor_entered_at=executor_entered_at,
            )
            await self._journal.commit(successor, expected_revision=snapshot.revision, lease=lease)
            if discard_ephemeral_secret:
                self._ephemeral_secrets.discard(snapshot.identity.operation_id)
        self._notify_durable_change(successor)
        return successor

    async def respond(self, response: OperationApplyResponse | OperationRejectResponse) -> OperationConsumedInteraction:
        """Consume one pending response and resume it when its policy permits."""
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
