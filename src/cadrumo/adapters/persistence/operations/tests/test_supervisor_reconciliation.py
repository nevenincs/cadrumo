"""Real durable-operation proofs exercised through :class:`OperationSupervisor`."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.errors import RepositoryError
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_runtime_profile,
)
from cadrumo.application.operations.capabilities import (
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
)
from cadrumo.application.operations.interactions import (
    OperationApplyResponse,
    OperationConsumedInteraction,
)
from cadrumo.application.operations.models import (
    OperationIdentity,
    OperationReconciliationOutcome,
)
from cadrumo.application.operations.persistence.events import (
    OperationReconciliationEvent,
)
from cadrumo.application.operations.persistence.journal import (
    OperationPersistedSnapshot,
)
from cadrumo.application.operations.persistence.leases import (
    OperationLeaseDisposition,
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from cadrumo.application.operations.registry import (
    OperationReconciliationPolicy,
)
from cadrumo.core.operations import (
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
)

from .supervision_support import run_to_settlement
from .supervisor_test_support import (
    _BASELINE_DIGEST,
    _NOW,
    _PROPOSED_EFFECT_DIGEST,
    _RESPONSE_TOKEN,
    DurableContinuationExecutor,
    IdleExecutor,
    ResumableIdleExecutor,
    ResumableReviewExecutor,
    ReviewedOperand,
    WaitingExecutor,
    _capabilities,
    _close_host_over_live_executor,
    _registry,
    _repositories,
    _request,
    _response,
    _supervisor,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def test_reconcile_takes_over_expired_owner_settles_and_releases_scope(tmp_path: Path) -> None:
    """A new owner with no local task admits genuine owner-loss interruption and frees the scope."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        started = asyncio.Event()
        executor = WaitingExecutor(started=started, release=asyncio.Event())
        registry = _registry(
            executor_type=WaitingExecutor,
            build=lambda: executor,
            capabilities=_capabilities(permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})),
        )
        owner = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            lease_duration=timedelta(minutes=1),
        )
        operation_id = asyncio.run(owner.submit(_request(subject_ref="subject:shared"), operation_id="3" * 64))
        abandoned = asyncio.run(_close_host_over_live_executor(owner, operation_id, started))
        assert abandoned.lifecycle is OperationLifecycle.RUNNING
        recovered_at = _NOW + timedelta(minutes=2)
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: recovered_at,
        )

        assert operation_id not in recovery._executor_tasks
        terminal = asyncio.run(recovery.reconcile(operation_id))
        released = asyncio.run(
            leases.inspect(
                operation_conflict_scope_reference(
                    definition_id=terminal.identity.definition_id,
                    subject_ref=terminal.identity.subject_ref,
                ),
                terminal.identity.operation_id,
                observed_at=recovered_at,
            )
        )
        replacement = asyncio.run(recovery.submit(_request(subject_ref="subject:shared"), operation_id="6" * 64))

        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert terminal.terminal_condition is OperationTerminalCondition.INTERRUPTED
        assert terminal.effect is OperationEffect.UNKNOWN
        replayed = asyncio.run(journal.read_after(operation_id, 0, limit=20))
        outcomes = tuple(event.outcome for event in replayed.events if isinstance(event, OperationReconciliationEvent))
        assert outcomes == (OperationReconciliationOutcome.INTERRUPTED,)
        assert released.current is None
        assert replacement == "6" * 64


def test_a_submission_recovers_a_started_holder_whose_owner_lapsed(tmp_path: Path) -> None:
    """A runtime that died mid-run must not hold its subject until someone reconciles by hand."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        started = asyncio.Event()
        executor = WaitingExecutor(started=started, release=asyncio.Event())
        registry = _registry(
            executor_type=WaitingExecutor,
            build=lambda: executor,
            capabilities=_capabilities(permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})),
        )
        owner = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            lease_duration=timedelta(minutes=1),
        )
        operation_id = asyncio.run(owner.submit(_request(subject_ref="subject:shared"), operation_id="3" * 64))
        abandoned = asyncio.run(_close_host_over_live_executor(owner, operation_id, started))
        assert abandoned.lifecycle is OperationLifecycle.RUNNING
        recovered_at = _NOW + timedelta(minutes=2)
        successor = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: recovered_at,
        )

        replacement = asyncio.run(successor.submit(_request(subject_ref="subject:shared"), operation_id="6" * 64))

        assert replacement == "6" * 64
        recovered = asyncio.run(journal.load(operation_id))
        assert recovered.lifecycle is OperationLifecycle.TERMINAL
        assert recovered.terminal_condition is OperationTerminalCondition.INTERRUPTED
        assert recovered.effect is OperationEffect.UNKNOWN


def test_reconcile_foreign_expired_lease_orphans_target_without_mutating_foreign_journal(tmp_path: Path) -> None:
    """A target owns only its acquired takeover; the foreign operation record is untouched."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        registry = _registry(executor_type=IdleExecutor, build=IdleExecutor)
        owner = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            lease_duration=timedelta(minutes=1),
        )
        target_id = asyncio.run(owner.submit(_request(subject_ref="subject:shared"), operation_id="3" * 64))
        target = asyncio.run(journal.load(target_id))
        scope_ref = operation_conflict_scope_reference(
            definition_id=target.identity.definition_id,
            subject_ref=target.identity.subject_ref,
        )
        target_lease = asyncio.run(leases.inspect(scope_ref, target_id, observed_at=_NOW)).current
        assert target_lease is not None
        foreign_at = _NOW + timedelta(minutes=2)
        foreign_lease = OperationOwnerLease(
            operation_id="6" * 64,
            scope_ref=scope_ref,
            owner_id="7" * 64,
            token="8" * 64,
            acquired_at=foreign_at,
            expires_at=foreign_at + timedelta(minutes=1),
        )
        assert (
            asyncio.run(leases.compare_and_swap(target_lease, foreign_lease, observed_at=foreign_at)).disposition
            is OperationLeaseDisposition.TAKEN_OVER
        )
        foreign_snapshot = OperationPersistedSnapshot(
            identity=OperationIdentity(
                operation_id=foreign_lease.operation_id,
                definition_id=target.identity.definition_id,
                subject_ref=target.identity.subject_ref,
            ),
            definition_contract_digest=target.definition_contract_digest,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            request_reference=target.request_reference,
            revision=0,
            lifecycle=OperationLifecycle.CREATED,
            started_at=foreign_at,
            updated_at=foreign_at,
            execution_deadline=None,
            cleanup_deadline=None,
            cancellation_requested_at=None,
            cancellation_acknowledged_at=None,
            cancellation_deferred=False,
        )
        asyncio.run(journal.create(foreign_snapshot, lease=foreign_lease))
        foreign_path = storage_root / "operation-journals" / f"{foreign_lease.operation_id}.json"
        foreign_before = foreign_path.read_bytes()
        recovered_at = foreign_at + timedelta(minutes=2)
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: recovered_at,
        )

        terminal = asyncio.run(recovery.reconcile(target_id))
        released = asyncio.run(leases.inspect(scope_ref, target_id, observed_at=recovered_at))
        replayed = asyncio.run(journal.read_after(target_id, 0, limit=20))

    assert terminal.terminal_condition is OperationTerminalCondition.INTERRUPTED
    assert terminal.effect is OperationEffect.UNKNOWN
    assert tuple(event.outcome for event in replayed.events if isinstance(event, OperationReconciliationEvent)) == (
        OperationReconciliationOutcome.ORPHANED,
    )
    assert foreign_path.read_bytes() == foreign_before
    assert asyncio.run(journal.load(foreign_lease.operation_id)) == foreign_snapshot
    assert released.current is None


def test_reconcile_recovers_an_unstarted_expired_entry_with_new_durable_ownership(tmp_path: Path) -> None:
    """A separate startup supervisor re-establishes only a provably effect-free created entry."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        started = asyncio.Event()
        executor = WaitingExecutor(started=started, release=asyncio.Event())
        registry = _registry(executor_type=WaitingExecutor, build=lambda: executor)
        owner = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            lease_duration=timedelta(minutes=1),
        )
        operation_id = asyncio.run(owner.submit(_request(), operation_id="3" * 64))
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: _NOW + timedelta(minutes=2),
        )

        recovered = asyncio.run(recovery.reconcile(operation_id))
        restarted = asyncio.run(_close_host_over_live_executor(recovery, operation_id, started))

    assert recovered.lifecycle is OperationLifecycle.CREATED
    assert isinstance(recovered.events[0], OperationReconciliationEvent)
    assert recovered.events[0].outcome is OperationReconciliationOutcome.RECOVERED
    assert len(recovered.events[0].lease_evidence_ref) == 64
    assert restarted.lifecycle is OperationLifecycle.RUNNING


def test_reconcile_reenters_only_a_declared_valid_checkpoint(tmp_path: Path) -> None:
    """A resumable definition resumes its actual executor, not merely its old snapshot."""
    executors: list[ResumableReviewExecutor] = []
    resume_entered = asyncio.Event()
    release_resume = asyncio.Event()

    def build() -> ResumableReviewExecutor:
        executor = ResumableReviewExecutor(
            result_ref="result:reentered-checkpoint",
            resume_entered=resume_entered,
            release_resume=release_resume,
        )
        executors.append(executor)
        return executor

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        registry = _registry(
            executor_type=ResumableReviewExecutor,
            build=build,
            capabilities=_capabilities(
                durability=OperationDurability.RESUMABLE,
                replay=OperationReplayPolicy.RESUMABLE,
            ),
            interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
            reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
        )
        owner = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            lease_duration=timedelta(minutes=1),
        )
        operation_id = asyncio.run(owner.submit(_request(), operation_id="3" * 64))
        waiting = asyncio.run(run_to_settlement(owner, operation_id))
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: _NOW + timedelta(minutes=2),
        )

        async def observe_live_resume() -> tuple[OperationPersistedSnapshot, OperationPersistedSnapshot]:
            reconciliation = asyncio.create_task(recovery.reconcile(operation_id))
            await resume_entered.wait()
            live = await journal.load(operation_id)
            release_resume.set()
            return live, await reconciliation

        resumed, settled = asyncio.run(observe_live_resume())
        replayed = asyncio.run(journal.read_after(operation_id, 0, limit=20))

    assert waiting.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
    assert len(executors) == 2
    assert executors[1].resume_checkpoints == [waiting.pending_interaction]
    assert resumed.lifecycle is OperationLifecycle.RUNNING
    assert resumed.pending_interaction is None
    assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert tuple(event.outcome for event in replayed.events if isinstance(event, OperationReconciliationEvent)) == (
        OperationReconciliationOutcome.RESUMED,
    )


def test_resumed_executor_result_reference_settles_the_recovered_operation(tmp_path: Path) -> None:
    """A resumed executor's domain reference follows the same terminal join as start."""
    executors: list[ResumableReviewExecutor] = []
    result_ref = "result:resumed-operation"

    def build() -> ResumableReviewExecutor:
        executor = ResumableReviewExecutor(result_ref=result_ref if executors else None)
        executors.append(executor)
        return executor

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "resumed-result-state",
            profile_objects=profile.repository,
        )
        registry = _registry(
            executor_type=ResumableReviewExecutor,
            build=build,
            capabilities=_capabilities(
                durability=OperationDurability.RESUMABLE,
                replay=OperationReplayPolicy.RESUMABLE,
            ),
            interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
            reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
        )
        owner = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            lease_duration=timedelta(minutes=1),
        )
        operation_id = asyncio.run(owner.submit(_request(), operation_id="3" * 64))
        waiting = asyncio.run(run_to_settlement(owner, operation_id))
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: _NOW + timedelta(minutes=2),
        )

        terminal = asyncio.run(recovery.reconcile(operation_id))
        reloaded = asyncio.run(journal.load(operation_id))

    assert waiting.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
    assert len(executors) == 2
    assert terminal.lifecycle is OperationLifecycle.TERMINAL
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.terminal_receipt is not None
    assert terminal.terminal_receipt.result_ref == result_ref
    assert reloaded == terminal


def test_reconcile_refuses_changed_definition_digest_before_reentry(tmp_path: Path) -> None:
    """A checkpoint valid for the old registry cannot enter a changed definition."""
    executors: list[ResumableReviewExecutor] = []

    def build() -> ResumableReviewExecutor:
        executor = ResumableReviewExecutor()
        executors.append(executor)
        return executor

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        owner_registry = _registry(
            executor_type=ResumableReviewExecutor,
            build=build,
            capabilities=_capabilities(
                durability=OperationDurability.RESUMABLE,
                replay=OperationReplayPolicy.RESUMABLE,
            ),
            interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
            reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
        )
        owner = _supervisor(
            registry=owner_registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            lease_duration=timedelta(minutes=1),
        )
        operation_id = asyncio.run(owner.submit(_request(), operation_id="3" * 64))
        waiting = asyncio.run(run_to_settlement(owner, operation_id))
        changed_registry = _registry(
            executor_type=ResumableReviewExecutor,
            build=build,
            capabilities=_capabilities(
                durability=OperationDurability.RESUMABLE,
                replay=OperationReplayPolicy.RESUMABLE,
            ),
            interaction_kinds=frozenset({OperationInteractionKind.INPUT}),
            reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
        )
        recovery = _supervisor(
            registry=changed_registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: _NOW + timedelta(minutes=2),
        )

        journal_path = tmp_path / "durable-state" / "operation-journals" / f"{operation_id}.json"
        before_response = journal_path.read_bytes()
        with pytest.raises(ValueError, match="no longer reproduces"):
            asyncio.run(
                recovery.respond(_response(intent="apply", operation_id=operation_id, revision=waiting.revision))
            )
        assert journal_path.read_bytes() == before_response
        with pytest.raises(ValueError, match="no longer reproduces"):
            asyncio.run(recovery.reconcile(operation_id))
        reloaded = asyncio.run(journal.load(operation_id))

    assert waiting.pending_interaction is not None
    assert reloaded == waiting
    assert len(executors) == 1


def test_reconcile_refuses_resume_without_a_declared_valid_checkpoint(tmp_path: Path) -> None:
    """An expired resumable definition without a checkpoint settles unknown interruption."""
    ResumableIdleExecutor.reset()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        registry = _registry(
            executor_type=ResumableIdleExecutor,
            build=ResumableIdleExecutor,
            capabilities=_capabilities(
                durability=OperationDurability.RESUMABLE,
                replay=OperationReplayPolicy.RESUMABLE,
            ),
            interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
            reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
        )
        owner = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            lease_duration=timedelta(minutes=1),
        )
        operation_id = asyncio.run(owner.submit(_request(), operation_id="3" * 64))
        abandoned = asyncio.run(_close_host_over_live_executor(owner, operation_id, ResumableIdleExecutor.started))
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: _NOW + timedelta(minutes=2),
        )

        terminal = asyncio.run(recovery.reconcile(operation_id))

    assert abandoned.lifecycle is OperationLifecycle.RUNNING
    assert abandoned.pending_interaction is None
    assert terminal.terminal_condition is OperationTerminalCondition.INTERRUPTED
    assert terminal.effect is OperationEffect.UNKNOWN


def test_reconcile_classifies_absent_lease_as_orphan_before_unknown_interruption(tmp_path: Path) -> None:
    """An existing journal without a current durable lease cannot become a resumed operation."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        registry = _registry(executor_type=IdleExecutor, build=IdleExecutor)
        owner = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(owner.submit(_request(), operation_id="3" * 64))
        scope_ref = operation_conflict_scope_reference(
            definition_id="operation.supervisor.test", subject_ref="subject:one"
        )
        observed = asyncio.run(leases.inspect(scope_ref, operation_id, observed_at=_NOW))
        assert observed.current is not None
        assert (
            asyncio.run(leases.release(observed.current, observed_at=_NOW)).disposition
            is OperationLeaseDisposition.RELEASED
        )
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
        )

        terminal = asyncio.run(recovery.reconcile(operation_id))
        replayed = asyncio.run(journal.read_after(operation_id, 0, limit=20))

    assert terminal.terminal_condition is OperationTerminalCondition.INTERRUPTED
    assert terminal.effect is OperationEffect.UNKNOWN
    assert tuple(event.outcome for event in replayed.events if isinstance(event, OperationReconciliationEvent)) == (
        OperationReconciliationOutcome.ORPHANED,
    )


def test_secure_review_publication_and_consumed_continuation_recover_without_reacquisition(
    tmp_path: Path,
) -> None:
    """A consumed secure review resumes after restart without repeating initial acquisition."""
    DurableContinuationExecutor.reset()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        registry = _registry(
            executor_type=DurableContinuationExecutor,
            build=DurableContinuationExecutor,
            capabilities=_capabilities(
                durability=OperationDurability.RESUMABLE,
                replay=OperationReplayPolicy.RESUMABLE,
            ),
            interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
            reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
        )
        owner = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            lease_duration=timedelta(minutes=1),
        )

        async def publish_consume_and_schedule() -> tuple[str, OperationConsumedInteraction]:
            operation_id = await owner.submit(_request(), operation_id="3" * 64)
            waiting = await run_to_settlement(owner, operation_id)
            pending = waiting.pending_interaction
            assert pending is not None
            secured = await operands.resolve(pending.reviewed_proposal_digest, ReviewedOperand)
            assert secured == ReviewedOperand(observation="encrypted post-submission observation")
            consumed = await owner.respond(
                OperationApplyResponse(
                    interaction_id=pending.request.interaction_id,
                    operation_id=operation_id,
                    revision=pending.request.revision,
                    response_token=_RESPONSE_TOKEN,
                    continuation_digest=pending.request.continuation_digest,
                    reviewed_proposal_digest=pending.reviewed_proposal_digest,
                    actor_ref="operator:integration",
                    responded_at=_NOW,
                    baseline_digest=_BASELINE_DIGEST,
                    proposed_effect_digest=_PROPOSED_EFFECT_DIGEST,
                )
            )
            await DurableContinuationExecutor.resumed.wait()
            return operation_id, consumed

        operation_id, consumed = asyncio.run(publish_consume_and_schedule())
        persisted = asyncio.run(journal.load(operation_id))
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: _NOW + timedelta(minutes=2),
        )

        async def observe_recovered_continuation() -> tuple[OperationPersistedSnapshot, OperationPersistedSnapshot]:
            reconciliation = asyncio.create_task(recovery.continue_operation(operation_id))
            await DurableContinuationExecutor.recovered_resume_entered.wait()
            await asyncio.sleep(0)
            acknowledged_while_waiting = reconciliation.done()
            live = await journal.load(operation_id)
            DurableContinuationExecutor.release_recovered_resume.set()
            await reconciliation
            settled = await recovery.settled(operation_id)
            assert acknowledged_while_waiting, "recovery must acknowledge before the resumed effect completes"
            return live, settled

        resumed, settled = asyncio.run(observe_recovered_continuation())

    assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert settled.terminal_receipt is not None
    assert settled.terminal_receipt.result_ref == DurableContinuationExecutor.recovered_result_ref
    assert persisted.pending_interaction is None
    assert persisted.consumed_interactions == (consumed,)
    assert consumed.intent.value == "apply"
    assert (
        consumed.checkpoint.reviewed_proposal_digest
        == persisted.consumed_interactions[0].checkpoint.reviewed_proposal_digest
    )
    assert DurableContinuationExecutor.acquisitions == 1
    assert DurableContinuationExecutor.resume_checkpoints == [consumed, consumed]
    assert resumed.lifecycle is OperationLifecycle.RUNNING
    assert resumed.phase_code == "operation.phase.declared"


def test_reconcile_refuses_active_or_corrupt_lease_without_journal_mutation(tmp_path: Path) -> None:
    """Live or unreadable owner evidence never authorizes a reconciliation transition."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        registry = _registry(executor_type=IdleExecutor, build=IdleExecutor)
        owner = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(owner.submit(_request(), operation_id="3" * 64))
        journal_path = storage_root / "operation-journals" / f"{operation_id}.json"
        journal_before = journal_path.read_bytes()
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
        )

        with pytest.raises(ValueError, match="active owner"):
            asyncio.run(recovery.reconcile(operation_id))
        assert journal_path.read_bytes() == journal_before

        scope_ref = operation_conflict_scope_reference(
            definition_id="operation.supervisor.test", subject_ref="subject:one"
        )
        lease_path = storage_root / "operation-journals" / f"{scope_ref}.lease.json"
        lease_path.write_bytes(b"invalid durable lease")
        with pytest.raises(RepositoryError, match="invalid operation lease"):
            asyncio.run(recovery.reconcile(operation_id))
        assert journal_path.read_bytes() == journal_before
