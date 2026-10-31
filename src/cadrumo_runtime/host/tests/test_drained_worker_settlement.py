"""A stop records the work its drained worker left unfinished, through the real journal and leases."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.tests.supervisor_test_support import (
    IdleExecutor,
    operation_repositories,
    operation_supervisor,
    supervisor_registry,
    supervisor_request,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.operations.models import OperationReconciliationOutcome
from cadrumo.application.operations.persistence.events import OperationPhaseEvent, OperationReconciliationEvent
from cadrumo.application.operations.persistence.leases import operation_conflict_scope_reference
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.contracts import ExitReason, RefusalCode, RefusalError
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_runtime.contracts.profile_worker import ProfileWorkerDrained

from ..profile_connections import RuntimeProfileConnections
from ..profile_host import RuntimeProfileHost
from ..shutdown import RuntimeStop
from .test_runtime_drain_refusal import _EmptyApprovals, _FailedWorker, _Owner

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _DrainedWorker:
    """The native worker boundary: a stop answers with its receipt, then the scope is contained."""

    def __init__(self, identity: ProfileWorkerIdentity, recovery_required: tuple[str, ...], *, contain: bool) -> None:
        self.identity = identity
        self._recovery_required = recovery_required
        self._contain = contain
        self.contained = False
        self.settled = False

    def drain(self, *, deadline: float) -> ProfileWorkerDrained:
        del deadline
        if not self._contain:
            raise RefusalError(RefusalCode.TIMEOUT)
        self.contained = True
        return ProfileWorkerDrained(
            identity=self.identity,
            request_id=uuid4(),
            unresolved=(),
            recovery_required=self._recovery_required,
        )

    def close(self, *, deadline: float) -> None:
        del deadline
        if not self._contain:
            raise RuntimeError("native containment unconfirmed")
        self.contained = True

    def settle(self, *, deadline: float) -> None:
        del deadline
        self.settled = True


def _identity(boot: UUID) -> ProfileWorkerIdentity:
    return ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=boot,
        binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="test-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
    )


async def _enter_executor(
    journal: OperationJournalRepository, leases: OperationLeaseFilesystemRepository, op: str
) -> None:
    """Persist the last fact a worker writes before its executor changes anything."""
    snapshot = await journal.load(op)
    scope = operation_conflict_scope_reference(
        definition_id=snapshot.identity.definition_id, subject_ref=snapshot.identity.subject_ref
    )
    lease = (await leases.inspect(scope, op, observed_at=now())).current
    assert lease is not None
    entered_at = now()
    running = snapshot.model_copy(
        update={
            "revision": snapshot.revision + 1,
            "lifecycle": OperationLifecycle.RUNNING,
            "executor_entered_at": entered_at,
            "updated_at": entered_at,
            "phase_code": "operation.running",
            "events": (
                OperationPhaseEvent(
                    identity=snapshot.identity,
                    revision=snapshot.revision + 1,
                    sequence=snapshot.event_cursor + 1,
                    timestamp=entered_at,
                    code="operation.phase",
                    phase_code="operation.running",
                ),
            ),
            "event_cursor": snapshot.event_cursor + 1,
        }
    )
    await journal.commit(running, expected_revision=snapshot.revision, lease=lease)


def _profiles(root: Path, registry: OperationRegistry | None) -> tuple[RuntimeProfileConnections, RuntimeStop]:
    stop = RuntimeStop()
    profiles = RuntimeProfileConnections(
        storage_root=root, storage_identity="test-storage", runtime_boot_id=uuid4(), stop=stop
    )
    # The registry the journaled operations were defined under, as startup installs it.
    profiles._registry = registry
    return profiles, stop


def _host(profiles: RuntimeProfileConnections, worker: _DrainedWorker) -> None:
    profiles._profiles[worker.identity.binding.profile_id] = cast(
        RuntimeProfileHost, SimpleNamespace(owner=_Owner(cast(_FailedWorker, worker)), approvals=_EmptyApprovals())
    )


@pytest.mark.parametrize("reason", [ExitReason.SUPERVISOR_STOP, ExitReason.SIGNAL_STOP])
def test_a_stop_records_unfinished_work_as_interrupted_with_its_effect(tmp_path: Path, reason: ExitReason) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / "runtime"
        journal, leases, operands = operation_repositories(storage_root=root, profile_objects=profile.repository)
        registry = supervisor_registry(executor_type=IdleExecutor, build=IdleExecutor)
        profiles, stop = _profiles(root, registry)
        identity = _identity(profiles.boot)
        running, created, foreign = "3" * 64, "4" * 64, "5" * 64

        async def seed() -> None:
            ours = operation_supervisor(
                registry=registry,
                journal=journal,
                leases=leases,
                operands=operands,
                owner_id=identity.operation_owner_id,
                token="2" * 64,
                clock=now,
            )
            await ours.submit(supervisor_request(subject_ref="subject:running"), operation_id=running)
            await ours.submit(supervisor_request(subject_ref="subject:created"), operation_id=created)
            await _enter_executor(journal, leases, running)
            theirs = operation_supervisor(
                registry=registry,
                journal=journal,
                leases=leases,
                operands=operands,
                owner_id="6" * 64,
                token="7" * 64,
                clock=now,
            )
            await theirs.submit(supervisor_request(subject_ref="subject:foreign"), operation_id=foreign)

        asyncio.run(seed())
        foreign_before = asyncio.run(journal.load(foreign))
        _host(profiles, _DrainedWorker(identity, (running, created, foreign), contain=True))
        stop.request(reason)

        result = profiles.drain(deadline=time.monotonic() + 15)

        assert result.uncontained == result.unsettled == ()
        assert not result.lacks_settlement_evidence
        assert result.receipts[0].recovery_required == (running, created, foreign)
        interrupted = asyncio.run(journal.load(running))
        assert interrupted.lifecycle is OperationLifecycle.TERMINAL
        assert interrupted.terminal_condition is OperationTerminalCondition.INTERRUPTED
        # The executor was entered, so whether the change took effect is not known.
        assert interrupted.effect is OperationEffect.UNKNOWN
        assert isinstance(interrupted.events[0], OperationReconciliationEvent)
        assert interrupted.events[0].outcome is OperationReconciliationOutcome.ORPHANED
        never_started = asyncio.run(journal.load(created))
        assert never_started.terminal_condition is OperationTerminalCondition.INTERRUPTED
        assert never_started.effect is OperationEffect.NONE
        # Work another owner leases is never settled on this worker's word.
        assert asyncio.run(journal.load(foreign)) == foreign_before
        for op, subject in ((running, "subject:running"), (created, "subject:created")):
            scope = operation_conflict_scope_reference(definition_id="operation.supervisor.test", subject_ref=subject)
            assert asyncio.run(leases.inspect(scope, op, observed_at=now())).current is None


def test_unconfirmed_containment_leaves_unfinished_work_running(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / "runtime"
        journal, leases, operands = operation_repositories(storage_root=root, profile_objects=profile.repository)
        registry = supervisor_registry(executor_type=IdleExecutor, build=IdleExecutor)
        profiles, stop = _profiles(root, registry)
        identity = _identity(profiles.boot)
        running = "3" * 64

        async def seed() -> None:
            supervisor = operation_supervisor(
                registry=registry,
                journal=journal,
                leases=leases,
                operands=operands,
                owner_id=identity.operation_owner_id,
                token="2" * 64,
                clock=now,
            )
            await supervisor.submit(supervisor_request(subject_ref="subject:running"), operation_id=running)
            await _enter_executor(journal, leases, running)

        asyncio.run(seed())
        before = asyncio.run(journal.load(running))
        _host(profiles, _DrainedWorker(identity, (running,), contain=False))
        stop.request(ExitReason.SUPERVISOR_STOP)

        result = profiles.drain(deadline=time.monotonic() + 2)

        assert result.uncontained == (identity.binding.profile_id,)
        # A worker that may still run keeps its lease and its record as they were.
        assert asyncio.run(journal.load(running)) == before


def test_a_settlement_that_cannot_run_leaves_the_record_for_lapse_reconciliation(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        root = tmp_path / "runtime"
        journal, leases, operands = operation_repositories(storage_root=root, profile_objects=profile.repository)
        registry = supervisor_registry(executor_type=IdleExecutor, build=IdleExecutor)
        profiles, stop = _profiles(root, None)
        identity = _identity(profiles.boot)
        running = "3" * 64

        async def seed() -> None:
            supervisor = operation_supervisor(
                registry=registry,
                journal=journal,
                leases=leases,
                operands=operands,
                owner_id=identity.operation_owner_id,
                token="2" * 64,
                clock=now,
            )
            await supervisor.submit(supervisor_request(subject_ref="subject:running"), operation_id=running)
            await _enter_executor(journal, leases, running)

        asyncio.run(seed())
        before = asyncio.run(journal.load(running))
        _host(profiles, _DrainedWorker(identity, (running,), contain=True))
        stop.request(ExitReason.SUPERVISOR_STOP)

        result = profiles.drain(deadline=time.monotonic() + 5)

        # The stop itself is settled; the record stays as the worker left it.
        assert result.uncontained == result.unsettled == ()
        assert asyncio.run(journal.load(running)) == before
