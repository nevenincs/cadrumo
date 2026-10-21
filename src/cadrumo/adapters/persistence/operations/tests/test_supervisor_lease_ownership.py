"""Real durable-operation proofs exercised through :class:`OperationSupervisor`."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.errors import RepositoryError
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
    OperationSubjectBusyError,
)
from cadrumo.application.operations.models import (
    OperationReconciliationOutcome,
    OperationTerminalReceipt,
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
from cadrumo.core.errors.error_codes import ErrorCategory, get_registered_error_code, resolve_error_message
from cadrumo.core.i18n.render import tr
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)

from .supervision_support import run_to_settlement
from .supervisor_test_support import (
    _NOW,
    _SHARED_SUBJECT,
    DeclaredResourceExecutor,
    IdleExecutor,
    ImmediateResultExecutor,
    WaitingExecutor,
    _abandon_running_operation,
    _capabilities,
    _close_host_over_live_executor,
    _drifted_registry,
    _lapse_settler,
    _leave_settlement_lease_behind,
    _registry,
    _repositories,
    _request,
    _settle_failed,
    _shared_scope_holder,
    _supervisor,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def test_supervisor_renews_exact_lease_before_expiry_and_settles_beyond_original_duration(tmp_path: Path) -> None:
    """A renewal made while live retains exclusive settlement beyond the original window."""
    observed_at = [_NOW]
    with isolated_ephemeral_secure_sql(tmp_path=tmp_path):
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state",
            profile_objects=SecureObjectRepository(namespace_registry=STORAGE_NAMESPACE_REGISTRY),
        )
        started = asyncio.Event()
        executor = WaitingExecutor(started=started, release=asyncio.Event())
        supervisor = _supervisor(
            registry=_registry(executor_type=WaitingExecutor, build=lambda: executor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            clock=lambda: observed_at[0],
            lease_duration=timedelta(minutes=1),
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))

        observed_at[0] = _NOW + timedelta(seconds=30)
        running = asyncio.run(_close_host_over_live_executor(supervisor, operation_id, started))
        scope_ref = operation_conflict_scope_reference(
            definition_id=running.identity.definition_id,
            subject_ref=running.identity.subject_ref,
        )
        renewed = asyncio.run(leases.inspect(scope_ref, operation_id, observed_at=observed_at[0]))

        assert running.lifecycle is OperationLifecycle.RUNNING
        assert renewed.current is not None
        assert renewed.current.acquired_at == _NOW
        assert renewed.current.expires_at == _NOW + timedelta(seconds=90)

        observed_at[0] = _NOW + timedelta(seconds=75)
        still_owned = asyncio.run(leases.inspect(scope_ref, operation_id, observed_at=observed_at[0]))
        terminal = asyncio.run(
            supervisor.settle(
                operation_id,
                OperationTerminalReceipt(
                    identity=running.identity,
                    revision=running.revision + 1,
                    condition=OperationTerminalCondition.SUCCEEDED,
                    effect=OperationEffect.NONE,
                    settled_at=observed_at[0],
                    result_ref="result:renewed-settlement",
                ),
            )
        )

        assert still_owned.current == renewed.current
        assert terminal.lifecycle is OperationLifecycle.TERMINAL


def test_start_heartbeats_a_quiet_executor_past_the_initial_lease_window(tmp_path: Path) -> None:
    """A quiet executor stays exclusively owned and can settle after its first lease expires."""
    observed_at = [_NOW]
    with isolated_ephemeral_secure_sql(tmp_path=tmp_path):
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state",
            profile_objects=SecureObjectRepository(namespace_registry=STORAGE_NAMESPACE_REGISTRY),
        )
        started = asyncio.Event()
        release = asyncio.Event()
        executor = WaitingExecutor(started=started, release=release, result_ref="result:heartbeat-settlement")
        registry = _registry(executor_type=WaitingExecutor, build=lambda: executor)
        supervisor = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            clock=lambda: observed_at[0],
            lease_duration=timedelta(milliseconds=30),
        )
        contender = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: observed_at[0],
            lease_duration=timedelta(milliseconds=30),
        )

        async def run_quiet_executor() -> OperationPersistedSnapshot:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            start_task = asyncio.create_task(run_to_settlement(supervisor, operation_id))
            await started.wait()
            observed_at[0] = _NOW + timedelta(milliseconds=20)
            await asyncio.sleep(0.025)
            running = await journal.load(operation_id)
            scope_ref = operation_conflict_scope_reference(
                definition_id=running.identity.definition_id,
                subject_ref=running.identity.subject_ref,
            )
            renewed = await leases.inspect(scope_ref, operation_id, observed_at=observed_at[0])

            assert renewed.current is not None
            assert renewed.current.expires_at > _NOW + timedelta(milliseconds=30)

            observed_at[0] = _NOW + timedelta(milliseconds=45)
            with pytest.raises(OperationSubjectBusyError):
                await contender.submit(_request(), operation_id="6" * 64)

            # The released executor returns its result, and its own settlement
            # commits under the renewed lease after the first window expired.
            release.set()
            return await start_task

        terminal = asyncio.run(run_quiet_executor())
        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert terminal.terminal_receipt is not None
        assert terminal.terminal_receipt.result_ref == "result:heartbeat-settlement"
        assert terminal.terminal_receipt.settled_at == _NOW + timedelta(milliseconds=45)


def test_heartbeat_owner_loss_cancels_executor_without_mutating_winner_bytes(tmp_path: Path) -> None:
    """An exact replacement refuses renewal, joins executor cancellation, and preserves winner bytes."""
    observed_at = [_NOW]
    with isolated_ephemeral_secure_sql(tmp_path=tmp_path):
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(
            storage_root=storage_root,
            profile_objects=SecureObjectRepository(namespace_registry=STORAGE_NAMESPACE_REGISTRY),
        )
        started = asyncio.Event()
        release = asyncio.Event()
        executor = WaitingExecutor(started=started, release=release)
        registry = _registry(executor_type=WaitingExecutor, build=lambda: executor)
        owner = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            clock=lambda: observed_at[0],
            lease_duration=timedelta(milliseconds=30),
        )
        replacement = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: observed_at[0],
            lease_duration=timedelta(milliseconds=30),
        )

        async def lose_owner_lease() -> None:
            operation_id = await owner.submit(_request(subject_ref="subject:shared"), operation_id="3" * 64)
            start_task = asyncio.create_task(run_to_settlement(owner, operation_id))
            await started.wait()
            running = await journal.load(operation_id)
            scope_ref = operation_conflict_scope_reference(
                definition_id=running.identity.definition_id,
                subject_ref=running.identity.subject_ref,
            )
            held = await leases.inspect(scope_ref, operation_id, observed_at=observed_at[0])
            assert held.current is not None
            assert (
                await leases.release(held.current, observed_at=observed_at[0])
            ).disposition is OperationLeaseDisposition.RELEASED
            await replacement.submit(_request(subject_ref="subject:shared"), operation_id="6" * 64)

            journal_path = storage_root / "operation-journals" / f"{operation_id}.json"
            lease_path = storage_root / "operation-journals" / f"{scope_ref}.lease.json"
            journal_before = journal_path.read_bytes()
            lease_before = lease_path.read_bytes()
            observed_at[0] = _NOW + timedelta(milliseconds=20)

            # The lease port yields while it works, so a heartbeat may observe
            # the replacement before the clock moves (retention refused) or
            # after (renewal refused); both are the owner-loss refusal.
            with pytest.raises(
                ValueError, match=r"renewal was refused|no longer matches this supervisor's exact held lease"
            ):
                await start_task

            assert executor.cancelled
            assert journal_path.read_bytes() == journal_before
            assert lease_path.read_bytes() == lease_before

        asyncio.run(lose_owner_lease())


def test_exact_lease_renewal_owner_loss_refuses_without_changing_durable_bytes(tmp_path: Path) -> None:
    """A replaced held lease refuses renewal without mutating either durable record."""
    observed_at = [_NOW]
    with isolated_ephemeral_secure_sql(tmp_path=tmp_path):
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(
            storage_root=storage_root,
            profile_objects=SecureObjectRepository(namespace_registry=STORAGE_NAMESPACE_REGISTRY),
        )
        registry = _registry(executor_type=IdleExecutor, build=IdleExecutor)
        owner = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            clock=lambda: observed_at[0],
            lease_duration=timedelta(minutes=1),
        )
        operation_id = asyncio.run(owner.submit(_request(subject_ref="subject:shared"), operation_id="3" * 64))
        original = asyncio.run(journal.load(operation_id))
        scope_ref = operation_conflict_scope_reference(
            definition_id=original.identity.definition_id,
            subject_ref=original.identity.subject_ref,
        )
        held = asyncio.run(leases.inspect(scope_ref, operation_id, observed_at=observed_at[0]))
        assert held.current is not None
        assert (
            asyncio.run(leases.release(held.current, observed_at=observed_at[0])).disposition
            is OperationLeaseDisposition.RELEASED
        )

        intruder = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: observed_at[0],
            lease_duration=timedelta(minutes=1),
        )
        asyncio.run(intruder.submit(_request(subject_ref="subject:shared"), operation_id="6" * 64))
        journal_path = storage_root / "operation-journals" / f"{operation_id}.json"
        lease_path = storage_root / "operation-journals" / f"{scope_ref}.lease.json"
        journal_before = journal_path.read_bytes()
        lease_before = lease_path.read_bytes()

        observed_at[0] = _NOW + timedelta(seconds=30)
        with pytest.raises(ValueError, match="renewal was refused"):
            asyncio.run(run_to_settlement(owner, operation_id))

        assert journal_path.read_bytes() == journal_before
        assert lease_path.read_bytes() == lease_before


def test_stale_settle_preserves_declared_resource_and_winner_evidence(tmp_path: Path) -> None:
    """A stale owner cannot close resources before exact lease proof; the winner closes its own once."""
    with isolated_ephemeral_secure_sql(tmp_path=tmp_path):
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(
            storage_root=storage_root,
            profile_objects=SecureObjectRepository(namespace_registry=STORAGE_NAMESPACE_REGISTRY),
        )
        executors: list[DeclaredResourceExecutor] = [
            DeclaredResourceExecutor(),
            DeclaredResourceExecutor(result_ref="result:winner-settlement"),
        ]
        built: list[DeclaredResourceExecutor] = []

        def build_executor() -> DeclaredResourceExecutor:
            executor = executors[len(built)]
            built.append(executor)
            return executor

        registry = _registry(
            executor_type=DeclaredResourceExecutor,
            build=build_executor,
            capabilities=_capabilities(owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK})),
        )
        owner = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        contender = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
        )
        operation_id = asyncio.run(owner.submit(_request(subject_ref="subject:shared"), operation_id="3" * 64))
        running = asyncio.run(_close_host_over_live_executor(owner, operation_id, executors[0].started))
        assert running.lifecycle is OperationLifecycle.RUNNING
        assert len(built) == 1
        stale_resource = executors[0].resource
        assert stale_resource is not None
        scope_ref = operation_conflict_scope_reference(
            definition_id=running.identity.definition_id,
            subject_ref=running.identity.subject_ref,
        )
        held = asyncio.run(leases.inspect(scope_ref, operation_id, observed_at=_NOW))
        assert held.current is not None
        assert (
            asyncio.run(leases.release(held.current, observed_at=_NOW)).disposition
            is OperationLeaseDisposition.RELEASED
        )
        winner_id = asyncio.run(contender.submit(_request(subject_ref="subject:shared"), operation_id="6" * 64))
        journal_path = storage_root / "operation-journals" / f"{operation_id}.json"
        lease_path = storage_root / "operation-journals" / f"{scope_ref}.lease.json"
        journal_before = journal_path.read_bytes()
        lease_before = lease_path.read_bytes()

        with pytest.raises(ValueError, match="exact held lease"):
            asyncio.run(
                owner.settle(
                    operation_id,
                    OperationTerminalReceipt(
                        identity=running.identity,
                        revision=running.revision + 1,
                        condition=OperationTerminalCondition.SUCCEEDED,
                        effect=OperationEffect.NONE,
                        settled_at=_NOW,
                        result_ref="result:stale-settlement",
                    ),
                )
            )

        assert stale_resource.close_calls == 0
        assert journal_path.read_bytes() == journal_before
        assert lease_path.read_bytes() == lease_before

        async def run_winner() -> OperationPersistedSnapshot:
            winner_task = asyncio.create_task(run_to_settlement(contender, winner_id))
            await executors[1].started.wait()
            assert (await contender.inspect(winner_id)).lifecycle is OperationLifecycle.RUNNING
            # The winner's executor returns its result; its own settlement
            # closes the winner's resource under the winner's lease.
            executors[1].release.set()
            return await winner_task

        terminal = asyncio.run(run_winner())
        assert len(built) == 2
        winner_resource = executors[1].resource
        assert winner_resource is not None

        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert terminal.terminal_receipt is not None
        assert terminal.terminal_receipt.result_ref == "result:winner-settlement"
        assert stale_resource.close_calls == 0
        assert winner_resource.close_calls == 1


def test_a_settled_operation_frees_its_subject_for_an_immediate_resubmission(tmp_path: Path) -> None:
    """The operator can act on a terminal state at once: the lease is already gone when it is visible."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        registry = _registry(executor_type=IdleExecutor, build=IdleExecutor)
        owner = _supervisor(
            registry=registry, journal=journal, leases=leases, operands=operands, owner_id="1" * 64, token="2" * 64
        )
        contender = _supervisor(
            registry=registry, journal=journal, leases=leases, operands=operands, owner_id="3" * 64, token="4" * 64
        )
        settled_operation = asyncio.run(owner.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="5" * 64))

        terminal = _settle_failed(owner, settled_operation)
        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert _shared_scope_holder(leases, observed_at=_NOW) is None

        resubmitted = asyncio.run(contender.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="6" * 64))

        assert resubmitted == "6" * 64
        holder = _shared_scope_holder(leases, observed_at=_NOW)
        assert holder is not None and holder.operation_id == resubmitted


def test_a_live_unsettled_holder_refuses_resubmission_with_the_registered_busy_refusal(tmp_path: Path) -> None:
    """A running operation keeps its subject; the refusal is typed, registered and names nothing internal."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        registry = _registry(executor_type=IdleExecutor, build=IdleExecutor)
        owner = _supervisor(
            registry=registry, journal=journal, leases=leases, operands=operands, owner_id="1" * 64, token="2" * 64
        )
        contender = _supervisor(
            registry=registry, journal=journal, leases=leases, operands=operands, owner_id="3" * 64, token="4" * 64
        )
        held_operation = asyncio.run(owner.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="5" * 64))
        held_lease = _shared_scope_holder(leases, observed_at=_NOW)

        with pytest.raises(OperationSubjectBusyError) as refused:
            asyncio.run(contender.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="6" * 64))

        assert not isinstance(refused.value, ValueError)
        registered = get_registered_error_code(refused.value)
        assert registered.code == "REFUSED_OPERATION_SUBJECT_BUSY"
        assert registered.category is ErrorCategory.REFUSED
        message = resolve_error_message(refused.value)
        assert message == tr(registered.message_key)
        assert message != registered.message_key
        assert held_operation not in message and _SHARED_SUBJECT not in message
        assert _shared_scope_holder(leases, observed_at=_NOW) == held_lease
        assert asyncio.run(journal.load(held_operation)).lifecycle is OperationLifecycle.CREATED
        with pytest.raises(RepositoryError):
            asyncio.run(journal.load("6" * 64))


def test_a_submission_interrupts_an_unstarted_holder_whose_lease_lapsed(tmp_path: Path) -> None:
    """Nobody started the holder within its whole lease: it had no effect, and it must not hold the subject."""
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
        lapsed_at = _NOW + timedelta(minutes=2)
        contender = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="3" * 64,
            token="4" * 64,
            clock=lambda: lapsed_at,
        )
        unstarted = asyncio.run(owner.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="5" * 64))
        expired_lease = _shared_scope_holder(leases, observed_at=lapsed_at)
        assert expired_lease is not None and expired_lease.expires_at <= lapsed_at

        admitted = asyncio.run(contender.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="6" * 64))

        assert admitted == "6" * 64
        holder = _shared_scope_holder(leases, observed_at=lapsed_at)
        assert holder is not None and holder.operation_id == admitted and holder.owner_id == "3" * 64
        settled = asyncio.run(journal.load(unstarted))
        assert settled.lifecycle is OperationLifecycle.TERMINAL
        assert settled.terminal_condition is OperationTerminalCondition.INTERRUPTED
        assert settled.effect is OperationEffect.NONE
        replayed = asyncio.run(journal.read_after(unstarted, 0, limit=20))
        outcomes = tuple(event.outcome for event in replayed.events if isinstance(event, OperationReconciliationEvent))
        assert outcomes == (OperationReconciliationOutcome.ORPHANED,)


def test_a_live_unstarted_holder_still_refuses_and_names_itself_to_the_runtime(tmp_path: Path) -> None:
    """Within its lease an unstarted holder may still be started; the refusal carries its id for the operator."""
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
        within_lease = _NOW + timedelta(seconds=30)
        contender = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="3" * 64,
            token="4" * 64,
            clock=lambda: within_lease,
        )
        unstarted = asyncio.run(owner.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="5" * 64))

        with pytest.raises(OperationSubjectBusyError) as refused:
            asyncio.run(contender.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="6" * 64))

        assert refused.value.holder_operation_id == unstarted
        assert asyncio.run(journal.load(unstarted)).lifecycle is OperationLifecycle.CREATED


def test_settle_lapsed_waits_out_the_grace_then_interrupts_a_started_operation_as_unknown(tmp_path: Path) -> None:
    """A returning submitter gets the grace to continue; after it, the dead owner's work settles honestly."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands, operation_id = _abandon_running_operation(tmp_path, profile.repository)
        grace = timedelta(minutes=10)
        early = _lapse_settler(journal=journal, leases=leases, operands=operands, at=_NOW + timedelta(minutes=5))

        assert asyncio.run(early.settle_lapsed(operation_id, grace=grace)) is None
        assert asyncio.run(journal.load(operation_id)).lifecycle is OperationLifecycle.RUNNING

        settled_at = _NOW + timedelta(minutes=12)
        late = _lapse_settler(journal=journal, leases=leases, operands=operands, at=settled_at)
        settled = asyncio.run(late.settle_lapsed(operation_id, grace=grace))

        assert settled is not None
        assert asyncio.run(journal.load(operation_id)) == settled
        assert settled.terminal_condition is OperationTerminalCondition.INTERRUPTED
        assert settled.effect is OperationEffect.UNKNOWN
        assert _shared_scope_holder(leases, observed_at=settled_at) is None
        assert asyncio.run(late.settle_lapsed(operation_id, grace=grace)) == settled


def test_settle_lapsed_leaves_an_operation_whose_owner_still_renews(tmp_path: Path) -> None:
    """An active lease is a live owner; nothing is taken from it."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        owner = _lapse_settler(journal=journal, leases=leases, operands=operands, at=_NOW)
        operation_id = asyncio.run(owner.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="5" * 64))
        held = _shared_scope_holder(leases, observed_at=_NOW)

        assert asyncio.run(owner.settle_lapsed(operation_id, grace=timedelta())) is None
        assert asyncio.run(journal.load(operation_id)).lifecycle is OperationLifecycle.CREATED
        assert _shared_scope_holder(leases, observed_at=_NOW) == held


def test_settle_lapsed_settles_an_operation_a_changed_definition_can_no_longer_reconcile(tmp_path: Path) -> None:
    """An operation left by an older build cannot be resumed, and must not be left unsettled for good."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands, operation_id = _abandon_running_operation(tmp_path, profile.repository)
        changed = _drifted_registry(_registry(executor_type=WaitingExecutor, build=IdleExecutor))
        settled_at = _NOW + timedelta(minutes=12)
        newer_build = _lapse_settler(journal=journal, leases=leases, operands=operands, at=settled_at, registry=changed)
        before = asyncio.run(journal.load(operation_id))
        assert (
            changed.lookup_public_contract(before.identity.definition_id).definition_contract_digest
            != before.definition_contract_digest
        )
        with pytest.raises(ValueError, match="no longer reproduces"):
            asyncio.run(newer_build.reconcile(operation_id))

        settled = asyncio.run(newer_build.settle_lapsed(operation_id, grace=timedelta(minutes=10)))

        assert settled is not None
        assert settled.terminal_condition is OperationTerminalCondition.INTERRUPTED
        assert settled.effect is OperationEffect.UNKNOWN
        assert _shared_scope_holder(leases, observed_at=settled_at) is None


def test_a_lease_whose_holder_has_no_journal_yet_is_a_live_conflict(tmp_path: Path) -> None:
    """A submission between its lease and its journal create is in progress, not a leftover."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        contender = _supervisor(
            registry=_registry(executor_type=IdleExecutor, build=IdleExecutor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="3" * 64,
            token="4" * 64,
        )
        request = _request(subject_ref=_SHARED_SUBJECT)
        in_flight = OperationOwnerLease(
            operation_id="9" * 64,
            scope_ref=operation_conflict_scope_reference(
                definition_id=request.definition_id, subject_ref=request.subject_ref
            ),
            owner_id="1" * 64,
            token="2" * 64,
            acquired_at=_NOW,
            expires_at=_NOW + timedelta(minutes=10),
        )
        acquired = asyncio.run(leases.acquire(in_flight, observed_at=_NOW))
        assert acquired.disposition is OperationLeaseDisposition.ACQUIRED

        with pytest.raises(OperationSubjectBusyError):
            asyncio.run(contender.submit(request, operation_id="6" * 64))

        assert _shared_scope_holder(leases, observed_at=_NOW) == in_flight


@pytest.mark.parametrize("leftover_expired", (False, True), ids=("live-leftover", "expired-leftover"))
def test_the_next_submission_reclaims_a_lease_left_by_a_crash_after_settlement(
    tmp_path: Path,
    leftover_expired: bool,
) -> None:
    """A terminal journal beside a lease its operation still owns is a crash leftover, reclaimed once."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        registry = _registry(executor_type=IdleExecutor, build=IdleExecutor)
        owner = _supervisor(
            registry=registry, journal=journal, leases=leases, operands=operands, owner_id="1" * 64, token="2" * 64
        )
        settled_operation = asyncio.run(owner.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="5" * 64))
        terminal = _settle_failed(owner, settled_operation)
        leftover = _leave_settlement_lease_behind(leases, terminal)
        submitted_at = leftover.expires_at + timedelta(minutes=1) if leftover_expired else _NOW + timedelta(seconds=1)
        assert _shared_scope_holder(leases, observed_at=submitted_at) == leftover
        contender = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="3" * 64,
            token="4" * 64,
            clock=lambda: submitted_at,
        )

        resubmitted = asyncio.run(contender.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="6" * 64))

        assert resubmitted == "6" * 64
        holder = _shared_scope_holder(leases, observed_at=submitted_at)
        assert holder is not None and holder.operation_id == resubmitted and holder.owner_id == "3" * 64
        assert asyncio.run(journal.load(settled_operation)) == terminal
        assert asyncio.run(journal.load(resubmitted)).lifecycle is OperationLifecycle.CREATED


def test_reconciling_a_settled_operation_releases_the_lease_its_crash_left_behind(tmp_path: Path) -> None:
    """Reconciliation frees a leftover of the terminal operation it names, and nothing else."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        registry = _registry(executor_type=IdleExecutor, build=IdleExecutor)
        owner = _supervisor(
            registry=registry, journal=journal, leases=leases, operands=operands, owner_id="1" * 64, token="2" * 64
        )
        settled_operation = asyncio.run(owner.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="5" * 64))
        terminal = _settle_failed(owner, settled_operation)
        _leave_settlement_lease_behind(leases, terminal)
        recovered_at = _NOW + timedelta(seconds=1)
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="3" * 64,
            token="4" * 64,
            clock=lambda: recovered_at,
        )

        assert asyncio.run(recovery.reconcile(settled_operation)) == terminal
        assert _shared_scope_holder(leases, observed_at=recovered_at) is None
        assert asyncio.run(recovery.reconcile(settled_operation)) == terminal
        assert _shared_scope_holder(leases, observed_at=recovered_at) is None

        resubmitted = asyncio.run(recovery.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="6" * 64))
        successor_lease = _shared_scope_holder(leases, observed_at=recovered_at)
        assert successor_lease is not None and successor_lease.operation_id == resubmitted

        assert asyncio.run(recovery.reconcile(settled_operation)) == terminal
        assert _shared_scope_holder(leases, observed_at=recovered_at) == successor_lease
        assert asyncio.run(journal.load(settled_operation)) == terminal


def test_an_executor_settlement_frees_its_subject_for_an_immediate_same_subject_submit(tmp_path: Path) -> None:
    """Whatever the definition, settling through its executor releases the subject with the terminal record."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        registry = _registry(executor_type=ImmediateResultExecutor, build=ImmediateResultExecutor)
        owner = _supervisor(
            registry=registry, journal=journal, leases=leases, operands=operands, owner_id="1" * 64, token="2" * 64
        )
        contender = _supervisor(
            registry=registry, journal=journal, leases=leases, operands=operands, owner_id="3" * 64, token="4" * 64
        )

        async def settle_then_resubmit() -> tuple[OperationPersistedSnapshot, OperationPersistedSnapshot, str]:
            first = await owner.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="5" * 64)
            first_terminal = await run_to_settlement(owner, first)
            again = await owner.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="6" * 64)
            again_terminal = await run_to_settlement(owner, again)
            other = await contender.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="7" * 64)
            return first_terminal, again_terminal, other

        first_terminal, again_terminal, other = asyncio.run(settle_then_resubmit())

        for terminal in (first_terminal, again_terminal):
            assert terminal.lifecycle is OperationLifecycle.TERMINAL
            assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert asyncio.run(journal.load(terminal.identity.operation_id)) == terminal
        assert other == "7" * 64
        holder = _shared_scope_holder(leases, observed_at=_NOW)
        assert holder is not None and holder.operation_id == other
