"""Application-owned baseline operation supervision."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, override

from pydantic import BaseModel

from ...core.async_cleanup import AsyncCloseable
from ...core.errors.hierarchy import InternalInvariantError
from ...core.hex import Hex64Str
from ...core.logging import get_logger
from ...core.operations import (
    OperationCancellation,
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)
from . import supervisor_context as _supervisor_context
from ._execution_context import DefinitionBoundContext
from ._supervisor_drain import SupervisorDrainMixin, require_positive_duration
from ._supervisor_execution import SupervisorExecutionMixin
from ._supervisor_lease import OperationSupervisorLeaseMixin
from ._supervisor_reconciliation import SupervisorReconciliationMixin
from ._supervisor_settlement import SupervisorSettlementMixin
from ._supervisor_submission import SupervisorSubmissionMixin
from .authorization import OperationExecutionAuthority
from .event_replay import OperationEventCursor
from .financial_operand_contract import (
    CredentialFreeFinancialOperationRequest,
    OperationFinancialOperandRefusalCode,
    OperationFinancialOperandRefusedError,
    OperationTransientFinancialOperandRequirementV1,
)
from .interactions import (
    OperationApplyResponse,
    OperationConsumedInteraction,
    OperationRejectResponse,
)
from .models import (
    OperationId,
    OperationRequest,
    OperationStoredInvocation,
    OperationTerminalReceipt,
    new_operation_id,
)
from .operation_definition import OperationDefinition
from .persistence.events import (
    OperationNoticeEvent,
)
from .persistence.financial_operand_custody import (
    OperationTypedFinancialOperandCustodyRepository,
)
from .persistence.journal import (
    OperationEventStream,
    OperationJournal,
    OperationLeaseRepository,
    OperationPersistedSnapshot,
    OperationSecureReferenceStore,
)
from .persistence.leases import (
    OperationLeaseObservationDisposition,
    OperationLeaseToken,
    OperationOwnerLease,
)
from .persistence.replay import (
    OperationReplayLimit,
    OperationReplayPage,
)
from .projection_services import OperationResponseAuthorityIssuer
from .provenance import OperationAdmissionProvenance
from .registry import OperationRegistry
from .secret_submission import (
    EphemeralSecretBroker,
    OperationSecretRequirement,
    zeroize_secret_buffer,
)
from .typed_financial_operand_submission import OperationTypedFinancialOperandBroker

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from .refusal_evidence import OperationExecutorResult

_log = get_logger(__name__)


def _validate_supervisor_configuration(
    registry: OperationRegistry,
    lease_duration: timedelta,
    execution_timeout: timedelta | None,
    cleanup_timeout: timedelta | None,
) -> None:
    if lease_duration <= timedelta():
        raise ValueError("operation lease duration must be positive")
    require_positive_duration("operation execution timeout", execution_timeout)
    require_positive_duration("operation cleanup timeout", cleanup_timeout)
    for definition in registry.definitions:
        declaration = definition.ephemeral_secret
        if declaration is not None and declaration.lifetime >= lease_duration:
            raise ValueError("ephemeral secret lifetime must be shorter than the owner lease")


class OperationSupervisor(
    SupervisorDrainMixin,
    SupervisorSubmissionMixin,
    SupervisorExecutionMixin,
    SupervisorSettlementMixin,
    SupervisorReconciliationMixin,
    OperationSupervisorLeaseMixin,
):
    """Coordinate durable execution, interactions, recovery, and settlement."""

    def __init__(
        self,
        *,
        registry: OperationRegistry,
        authority_operation: PinnedAuthorityOperation,
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
        response_authority_issuer: OperationResponseAuthorityIssuer | None = None,
        response_token_factory: Callable[[], str] = _supervisor_context.new_response_token,
        execution_authority: OperationExecutionAuthority | None = None,
        typed_financial_operand_custody: OperationTypedFinancialOperandCustodyRepository | None = None,
    ) -> None:
        """Bind the registry and durable ports for one process owner."""
        self.registry = registry
        self._execution_authority = execution_authority
        self._authority_operation = authority_operation
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
        self._response_authority_issuer = response_authority_issuer
        self._response_token_factory = response_token_factory
        self._leases_by_operation: dict[OperationId, OperationOwnerLease] = {}
        self._lease_locks: dict[OperationId, asyncio.Lock] = {}
        self._resources: dict[OperationId, list[AsyncCloseable]] = {}
        self._contexts: dict[OperationId, DefinitionBoundContext] = {}
        self._executor_tasks: dict[OperationId, asyncio.Task[OperationExecutorResult]] = {}
        self._cleanup_tasks: dict[OperationId, asyncio.Task[None]] = {}
        self._continuation_tasks: dict[OperationId, asyncio.Task[OperationPersistedSnapshot]] = {}
        self._settlement_tasks: dict[OperationId, asyncio.Task[OperationPersistedSnapshot]] = {}
        self._accepting_admissions = True
        self._admissions: dict[asyncio.Task[object], OperationId] = {}
        self._drain_tasks: dict[OperationId, set[asyncio.Task[object]]] = {}
        self._drain_close_tasks: dict[OperationId, asyncio.Task[None]] = {}
        self._drain_settlements: dict[OperationId, asyncio.Task[OperationPersistedSnapshot]] = {}
        self._durable_change_events: dict[OperationId, asyncio.Event] = {}
        self._durable_revisions: dict[OperationId, int] = {}
        self._ephemeral_secrets = EphemeralSecretBroker()
        self._typed_financial_operands = (
            None
            if typed_financial_operand_custody is None
            else OperationTypedFinancialOperandBroker(
                custody=typed_financial_operand_custody,
                clock=clock,
                lock_for=self._lease_lock,
                require_current=self._require_current_financial_binding,
                settle_expiry=self._settle_pre_entry_financial_expiry,
            )
        )
        if self._typed_financial_operands is None and any(
            definition.transient_financial_operand is not None for definition in registry.definitions
        ):
            raise ValueError("typed financial operations require hardened durable custody")
        _validate_supervisor_configuration(
            registry,
            lease_duration,
            execution_timeout,
            cleanup_timeout,
        )

    @override
    async def _acknowledge_cancellation(
        self,
        context_snapshot: OperationPersistedSnapshot,
    ) -> OperationPersistedSnapshot:
        return await SupervisorSettlementMixin._acknowledge_cancellation(self, context_snapshot)

    @override
    async def _set_cancellation_deferred(
        self,
        context_snapshot: OperationPersistedSnapshot,
        deferred: bool,
    ) -> OperationPersistedSnapshot:
        return await SupervisorSettlementMixin._set_cancellation_deferred(self, context_snapshot, deferred)

    @override
    @staticmethod
    def _validate_request_payload(payload: BaseModel, request_type: type[BaseModel]) -> None:
        """Require exactly the registered request model at admission and at restore.

        A subclass is refused: it may carry fields or validation the definition
        was never registered for, and durable restore hydrates only the
        registered type, so admitting it would change the operand's type
        between submission and execution.
        """
        if type(payload) is not request_type:
            raise ValueError("request payload does not match definition")

    @override
    async def _settle_financial_operand_custody(self, operation_id: OperationId) -> None:
        """Require delivery custody to finish before any terminal receipt is committed."""
        if self._typed_financial_operands is not None:
            await self._typed_financial_operands.settle_operation(operation_id)

    def in_flight_operation_count(self) -> int:
        """Observe distinct admitted operations until all local settlement completes.

        Called on the owning event loop without yielding. Pending admissions,
        durable leases and unfinished executor/cleanup/settlement tasks overlap;
        an operation contributes once. Observation does not renew any lease.
        """
        identifiers = set(self._leases_by_operation)
        identifiers.update(operation_id for task, operation_id in self._admissions.items() if not task.done())
        for mapping in (self._executor_tasks, self._cleanup_tasks, self._continuation_tasks, self._settlement_tasks):
            identifiers.update(operation_id for operation_id, task in mapping.items() if not task.done())
        identifiers.update(
            operation_id for operation_id, tasks in self._drain_tasks.items() if any(not task.done() for task in tasks)
        )
        return len(identifiers)

    async def bind_typed_financial_operand(self, operation_id: OperationId, operand: BaseModel) -> None:
        """Transfer a complete batch only after its amount-free invocation was admitted."""
        if not self._accepting_admissions:
            raise OperationFinancialOperandRefusedError(OperationFinancialOperandRefusalCode.OWNER_LOST)

        async def transfer(batch: BaseModel) -> None:
            try:
                broker = self._typed_financial_operands
                if broker is None:
                    raise OperationFinancialOperandRefusedError(
                        OperationFinancialOperandRefusalCode.UNKNOWN_REQUIREMENT
                    )
                snapshot = await self.inspect(operation_id)
                definition = self._require_pinned_definition(snapshot)
                declaration = definition.transient_financial_operand
                if declaration is None or type(batch) is not declaration.operand_type:
                    raise OperationFinancialOperandRefusedError(OperationFinancialOperandRefusalCode.WRONG_MODEL)
                baseline = declaration.baseline_accessor(batch)
                if type(baseline) is not declaration.baseline_type:
                    raise OperationFinancialOperandRefusedError(OperationFinancialOperandRefusalCode.WRONG_BASELINE)
                submission = await broker.open(
                    declaration=declaration,
                    identity=snapshot.identity,
                    revision=snapshot.revision + 1,
                    domain_baseline_ref=declaration.baseline_reference(baseline),
                    bind_requirement=self._attach_financial_requirement,
                )
                try:
                    submission.operand = batch
                    await broker.submit(submission)
                finally:
                    submission.release()
            finally:
                del batch

        try:
            await self._admit(operation_id, partial(transfer, operand))
        finally:
            del operand

    async def refuse_unstarted_financial_input(self, operation_id: OperationId) -> None:
        """Release an admitted batch and settle a failed intake with no executor or domain effect."""
        snapshot = await self.inspect(operation_id)
        definition = self._require_pinned_definition(snapshot)
        if (
            definition.transient_financial_operand is None
            or snapshot.executor_entered_at is not None
            or snapshot.lifecycle is not OperationLifecycle.CREATED
        ):
            raise OperationFinancialOperandRefusedError(OperationFinancialOperandRefusalCode.STALE_REVISION)
        await self._settle_financial_operand_custody(operation_id)
        await self.settle(
            operation_id,
            OperationTerminalReceipt(
                identity=snapshot.identity,
                revision=snapshot.revision + 1,
                condition=OperationTerminalCondition.REFUSED,
                effect=OperationEffect.NONE,
                settled_at=self._clock(),
                refusal_ref="REFUSED_OPERATION_FINANCIAL_OPERAND",
            ),
        )

    async def _attach_financial_requirement(self, requirement: OperationTransientFinancialOperandRequirementV1) -> None:
        """Coherently attach only safe coordinates while the broker owns the operation lock."""
        snapshot = await self.inspect(requirement.identity.operation_id)
        if snapshot.lifecycle is not OperationLifecycle.CREATED or snapshot.financial_requirement is not None:
            raise OperationFinancialOperandRefusedError(OperationFinancialOperandRefusalCode.DUPLICATE_SUBMISSION)
        if snapshot.revision + 1 != requirement.invocation_revision:
            raise OperationFinancialOperandRefusedError(OperationFinancialOperandRefusalCode.STALE_REVISION)
        definition = self._require_pinned_definition(snapshot)
        payload = await self._resolve_request_payload(snapshot, definition)
        if not isinstance(payload, CredentialFreeFinancialOperationRequest) or (
            payload.financial_baseline_ref != requirement.domain_baseline_ref
        ):
            raise OperationFinancialOperandRefusedError(OperationFinancialOperandRefusalCode.WRONG_BASELINE)
        now = self._clock()
        lease = await self._require_owned_lease_unlocked(snapshot.identity, now)
        successor = snapshot.model_copy(
            update={
                "financial_requirement": requirement,
                "revision": requirement.invocation_revision,
                "updated_at": now,
                "event_cursor": snapshot.event_cursor + 1,
                "events": (
                    OperationNoticeEvent(
                        identity=snapshot.identity,
                        revision=requirement.invocation_revision,
                        sequence=snapshot.event_cursor + 1,
                        timestamp=now,
                        code="operation.financial_operand.awaiting",
                        notice_code="operation.financial_operand.awaiting",
                    ),
                ),
            }
        )
        await self._journal.commit(successor, expected_revision=snapshot.revision, lease=lease)
        self._notify_durable_change(successor)

    async def _require_current_financial_binding(
        self, requirement: OperationTransientFinancialOperandRequirementV1
    ) -> None:
        """Verify immutable invocation, model, baseline and owner coordinates under the operation lock."""
        snapshot = await self.inspect(requirement.identity.operation_id)
        if snapshot.lifecycle is OperationLifecycle.TERMINAL:
            raise OperationFinancialOperandRefusedError(OperationFinancialOperandRefusalCode.TERMINAL_OPERATION)
        if snapshot.identity != requirement.identity or snapshot.financial_requirement != requirement:
            raise OperationFinancialOperandRefusedError(OperationFinancialOperandRefusalCode.STALE_REVISION)
        declaration = self._require_pinned_definition(snapshot).transient_financial_operand
        if declaration is None or (
            declaration.operand_schema != requirement.operand_schema
            or declaration.baseline_schema != requirement.baseline_schema
        ):
            raise OperationFinancialOperandRefusedError(OperationFinancialOperandRefusalCode.WRONG_MODEL)
        await self._require_owned_lease_unlocked(snapshot.identity, self._clock())

    async def _settle_pre_entry_financial_expiry(
        self, requirement: OperationTransientFinancialOperandRequirementV1
    ) -> None:
        """Settle an unconsumed expired handoff without claiming a domain effect."""
        snapshot = await self.inspect(requirement.identity.operation_id)
        if snapshot.lifecycle is OperationLifecycle.TERMINAL or snapshot.executor_entered_at is not None:
            return
        await self.settle(
            snapshot.identity.operation_id,
            OperationTerminalReceipt(
                identity=snapshot.identity,
                revision=snapshot.revision + 1,
                condition=OperationTerminalCondition.INTERRUPTED,
                effect=OperationEffect.NONE,
                settled_at=self._clock(),
            ),
        )

    async def _admit[T](self, operation_id: OperationId, action: Callable[[], Awaitable[T]]) -> T:
        if not self._accepting_admissions:
            raise ValueError("operation owner is draining")
        task = asyncio.current_task()
        if task is None:
            raise InternalInvariantError("operation admission requires an asyncio task")
        previous = self._admissions.get(task)
        self._admissions[task] = operation_id
        try:
            return await action()
        finally:
            if previous is None:
                self._admissions.pop(task, None)
            else:
                self._admissions[task] = previous

    @override
    async def submit[RequestPayloadT: BaseModel](
        self,
        request: OperationRequest[RequestPayloadT],
        *,
        operation_id: OperationId | None = None,
        provenance: OperationAdmissionProvenance | None = None,
    ) -> OperationId:
        proposed_id = operation_id or new_operation_id()
        return await self._admit(
            proposed_id,
            lambda: SupervisorSubmissionMixin.submit(self, request, operation_id=proposed_id, provenance=provenance),
        )

    @override
    async def start(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        return await self._admit(operation_id, lambda: SupervisorExecutionMixin.start(self, operation_id))

    @override
    async def respond(self, response: OperationApplyResponse | OperationRejectResponse) -> OperationConsumedInteraction:
        return await self._admit(response.operation_id, lambda: SupervisorExecutionMixin.respond(self, response))

    @override
    def _schedule_continuation(
        self,
        snapshot: OperationPersistedSnapshot,
        definition: OperationDefinition,
        continuation: OperationConsumedInteraction,
    ) -> None:
        if not self._accepting_admissions:
            raise ValueError("operation owner is draining")
        SupervisorExecutionMixin._schedule_continuation(self, snapshot, definition, continuation)

    @override
    async def submit_ephemeral_secret(self, requirement: OperationSecretRequirement, secret: bytearray) -> None:
        try:
            await self._admit(
                requirement.identity.operation_id,
                lambda: SupervisorExecutionMixin.submit_ephemeral_secret(self, requirement, secret),
            )
        except BaseException:
            zeroize_secret_buffer(secret)
            raise

    async def require_ephemeral_secret_ready(self, requirement: OperationSecretRequirement) -> None:
        """Inspect the canonical wait without accepting or reserving any secret.

        Delivery still rechecks lifecycle and single-use custody atomically;
        this inspection grants no permission to a later delivery.
        """

        async def inspect_ready() -> None:
            async with self._lease_lock(requirement.identity.operation_id):
                snapshot = await self.inspect(requirement.identity.operation_id)
                if snapshot.secret_requirement != requirement:
                    raise ValueError("ephemeral secret submission does not match the durable requirement")
                if snapshot.lifecycle is not OperationLifecycle.CREATED or snapshot.executor_entered_at is not None:
                    raise ValueError("ephemeral secret requirement is no longer awaiting submission")
                self._ephemeral_secrets.require_ready(requirement, observed_at=self._clock())

        await self._admit(requirement.identity.operation_id, inspect_ready)

    @override
    def _require_cleanup_timeout(self, cancellation: OperationCancellation) -> None:
        if cancellation is not OperationCancellation.UNSUPPORTED and self._cleanup_timeout is None:
            raise ValueError("cancellable operation requires a configured cleanup timeout")

    @override
    @staticmethod
    def _acknowledged_cancellation_condition(snapshot: OperationPersistedSnapshot) -> OperationTerminalCondition:
        """Derive the sole terminal fact a cooperatively stopped executor permits."""
        requested_at = snapshot.cancellation_requested_at
        if requested_at is None or snapshot.cancellation_acknowledged_at is None:
            raise ValueError("automatic cancellation settlement requires durable request and acknowledgement")
        if snapshot.execution_deadline is not None and requested_at >= snapshot.execution_deadline:
            return OperationTerminalCondition.TIMED_OUT
        return OperationTerminalCondition.CANCELLED

    @override
    @staticmethod
    async def _wait_for_executor_or_deadline(
        executor_task: asyncio.Task[object],
        deadline: datetime,
        now: datetime,
    ) -> None:
        """Yield until a real task ends or the supervisor-owned UTC deadline arrives."""
        remaining_seconds = max((deadline - now).total_seconds(), 0.0)
        await asyncio.wait((executor_task,), timeout=remaining_seconds)

    @override
    async def inspect(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Load the authoritative current snapshot for one operation."""
        return await self._load_pinned_snapshot(operation_id)

    async def observe(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Return the latest durable operation observation."""
        return await self.inspect(operation_id)

    async def stored_invocation(
        self, operation_id: OperationId, *, require_idle: bool = False
    ) -> OperationStoredInvocation:
        """Resolve a host invocation only while private admission remains open."""
        return await self._admit(
            operation_id,
            lambda: self._stored_invocation(operation_id, require_idle=require_idle),
        )

    async def _stored_invocation(
        self, operation_id: OperationId, *, require_idle: bool = False
    ) -> OperationStoredInvocation:
        """Resolve exact pinned operands for the authenticated host's policy owner.

        This internal door grants neither execution nor disclosure. The host
        must check current authority before using or projecting the invocation.
        Response capabilities cannot be recovered through it.
        """
        snapshot = await self.inspect(operation_id)
        if require_idle:
            self._require_idle_invocation(operation_id)
        payload = await self._resolve_request_payload(snapshot, self._require_pinned_definition(snapshot))
        request = OperationRequest(
            definition_id=snapshot.identity.definition_id,
            subject_ref=snapshot.identity.subject_ref,
            payload=payload,
        )
        provenance = None
        if snapshot.admission_provenance_reference is not None:
            if self._operands is None:
                raise ValueError("operation admission provenance requires its encrypted operand store")
            provenance = await self._operands.resolve(
                snapshot.admission_provenance_reference, OperationAdmissionProvenance
            )
            provenance.require_invocation(snapshot.identity, request)
        return OperationStoredInvocation(
            identity=snapshot.identity,
            request=request,
            lifecycle=snapshot.lifecycle,
            provenance=provenance,
        )

    def _require_idle_invocation(self, operation_id: OperationId) -> None:
        tasks = (
            self._executor_tasks.get(operation_id),
            self._settlement_tasks.get(operation_id),
            self._continuation_tasks.get(operation_id),
            self._cleanup_tasks.get(operation_id),
        )
        if any(task is not None and not task.done() for task in tasks):
            raise ValueError("operation still has live local execution or settlement")

    async def continue_operation(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Admit a freshly authorized continuation while this owner is active."""
        return await self._admit(operation_id, lambda: self._continue_operation(operation_id))

    @override
    async def reconcile(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Allow direct recovery only while this owner accepts private work."""
        return await self._admit(operation_id, lambda: SupervisorReconciliationMixin.reconcile(self, operation_id))

    async def _continue_operation(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Continue admitted intent through canonical lease recovery, never blind replay.

        A newly authorized host binding is required when execution authority is
        configured. A current local execution cannot be retargeted. Recorded
        interrupted work is reconciled; only declared resumable checkpoints can
        re-enter an executor.
        """
        snapshot = await self.inspect(operation_id)
        self._require_idle_invocation(operation_id)
        if snapshot.lifecycle is OperationLifecycle.TERMINAL:
            return snapshot
        observed, instant = await self._inspect_reconciliation_lease(operation_id, snapshot)
        if observed.disposition is OperationLeaseObservationDisposition.ACTIVE:
            # Exact owner/token verification; another live owner remains busy.
            await self._require_owned_lease(snapshot.identity, instant)
            if snapshot.lifecycle is not OperationLifecycle.CREATED:
                raise ValueError("owned nonterminal invocation requires its original continuation")
        else:
            snapshot = await self.reconcile(operation_id)
        if snapshot.lifecycle is OperationLifecycle.CREATED:
            return await self.start(operation_id)
        return snapshot

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
        """Release a frontend without mutating the durable operation."""
        return await self.inspect(operation_id)

    @override
    def _settlement_completed(self, task: asyncio.Task[OperationPersistedSnapshot]) -> None:
        """Retrieve a finished task's failure so it is logged once rather than orphaned.

        A failure leaves the journal as it was and the lease to expire, so owner
        recovery settles the operation; :meth:`settled` reports the same state.
        """
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            _log.error("supervised operation task stopped without settlement: %s", task.get_name(), exc_info=error)

    @override
    def _continuation_completed(self, task: asyncio.Task[OperationPersistedSnapshot]) -> None:
        """Observe scheduled completion so task failures are never orphaned by asyncio."""
        if task.cancelled():
            return
        task.exception()

    async def reject(self, response: OperationRejectResponse) -> OperationConsumedInteraction:
        """Consume a rejected REVIEW response through the shared response transition."""
        return await self.respond(response)

    @override
    async def _cancel_pre_entry_secret(
        self,
        snapshot: OperationPersistedSnapshot,
    ) -> OperationPersistedSnapshot | None:
        """Acknowledge and settle a cancellation before executor entry."""
        if snapshot.secret_requirement is None or snapshot.executor_entered_at is not None:
            return None
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


__all__ = ["OperationSupervisor"]
