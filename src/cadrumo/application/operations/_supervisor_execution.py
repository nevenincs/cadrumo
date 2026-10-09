"""Execution and invocation stages for the durable operation supervisor."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import datetime
from typing import override

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.errors.error_codes import ErrorCategory, get_registered_error_code
from ...core.errors.hierarchy import CadrumoError, InternalInvariantError
from ...core.hashing import canonical_json_bytes, content_hash_hex, prefixed_digest
from ...core.identity.digest import ContentDigest
from ...core.logging import get_logger
from ...core.operations import (
    OperationDeadline,
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ...core.operator_progress import OperatorProgress, operator_progress_sink
from ..user_profile.access_contracts import AccessAction
from ..user_profile.access_errors import ProfileAccessRefusedError
from . import _supervisor_snapshot
from . import supervisor_context as _supervisor_context
from ._execution_context import DefinitionBoundContext
from ._supervisor_host import SupervisorHost
from ._supervisor_refusal import _validated_refusal_receipt
from .authorization import invoke_authorized
from .capabilities import OperationRequestStoragePolicy
from .error_detail import build_operation_error_detail
from .errors import OperationDeclarationError, OperationExecutorReturnedNoResultError, OperationUnsettledError
from .financial_operand_contract import OperationFinancialOperandRefusalCode, OperationFinancialOperandRefusedError
from .interactions import (
    OperationApplyResponse,
    OperationConsumedInteraction,
    OperationPendingInteraction,
    OperationRejectResponse,
)
from .models import (
    OperationId,
    OperationIdentity,
    OperationRequest,
    OperationTerminalReceipt,
)
from .operation_definition import OperationDefinition
from .persistence.events import (
    OperationEvent,
    OperationInteractionEvent,
    OperationNoticeEvent,
)
from .persistence.journal import (
    OperationPersistedSnapshot,
    OperationSecureReferenceStore,
)
from .refusal_evidence import OperationExecutorResult, OperationRefusalEvidence
from .registry import OperationReconciliationPolicy, OperationRegistry
from .secret_submission import BoundEphemeralSecretAccess, OperationSecretRequirement, zeroize_secret_buffer
from .typed_financial_operand_context import BoundTypedFinancialOperandAccess

_log = get_logger(__name__)

_AWAIT_TERMINAL_INITIAL_BACKOFF_SECONDS = 0.025
_AWAIT_TERMINAL_MAX_BACKOFF_SECONDS = 0.25


async def _forwarding_operator_progress(
    context: DefinitionBoundContext,
    executor: Coroutine[None, None, OperationExecutorResult],
) -> OperationExecutorResult:
    """Run ``executor`` with its operator progress journaled as the operation's public notices.

    The executor's adapters run inside the profile worker, where no frontend
    sink exists; forwarding through the journal is what lets an observing
    frontend prompt the operator. Only the stable notice code and the typed
    comparison code cross, so the progress text stays with the emitter's log.
    """

    async def forward(progress: OperatorProgress) -> None:
        await context.events.notice(progress.notice_code, display_code=progress.display_code)

    with operator_progress_sink(forward):
        return await executor


async def _stored_error_detail(
    registry: OperationRegistry,
    definition_id: str,
    operands: OperationSecureReferenceStore | None,
    error: Exception,
    *,
    written_at: datetime,
) -> ContentDigest | None:
    """Store the stopped executor's public detail as an encrypted operand, when its definition opts in.

    Settlement never depends on it: a definition that does not opt in, a host
    without an operand store, an error with no public facts, or a detail that
    cannot be built or stored leaves the receipt with the registered code it
    has always carried.
    """
    if operands is None:
        return None
    try:
        if not registry.lookup(definition_id).public_error_detail:
            return None
        detail = build_operation_error_detail(error)
        if detail is None:
            return None
        return await operands.put(detail, written_at=written_at)
    except Exception:
        return None


class SupervisorExecutionMixin(SupervisorHost):
    """Own request binding, executor execution, and durable interaction stages."""

    @override
    def _require_pinned_definition(self: SupervisorHost, snapshot: OperationPersistedSnapshot) -> OperationDefinition:
        definition_id = snapshot.identity.definition_id
        definition = self.registry.lookup(definition_id)
        current_contract = self.registry.lookup_public_contract(definition_id)
        if current_contract.definition_contract_digest != snapshot.definition_contract_digest:
            raise ValueError("operation definition contract no longer reproduces its invocation digest")
        return definition

    @override
    async def _load_pinned_snapshot(self: SupervisorHost, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Load one invocation only after its immutable registry contract reproduces."""
        snapshot = await self._journal.load(operation_id)
        self._require_pinned_definition(snapshot)
        return snapshot

    @override
    async def start(self: SupervisorHost, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Admit one owned registered executor and return its running snapshot.

        Every refusal before executor entry is raised here, and admission -- the
        lease held and the running state committed -- is durable before this
        returns. Execution and settlement continue in one supervised task;
        ``settled`` returns what it concluded, and observers follow its
        events through the journal meanwhile.
        """
        snapshot = await self.inspect(operation_id)
        if snapshot.lifecycle is not OperationLifecycle.CREATED:
            raise ValueError("only a created operation may be started")
        definition = self._require_pinned_definition(snapshot)
        if definition.transient_financial_operand is not None:
            if snapshot.financial_requirement is None or self._typed_financial_operands is None:
                raise OperationFinancialOperandRefusedError(OperationFinancialOperandRefusalCode.UNKNOWN_REQUIREMENT)
            await self._typed_financial_operands.require_ready(snapshot.financial_requirement)
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
        if self._execution_authority is not None:
            await self._execution_authority.require(
                identity=snapshot.identity, request=request, action=AccessAction.START
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
            authority_operation=self._authority_operation,
            operands=self._operands,
            ephemeral_secret=BoundEphemeralSecretAccess(
                requirement=requirement,
                broker=self._ephemeral_secrets,
                clock=self._clock,
            ),
            typed_financial_operand=BoundTypedFinancialOperandAccess(
                broker=self._typed_financial_operands,
                declaration=definition.transient_financial_operand,
                requirement=running.financial_requirement,
            ),
            clock=self._clock,
            response_authority_issuer=self._response_authority_issuer,
            response_token_factory=self._response_token_factory,
        )
        self._contexts[operation_id] = context
        executor = definition.executor_factory.create()
        settlement = asyncio.create_task(
            self._execute_and_settle(
                operation_id=operation_id,
                context=context,
                executor=invoke_authorized(
                    self._execution_authority,
                    identity=running.identity,
                    request=request,
                    action=AccessAction.START,
                    executor=lambda: executor.execute(request, executor_context),
                ),
            ),
            name=f"operation-settlement-{operation_id}",
        )
        self._settlement_tasks[operation_id] = settlement
        settlement.add_done_callback(self._settlement_completed)
        return running

    @override
    async def _execute_and_settle(
        self: SupervisorHost,
        *,
        operation_id: OperationId,
        context: DefinitionBoundContext,
        executor: Coroutine[None, None, OperationExecutorResult],
    ) -> OperationPersistedSnapshot:
        """Run one admitted executor to its settlement; the body of the supervised task.

        Operand custody is settled on every exit, including cancellation by a
        closing host, so no decrypted operand outlives the task.
        """
        failure: Exception | None = None
        result_ref: OperationExecutorResult = None
        try:
            result_ref = await self._execute_with_deadlines(
                identity=context.snapshot.identity,
                context=context,
                executor=executor,
            )
        except OperationDeclarationError:
            raise
        except Exception as error:
            failure = error
        finally:
            await self._settle_financial_operand_custody(operation_id)
        if failure is not None:
            return await self._settle_executor_failure(context.snapshot, failure)
        return await self._settle_returned_result(context.snapshot, result_ref)

    @override
    async def settled(self: SupervisorHost, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Return what one started operation concluded once its supervised task ends.

        A cancelled wait leaves the operation running. When the task stopped
        without a commitable settlement, the journal's state is raised inside
        :class:`OperationUnsettledError` with the stopping error as its cause.
        Without a task in this process, the durable terminal state is awaited.
        """
        settlement = self._settlement_tasks.get(operation_id)
        if settlement is None:
            return await self.await_terminal(operation_id)
        try:
            return await asyncio.shield(settlement)
        except asyncio.CancelledError:
            if not settlement.cancelled():
                raise
            unsettled = OperationUnsettledError(await self.inspect(operation_id))
            raise unsettled from None
        except Exception as error:
            raise OperationUnsettledError(await self.inspect(operation_id)) from error
        finally:
            if settlement.done() and self._settlement_tasks.get(operation_id) is settlement:
                del self._settlement_tasks[operation_id]

    @override
    async def submit_ephemeral_secret(
        self: SupervisorHost,
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

    @override
    async def _resolve_request_payload(
        self: SupervisorHost,
        snapshot: OperationPersistedSnapshot,
        definition: OperationDefinition,
    ) -> BaseModel:
        if snapshot.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE:
            if self._operands is None:
                raise ValueError("secure-reference request storage requires an operand store")
            # The store is a port: an executor relies on the exact registered
            # type, so a store that resolves any other type is refused here.
            payload = await self._operands.resolve(snapshot.request_reference, definition.request_type)
            self._validate_request_payload(payload, definition.request_type)
            return payload
        raw = snapshot.credential_free_request_json
        if raw is None:
            raise ValueError("credential-free operation request is absent")
        payload = self.registry.resolve_credential_free_payload(definition.definition_id, raw)
        if content_hash_hex(payload.model_dump(mode="json")) != snapshot.request_reference:
            raise ValueError("credential-free operation request digest does not match durable content")
        return payload

    @override
    async def _settle_pre_entry_secret_wait(
        self: SupervisorHost,
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

    async def settle_refused_start(
        self: SupervisorHost, operation_id: OperationId, refusal: ProfileAccessRefusedError
    ) -> OperationPersistedSnapshot:
        """Settle a frontend start refused before executor entry, releasing its subject.

        Continuation keeps a refused start CREATED so a later authorized continuation can
        run it; a frontend start has no such follow-up, and a CREATED record would hold the
        subject's lease and refuse every later submission for it.
        """
        snapshot = await self.inspect(operation_id)
        if snapshot.lifecycle is not OperationLifecycle.CREATED or snapshot.executor_entered_at is not None:
            raise ValueError("only an unstarted operation settles a refused start")
        return await self._settle_executor_failure(snapshot, refusal)

    @override
    async def _settle_executor_failure(
        self: SupervisorHost,
        snapshot: OperationPersistedSnapshot,
        error: Exception,
    ) -> OperationPersistedSnapshot:
        """Settle one stopped executor without persisting its exception surface.

        Registered ``REFUSED`` errors retain their registry code as the
        canonical operator reference. Every other exception receives a stable
        opaque correlation digest over safe lifecycle facts only; exception
        message text, arguments, contexts, tracebacks, paths, and URLs never
        enter operation persistence. The bounded public detail a frontend
        renders is kept apart, as an encrypted operand the receipt references.
        """
        registered = get_registered_error_code(error) if isinstance(error, CadrumoError) else None
        settled_at = self._clock()
        error_detail_ref = await _stored_error_detail(
            self.registry, snapshot.identity.definition_id, self._operands, error, written_at=settled_at
        )
        if registered is not None and registered.category is ErrorCategory.REFUSED:
            # Log only registered lifecycle facts; the exception may carry private operands.
            _log.warning(
                "operation refused definition=%s operation=%s code=%s",
                snapshot.identity.definition_id,
                snapshot.identity.operation_id,
                registered.code,
            )
            receipt = OperationTerminalReceipt(
                identity=snapshot.identity,
                revision=snapshot.revision + 1,
                condition=OperationTerminalCondition.REFUSED,
                effect=snapshot.effect,
                settled_at=settled_at,
                refusal_ref=registered.code,
                error_detail_ref=error_detail_ref,
            )
        else:
            diagnostic_ref = self._executor_failure_diagnostic_reference(snapshot, error)
            # The opaque reference correlates with the encrypted error detail.
            _log.error(
                "operation failed definition=%s operation=%s diagnostic_ref=%s exception_type=%s",
                snapshot.identity.definition_id,
                snapshot.identity.operation_id,
                diagnostic_ref,
                type(error).__name__,
            )
            receipt = OperationTerminalReceipt(
                identity=snapshot.identity,
                revision=snapshot.revision + 1,
                condition=OperationTerminalCondition.FAILED,
                effect=snapshot.effect,
                settled_at=settled_at,
                failure_error_code=None if registered is None else registered.code,
                diagnostic_ref=diagnostic_ref,
                error_detail_ref=error_detail_ref,
            )
        return await self.settle(snapshot.identity.operation_id, receipt)

    @override
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
        return prefixed_digest(
            canonical_json_bytes(
                {
                    "schema_version": 1,
                    "operation_id": snapshot.identity.operation_id,
                    "definition_id": snapshot.identity.definition_id,
                    "exception_type": f"{error_type.__module__}.{error_type.__qualname__}",
                    "terminal_revision": snapshot.revision + 1,
                }
            )
        )

    @override
    def _execution_deadline_for(self: SupervisorHost, deadline_capability: OperationDeadline) -> datetime | None:
        if deadline_capability is OperationDeadline.ABSENT:
            return None
        if self._execution_timeout is None:
            raise ValueError("deadline-capable operation requires a configured execution timeout")
        if self._cleanup_timeout is None:
            raise ValueError("deadline-capable operation requires a configured cleanup timeout")
        return self._clock() + self._execution_timeout

    @override
    async def _execute_with_deadlines(
        self: SupervisorHost,
        *,
        identity: OperationIdentity,
        context: DefinitionBoundContext,
        executor: Coroutine[None, None, OperationExecutorResult],
    ) -> OperationExecutorResult:
        """Await executor completion while aggregate and cleanup deadlines remain supervisor-owned."""
        entry = context.snapshot
        await self._request_expired_entry_cancellation(identity, entry)
        executor_task = asyncio.create_task(
            self._renew_while_executing(
                identity=identity,
                executor=_forwarding_operator_progress(context, executor),
            ),
            name=f"operation-supervision-{identity.operation_id}",
        )
        self._executor_tasks[identity.operation_id] = executor_task
        while not executor_task.done():
            snapshot = context.snapshot
            now = self._clock()
            if snapshot.cancellation_requested_at is None:
                completed = await self._watch_execution_deadline(identity, snapshot, executor_task, now)
            else:
                completed = await self._watch_cleanup_deadline(identity, context, snapshot, executor_task, now)
            if completed:
                break
        return await executor_task

    @override
    async def _request_expired_entry_cancellation(
        self: SupervisorHost,
        identity: OperationIdentity,
        entry: OperationPersistedSnapshot,
    ) -> None:
        if (
            entry.cancellation_requested_at is None
            and entry.execution_deadline is not None
            and self._clock() >= entry.execution_deadline
        ):
            # A continuation resumed after its deadline starts already cancelled,
            # so its first cooperative check observes the request instead of
            # racing the supervisor into an irreversible section.
            await self.request_cancel(identity.operation_id)

    @override
    async def _watch_execution_deadline(
        self: SupervisorHost,
        identity: OperationIdentity,
        snapshot: OperationPersistedSnapshot,
        executor_task: asyncio.Task[OperationExecutorResult],
        now: datetime,
    ) -> bool:
        execution_deadline = snapshot.execution_deadline
        if execution_deadline is None:
            await executor_task
            return True
        if now >= execution_deadline:
            observed_revision = (await self.inspect(identity.operation_id)).revision
            try:
                await self.request_cancel(identity.operation_id)
            except Exception:
                # An operator response may commit between the deadline's read and
                # its write. Only that moved revision is retried; other refusals stand.
                if (await self.inspect(identity.operation_id)).revision == observed_revision:
                    raise
            return False
        await self._wait_for_executor_or_deadline(executor_task, execution_deadline, now)
        return False

    @override
    async def _watch_cleanup_deadline(
        self: SupervisorHost,
        identity: OperationIdentity,
        context: DefinitionBoundContext,
        snapshot: OperationPersistedSnapshot,
        executor_task: asyncio.Task[OperationExecutorResult],
        now: datetime,
    ) -> bool:
        cleanup_deadline = snapshot.cleanup_deadline
        if cleanup_deadline is None:
            raise ValueError("durable cancellation request is missing its cleanup deadline")
        if now >= cleanup_deadline:
            context.cancellation.record_request(await self._escalate_cleanup_deadline(identity.operation_id))
            await executor_task
            return True
        await self._wait_for_executor_or_deadline(executor_task, cleanup_deadline, now)
        return False

    @override
    async def _settle_returned_result(
        self: SupervisorHost,
        snapshot: OperationPersistedSnapshot,
        result_ref: OperationExecutorResult,
    ) -> OperationPersistedSnapshot:
        """Join an executor's domain result to its settlement after it stops.

        ``snapshot`` is the executor's own last committed state. A ``None``
        return leaves the operation unsettled only when something else will
        settle it: the executor suspended at a pending interaction or external
        wait (whose response may already have been consumed), a cancellation
        request is in flight, or the operation already settled. An
        acknowledged cancellation settles as cancelled or timed out. Any other
        ``None`` is an executor contract breach that nothing could ever
        settle, so it settles as failed with a registered code.
        """
        if isinstance(result_ref, OperationRefusalEvidence):
            try:
                receipt = await await_cancellation_complete(
                    _validated_refusal_receipt(
                        registry=self.registry,
                        operands=self._operands,
                        snapshot=snapshot,
                        evidence=result_ref,
                        settled_at=self._clock(),
                    ),
                    task_name="operation-refusal-evidence",
                )
            except Exception as error:
                return await self._settle_executor_failure(snapshot, error)
            return await self.settle(snapshot.identity.operation_id, receipt)
        if result_ref is None:
            returned = await self.inspect(snapshot.identity.operation_id)
            if returned.cancellation_acknowledged_at is None:
                if _supervisor_snapshot.awaits_another_settler(snapshot) or _supervisor_snapshot.awaits_another_settler(
                    returned
                ):
                    return returned
                return await self._settle_executor_failure(returned, OperationExecutorReturnedNoResultError())
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

    @override
    async def await_terminal(self: SupervisorHost, operation_id: OperationId) -> OperationPersistedSnapshot:
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

    @override
    async def _advance(
        self: SupervisorHost,
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
        if lifecycle is OperationLifecycle.TERMINAL:
            raise InternalInvariantError("a terminal transition is committed only by settlement with its receipt")
        self._require_pinned_definition(snapshot)
        now = self._clock()
        async with self._lease_lock(snapshot.identity.operation_id):
            lease = await self._require_owned_lease_unlocked(snapshot.identity, now)
            revision = snapshot.revision + 1
            emitted = _supervisor_snapshot.advance_events(snapshot, events, revision, now)
            successor = _supervisor_snapshot.advanced_snapshot(
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

    @override
    async def respond(
        self: SupervisorHost,
        response: OperationApplyResponse | OperationRejectResponse,
    ) -> OperationConsumedInteraction:
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

    @override
    def _schedule_continuation(
        self: SupervisorHost,
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
