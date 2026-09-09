"""Lease-recovery and resumable-operation reconciliation stages."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, cast

from pydantic import BaseModel

from ...core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from . import supervisor_context as _supervisor_context
from ._execution_context import DefinitionBoundContext
from .errors import OperationDeclarationError
from .interactions import OperationConsumedInteraction, OperationPendingInteraction
from .models import OperationId, OperationReconciliationOutcome, OperationRequest, OperationTerminalReceipt
from .owner import OperationResumableExecutor
from .persistence.events import OperationReconciliationEvent
from .persistence.journal import OperationPersistedSnapshot
from .persistence.leases import (
    OperationLeaseDisposition,
    OperationLeaseObservation,
    OperationLeaseObservationDisposition,
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from .registry import OperationDefinition, OperationReconciliationPolicy
from .secret_submission import BoundEphemeralSecretAccess


class SupervisorHost(Protocol):
    if TYPE_CHECKING:

        def __getattr__(self, name: str) -> Any: ...


class SupervisorReconciliationMixin(SupervisorHost):
    """Own takeover, checkpoint validation, resume, and interruption paths."""

    async def reconcile(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Recover one startup entry only through its durable owner evidence."""
        snapshot = await self.inspect(operation_id)
        if snapshot.lifecycle is OperationLifecycle.TERMINAL:
            return snapshot
        definition = self._require_pinned_definition(snapshot)
        observed, now = await self._inspect_reconciliation_lease(operation_id, snapshot)
        if observed.disposition is OperationLeaseObservationDisposition.ACTIVE:
            raise ValueError("operation has active owner")
        if observed.disposition is OperationLeaseObservationDisposition.ABSENT:
            return await self._reconcile_absent_lease(operation_id, snapshot, now)
        if observed.disposition is not OperationLeaseObservationDisposition.EXPIRED or observed.current is None:
            raise ValueError("operation lease observation cannot establish startup reconciliation ownership")
        return await self._reconcile_expired_lease(operation_id, snapshot, definition, observed.current, now)

    async def _inspect_reconciliation_lease(
        self,
        operation_id: OperationId,
        snapshot: OperationPersistedSnapshot,
    ) -> tuple[OperationLeaseObservation, datetime]:
        """Observe the operation's conflict lease at one reconciliation instant."""
        scope_ref = operation_conflict_scope_reference(
            definition_id=snapshot.identity.definition_id,
            subject_ref=snapshot.identity.subject_ref,
        )
        now = self._clock()
        observed = await self._leases.inspect(scope_ref, operation_id, observed_at=now)
        return observed, now

    async def _reconcile_absent_lease(
        self,
        operation_id: OperationId,
        snapshot: OperationPersistedSnapshot,
        now: datetime,
    ) -> OperationPersistedSnapshot:
        """Classify a record whose owner lease disappeared before recovery."""
        acquired = await self._leases.acquire(self._candidate(snapshot.identity, now), observed_at=now)
        if acquired.disposition is not OperationLeaseDisposition.ACQUIRED or acquired.current is None:
            raise ValueError("operation orphan lease acquisition was refused")
        self._leases_by_operation[operation_id] = acquired.current
        effect = (
            OperationEffect.NONE
            if snapshot.secret_requirement is not None and snapshot.executor_entered_at is None
            else OperationEffect.UNKNOWN
        )
        return await self._interrupt_reconciliation(
            snapshot,
            outcome=OperationReconciliationOutcome.ORPHANED,
            lease_evidence_ref=acquired.evidence_ref,
            effect=effect,
        )

    async def _reconcile_expired_lease(
        self,
        operation_id: OperationId,
        snapshot: OperationPersistedSnapshot,
        definition: OperationDefinition,
        predecessor: OperationOwnerLease,
        now: datetime,
    ) -> OperationPersistedSnapshot:
        """Take over an expired lease and classify the durable operation state."""
        resume_checkpoint = self._resume_checkpoint_for_reconciliation(snapshot, definition)
        takeover = self._candidate(snapshot.identity, now)
        taken_over = await self._leases.compare_and_swap(predecessor, takeover, observed_at=now)
        if taken_over.disposition is not OperationLeaseDisposition.TAKEN_OVER or taken_over.current != takeover:
            raise ValueError("operation expired owner lease takeover was refused")
        self._leases_by_operation[operation_id] = takeover
        if predecessor.operation_id != operation_id:
            return await self._interrupt_reconciliation(
                snapshot,
                outcome=OperationReconciliationOutcome.ORPHANED,
                lease_evidence_ref=taken_over.evidence_ref,
            )
        return await self._reconcile_taken_over_operation(
            snapshot,
            definition,
            resume_checkpoint,
            lease_evidence_ref=taken_over.evidence_ref,
        )

    def _resume_checkpoint_for_reconciliation(
        self,
        snapshot: OperationPersistedSnapshot,
        definition: OperationDefinition,
    ) -> OperationPendingInteraction | OperationConsumedInteraction | None:
        """Select the latest valid durable checkpoint in its established priority order."""
        checkpoint = snapshot.pending_interaction
        continuation = snapshot.consumed_interactions[-1] if snapshot.consumed_interactions else None
        if definition.reconciliation_policy is not OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT:
            return None
        if checkpoint is not None and self._is_valid_resume_checkpoint(snapshot, checkpoint, definition):
            return checkpoint
        if continuation is not None and self._is_valid_resume_continuation(snapshot, continuation, definition):
            return continuation
        return None

    async def _reconcile_taken_over_operation(
        self,
        snapshot: OperationPersistedSnapshot,
        definition: OperationDefinition,
        resume_checkpoint: OperationPendingInteraction | OperationConsumedInteraction | None,
        *,
        lease_evidence_ref: str,
    ) -> OperationPersistedSnapshot:
        """Apply the lifecycle-specific recovery policy after durable takeover."""
        if snapshot.lifecycle is OperationLifecycle.CREATED:
            if snapshot.secret_requirement is not None and snapshot.executor_entered_at is None:
                return await self._interrupt_reconciliation(
                    snapshot,
                    outcome=OperationReconciliationOutcome.INTERRUPTED,
                    lease_evidence_ref=lease_evidence_ref,
                    effect=OperationEffect.NONE,
                )
            return await self._record_reconciliation(
                snapshot,
                outcome=OperationReconciliationOutcome.RECOVERED,
                lease_evidence_ref=lease_evidence_ref,
            )
        if resume_checkpoint is None:
            return await self._interrupt_reconciliation(
                snapshot,
                outcome=OperationReconciliationOutcome.INTERRUPTED,
                lease_evidence_ref=lease_evidence_ref,
            )
        resumed = await self._record_reconciliation(
            snapshot,
            outcome=OperationReconciliationOutcome.RESUMED,
            lease_evidence_ref=lease_evidence_ref,
        )
        return await self._resume_from_checkpoint(resumed, definition, resume_checkpoint)

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
        executor_context = _supervisor_context.SupervisorExecutorContext(
            context=context,
            operands=self._operands,
            ephemeral_secret=BoundEphemeralSecretAccess(
                requirement=snapshot.secret_requirement,
                broker=self._ephemeral_secrets,
                clock=self._clock,
            ),
            financial_operand=self._bound_financial_operand(snapshot.identity, definition),
            clock=self._clock,
            response_authority_issuer=self._response_authority_issuer,
            response_token_factory=self._response_token_factory,
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
            registry=self.registry,
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
