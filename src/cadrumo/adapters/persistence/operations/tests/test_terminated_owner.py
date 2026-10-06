"""Terminated-owner settlement through the real journal and exact lease CAS."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
from typing import override

import pytest

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.storage.errors import RepositoryError
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.operations.models import OperationReconciliationOutcome
from cadrumo.application.operations.persistence.events import OperationPhaseEvent, OperationReconciliationEvent
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.persistence.leases import OperationOwnerLease, operation_conflict_scope_reference
from cadrumo.application.operations.terminated_owner import settle_terminated_operation
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition

from .test_supervisor import _NOW, IdleExecutor, _registry, _repositories, _request, _supervisor

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]


@pytest.mark.parametrize("entered", [False, True])
def test_dead_owner_settlement_is_atomic_and_never_resolves_operands(tmp_path: Path, entered: bool) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(storage_root=tmp_path / "journal", profile_objects=profile.repository)
        registry = _registry(executor_type=IdleExecutor, build=IdleExecutor)

        async def exercise() -> None:
            supervisor = _supervisor(
                registry=registry,
                journal=journal,
                leases=leases,
                operands=operands,
                owner_id="1" * 64,
                token="2" * 64,
            )
            operation_id = "3" * 64
            await supervisor.submit(_request(), operation_id=operation_id)
            snapshot = await journal.load(operation_id)
            scope = operation_conflict_scope_reference(
                definition_id=snapshot.identity.definition_id, subject_ref=snapshot.identity.subject_ref
            )
            before = await leases.inspect(scope, operation_id, observed_at=_NOW)
            assert before.current is not None
            if entered:
                # Persist the last worker fact before simulated native death;
                # this test supplies termination evidence, not a live executor.
                snapshot = snapshot.model_copy(
                    update={
                        "revision": snapshot.revision + 1,
                        "lifecycle": OperationLifecycle.RUNNING,
                        "executor_entered_at": _NOW,
                        "phase_code": "operation.running",
                        "events": (
                            OperationPhaseEvent(
                                identity=snapshot.identity,
                                revision=snapshot.revision + 1,
                                sequence=snapshot.event_cursor + 1,
                                timestamp=_NOW,
                                code="operation.phase",
                                phase_code="operation.running",
                            ),
                        ),
                        "event_cursor": snapshot.event_cursor + 1,
                    }
                )
                await journal.commit(snapshot, expected_revision=snapshot.revision - 1, lease=before.current)
            assert not await settle_terminated_operation(
                operation_id=operation_id,
                terminated_owner_id="4" * 64,
                journal=journal,
                leases=leases,
                registry=registry,
                observed_at=_NOW,
            )
            assert await journal.load(operation_id) == snapshot
            assert await leases.inspect(scope, operation_id, observed_at=_NOW) == before
            assert await settle_terminated_operation(
                operation_id=operation_id,
                terminated_owner_id="1" * 64,
                journal=journal,
                leases=leases,
                registry=registry,
                observed_at=_NOW,
            )
            settled = await journal.load(operation_id)
            assert settled.terminal_condition is OperationTerminalCondition.INTERRUPTED
            assert settled.effect is (OperationEffect.UNKNOWN if entered else OperationEffect.NONE)
            assert settled.revision == snapshot.revision + 1
            assert isinstance(settled.events[0], OperationReconciliationEvent)
            assert settled.events[0].outcome is OperationReconciliationOutcome.ORPHANED
            assert settled.events[0].lease_evidence_ref == before.evidence_ref
            assert (await leases.inspect(scope, operation_id, observed_at=_NOW)).current is None
            assert not await settle_terminated_operation(
                operation_id=operation_id,
                terminated_owner_id="1" * 64,
                journal=journal,
                leases=leases,
                registry=registry,
                observed_at=_NOW,
            )

        asyncio.run(exercise())


def test_expired_dead_owner_lease_is_not_renewed_or_released(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(storage_root=tmp_path / "journal", profile_objects=profile.repository)
        registry = _registry(executor_type=IdleExecutor, build=IdleExecutor)

        async def exercise() -> None:
            supervisor = _supervisor(
                registry=registry,
                journal=journal,
                leases=leases,
                operands=operands,
                owner_id="1" * 64,
                token="2" * 64,
                lease_duration=timedelta(seconds=1),
            )
            operation_id = "3" * 64
            await supervisor.submit(_request(), operation_id=operation_id)
            snapshot = await journal.load(operation_id)
            scope = operation_conflict_scope_reference(
                definition_id=snapshot.identity.definition_id, subject_ref=snapshot.identity.subject_ref
            )
            instant = _NOW + timedelta(seconds=2)
            before = await leases.inspect(scope, operation_id, observed_at=instant)
            with pytest.raises(ValueError, match="expired"):
                await settle_terminated_operation(
                    operation_id=operation_id,
                    terminated_owner_id="1" * 64,
                    journal=journal,
                    leases=leases,
                    registry=registry,
                    observed_at=instant,
                )
            assert await journal.load(operation_id) == snapshot
            assert await leases.inspect(scope, operation_id, observed_at=instant) == before

        asyncio.run(exercise())


def test_raced_lease_replacement_cannot_be_settled_by_dead_owner(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / "journal"
        journal, leases, operands = _repositories(storage_root=root, profile_objects=profile.repository)
        registry = _registry(executor_type=IdleExecutor, build=IdleExecutor)

        class RacingJournal(OperationJournalRepository):
            @override
            async def commit_settlement(
                self, snapshot: OperationPersistedSnapshot, *, expected_revision: int, lease: OperationOwnerLease
            ) -> None:
                takeover_at = lease.expires_at + timedelta(seconds=1)
                replacement = lease.model_copy(
                    update={
                        "owner_id": "4" * 64,
                        "token": "5" * 64,
                        "acquired_at": takeover_at,
                        "expires_at": takeover_at + timedelta(minutes=1),
                    }
                )
                changed = await leases.compare_and_swap(lease, replacement, observed_at=takeover_at)
                assert changed.current == replacement
                await super().commit_settlement(snapshot, expected_revision=expected_revision, lease=lease)

        async def exercise() -> None:
            supervisor = _supervisor(
                registry=registry,
                journal=journal,
                leases=leases,
                operands=operands,
                owner_id="1" * 64,
                token="2" * 64,
            )
            operation_id = "3" * 64
            await supervisor.submit(_request(), operation_id=operation_id)
            before = await journal.load(operation_id)
            with pytest.raises(RepositoryError):
                await settle_terminated_operation(
                    operation_id=operation_id,
                    terminated_owner_id="1" * 64,
                    journal=RacingJournal(storage_root=root),
                    leases=leases,
                    registry=registry,
                    observed_at=_NOW,
                )
            assert await journal.load(operation_id) == before
            scope = operation_conflict_scope_reference(
                definition_id=before.identity.definition_id, subject_ref=before.identity.subject_ref
            )
            current = (await leases.inspect(scope, operation_id, observed_at=_NOW + timedelta(minutes=11))).current
            assert current is not None and current.owner_id == "4" * 64 and current.token == "5" * 64

        asyncio.run(exercise())
