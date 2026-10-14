"""Real durable-operation proofs exercised through :class:`OperationSupervisor`."""

from __future__ import annotations

import asyncio
import gc
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.namespace_registry import STORAGE_NAMESPACE_REGISTRY
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_ephemeral_secure_sql,
    isolated_runtime_profile,
)
from cadrumo.application.operations.capabilities import (
    OperationOwnedResource,
)
from cadrumo.application.operations.errors import (
    OperationDeclarationError,
    OperationUnsettledError,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from cadrumo.application.operations.interactions import (
    OperationApplyResponse,
)
from cadrumo.application.operations.models import (
    OperationTerminalReceipt,
)
from cadrumo.application.operations.observation import OperationObservationService
from cadrumo.application.operations.persistence.events import (
    OperationDiagnosticEvent,
    OperationTerminalEvent,
)
from cadrumo.application.operations.persistence.journal import (
    OperationPersistedSnapshot,
)
from cadrumo.core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationEffect,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
)

from .supervision_support import run_to_settlement
from .supervisor_test_support import (
    _NOW,
    CancellableResourceExecutor,
    CleanupDeadlineExecutor,
    DeadlineAcknowledgingExecutor,
    DeclaredResourceExecutor,
    IdleExecutor,
    IrreversibleSectionExecutor,
    ReviewExecutor,
    UnacknowledgedCancellationExecutor,
    UndeclaredPhaseExecutor,
    WaitingExecutor,
    _admission_supervisor,
    _capabilities,
    _close_host_over_live_executor,
    _failure_logged,
    _registry,
    _repositories,
    _request,
    _response,
    _start_and_walk_away,
    _supervisor,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def test_host_close_cancels_a_detachable_operation_without_false_terminal_artifacts(tmp_path: Path) -> None:
    """Abandoning a wait leaves the operation running; closing the host cancels it, settling nothing."""
    executor = CancellableResourceExecutor()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        supervisor = _supervisor(
            registry=_registry(
                executor_type=CancellableResourceExecutor,
                build=lambda: executor,
                capabilities=_capabilities(
                    owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK}),
                ),
            ),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )

        async def cancel_then_settle() -> tuple[OperationPersistedSnapshot, OperationPersistedSnapshot]:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            start_task = asyncio.create_task(run_to_settlement(supervisor, operation_id))
            await executor.started.wait()
            start_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await start_task
            assert executor.cancelled is False, "abandoning the wait must leave the operation running"
            await supervisor.shutdown()

            running = await supervisor.inspect(operation_id)
            replay = await journal.read_after(operation_id, 0, limit=10)
            assert executor.cancelled is True
            assert running.lifecycle is OperationLifecycle.RUNNING
            assert running.terminal_receipt is None
            assert running.terminal_condition is None
            assert running.revision == 1
            assert not any(isinstance(event, OperationDiagnosticEvent) for event in replay.events)
            assert not any(isinstance(event, OperationTerminalEvent) for event in replay.events)

            settled = await supervisor.settle(
                operation_id,
                OperationTerminalReceipt(
                    identity=running.identity,
                    revision=running.revision + 1,
                    condition=OperationTerminalCondition.FAILED,
                    effect=OperationEffect.NONE,
                    settled_at=_NOW,
                ),
            )
            return running, settled

        running, settled = asyncio.run(cancel_then_settle())
        assert running.terminal_receipt is None
        assert settled.lifecycle is OperationLifecycle.TERMINAL
        assert settled.terminal_condition is OperationTerminalCondition.FAILED
        assert executor.resource.close_calls == 1


@pytest.mark.parametrize("intent", ("apply", "reject"))
def test_response_consumption_is_exact_single_use_and_durable_across_supervisor_restart(
    tmp_path: Path,
    intent: str,
) -> None:
    """Apply and reject both consume one persisted checkpoint once across restart."""
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
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))
        waiting = asyncio.run(run_to_settlement(supervisor, operation_id))
        assert waiting.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
        assert waiting.pending_interaction is not None

        restarted = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        response = _response(intent=intent, operation_id=operation_id, revision=waiting.revision)
        if isinstance(response, OperationApplyResponse):
            consumed = asyncio.run(restarted.respond(response))
        else:
            consumed = asyncio.run(restarted.reject(response))

        persisted = asyncio.run(journal.load(operation_id))
        assert persisted.pending_interaction is None
        assert persisted.consumed_interactions == (consumed,)
        assert persisted.lifecycle is OperationLifecycle.RUNNING

        duplicate = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        with pytest.raises(ValueError, match="not pending"):
            if isinstance(response, OperationApplyResponse):
                asyncio.run(duplicate.respond(response))
            else:
                asyncio.run(duplicate.reject(response))
        assert asyncio.run(journal.load(operation_id)) == persisted


def test_await_terminal_waits_for_a_real_durable_settlement(tmp_path: Path) -> None:
    """Awaiting a live operation reloads until its terminal journal record exists."""
    with isolated_ephemeral_secure_sql(tmp_path=tmp_path):
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state",
            profile_objects=SecureObjectRepository(namespace_registry=STORAGE_NAMESPACE_REGISTRY),
        )
        supervisor = _supervisor(
            registry=_registry(executor_type=IdleExecutor, build=IdleExecutor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))
        pending = asyncio.run(journal.load(operation_id))

        async def await_after_settlement() -> OperationPersistedSnapshot:
            waiter = asyncio.create_task(supervisor.await_terminal(operation_id))
            await asyncio.sleep(0)
            assert not waiter.done()
            await supervisor.settle(
                operation_id,
                OperationTerminalReceipt(
                    identity=pending.identity,
                    revision=pending.revision + 1,
                    condition=OperationTerminalCondition.SUCCEEDED,
                    effect=OperationEffect.NONE,
                    settled_at=_NOW,
                    result_ref="result:awaited-settlement",
                ),
            )
            return await waiter

        terminal = asyncio.run(await_after_settlement())
        assert terminal.lifecycle is OperationLifecycle.TERMINAL


def test_await_terminal_sustained_wait_uses_bounded_real_journal_reads(tmp_path: Path) -> None:
    """A non-terminal durable wait backs off instead of repeatedly opening its real journal file."""
    with isolated_ephemeral_secure_sql(tmp_path=tmp_path):
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(
            storage_root=storage_root,
            profile_objects=SecureObjectRepository(namespace_registry=STORAGE_NAMESPACE_REGISTRY),
        )
        supervisor = _supervisor(
            registry=_registry(executor_type=IdleExecutor, build=IdleExecutor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))
        journal_path = (storage_root / "operation-journals" / f"{operation_id}.json").resolve()
        journal_opens = [0]
        # An audit hook cannot be removed, so it outlives this test in the worker.
        # Disarmed after the measurement, it returns before resolving anything, so
        # no later test pays for or observes the resolve this hook performs.
        recording = [True]

        def audit_open(event: str, arguments: tuple[object, ...]) -> None:
            if not recording[0] or event != "open" or not arguments:
                return
            opened_argument = arguments[0]
            if not isinstance(opened_argument, str):
                return
            try:
                opened_path = Path(opened_argument).resolve()
            except (OSError, TypeError):
                return
            if opened_path == journal_path:
                journal_opens[0] += 1

        sys.addaudithook(audit_open)

        async def sustain_non_terminal_wait() -> None:
            waiter = asyncio.create_task(supervisor.await_terminal(operation_id))
            await asyncio.sleep(0.13)
            assert not waiter.done()
            assert 1 <= journal_opens[0] <= 3
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter

        try:
            asyncio.run(sustain_non_terminal_wait())
        finally:
            recording[0] = False


def test_token_mismatch_refuses_interaction_mutation_before_consumption(tmp_path: Path) -> None:
    """An equal owner ID cannot adopt another supervisor's different lease token."""
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
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(owner.submit(_request(), operation_id="3" * 64))
        waiting = asyncio.run(run_to_settlement(owner, operation_id))
        intruder = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="4" * 64,
        )
        response = _response(intent="apply", operation_id=operation_id, revision=waiting.revision)

        with pytest.raises(ValueError, match="not owned"):
            asyncio.run(intruder.respond(response))
        assert asyncio.run(journal.load(operation_id)) == waiting
        consumed = asyncio.run(owner.respond(response))
        assert asyncio.run(journal.load(operation_id)).consumed_interactions == (consumed,)


def test_request_cancel_persists_an_event_free_revision_and_later_terminal_event(tmp_path: Path) -> None:
    """Cancellation retains prior history without inventing a lifecycle event."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        executor = UnacknowledgedCancellationExecutor()
        registry = _registry(
            executor_type=UnacknowledgedCancellationExecutor,
            build=lambda: executor,
            capabilities=_capabilities(cancellation=OperationCancellation.COOPERATIVE),
        )
        supervisor = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))

        async def cancel_live_executor() -> tuple[
            OperationPersistedSnapshot, OperationPersistedSnapshot, OperationPersistedSnapshot
        ]:
            start_task = asyncio.create_task(run_to_settlement(supervisor, operation_id))
            await executor.started.wait()
            running = await supervisor.inspect(operation_id)
            cancellation = await supervisor.request_cancel(operation_id)
            # The executor stops without acknowledging, so the request stays
            # unsettled for the explicit terminal receipt below.
            stopped = await start_task
            return running, cancellation, stopped

        running, cancellation, stopped = asyncio.run(cancel_live_executor())

        assert stopped == cancellation
        assert running.revision == 1
        assert cancellation.lifecycle is OperationLifecycle.CANCELLATION_REQUESTED
        assert cancellation.revision == 2
        assert cancellation.events == ()
        assert cancellation.event_cursor == running.event_cursor

        terminal = asyncio.run(
            supervisor.settle(
                operation_id,
                OperationTerminalReceipt(
                    identity=cancellation.identity,
                    revision=cancellation.revision + 1,
                    condition=OperationTerminalCondition.FAILED,
                    effect=OperationEffect.NONE,
                    settled_at=_NOW,
                ),
            )
        )
        replay = asyncio.run(journal.read_after(operation_id, 0, limit=10))

        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert tuple(event.sequence for event in replay.events) == (1, 2)
        assert tuple(event.revision for event in replay.events) == (1, 3)


def test_aggregate_deadline_requests_cooperative_stop_before_timed_out_cleanup_settlement(tmp_path: Path) -> None:
    """A real deadline acknowledgement settles as timed out after owned cleanup."""
    executor = DeadlineAcknowledgingExecutor()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
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

        async def run_deadline_controlled_operation() -> OperationPersistedSnapshot:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            start_task = asyncio.create_task(run_to_settlement(supervisor, operation_id))
            await executor.started.wait()
            return await start_task

        terminal = asyncio.run(run_deadline_controlled_operation())

    assert terminal.lifecycle is OperationLifecycle.TERMINAL
    assert terminal.terminal_condition is OperationTerminalCondition.TIMED_OUT
    assert terminal.effect is OperationEffect.NONE
    assert terminal.cancellation_requested_at is not None
    assert terminal.execution_deadline is not None
    assert terminal.cancellation_requested_at >= terminal.execution_deadline
    assert terminal.cancellation_acknowledged_at is not None
    assert terminal.cleanup_deadline is not None
    assert executor.resource.close_calls == 1


def test_cancelled_terminal_refuses_an_executor_that_stopped_without_acknowledging(tmp_path: Path) -> None:
    """Returning from work is not interchangeable with the executor's durable safe-stop fact."""
    executor = UnacknowledgedCancellationExecutor()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        supervisor = _supervisor(
            registry=_registry(
                executor_type=UnacknowledgedCancellationExecutor,
                build=lambda: executor,
                capabilities=_capabilities(cancellation=OperationCancellation.COOPERATIVE),
            ),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )

        async def stop_without_acknowledgement() -> OperationPersistedSnapshot:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            start_task = asyncio.create_task(run_to_settlement(supervisor, operation_id))
            await executor.started.wait()
            requested = await supervisor.request_cancel(operation_id)
            stopped = await start_task
            assert requested.cancellation_requested_at is not None
            assert stopped.cancellation_acknowledged_at is None
            with pytest.raises(ValueError, match="durable executor acknowledgement"):
                await supervisor.settle(
                    operation_id,
                    OperationTerminalReceipt(
                        identity=stopped.identity,
                        revision=stopped.revision + 1,
                        condition=OperationTerminalCondition.CANCELLED,
                        effect=OperationEffect.NONE,
                        settled_at=_NOW,
                    ),
                )
            return await supervisor.inspect(operation_id)

        unsettled = asyncio.run(stop_without_acknowledgement())

    assert unsettled.lifecycle is OperationLifecycle.CANCELLATION_REQUESTED
    assert unsettled.terminal_receipt is None


def test_irreversible_section_allows_request_but_refuses_acknowledgement_until_exit(tmp_path: Path) -> None:
    """An unsafe mutation completes before its executor can acknowledge a cooperative stop."""
    executor = IrreversibleSectionExecutor()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        registry = _registry(
            executor_type=IrreversibleSectionExecutor,
            build=lambda: executor,
            capabilities=_capabilities(cancellation=OperationCancellation.COOPERATIVE),
        )
        supervisor = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )

        async def request_during_irreversible_section() -> OperationPersistedSnapshot:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            start_task = asyncio.create_task(run_to_settlement(supervisor, operation_id))
            await executor.entered.wait()
            observation = await OperationObservationService(reader=journal, registry=registry).observe(
                OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=20)
            )
            assert isinstance(observation, OperationObservationSuccessV1)
            assert observation.projection.lifecycle is OperationLifecycle.RUNNING
            assert not observation.projection.cancellable_now
            assert (await supervisor.inspect(operation_id)).cancellation_deferred
            requested = await supervisor.request_cancel(operation_id)
            assert executor.context is not None
            with pytest.raises(ValueError, match="irreversible section"):
                await executor.context.cancellation.acknowledge_cancellation()
            assert requested.cancellation_requested_at is not None
            assert (await supervisor.inspect(operation_id)).cancellation_acknowledged_at is None
            executor.exit_requested.set()
            return await start_task

        terminal = asyncio.run(request_during_irreversible_section())
        assert not terminal.cancellation_deferred

    assert terminal.lifecycle is OperationLifecycle.TERMINAL
    assert terminal.cancellation_requested_at is not None
    assert terminal.cancellation_acknowledged_at is not None
    assert terminal.effect is OperationEffect.NONE
    assert terminal.terminal_condition is OperationTerminalCondition.CANCELLED


def test_cleanup_deadline_escalates_to_settling_without_a_false_timeout_terminal(tmp_path: Path) -> None:
    """A cooperative executor still running beyond cleanup grace leaves durable uncertainty open."""
    executor = CleanupDeadlineExecutor()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        supervisor = _supervisor(
            registry=_registry(
                executor_type=CleanupDeadlineExecutor,
                build=lambda: executor,
                capabilities=_capabilities(
                    cancellation=OperationCancellation.COOPERATIVE,
                    deadline=OperationDeadline.COOPERATIVE,
                ),
            ),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            clock=lambda: datetime.now(UTC),
            execution_timeout=timedelta(milliseconds=30),
            cleanup_timeout=timedelta(milliseconds=50),
        )

        async def let_cleanup_deadline_elapse() -> OperationPersistedSnapshot:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            start_task = asyncio.create_task(run_to_settlement(supervisor, operation_id))
            await executor.cancellation_observed.wait()
            # Wait for the escalation itself rather than a fixed interval: under
            # load the cleanup deadline can elapse later than a sleep assumes.
            async with asyncio.timeout(10):
                escalating = await supervisor.inspect(operation_id)
                while escalating.lifecycle is not OperationLifecycle.SETTLING:
                    await asyncio.sleep(0.01)
                    escalating = await supervisor.inspect(operation_id)
            executor.release.set()
            finished = await start_task
            assert finished == escalating
            return escalating

        unsettled = asyncio.run(let_cleanup_deadline_elapse())

    assert unsettled.lifecycle is OperationLifecycle.SETTLING
    assert unsettled.cancellation_requested_at is not None
    assert unsettled.cancellation_acknowledged_at is None
    assert unsettled.terminal_receipt is None


def test_settle_refuses_definition_forbidden_effect_before_cleanup_or_journal_mutation(tmp_path: Path) -> None:
    """Terminal effects use the same definition capability boundary as executor facts."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        executor = DeclaredResourceExecutor()
        supervisor = _supervisor(
            registry=_registry(
                executor_type=DeclaredResourceExecutor,
                build=lambda: executor,
                capabilities=_capabilities(owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK})),
            ),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))
        running = asyncio.run(_close_host_over_live_executor(supervisor, operation_id, executor.started))

        assert running.lifecycle is OperationLifecycle.RUNNING
        with pytest.raises(OperationDeclarationError, match="terminal receipt effect is not declared"):
            asyncio.run(
                supervisor.settle(
                    operation_id,
                    OperationTerminalReceipt(
                        identity=running.identity,
                        revision=running.revision + 1,
                        condition=OperationTerminalCondition.SUCCEEDED,
                        effect=OperationEffect.UPDATED,
                        settled_at=_NOW,
                        result_ref="result:complete",
                    ),
                )
            )

        assert executor.resource is not None
        assert executor.resource.close_calls == 0
        assert asyncio.run(journal.load(operation_id)) == running


def test_start_returns_the_admitted_running_state_while_the_executor_still_works(tmp_path: Path) -> None:
    """A caller can show progress: admission is durable and observable before execution ends."""
    started = asyncio.Event()
    release = asyncio.Event()
    executor = WaitingExecutor(started=started, release=release)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        supervisor, journal = _admission_supervisor(
            tmp_path, profile.repository, executor_type=WaitingExecutor, build=lambda: executor
        )

        async def admit_then_settle() -> tuple[OperationPersistedSnapshot, OperationPersistedSnapshot, bool]:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            admitted = await supervisor.start(operation_id)
            observed = await journal.load(operation_id)
            await started.wait()
            executor_was_still_working = not release.is_set()
            release.set()
            await supervisor.settled(operation_id)
            return admitted, observed, executor_was_still_working

        admitted, observed, executor_was_still_working = asyncio.run(admit_then_settle())

    assert admitted.lifecycle is OperationLifecycle.RUNNING
    assert admitted.executor_entered_at is not None
    assert observed == admitted
    assert executor_was_still_working
    assert executor.cancelled is False


def test_settled_raises_the_journal_state_when_the_task_stops_without_settling(tmp_path: Path) -> None:
    """A declaration breach is never settled; the waiter receives the durable state and the cause."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        supervisor, _journal = _admission_supervisor(
            tmp_path, profile.repository, executor_type=UndeclaredPhaseExecutor, build=UndeclaredPhaseExecutor
        )

        async def start_then_wait() -> OperationUnsettledError:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            await supervisor.start(operation_id)
            with pytest.raises(OperationUnsettledError) as unsettled:
                await supervisor.settled(operation_id)
            return unsettled.value

        unsettled = asyncio.run(start_then_wait())

    assert unsettled.snapshot.lifecycle is OperationLifecycle.RUNNING
    assert unsettled.snapshot.terminal_receipt is None
    assert isinstance(unsettled.__cause__, OperationDeclarationError)


def test_a_task_failure_nobody_awaits_is_logged_and_never_orphaned(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """No 'exception was never retrieved': the supervisor retrieves and logs the failure itself."""
    with caplog.at_level(logging.ERROR):
        left_running = _start_and_walk_away(tmp_path, caplog)
        gc.collect()

    assert _failure_logged(caplog)
    assert left_running.lifecycle is OperationLifecycle.RUNNING
    assert not any("never retrieved" in record.getMessage() for record in caplog.records)


def test_host_close_asks_a_cancellable_operation_to_stop_and_settles_it(tmp_path: Path) -> None:
    """A non-detachable operation is cancelled cooperatively within its cleanup window, then settled."""
    executor = DeadlineAcknowledgingExecutor()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        supervisor, journal = _admission_supervisor(
            tmp_path,
            profile.repository,
            executor_type=DeadlineAcknowledgingExecutor,
            build=lambda: executor,
            capabilities=_capabilities(
                cancellation=OperationCancellation.COOPERATIVE,
                owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK}),
                close_policy=OperationClosePolicy.REQUEST_CANCEL,
            ),
        )

        async def start_then_close() -> OperationPersistedSnapshot:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            await supervisor.start(operation_id)
            await executor.started.wait()
            await supervisor.shutdown()
            return await journal.load(operation_id)

        closed = asyncio.run(start_then_close())

    assert closed.lifecycle is OperationLifecycle.TERMINAL
    assert closed.terminal_condition is OperationTerminalCondition.CANCELLED
    assert executor.resource.close_calls == 1
