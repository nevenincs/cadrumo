"""Real terminal-lifecycle proofs for :class:`OperationSupervisor`."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from ....adapters.persistence.operations import (
    OperationJournalRepository,
    OperationLeaseFilesystemRepository,
    OperationSecureReferenceRepository,
)
from ....adapters.persistence.storage import (
    SecureObjectNamespaceDefinition,
    SecureObjectRepository,
    StorageCustodyDisposition,
    StorageNamespaceScope,
)
from ....core import STRICT_FROZEN_CONFIG
from ....core.classification import SensitivityClass
from ....tests.secure_namespace_registration import registered_objects as _registered_objects
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    OperationBaselinePolicy,
    OperationCancellation,
    OperationCapabilities,
    OperationClosePolicy,
    OperationConflictScope,
    OperationDeadline,
    OperationDefinition,
    OperationDurability,
    OperationEffect,
    OperationExecutorContext,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationLifecycle,
    OperationOwnedResource,
    OperationPersistedSnapshot,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationReplayPolicy,
    OperationRequest,
    OperationSensitiveInputPolicy,
    OperationSupervisor,
    OperationTerminalCondition,
    OperationTerminalEvent,
    OperationTerminalReceipt,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 14, 18, tzinfo=UTC)

#: Cleanup window for the deadline-expiry proof below.
#:
#: The window is measured from the moment cancellation is REQUESTED, not from
#: the moment settlement begins the owned close, so everything the test does in
#: between spends it: awaiting the start task and two journal round-trips
#: through real SQLite. At 30ms it was routinely gone before settlement ran, and
#: ``_complete_cleanup_before_settlement`` then took its early
#: ``now >= cleanup_deadline`` exit and refused WITHOUT starting the close --
#: leaving ``cleanup_started`` unset and the test awaiting it forever. On this
#: platform that wedges the whole session rather than one test, because a
#: thread-based timeout cannot interrupt a blocked event loop.
#:
#: The clock cannot be frozen to remove the race: the operation lease is
#: evaluated against real time, so a frozen supervisor clock fails the settle
#: with "operation exact lease expired before renewal" instead.
#:
#: A second is far beyond the setup cost and still bounds the test, and once the
#: close has started the refusal is deterministic regardless of the window,
#: because the resource holds its cleanup until the test releases it.
_CLEANUP_WINDOW = timedelta(seconds=1)
_NAMESPACE = SecureObjectNamespaceDefinition(
    key="operation_supervisor_lifecycle_test",
    namespace="cadrumo-test.operations.supervisor-lifecycle",
    owner="cadrumo.application.operations.tests.test_supervisor_lifecycle",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=1,
    object_key_grammar="{content_digest}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)


class LifecycleRequest(BaseModel):
    """Concrete encrypted operand that reaches the real secure-reference adapter."""

    model_config = STRICT_FROZEN_CONFIG

    value: str = Field(min_length=1)


class LifecycleResult(BaseModel):
    """Concrete registry result type for this terminal-lifecycle operation."""

    model_config = STRICT_FROZEN_CONFIG

    reference: str = Field(min_length=1)


class JournalObservedFileResource:
    """One real open file whose close records the durable lifecycle it observed."""

    def __init__(
        self,
        *,
        journal: OperationJournalRepository,
        operation_id: str,
        marker_path: Path,
        hold_cleanup: bool,
    ) -> None:
        self._journal = journal
        self._operation_id = operation_id
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = marker_path.open("xb")
        self._allow_cleanup = asyncio.Event()
        if not hold_cleanup:
            self._allow_cleanup.set()
        self.cleanup_started = asyncio.Event()
        self.closed = asyncio.Event()
        self.close_calls = 0
        self.lifecycle_at_close: OperationLifecycle | None = None

    @property
    def is_closed(self) -> bool:
        return self._handle.closed

    def allow_cleanup(self) -> None:
        self._allow_cleanup.set()

    async def close(self) -> None:
        snapshot = await self._journal.load(self._operation_id)
        self.lifecycle_at_close = snapshot.lifecycle
        self.close_calls += 1
        self.cleanup_started.set()
        await self._allow_cleanup.wait()
        self._handle.close()
        self.closed.set()


class CleanupFailingFileResource(JournalObservedFileResource):
    """A real file close that reports a cleanup error after releasing its handle."""

    async def close(self) -> None:
        await super().close()
        raise OSError("terminal lifecycle cleanup reporting failed")


class LifecycleExecutor:
    """Concrete executor that publishes one declared effect and transfers an owned file."""

    def __init__(
        self,
        *,
        journal: OperationJournalRepository,
        resource_root: Path,
        effect: OperationEffect,
        await_cancellation: bool,
        resource_type: type[JournalObservedFileResource] = JournalObservedFileResource,
        hold_cleanup: bool = True,
    ) -> None:
        self._journal = journal
        self._resource_root = resource_root
        self._effect = effect
        self._await_cancellation = await_cancellation
        self._resource_type = resource_type
        self._hold_cleanup = hold_cleanup
        self.started = asyncio.Event()
        self.resource: JournalObservedFileResource | None = None

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        resource = self._resource_type(
            journal=self._journal,
            operation_id=context.identity.operation_id,
            marker_path=self._resource_root / f"{context.identity.operation_id}.owned",
            hold_cleanup=self._hold_cleanup,
        )
        self.resource = resource
        context.cleanup.own(resource, family=OperationOwnedResource.ASYNC_TASK)
        await context.events.effect(self._effect)
        self.started.set()
        if self._await_cancellation:
            while not context.cancellation.cancellation_requested:
                await asyncio.sleep(0)
            await context.cancellation.acknowledge_cancellation()
        return None


@dataclass(frozen=True)
class TerminalCase:
    condition: OperationTerminalCondition
    effect: OperationEffect
    result_ref: str | None = None
    refusal_ref: str | None = None
    await_cancellation: bool = False


_TERMINAL_CASES = (
    TerminalCase(
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        result_ref="result:lifecycle-complete",
    ),
    TerminalCase(
        condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.PARTIAL,
        refusal_ref="refusal:lifecycle-policy",
    ),
    TerminalCase(
        condition=OperationTerminalCondition.FAILED,
        effect=OperationEffect.UPDATED,
    ),
    TerminalCase(
        condition=OperationTerminalCondition.CANCELLED,
        effect=OperationEffect.NONE,
        await_cancellation=True,
    ),
    TerminalCase(
        condition=OperationTerminalCondition.TIMED_OUT,
        effect=OperationEffect.PARTIAL,
    ),
    TerminalCase(
        condition=OperationTerminalCondition.INTERRUPTED,
        effect=OperationEffect.UNKNOWN,
    ),
)


def _repositories(
    *,
    storage_root: Path,
    profile_objects: SecureObjectRepository,
) -> tuple[OperationJournalRepository, OperationLeaseFilesystemRepository, OperationSecureReferenceRepository]:
    return (
        OperationJournalRepository(storage_root=storage_root),
        OperationLeaseFilesystemRepository(storage_root=storage_root),
        OperationSecureReferenceRepository(objects=_registered_objects(profile_objects, _NAMESPACE), namespace=_NAMESPACE),
    )


def _supervisor(
    *,
    journal: OperationJournalRepository,
    leases: OperationLeaseFilesystemRepository,
    operands: OperationSecureReferenceRepository,
    executor: LifecycleExecutor,
    clock: Callable[[], datetime] = lambda: _NOW,
    cleanup_timeout: timedelta = timedelta(minutes=1),
) -> OperationSupervisor:
    capabilities = OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.COOPERATIVE,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.NONE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK}),
        permitted_effects=frozenset(OperationEffect),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )
    definition = OperationDefinition(
        definition_id="operation.supervisor.lifecycle",
        request_type=LifecycleRequest,
        result_type=LifecycleResult,
        executor_factory=OperationExecutorFactory(
            request_type=LifecycleRequest,
            executor_type=LifecycleExecutor,
            build=lambda: executor,
        ),
        phase_codes=("operation.phase.lifecycle",),
        interaction_kinds=frozenset(),
        capabilities=capabilities,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
    )
    return OperationSupervisor(
        registry=OperationRegistry(definitions=(definition,)),
        journal=journal,
        event_stream=journal,
        leases=leases,
        operands=operands,
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=clock,
        lease_duration=timedelta(minutes=10),
        cleanup_timeout=cleanup_timeout,
    )


def _request(*, subject_ref: str) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id="operation.supervisor.lifecycle",
        subject_ref=subject_ref,
        payload=LifecycleRequest(value="encrypted-lifecycle-input"),
    )


def _receipt(
    snapshot: OperationPersistedSnapshot,
    case: TerminalCase,
    *,
    settled_at: datetime,
) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=snapshot.identity,
        revision=snapshot.revision + 1,
        condition=case.condition,
        effect=case.effect,
        settled_at=settled_at,
        result_ref=case.result_ref,
        refusal_ref=case.refusal_ref,
    )


@pytest.mark.parametrize("case", _TERMINAL_CASES, ids=lambda case: case.condition.value)
def test_every_terminal_condition_waits_for_owned_file_cleanup_and_preserves_effect(
    tmp_path: Path,
    case: TerminalCase,
) -> None:
    """Every terminal fact commits after a real close and retains its independent effect."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        executor = LifecycleExecutor(
            journal=journal,
            resource_root=tmp_path / "owned-files",
            effect=case.effect,
            await_cancellation=case.await_cancellation,
        )
        supervisor = _supervisor(journal=journal, leases=leases, operands=operands, executor=executor)

        async def settle_after_observed_cleanup() -> None:
            operation_id = f"{case.condition.value.__len__():064x}"
            await supervisor.submit(_request(subject_ref=f"subject:{case.condition.value}"), operation_id=operation_id)
            if case.await_cancellation:
                start_task = asyncio.create_task(supervisor.start(operation_id))
                await executor.started.wait()
                await supervisor.request_cancel(operation_id)
                ready_for_settlement = await start_task
            else:
                ready_for_settlement = await supervisor.start(operation_id)

            resource = executor.resource
            assert resource is not None
            terminal_waiter = asyncio.create_task(supervisor.await_terminal(operation_id))
            settlement_task = asyncio.create_task(
                supervisor.settle(operation_id, _receipt(ready_for_settlement, case, settled_at=_NOW))
            )
            await resource.cleanup_started.wait()

            during_cleanup = await supervisor.inspect(operation_id)
            assert during_cleanup == ready_for_settlement
            assert during_cleanup.lifecycle is not OperationLifecycle.TERMINAL
            assert resource.lifecycle_at_close is not OperationLifecycle.TERMINAL
            assert not resource.is_closed
            assert not terminal_waiter.done()
            replay_before_close = await journal.read_after(operation_id, 0, limit=20)
            assert not any(isinstance(event, OperationTerminalEvent) for event in replay_before_close.events)

            resource.allow_cleanup()
            terminal = await settlement_task
            awaited_terminal = await terminal_waiter
            replay = await journal.read_after(operation_id, 0, limit=20)

            assert resource.closed.is_set()
            assert resource.is_closed
            assert resource.close_calls == 1
            assert awaited_terminal == terminal
            assert terminal.lifecycle is OperationLifecycle.TERMINAL
            assert terminal.terminal_condition is case.condition
            assert terminal.effect is case.effect
            assert terminal.terminal_receipt is not None
            assert terminal.terminal_receipt.effect is case.effect
            assert isinstance(replay.events[-1], OperationTerminalEvent)
            assert replay.events[-1].receipt == terminal.terminal_receipt

        asyncio.run(settle_after_observed_cleanup())


def test_cleanup_failure_refuses_terminal_journal_persistence(tmp_path: Path) -> None:
    """A reported owned-resource close failure leaves the real journal nonterminal."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        executor = LifecycleExecutor(
            journal=journal,
            resource_root=tmp_path / "owned-files",
            effect=OperationEffect.UPDATED,
            await_cancellation=False,
            resource_type=CleanupFailingFileResource,
            hold_cleanup=False,
        )
        supervisor = _supervisor(journal=journal, leases=leases, operands=operands, executor=executor)
        case = _TERMINAL_CASES[0]

        async def refuse_terminal_after_cleanup_failure() -> None:
            operation_id = "3" * 64
            await supervisor.submit(_request(subject_ref="subject:cleanup-failure"), operation_id=operation_id)
            running = await supervisor.start(operation_id)
            resource = executor.resource
            assert resource is not None

            with pytest.raises(RuntimeError, match="cleanup"):
                await supervisor.settle(operation_id, _receipt(running, case, settled_at=_NOW))

            persisted = await supervisor.inspect(operation_id)
            replay = await journal.read_after(operation_id, 0, limit=20)
            assert resource.closed.is_set()
            assert resource.is_closed
            assert resource.lifecycle_at_close is OperationLifecycle.RUNNING
            assert persisted == running
            assert persisted.lifecycle is not OperationLifecycle.TERMINAL
            assert not any(isinstance(event, OperationTerminalEvent) for event in replay.events)

        asyncio.run(refuse_terminal_after_cleanup_failure())


def test_cleanup_timeout_refuses_terminal_journal_persistence(tmp_path: Path) -> None:
    """A deadline-expired owned close remains settling instead of publishing cancellation.

    The clock is the module's frozen one rather than wall time, and that is what
    makes the deadline expire for the reason under test.

    The cleanup deadline starts when cancellation is REQUESTED, while the window
    the test cares about opens later, when settlement begins the owned close.
    Read against wall time, every await in between spends the deadline, so on a
    loaded machine it was already elapsed by the time settlement ran:
    ``_complete_cleanup_before_settlement`` then took its early ``now >=
    cleanup_deadline`` exit and refused before starting the close at all.
    ``cleanup_started`` was therefore never set and the test waited on it
    forever, which wedged the whole session rather than one test, because the
    thread-based timeout cannot interrupt a blocked event loop here.

    Frozen, the deadline cannot be spent by setup. Settlement reaches the close,
    the resource records that it started, and the deadline then expires the only
    way this test means: the blocked cleanup task is still unfinished when the
    supervisor's bounded wait elapses. Same refusal, same assertions, reached by
    the path the test is named for -- and in milliseconds rather than seconds,
    since the deadline stays 30ms of real waiting rather than a headroom margin
    wide enough to out-run scheduling jitter.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        executor = LifecycleExecutor(
            journal=journal,
            resource_root=tmp_path / "owned-files",
            effect=OperationEffect.NONE,
            await_cancellation=True,
        )
        supervisor = _supervisor(
            journal=journal,
            leases=leases,
            operands=operands,
            executor=executor,
            clock=lambda: datetime.now(UTC),
            cleanup_timeout=_CLEANUP_WINDOW,
        )
        case = _TERMINAL_CASES[3]

        async def retain_nonterminal_state_after_cleanup_timeout() -> None:
            operation_id = "4" * 64
            await supervisor.submit(_request(subject_ref="subject:cleanup-timeout"), operation_id=operation_id)
            start_task = asyncio.create_task(supervisor.start(operation_id))
            await executor.started.wait()
            await supervisor.request_cancel(operation_id)
            settling = await start_task
            assert settling.lifecycle is OperationLifecycle.SETTLING
            resource = executor.resource
            assert resource is not None

            terminal_waiter = asyncio.create_task(supervisor.await_terminal(operation_id))
            settlement_task = asyncio.create_task(
                supervisor.settle(
                    operation_id,
                    _receipt(settling, case, settled_at=datetime.now(UTC)),
                )
            )
            await resource.cleanup_started.wait()
            with pytest.raises(TimeoutError, match="cleanup deadline"):
                await settlement_task

            unsettled = await supervisor.inspect(operation_id)
            replay = await journal.read_after(operation_id, 0, limit=20)
            assert unsettled == settling
            assert unsettled.lifecycle is OperationLifecycle.SETTLING
            assert unsettled.terminal_receipt is None
            assert resource.lifecycle_at_close is OperationLifecycle.SETTLING
            assert not resource.is_closed
            assert not terminal_waiter.done()
            assert not any(isinstance(event, OperationTerminalEvent) for event in replay.events)

            resource.allow_cleanup()
            await resource.closed.wait()
            terminal_waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await terminal_waiter

        asyncio.run(retain_nonterminal_state_after_cleanup_timeout())
