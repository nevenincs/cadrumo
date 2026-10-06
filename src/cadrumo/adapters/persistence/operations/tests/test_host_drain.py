"""Bounded host drain against the real operation journal and supervisor."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.operations.composition import compose_operation_services
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.persistence.leases import operation_conflict_scope_reference
from cadrumo.application.operations.tests.authority_test_support import unread_authority_operation
from cadrumo.core.operations import OperationLifecycle

from .supervision_support import run_to_settlement
from .test_supervisor import _NOW, IdleExecutor, _registry, _repositories, _request, _supervisor

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]


class CancellationResistantExecutor:
    """A real executor task that remains live after its first cancellation."""

    def __init__(self, release: asyncio.Event, entered: asyncio.Queue[None]) -> None:
        self.release = release
        self.entered = entered
        self.cancelled = asyncio.Event()

    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> str:
        del request, context
        self.entered.put_nowait(None)
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            await self.release.wait()
        return "result:released"


def test_composed_drain_has_one_deadline_and_reports_uncontained_work(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )

        async def exercise() -> None:
            release = asyncio.Event()
            entered: asyncio.Queue[None] = asyncio.Queue()
            executors: list[CancellationResistantExecutor] = []

            def build() -> CancellationResistantExecutor:
                executor = CancellationResistantExecutor(release, entered)
                executors.append(executor)
                return executor

            services = compose_operation_services(
                registry=_registry(executor_type=CancellationResistantExecutor, build=build),
                authority_operation=unread_authority_operation(),
                journal=journal,
                reader=journal,
                event_stream=journal,
                leases=leases,
                operands=operands,
                owner_id="1" * 64,
                lease_token_factory=lambda: "2" * 64,
                clock=lambda: _NOW,
                lease_duration=timedelta(minutes=10),
                execution_timeout=timedelta(minutes=1),
                cleanup_timeout=timedelta(minutes=1),
            )
            ids = ("3" * 64, "4" * 64)
            assert services.submission.supervisor.in_flight_operation_count() == 0
            try:
                for index, operation_id in enumerate(ids):
                    await services.submission.submit(
                        _request(subject_ref=f"subject:{index}"),
                        actor_ref="operator:drain-test",
                        operation_id=operation_id,
                    )
                    await services.submission.start(operation_id)
                for _ in ids:
                    await asyncio.wait_for(entered.get(), timeout=3)

                assert services.submission.supervisor.in_flight_operation_count() == 2
                started = asyncio.get_running_loop().time()
                result = await services.drain(timedelta(milliseconds=40))
                elapsed = asyncio.get_running_loop().time() - started
                assert elapsed < 0.5
                assert result.unresolved == ids
                assert result.recovery_required == ids
                assert result.needs_containment
                assert services.submission.supervisor.in_flight_operation_count() == 2
                assert all(executor.cancelled.is_set() for executor in executors)
                for operation_id in ids:
                    assert (await journal.load(operation_id)).lifecycle is not OperationLifecycle.TERMINAL
                with pytest.raises(ValueError, match="draining"):
                    await services.submission.submit(
                        _request(subject_ref="subject:new"), actor_ref="operator:drain-test"
                    )

                release.set()
                await asyncio.sleep(0.05)
                repeated = await services.drain(timedelta(milliseconds=40))
                assert not repeated.needs_containment
            finally:
                release.set()
                await services.shutdown()

        asyncio.run(exercise())


def test_created_submission_remains_recoverable_and_fences_direct_admission(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )

        async def exercise() -> None:
            supervisor = _supervisor(
                registry=_registry(
                    executor_type=CancellationResistantExecutor,
                    build=lambda: CancellationResistantExecutor(asyncio.Event(), asyncio.Queue()),
                ),
                journal=journal,
                leases=leases,
                operands=operands,
                owner_id="1" * 64,
                token="2" * 64,
            )
            operation_id = "3" * 64
            request = _request()
            assert supervisor.in_flight_operation_count() == 0
            await supervisor.submit(request, operation_id=operation_id)
            assert supervisor.in_flight_operation_count() == 1
            scope = operation_conflict_scope_reference(
                definition_id=request.definition_id, subject_ref=request.subject_ref
            )
            before = await leases.inspect(scope, operation_id, observed_at=_NOW)
            assert before.current is not None

            drained = await supervisor.drain(timedelta(milliseconds=40))
            assert drained.unresolved == ()
            assert drained.recovery_required == (operation_id,)
            assert not drained.needs_containment
            assert supervisor.in_flight_operation_count() == 1
            assert (await journal.load(operation_id)).lifecycle is OperationLifecycle.CREATED
            assert (await leases.inspect(scope, operation_id, observed_at=_NOW)).current == before.current

            for admission in (
                supervisor.start(operation_id),
                supervisor.continue_operation(operation_id),
                supervisor.reconcile(operation_id),
                supervisor.stored_invocation(operation_id),
                supervisor.submit(_request(subject_ref="subject:new")),
            ):
                with pytest.raises(ValueError, match="draining"):
                    await admission
            assert (await supervisor.shutdown()).recovery_required == (operation_id,)

        asyncio.run(exercise())


def test_operation_count_returns_to_zero_after_durable_settlement(tmp_path: Path) -> None:
    """An idle host is not an in-flight operation; observation does not renew leases."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )

        async def exercise() -> None:
            supervisor = _supervisor(
                registry=_registry(executor_type=IdleExecutor, build=IdleExecutor),
                journal=journal,
                leases=leases,
                operands=operands,
                owner_id="1" * 64,
                token="2" * 64,
            )
            request = _request()
            operation_id = await supervisor.submit(request)
            scope = operation_conflict_scope_reference(
                definition_id=request.definition_id, subject_ref=request.subject_ref
            )
            before = await leases.inspect(scope, operation_id, observed_at=_NOW)
            assert supervisor.in_flight_operation_count() == 1
            assert supervisor.in_flight_operation_count() == 1
            assert await leases.inspect(scope, operation_id, observed_at=_NOW) == before
            settled = await run_to_settlement(supervisor, operation_id)
            assert settled.lifecycle is OperationLifecycle.TERMINAL
            assert supervisor.in_flight_operation_count() == 0

        asyncio.run(exercise())
