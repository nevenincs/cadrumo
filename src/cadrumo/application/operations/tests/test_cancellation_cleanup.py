"""Real cancellation proofs across every declared cancellable phase.

Each case drives the production :class:`OperationSupervisor` against real
durable adapters, a real child process, and a real background task. The stop
is requested at one declared phase, and the resulting terminal fact must be
reached only after the supervisor's own cleanup has closed every owned
resource, reaped the child, and released the durable conflict scope.

The interruption point is injected by the test, which is what a cancellation
proof is for. Everything downstream of the request -- acknowledgement,
cleanup, reaping, lease release, terminal settlement -- runs through the
supervisor's own code paths; nothing here closes a resource on the
supervisor's behalf.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from ....adapters.persistence.operations.journal import OperationJournalRepository
from ....adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ....adapters.persistence.operations.secure_references import (
    OperationSecureReferenceRepository,
    operation_secure_reference_repository,
)
from ....adapters.persistence.storage import SecureObjectRepository
from ....core import STRICT_FROZEN_CONFIG
from ....core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ....tests.secure_sql import isolated_runtime_profile
from ..capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..models import OperationRequest
from ..owner import OperationExecutorContext
from ..persistence.leases import operation_conflict_scope_reference
from ..registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from ..supervisor import OperationSupervisor

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 28, 9, tzinfo=UTC)
_DEFINITION_ID = "operation.supervisor.cancellation"

#: Every phase this definition declares. The cancellable-phase sweep is derived
#: from this tuple rather than restated, so adding a phase widens the sweep
#: instead of silently leaving the new phase unproven.
_PHASES: tuple[str, ...] = (
    "operation.phase.preflight",
    "operation.phase.acquire",
    "operation.phase.transform",
    "operation.phase.persist",
)

#: Source for the owned child. It reports readiness on stdout and then blocks,
#: so the parent observes a genuinely live process rather than a race.
_CHILD_SOURCE = "import sys, time\nsys.stdout.write('ready\\n')\nsys.stdout.flush()\ntime.sleep(600)\n"


class CancellationRequest(BaseModel):
    """Encrypted operand reaching the real secure-reference adapter."""

    model_config = STRICT_FROZEN_CONFIG

    value: str = Field(min_length=1)


class CancellationResult(BaseModel):
    """Registry result type for this cancellation operation."""

    model_config = STRICT_FROZEN_CONFIG

    reference: str = Field(min_length=1)


class ChildProcessResource:
    """One real child process whose close terminates and reaps it."""

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self._process = process
        self.close_calls = 0

    @property
    def pid(self) -> int:
        return self._process.pid

    @property
    def returncode(self) -> int | None:
        return self._process.returncode

    async def read_ready_line(self) -> bytes:
        """Block until the child reports it is genuinely running."""
        stdout = self._process.stdout
        if stdout is None:
            raise RuntimeError("owned child process was spawned without a stdout pipe")
        return await stdout.readline()

    async def stdout_at_eof(self) -> bool:
        """Report whether the child's pipe closed, which only a dead child does."""
        stdout = self._process.stdout
        if stdout is None:
            raise RuntimeError("owned child process was spawned without a stdout pipe")
        return not await stdout.read()

    async def close(self) -> None:
        self.close_calls += 1
        if self._process.returncode is None:
            self._process.terminate()
        await self._process.wait()


class BackgroundTaskResource:
    """One real background task whose close cancels and settles it."""

    def __init__(self) -> None:
        self._task = asyncio.create_task(asyncio.sleep(600), name="operation-owned-background")
        self.close_calls = 0

    @property
    def done(self) -> bool:
        return self._task.done()

    async def close(self) -> None:
        self.close_calls += 1
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task


class PhaseGatedProcessExecutor:
    """Own a real child and a real task, then stop at one declared phase."""

    def __init__(self, *, cancel_at: str) -> None:
        self._cancel_at = cancel_at
        self.reached_cancel_phase = asyncio.Event()
        self.acknowledged = asyncio.Event()
        self.process_resource: ChildProcessResource | None = None
        self.task_resource: BackgroundTaskResource | None = None
        self.phases_entered: list[str] = []

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            _CHILD_SOURCE,
            stdout=asyncio.subprocess.PIPE,
        )
        process_resource = ChildProcessResource(process)
        self.process_resource = process_resource
        context.cleanup.own(process_resource, family=OperationOwnedResource.PROCESS)

        task_resource = BackgroundTaskResource()
        self.task_resource = task_resource
        context.cleanup.own(task_resource, family=OperationOwnedResource.ASYNC_TASK)

        await process_resource.read_ready_line()

        for phase in _PHASES:
            await context.events.phase(phase)
            self.phases_entered.append(phase)
            if phase != self._cancel_at:
                continue
            self.reached_cancel_phase.set()
            while not context.cancellation.cancellation_requested:
                await asyncio.sleep(0)
            await context.cancellation.acknowledge_cancellation()
            self.acknowledged.set()
            return None
        return None


def _capabilities() -> OperationCapabilities:
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.COOPERATIVE,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK, OperationOwnedResource.PROCESS}),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.PARTIAL, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def _definition(executor: PhaseGatedProcessExecutor) -> OperationDefinition:
    return OperationDefinition(
        definition_id=_DEFINITION_ID,
        request_type=CancellationRequest,
        result_type=CancellationResult,
        executor_factory=OperationExecutorFactory(
            request_type=CancellationRequest,
            executor_type=PhaseGatedProcessExecutor,
            build=lambda: executor,
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
    )


def _repositories(
    *,
    storage_root: Path,
    profile_objects: SecureObjectRepository,
) -> tuple[OperationJournalRepository, OperationLeaseFilesystemRepository, OperationSecureReferenceRepository]:
    return (
        OperationJournalRepository(storage_root=storage_root),
        OperationLeaseFilesystemRepository(storage_root=storage_root),
        operation_secure_reference_repository(objects=profile_objects),
    )


def _supervisor(
    *,
    journal: OperationJournalRepository,
    leases: OperationLeaseFilesystemRepository,
    operands: OperationSecureReferenceRepository,
    executor: PhaseGatedProcessExecutor,
    clock: Callable[[], datetime] = lambda: _NOW,
) -> OperationSupervisor:
    definition = _definition(executor)
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.cancellation.request",
            schema_version=1,
            model_type=CancellationRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.cancellation.result",
            schema_version=1,
            model_type=CancellationResult,
        ),
    )
    return OperationSupervisor(
        registry=OperationRegistry(definitions=(definition,), public_registrations=(registration,)),
        journal=journal,
        event_stream=journal,
        leases=leases,
        operands=operands,
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=clock,
        lease_duration=timedelta(minutes=10),
        cleanup_timeout=timedelta(minutes=5),
    )


def _request(*, subject_ref: str) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=_DEFINITION_ID,
        subject_ref=subject_ref,
        payload=CancellationRequest(value="encrypted-cancellation-input"),
    )


@pytest.mark.parametrize("cancel_at", _PHASES, ids=lambda phase: phase.rsplit(".", 1)[-1])
def test_cancellation_at_each_declared_phase_reaps_the_child_and_frees_the_scope(
    tmp_path: Path,
    cancel_at: str,
) -> None:
    """A stop at any declared phase settles only after real cleanup and reaping."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state",
            profile_objects=profile.repository,
        )
        executor = PhaseGatedProcessExecutor(cancel_at=cancel_at)
        supervisor = _supervisor(journal=journal, leases=leases, operands=operands, executor=executor)

        async def cancel_at_phase() -> None:
            operation_id = f"{_PHASES.index(cancel_at) + 1:064x}"
            await supervisor.submit(_request(subject_ref=f"subject:{cancel_at}"), operation_id=operation_id)
            start_task = asyncio.create_task(supervisor.start(operation_id))
            await executor.reached_cancel_phase.wait()

            process_resource = executor.process_resource
            task_resource = executor.task_resource
            assert process_resource is not None
            assert task_resource is not None

            # The child is genuinely alive and unreaped before the stop is asked for.
            assert process_resource.returncode is None
            assert process_resource.close_calls == 0
            assert not task_resource.done

            requested = await supervisor.request_cancel(operation_id)
            assert requested.cancellation_requested_at is not None
            assert requested.cleanup_deadline is not None

            terminal = await start_task
            await executor.acknowledged.wait()

            released = await leases.inspect(
                operation_conflict_scope_reference(
                    definition_id=terminal.identity.definition_id,
                    subject_ref=terminal.identity.subject_ref,
                ),
                terminal.identity.operation_id,
                observed_at=_NOW,
            )

            # Acknowledgement is durable and precedes the terminal fact.
            assert terminal.cancellation_acknowledged_at is not None
            assert terminal.cancellation_requested_at is not None
            assert terminal.cancellation_acknowledged_at >= terminal.cancellation_requested_at
            assert terminal.lifecycle is OperationLifecycle.TERMINAL
            assert terminal.terminal_condition is OperationTerminalCondition.CANCELLED

            # The stop happened at the phase asked for, not later.
            assert executor.phases_entered == list(_PHASES[: _PHASES.index(cancel_at) + 1])

            # Supervisor-owned cleanup closed both families exactly once.
            assert process_resource.close_calls == 1
            assert task_resource.close_calls == 1
            assert task_resource.done

            # The child was reaped: its exit status was collected, and its pipe
            # reached EOF, which only a dead process produces.
            assert process_resource.returncode is not None
            assert await process_resource.stdout_at_eof()

            # The durable conflict scope is free for a successor.
            assert released.current is None

        asyncio.run(cancel_at_phase())
