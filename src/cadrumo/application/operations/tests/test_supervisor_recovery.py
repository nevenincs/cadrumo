"""Real durable recovery proofs for :class:`OperationSupervisor`."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

import pytest

from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationLifecycle,
    OperationReconciliationEvent,
    OperationReconciliationOutcome,
    OperationReconciliationPolicy,
    OperationReplayLimit,
    OperationReplayPolicy,
    OperationTerminalCondition,
)
from .test_supervisor import (
    _NOW,
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
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
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
        detached = asyncio.run(supervisor.detach(operation_id))
        replay = asyncio.run(supervisor.replay(operation_id, 0, limit=OperationReplayLimit(20)))

    assert waiting.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
    assert detached == waiting
    assert detached.pending_interaction is not None
    assert tuple(event.sequence for event in replay.events) == tuple(range(1, len(replay.events) + 1))
    assert replay.next_cursor == detached.event_cursor


def test_duplicate_response_is_refused_after_detach_and_supervisor_restart(tmp_path: Path) -> None:
    """The persisted consumed checkpoint, not frontend attachment, refuses a duplicate response."""
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
        checkpoint = asyncio.run(owner.start(operation_id))
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: _NOW + timedelta(minutes=2),
        )
        resumed = asyncio.run(recovery.reconcile(operation_id))
        replay = asyncio.run(journal.read_after(operation_id, 0, limit=20))

    assert checkpoint.pending_interaction is not None
    assert resumed.lifecycle is OperationLifecycle.RUNNING
    assert executors[1].resume_checkpoints == [checkpoint.pending_interaction]
    assert tuple(event.outcome for event in replay.events if isinstance(event, OperationReconciliationEvent)) == (
        OperationReconciliationOutcome.RESUMED,
    )


def test_expired_running_operation_reconciles_to_unknown_interruption_without_false_success(tmp_path: Path) -> None:
    """A fresh supervisor classifies owner loss from the real lease before publishing interruption."""
    from .test_supervisor import IdleExecutor

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
            lease_duration=timedelta(minutes=1),
        )
        operation_id = asyncio.run(owner.submit(_request(), operation_id="3" * 64))
        asyncio.run(owner.start(operation_id))
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

    assert terminal.terminal_condition is OperationTerminalCondition.INTERRUPTED
    assert terminal.effect is OperationEffect.UNKNOWN
