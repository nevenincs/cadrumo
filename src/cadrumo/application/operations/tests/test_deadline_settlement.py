"""Real deadline proofs that no timed-out fact is published prematurely.

An elapsed deadline is a supervisor decision to ask for a stop, never a
licence to declare the work over. These cases hold the two live things a
deadline can outrun -- the executor itself, and an owned resource still
closing -- and repeatedly read the real durable journal throughout that
window. The claim is a continuous negative: while either continues, no
terminal receipt and no timed-out condition may appear on disk.

The deadline windows are short and read against real time, because the
supervisor's own bounded waits are real waits; a frozen clock cannot expire
them. What the test controls is not the clock but the release of the live
thing, so the window stays open until the assertions have run rather than for
a guessed number of milliseconds.
"""

from __future__ import annotations

import asyncio
import contextlib
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
from ..persistence.events import OperationTerminalEvent
from ..persistence.journal import OperationPersistedSnapshot
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

_DEFINITION_ID = "operation.supervisor.deadline"
_PHASE = "operation.phase.work"

#: Aggregate window. It must NOT be able to expire before the executor has
#: entered: a window that does turns this into a proof about pre-entry refusal
#: rather than about outrunning live execution, and on a loaded machine that is
#: exactly what a few-millisecond window does. Entry takes milliseconds, so a
#: window of seconds cannot lose that race, while the executor is held open
#: afterwards so the window still expires underneath it for certain.
_EXECUTION_WINDOW = timedelta(seconds=2)

#: Cleanup window for the case that must outrun a held-open close. It has to
#: survive long enough for settlement to actually begin the close -- a window
#: that expires first makes the supervisor refuse before cleanup starts, which
#: is a different path than this case means to exercise. The close is then held
#: open indefinitely, so the window expires underneath it for certain rather
#: than by luck.
_SHORT_CLEANUP_WINDOW = timedelta(seconds=2)

#: Cleanup window for the case that must NOT elapse while the executor is held.
_WIDE_CLEANUP_WINDOW = timedelta(seconds=30)

#: Ceiling on every wait for a live thing to reach an expected state. A wait
#: that would otherwise block forever becomes a bounded, readable failure, so
#: a supervisor that never reaches the state reds instead of hanging.
_EVENT_CEILING = 15.0

#: How many times the durable journal is re-read while a live thing continues.
#: The negative invariant is checked on every read, so a terminal fact that
#: appeared at any point inside the window is caught rather than averaged away.
_WINDOW_OBSERVATIONS = 12


def _real_clock() -> datetime:
    """Read real UTC, which is the only clock the supervisor's waits obey."""
    return datetime.now(UTC)


async def _reach(event: asyncio.Event, *, described_as: str) -> None:
    """Wait for one expected live state, failing rather than hanging."""
    try:
        await asyncio.wait_for(event.wait(), timeout=_EVENT_CEILING)
    except TimeoutError:
        pytest.fail(f"the supervisor never reached the expected state: {described_as}")


class DeadlineRequest(BaseModel):
    """Encrypted operand reaching the real secure-reference adapter."""

    model_config = STRICT_FROZEN_CONFIG

    value: str = Field(min_length=1)


class DeadlineResult(BaseModel):
    """Registry result type for this deadline operation."""

    model_config = STRICT_FROZEN_CONFIG

    reference: str = Field(min_length=1)


class BlockingFileResource:
    """A real file handle whose close is held open until the test releases it."""

    def __init__(self, *, marker_path: Path) -> None:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = marker_path.open("xb")
        self._release = asyncio.Event()
        self.close_started = asyncio.Event()
        self.close_calls = 0

    @property
    def is_closed(self) -> bool:
        return self._handle.closed

    def release(self) -> None:
        self._release.set()

    async def close(self) -> None:
        self.close_calls += 1
        self.close_started.set()
        await self._release.wait()
        self._handle.close()


class HeldExecutor:
    """Run until released, then acknowledge whatever stop was requested."""

    def __init__(self, *, resource_root: Path, hold_before_acknowledge: bool) -> None:
        self._resource_root = resource_root
        self._hold_before_acknowledge = hold_before_acknowledge
        self.started = asyncio.Event()
        self.cancellation_observed = asyncio.Event()
        self.release = asyncio.Event()
        self.resource: BlockingFileResource | None = None

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        resource = BlockingFileResource(
            marker_path=self._resource_root / f"{context.identity.operation_id}.owned",
        )
        self.resource = resource
        context.cleanup.own(resource, family=OperationOwnedResource.ASYNC_TASK)
        await context.events.phase(_PHASE)
        self.started.set()

        while not context.cancellation.cancellation_requested:
            await asyncio.sleep(0.005)
        self.cancellation_observed.set()

        if self._hold_before_acknowledge:
            await self.release.wait()
        await context.cancellation.acknowledge_cancellation()
        return None


def _capabilities() -> OperationCapabilities:
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.COOPERATIVE,
        deadline=OperationDeadline.COOPERATIVE,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK}),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.PARTIAL, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def _definition(executor: HeldExecutor) -> OperationDefinition:
    return OperationDefinition(
        definition_id=_DEFINITION_ID,
        request_type=DeadlineRequest,
        result_type=DeadlineResult,
        executor_factory=OperationExecutorFactory(
            request_type=DeadlineRequest,
            executor_type=HeldExecutor,
            build=lambda: executor,
        ),
        phase_codes=(_PHASE,),
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
    executor: HeldExecutor,
    execution_timeout: timedelta,
    cleanup_timeout: timedelta,
) -> OperationSupervisor:
    definition = _definition(executor)
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.deadline.request",
            schema_version=1,
            model_type=DeadlineRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.deadline.result",
            schema_version=1,
            model_type=DeadlineResult,
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
        clock=_real_clock,
        lease_duration=timedelta(minutes=30),
        execution_timeout=execution_timeout,
        cleanup_timeout=cleanup_timeout,
    )


def _request(*, subject_ref: str) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=_DEFINITION_ID,
        subject_ref=subject_ref,
        payload=DeadlineRequest(value="encrypted-deadline-input"),
    )


async def _assert_no_terminal_published(
    journal: OperationJournalRepository,
    operation_id: str,
) -> OperationPersistedSnapshot:
    """Read the real durable record and refuse any published terminal fact."""
    snapshot = await journal.load(operation_id)
    replay = await journal.read_after(operation_id, 0, limit=64)

    assert snapshot.lifecycle is not OperationLifecycle.TERMINAL
    assert snapshot.terminal_condition is None
    assert snapshot.terminal_receipt is None
    assert not any(isinstance(event, OperationTerminalEvent) for event in replay.events)
    return snapshot


def test_elapsed_aggregate_deadline_publishes_nothing_while_the_executor_continues(tmp_path: Path) -> None:
    """An outrun executor keeps the record open until it actually stops."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state",
            profile_objects=profile.repository,
        )
        executor = HeldExecutor(resource_root=tmp_path / "owned-files", hold_before_acknowledge=True)
        supervisor = _supervisor(
            journal=journal,
            leases=leases,
            operands=operands,
            executor=executor,
            execution_timeout=_EXECUTION_WINDOW,
            cleanup_timeout=_WIDE_CLEANUP_WINDOW,
        )

        async def outrun_the_executor() -> None:
            operation_id = "a" * 64
            await supervisor.submit(_request(subject_ref="subject:aggregate"), operation_id=operation_id)
            start_task = asyncio.create_task(supervisor.start(operation_id))
            await _reach(executor.started, described_as="executor entry")

            # The supervisor asks for a stop once its own aggregate window
            # elapses. The executor deliberately does not acknowledge yet.
            await _reach(executor.cancellation_observed, described_as="cancellation observed by the executor")

            requested = await supervisor.inspect(operation_id)
            assert requested.execution_deadline is not None
            assert requested.cancellation_requested_at is not None
            assert requested.cancellation_requested_at >= requested.execution_deadline

            resource = executor.resource
            assert resource is not None

            # Throughout the window the executor keeps running, so nothing
            # terminal may reach disk -- least of all a timed-out claim.
            for _ in range(_WINDOW_OBSERVATIONS):
                during = await _assert_no_terminal_published(journal, operation_id)
                assert during.cancellation_acknowledged_at is None
                assert not start_task.done()
                assert not resource.is_closed
                await asyncio.sleep(0)

            resource.release()
            executor.release.set()
            terminal = await start_task

            assert terminal.lifecycle is OperationLifecycle.TERMINAL
            assert terminal.terminal_condition is OperationTerminalCondition.TIMED_OUT
            assert terminal.cancellation_acknowledged_at is not None
            assert resource.close_calls == 1
            assert resource.is_closed

        asyncio.run(outrun_the_executor())


def test_elapsed_cleanup_deadline_retains_uncertainty_while_an_owned_resource_closes(tmp_path: Path) -> None:
    """A resource still closing leaves the record unsettled, never falsely timed out."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state",
            profile_objects=profile.repository,
        )
        executor = HeldExecutor(resource_root=tmp_path / "owned-files", hold_before_acknowledge=False)
        supervisor = _supervisor(
            journal=journal,
            leases=leases,
            operands=operands,
            executor=executor,
            execution_timeout=_EXECUTION_WINDOW,
            cleanup_timeout=_SHORT_CLEANUP_WINDOW,
        )

        async def outrun_the_cleanup() -> None:
            operation_id = "b" * 64
            await supervisor.submit(_request(subject_ref="subject:cleanup"), operation_id=operation_id)
            start_task = asyncio.create_task(supervisor.start(operation_id))
            await _reach(executor.started, described_as="executor entry")
            await _reach(executor.cancellation_observed, described_as="cancellation observed by the executor")

            resource = executor.resource
            assert resource is not None
            await _reach(resource.close_started, described_as="supervisor-owned cleanup starting the close")

            # The owned close is genuinely in flight and stays that way. The
            # supervisor's cleanup window elapses underneath it; the loop below
            # is bounded by the supervisor giving up, not by a guessed sleep.
            observations = 0
            while not start_task.done():
                await _assert_no_terminal_published(journal, operation_id)
                assert not resource.is_closed
                observations += 1
                await asyncio.sleep(0.005)

            assert observations >= 1

            with contextlib.suppress(TimeoutError):
                await start_task

            # Uncertainty is retained, not resolved into a false terminal fact,
            # and the resource is still genuinely open.
            unsettled = await _assert_no_terminal_published(journal, operation_id)
            assert unsettled.lifecycle is OperationLifecycle.SETTLING
            assert unsettled.cancellation_requested_at is not None
            assert not resource.is_closed

            # Releasing the held close lets the retained cleanup finish, which
            # proves the resource was genuinely blocked rather than abandoned.
            resource.release()
            for _ in range(_WINDOW_OBSERVATIONS):
                if resource.is_closed:
                    break
                await asyncio.sleep(0.01)
            assert resource.is_closed
            assert resource.close_calls == 1

        asyncio.run(outrun_the_cleanup())
