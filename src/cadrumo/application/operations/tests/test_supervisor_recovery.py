"""Real durable recovery proofs for :class:`OperationSupervisor`."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cadrumo.application.operations.capabilities import (
    OperationOwnedResource,
    OperationReplayPolicy,
)
from cadrumo.application.operations.interactions import OperationRejectResponse
from cadrumo.application.operations.models import (
    OperationReconciliationOutcome,
    OperationTerminalReceipt,
)
from cadrumo.application.operations.persistence.events import OperationReconciliationEvent
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.persistence.leases import (
    OperationLeaseObservationDisposition,
    operation_conflict_scope_reference,
)
from cadrumo.application.operations.registry import OperationReconciliationPolicy
from cadrumo.core.operations import (
    OperationCancellation,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
)

from ....tests.secure_sql import isolated_runtime_profile
from .test_supervisor import (
    _NOW,
    DeadlineAcknowledgingExecutor,
    ResumableReviewExecutor,
    ReviewExecutor,
    _capabilities,
    _registry,
    _repositories,
    _request,
    _response,
    _supervisor,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def test_detach_preserves_real_journal_cursor_replay_and_pending_interaction(tmp_path: Path) -> None:
    """Detaching only re-reads durable state; a new observer replays its exact cursor."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        registry = _registry(
            executor_type=ReviewExecutor,
            build=ReviewExecutor,
            interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
        )
        supervisor = _supervisor(
            registry=registry, journal=journal, leases=leases, operands=operands, owner_id="1" * 64, token="2" * 64
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))
        waiting = asyncio.run(supervisor.start(operation_id))
        initial_replay = asyncio.run(supervisor.replay(operation_id, 0, limit=20))
        saved_cursor = initial_replay.next_cursor
        detached = asyncio.run(supervisor.detach(operation_id))
        response = _response(intent="reject", operation_id=operation_id, revision=waiting.revision)
        assert isinstance(response, OperationRejectResponse)
        consumed = asyncio.run(supervisor.reject(response))
        observer_journal, observer_leases, observer_operands = _repositories(
            storage_root=storage_root, profile_objects=profile.repository
        )
        observer = _supervisor(
            registry=registry,
            journal=observer_journal,
            leases=observer_leases,
            operands=observer_operands,
            owner_id="4" * 64,
            token="5" * 64,
        )
        missed = asyncio.run(observer.replay(operation_id, saved_cursor, limit=20))
        reloaded = asyncio.run(observer_journal.load(operation_id))

    assert waiting.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
    assert detached == waiting
    assert detached.pending_interaction is not None
    assert saved_cursor == detached.event_cursor
    assert tuple(event.sequence for event in initial_replay.events) == tuple(range(1, len(initial_replay.events) + 1))
    assert reloaded.consumed_interactions == (consumed,)
    assert missed.requested_cursor == saved_cursor
    assert missed.events == reloaded.events
    assert tuple(event.sequence for event in missed.events) == (saved_cursor + 1,)
    assert missed.next_cursor == reloaded.event_cursor


def test_duplicate_response_is_refused_after_detach_and_same_owner_supervisor_reconstruction(tmp_path: Path) -> None:
    """The persisted consumed checkpoint survives reconstruction by its same durable owner."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        registry = _registry(
            executor_type=ReviewExecutor,
            build=ReviewExecutor,
            interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
        )
        owner = _supervisor(
            registry=registry, journal=journal, leases=leases, operands=operands, owner_id="1" * 64, token="2" * 64
        )
        operation_id = asyncio.run(owner.submit(_request(), operation_id="3" * 64))
        waiting = asyncio.run(owner.start(operation_id))
        assert waiting.pending_interaction is not None
        assert asyncio.run(owner.detach(operation_id)) == waiting
        response = _response(intent="reject", operation_id=operation_id, revision=waiting.revision)
        assert isinstance(response, OperationRejectResponse)
        restarted = _supervisor(
            registry=registry, journal=journal, leases=leases, operands=operands, owner_id="1" * 64, token="2" * 64
        )
        consumed = asyncio.run(restarted.reject(response))
        persisted = asyncio.run(journal.load(operation_id))
        duplicate = _supervisor(
            registry=registry, journal=journal, leases=leases, operands=operands, owner_id="1" * 64, token="2" * 64
        )

        with pytest.raises(ValueError, match="not pending"):
            asyncio.run(duplicate.reject(response))

    assert persisted.consumed_interactions == (consumed,)
    assert persisted.pending_interaction is None
    assert persisted.lifecycle is OperationLifecycle.RUNNING


def test_expired_resumable_checkpoint_restarts_through_real_storage_and_replays_reconciliation(tmp_path: Path) -> None:
    """An expired owner resumes only the real persisted checkpoint and records that fact in the journal."""
    executors: list[ResumableReviewExecutor] = []

    def build() -> ResumableReviewExecutor:
        executor = ResumableReviewExecutor()
        executors.append(executor)
        return executor

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
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
        checkpoint = asyncio.run(owner.start(operation_id))
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
        resumed = asyncio.run(recovery.reconcile(operation_id))
        replay = asyncio.run(journal.read_after(operation_id, 0, limit=20))
        reloaded_journal, reloaded_leases, _ = _repositories(
            storage_root=storage_root, profile_objects=profile.repository
        )
        reloaded = asyncio.run(reloaded_journal.load(operation_id))
        scope_ref = operation_conflict_scope_reference(
            definition_id=reloaded.identity.definition_id,
            subject_ref=reloaded.identity.subject_ref,
        )
        recovered_lease = asyncio.run(reloaded_leases.inspect(scope_ref, operation_id, observed_at=recovered_at))

    assert checkpoint.pending_interaction is not None
    assert resumed.lifecycle is OperationLifecycle.RUNNING
    assert reloaded == resumed
    assert executors[1].resume_checkpoints == [checkpoint.pending_interaction]
    assert recovered_lease.disposition is OperationLeaseObservationDisposition.ACTIVE
    assert recovered_lease.current is not None
    assert recovered_lease.current.operation_id == operation_id
    assert recovered_lease.current.scope_ref == scope_ref
    assert recovered_lease.current.owner_id == "4" * 64
    assert recovered_lease.current.token == "5" * 64
    assert recovered_lease.current.acquired_at == recovered_at
    assert recovered_lease.current.expires_at == recovered_at + timedelta(minutes=10)
    assert tuple(event.outcome for event in replay.events if isinstance(event, OperationReconciliationEvent)) == (
        OperationReconciliationOutcome.RESUMED,
    )


def test_expired_running_operation_reconciles_to_unknown_interruption_without_false_success(tmp_path: Path) -> None:
    """A fresh supervisor classifies owner loss from the real lease before publishing interruption."""
    from .test_supervisor import IdleExecutor

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
        operation_id = asyncio.run(owner.submit(_request(), operation_id="3" * 64))
        asyncio.run(owner.start(operation_id))
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
        terminal = asyncio.run(recovery.reconcile(operation_id))
        reloaded_journal, reloaded_leases, _ = _repositories(
            storage_root=storage_root, profile_objects=profile.repository
        )
        reloaded = asyncio.run(reloaded_journal.load(operation_id))
        replay = asyncio.run(reloaded_journal.read_after(operation_id, 0, limit=20))
        scope_ref = operation_conflict_scope_reference(
            definition_id=reloaded.identity.definition_id,
            subject_ref=reloaded.identity.subject_ref,
        )
        released_lease = asyncio.run(reloaded_leases.inspect(scope_ref, operation_id, observed_at=recovered_at))

    assert terminal.terminal_condition is OperationTerminalCondition.INTERRUPTED
    assert terminal.effect is OperationEffect.UNKNOWN
    assert reloaded == terminal
    assert tuple(event.outcome for event in replay.events if isinstance(event, OperationReconciliationEvent)) == (
        OperationReconciliationOutcome.INTERRUPTED,
    )
    assert released_lease.disposition is OperationLeaseObservationDisposition.ABSENT
    assert released_lease.current is None


def test_detached_cancellation_race_persists_acknowledgement_before_terminal_settlement(tmp_path: Path) -> None:
    """A detached observer cannot race a real cooperative cancellation out of durable authority."""
    executor = DeadlineAcknowledgingExecutor()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        reloaded_journal, reloaded_leases, _ = _repositories(
            storage_root=storage_root, profile_objects=profile.repository
        )
        supervisor = _supervisor(
            registry=_registry(
                executor_type=DeadlineAcknowledgingExecutor,
                build=lambda: executor,
                capabilities=_capabilities(
                    cancellation=OperationCancellation.COOPERATIVE,
                    owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK}),
                ),
            ),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )

        async def run_detached_cancellation_race() -> tuple[
            OperationPersistedSnapshot,
            OperationPersistedSnapshot,
            OperationPersistedSnapshot,
            OperationPersistedSnapshot,
        ]:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            start_task = asyncio.create_task(supervisor.start(operation_id))
            await executor.started.wait()
            detached = await supervisor.detach(operation_id)
            cancellation_task = asyncio.create_task(supervisor.request_cancel(operation_id))
            requested = await cancellation_task
            settling = await start_task
            reloaded = await reloaded_journal.load(operation_id)
            terminal = await supervisor.settle(
                operation_id,
                OperationTerminalReceipt(
                    identity=settling.identity,
                    revision=settling.revision + 1,
                    condition=OperationTerminalCondition.CANCELLED,
                    effect=OperationEffect.NONE,
                    settled_at=_NOW,
                ),
            )
            return detached, requested, reloaded, terminal

        detached, requested, reloaded, terminal = asyncio.run(run_detached_cancellation_race())
        persisted_terminal = asyncio.run(reloaded_journal.load(terminal.identity.operation_id))
        scope_ref = operation_conflict_scope_reference(
            definition_id=terminal.identity.definition_id,
            subject_ref=terminal.identity.subject_ref,
        )
        released_lease = asyncio.run(
            reloaded_leases.inspect(scope_ref, terminal.identity.operation_id, observed_at=_NOW)
        )

    assert detached.lifecycle is OperationLifecycle.RUNNING
    assert requested.lifecycle is OperationLifecycle.CANCELLATION_REQUESTED
    assert requested.cancellation_requested_at is not None
    assert reloaded.lifecycle is OperationLifecycle.SETTLING
    assert reloaded.cancellation_requested_at == requested.cancellation_requested_at
    assert reloaded.cancellation_acknowledged_at is not None
    assert terminal.terminal_condition is OperationTerminalCondition.CANCELLED
    assert persisted_terminal == terminal
    assert released_lease.disposition is OperationLeaseObservationDisposition.ABSENT
    assert released_lease.current is None
    assert executor.resource.close_calls == 1


def test_detached_deadline_race_persists_cooperative_stop_before_terminal_settlement(tmp_path: Path) -> None:
    """The aggregate deadline races real execution through the filesystem journal before settlement."""
    executor = DeadlineAcknowledgingExecutor()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        reloaded_journal, reloaded_leases, _ = _repositories(
            storage_root=storage_root, profile_objects=profile.repository
        )
        supervisor = _supervisor(
            registry=_registry(
                executor_type=DeadlineAcknowledgingExecutor,
                build=lambda: executor,
                capabilities=_capabilities(
                    cancellation=OperationCancellation.COOPERATIVE,
                    deadline=OperationDeadline.COOPERATIVE,
                    owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK}),
                ),
            ),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            clock=lambda: datetime.now(UTC),
            execution_timeout=timedelta(milliseconds=50),
            cleanup_timeout=timedelta(seconds=1),
        )

        async def run_detached_deadline_race() -> tuple[
            OperationPersistedSnapshot,
            OperationPersistedSnapshot,
            OperationPersistedSnapshot,
        ]:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            start_task = asyncio.create_task(supervisor.start(operation_id))
            await executor.started.wait()
            detached = await supervisor.detach(operation_id)
            settling = await start_task
            reloaded = await reloaded_journal.load(operation_id)
            terminal = await supervisor.settle(
                operation_id,
                OperationTerminalReceipt(
                    identity=settling.identity,
                    revision=settling.revision + 1,
                    condition=OperationTerminalCondition.CANCELLED,
                    effect=OperationEffect.NONE,
                    settled_at=datetime.now(UTC),
                ),
            )
            return detached, reloaded, terminal

        detached, reloaded, terminal = asyncio.run(run_detached_deadline_race())
        persisted_terminal = asyncio.run(reloaded_journal.load(terminal.identity.operation_id))
        scope_ref = operation_conflict_scope_reference(
            definition_id=terminal.identity.definition_id,
            subject_ref=terminal.identity.subject_ref,
        )
        released_lease = asyncio.run(
            reloaded_leases.inspect(scope_ref, terminal.identity.operation_id, observed_at=datetime.now(UTC))
        )

    assert detached.lifecycle is OperationLifecycle.RUNNING
    assert reloaded.lifecycle is OperationLifecycle.SETTLING
    assert reloaded.execution_deadline is not None
    assert reloaded.cancellation_requested_at is not None
    assert reloaded.cancellation_acknowledged_at is not None
    assert reloaded.cleanup_deadline is not None
    assert terminal.terminal_condition is OperationTerminalCondition.CANCELLED
    assert persisted_terminal == terminal
    assert released_lease.disposition is OperationLeaseObservationDisposition.ABSENT
    assert released_lease.current is None
    assert executor.resource.close_calls == 1
