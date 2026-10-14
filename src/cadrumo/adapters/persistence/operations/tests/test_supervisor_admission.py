"""Real durable-operation proofs exercised through :class:`OperationSupervisor`."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from pathlib import Path

import pytest
from pydantic import BaseModel

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
    OperationDeclarationError,
    OperationSubjectBusyError,
)
from cadrumo.application.operations.models import (
    OperationRequest,
    OperationTerminalReceipt,
)
from cadrumo.application.operations.owner import OperationExecutor
from cadrumo.application.operations.persistence.events import (
    OperationDiagnosticEvent,
    OperationNoticeEvent,
    OperationTerminalEvent,
)
from cadrumo.application.operations.persistence.journal import (
    OperationPersistedSnapshot,
)
from cadrumo.application.operations.persistence.leases import (
    operation_conflict_scope_reference,
)
from cadrumo.core.access_gate.errors import AeatLiveReadNotEnabledError
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.errors.hierarchy import CoreError
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)

from .supervision_support import run_to_settlement
from .supervisor_test_support import (
    _NOW,
    _SENSITIVE_EXCEPTION_DETAIL,
    IdleExecutor,
    PayloadTypeRecordingExecutor,
    RegisteredErrorExecutor,
    RegisteredRefusalExecutor,
    SubclassResolvingOperands,
    SupervisorRequest,
    UndeclaredEffectExecutor,
    UndeclaredInteractionExecutor,
    UndeclaredPhaseExecutor,
    UndeclaredResourceExecutor,
    UnexpectedFailureExecutor,
    UnregisteredSupervisorRequestRefinement,
    WaitingExecutor,
    _assert_sensitive_detail_absent_from_operation_bytes,
    _capabilities,
    _drifted_registry,
    _registry,
    _repositories,
    _request,
    _supervisor,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def test_timed_out_settlement_refuses_live_executor_before_durable_terminal_commit(tmp_path: Path) -> None:
    """A real secure operand, journal, and lease cannot publish timeout while work remains live."""
    started = asyncio.Event()
    release = asyncio.Event()
    executor = WaitingExecutor(started=started, release=release)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        supervisor = _supervisor(
            registry=_registry(executor_type=WaitingExecutor, build=lambda: executor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )

        async def refuse_live_timeout_then_settle() -> OperationPersistedSnapshot:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            start_task = asyncio.create_task(run_to_settlement(supervisor, operation_id))
            await started.wait()
            running = await supervisor.inspect(operation_id)
            assert await operands.resolve(running.request_reference, SupervisorRequest) == SupervisorRequest(
                value="encrypted-operation-input"
            )
            scope_ref = operation_conflict_scope_reference(
                definition_id=running.identity.definition_id,
                subject_ref=running.identity.subject_ref,
            )
            active_lease = await leases.inspect(scope_ref, operation_id, observed_at=_NOW)
            assert active_lease.current is not None
            with pytest.raises(ValueError, match="timed_out settlement requires completed executor work"):
                await supervisor.settle(
                    operation_id,
                    OperationTerminalReceipt(
                        identity=running.identity,
                        revision=running.revision + 1,
                        condition=OperationTerminalCondition.TIMED_OUT,
                        effect=OperationEffect.NONE,
                        settled_at=_NOW,
                    ),
                )
            durable_running = await journal.load(operation_id)
            assert durable_running.lifecycle is OperationLifecycle.RUNNING
            assert durable_running.terminal_receipt is None
            assert not start_task.done()
            # Closing the host stops the executor without settling it, so the
            # timeout below is claimed over completed work, not a live task.
            start_task.cancel()
            with suppress(asyncio.CancelledError):
                await start_task
            await supervisor.shutdown()
            assert executor.cancelled
            stopped = await supervisor.inspect(operation_id)
            assert stopped.lifecycle is OperationLifecycle.RUNNING
            return await supervisor.settle(
                operation_id,
                OperationTerminalReceipt(
                    identity=stopped.identity,
                    revision=stopped.revision + 1,
                    condition=OperationTerminalCondition.TIMED_OUT,
                    effect=OperationEffect.NONE,
                    settled_at=_NOW,
                ),
            )

        timed_out = asyncio.run(refuse_live_timeout_then_settle())

    assert timed_out.lifecycle is OperationLifecycle.TERMINAL
    assert timed_out.terminal_condition is OperationTerminalCondition.TIMED_OUT


def test_interrupted_settlement_refuses_known_live_executor_without_mutating_the_filesystem_journal(
    tmp_path: Path,
) -> None:
    """A known live executor cannot be overwritten with an unknown-owner terminal receipt."""
    started = asyncio.Event()
    release = asyncio.Event()
    executor = WaitingExecutor(started=started, release=release)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        supervisor = _supervisor(
            registry=_registry(
                executor_type=WaitingExecutor,
                build=lambda: executor,
                capabilities=_capabilities(
                    permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
                ),
            ),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )

        async def refuse_live_interruption() -> None:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            start_task = asyncio.create_task(run_to_settlement(supervisor, operation_id))
            await started.wait()
            running = await supervisor.inspect(operation_id)
            journal_path = storage_root / "operation-journals" / f"{operation_id}.json"
            journal_before = journal_path.read_bytes()
            assert await operands.resolve(running.request_reference, SupervisorRequest) == SupervisorRequest(
                value="encrypted-operation-input"
            )
            scope_ref = operation_conflict_scope_reference(
                definition_id=running.identity.definition_id,
                subject_ref=running.identity.subject_ref,
            )
            assert (await leases.inspect(scope_ref, operation_id, observed_at=_NOW)).current is not None
            with pytest.raises(ValueError, match="interrupted settlement requires completed executor work"):
                await supervisor.settle(
                    operation_id,
                    OperationTerminalReceipt(
                        identity=running.identity,
                        revision=running.revision + 1,
                        condition=OperationTerminalCondition.INTERRUPTED,
                        effect=OperationEffect.UNKNOWN,
                        settled_at=_NOW,
                    ),
                )
            assert journal_path.read_bytes() == journal_before
            assert await journal.load(operation_id) == running
            assert not start_task.done()
            release.set()
            await start_task

        asyncio.run(refuse_live_interruption())


def test_filesystem_journal_refuses_non_current_operation_snapshots_without_rewrite(tmp_path: Path) -> None:
    """Pre-release operation journals reject a superseded snapshot without rewriting it."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        registry = _registry(executor_type=IdleExecutor, build=IdleExecutor)
        supervisor = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))
        created = asyncio.run(journal.load(operation_id))
        assert (
            created.definition_contract_digest
            == registry.lookup_public_contract(created.identity.definition_id).definition_contract_digest
        )
        journal_path = storage_root / "operation-journals" / f"{operation_id}.json"
        current_record = json.loads(journal_path.read_text(encoding="utf-8"))
        old_record = json.loads(json.dumps(current_record))
        old_record["snapshot"]["schema_version"] = 5
        raw_old_record = json.dumps(old_record, sort_keys=True).encode("utf-8")
        journal_path.write_bytes(raw_old_record)
        with pytest.raises(RepositoryError):
            asyncio.run(journal.load(operation_id))
        assert journal_path.read_bytes() == raw_old_record


def test_supervisor_refuses_registry_drift_against_the_pinned_invocation_digest(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        original_registry = _registry(executor_type=IdleExecutor, build=IdleExecutor)
        owner = _supervisor(
            registry=original_registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(owner.submit(_request(), operation_id="3" * 64))
        restarted = _supervisor(
            registry=_drifted_registry(original_registry),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )

        with pytest.raises(ValueError, match="no longer reproduces"):
            asyncio.run(run_to_settlement(restarted, operation_id))
        assert asyncio.run(journal.load(operation_id)).lifecycle is OperationLifecycle.CREATED


@pytest.mark.parametrize(
    "route",
    (
        "inspect",
        "observe",
        "detach",
        "replay",
        "await_terminal",
        "request_cancel",
        "acknowledge_cancellation",
        "escalate_cleanup_deadline",
    ),
)
def test_loaded_snapshot_routes_refuse_definition_drift_before_return_or_mutation(
    tmp_path: Path,
    route: str,
) -> None:
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
        )
        operation_id = asyncio.run(owner.submit(_request(), operation_id="3" * 64))
        snapshot = asyncio.run(journal.load(operation_id))
        journal_path = storage_root / "operation-journals" / f"{operation_id}.json"
        original_bytes = journal_path.read_bytes()
        restarted = _supervisor(
            registry=_drifted_registry(registry),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )

        async def invoke() -> None:
            if route == "replay":
                await restarted.replay(operation_id, 0, limit=20)
            elif route == "acknowledge_cancellation":
                context = restarted._build_context(snapshot)
                await context.cancellation._acknowledge(snapshot)
            elif route == "escalate_cleanup_deadline":
                await restarted._escalate_cleanup_deadline(operation_id)
            else:
                await getattr(restarted, route)(operation_id)

        with pytest.raises(ValueError, match="no longer reproduces"):
            asyncio.run(invoke())
        assert journal_path.read_bytes() == original_bytes


def test_submit_replays_a_durable_idempotency_claim_without_second_lease_acquisition(tmp_path: Path) -> None:
    """A replay returns its original operation after the first real durable submit."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        registry = _registry(executor_type=IdleExecutor, build=IdleExecutor)
        supervisor = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )

        original = asyncio.run(supervisor.submit(_request(idempotency_key="submit-once"), operation_id="3" * 64))
        replayed = asyncio.run(supervisor.submit(_request(idempotency_key="submit-once"), operation_id="4" * 64))

        persisted = asyncio.run(journal.load(original))
        assert original == replayed == "3" * 64
        assert persisted.idempotency_claim is not None
        assert persisted.idempotency_claim.operation_id == original
        assert persisted.idempotency_claim.key_digest != "submit-once"


def test_submit_excludes_only_the_exact_definition_subject_conflict_scope(tmp_path: Path) -> None:
    """One definition-subject lease conflicts, while a distinct subject coexists."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        registry = _registry(executor_type=IdleExecutor, build=IdleExecutor)
        first = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        second = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="3" * 64,
            token="4" * 64,
        )

        first_operation = asyncio.run(first.submit(_request(subject_ref="subject:shared"), operation_id="5" * 64))
        with pytest.raises(OperationSubjectBusyError):
            asyncio.run(second.submit(_request(subject_ref="subject:shared"), operation_id="6" * 64))
        separate_operation = asyncio.run(second.submit(_request(subject_ref="subject:separate"), operation_id="7" * 64))

        assert asyncio.run(journal.load(first_operation)).identity.subject_ref == "subject:shared"
        assert asyncio.run(journal.load(separate_operation)).identity.subject_ref == "subject:separate"


def test_submit_refuses_a_subclass_of_the_registered_request_type(tmp_path: Path) -> None:
    """Admission is exact: a subclass is refused before any lease or journal write, the registered type is not."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        supervisor = _supervisor(
            registry=_registry(executor_type=IdleExecutor, build=IdleExecutor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = "3" * 64
        refined = OperationRequest[BaseModel](
            definition_id="operation.supervisor.test",
            subject_ref="subject:one",
            payload=UnregisteredSupervisorRequestRefinement(value="encrypted-operation-input"),
        )

        with pytest.raises(ValueError, match="request payload does not match definition"):
            asyncio.run(supervisor.submit(refined, operation_id=operation_id))

        assert asyncio.run(journal.inventory_page(after=None, limit=128)).entries == ()
        observation = asyncio.run(
            leases.inspect(
                operation_conflict_scope_reference(
                    definition_id=refined.definition_id, subject_ref=refined.subject_ref
                ),
                operation_id,
                observed_at=_NOW,
            )
        )
        assert observation.current is None
        assert asyncio.run(supervisor.submit(_request(), operation_id=operation_id)) == operation_id


def test_start_hands_the_executor_exactly_the_registered_request_type(tmp_path: Path) -> None:
    """The real encrypted store restores the submitted operand as the registered type itself."""
    executor = PayloadTypeRecordingExecutor()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        supervisor = _supervisor(
            registry=_registry(executor_type=PayloadTypeRecordingExecutor, build=lambda: executor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))
        terminal = asyncio.run(run_to_settlement(supervisor, operation_id))

        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert executor.payload_types == [SupervisorRequest]


def test_start_refuses_a_restored_operand_that_is_not_exactly_the_registered_type(tmp_path: Path) -> None:
    """Restore is exact whatever store is wired: a look-alike operand never reaches the executor."""
    executor = PayloadTypeRecordingExecutor()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, store = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        supervisor = _supervisor(
            registry=_registry(executor_type=PayloadTypeRecordingExecutor, build=lambda: executor),
            journal=journal,
            leases=leases,
            operands=SubclassResolvingOperands(store),
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))

        with pytest.raises(ValueError, match="request payload does not match definition"):
            asyncio.run(supervisor.start(operation_id))

        persisted = asyncio.run(journal.load(operation_id))
        assert persisted.lifecycle is OperationLifecycle.CREATED
        assert persisted.executor_entered_at is None
        assert executor.payload_types == []


@pytest.mark.parametrize(
    "executor",
    (
        UndeclaredPhaseExecutor(),
        UndeclaredEffectExecutor(),
        UndeclaredResourceExecutor(),
        UndeclaredInteractionExecutor(),
    ),
)
def test_start_refuses_each_undeclared_executor_mutation_after_only_the_safe_started_transition(
    tmp_path: Path,
    executor: OperationExecutor[BaseModel],
) -> None:
    """A definition-undeclared claim reaches its caller and settles nothing durable.

    A declaration breach is a definition-contract fault the supervisor detects
    before mutation, not an executor runtime outcome, so it leaves the journal
    at the safe started transition instead of inventing a terminal receipt that
    reads as an operator-facing failure.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        supervisor = _supervisor(
            registry=_registry(executor_type=type(executor), build=lambda: executor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))

        with pytest.raises(OperationDeclarationError, match="not declared"):
            asyncio.run(run_to_settlement(supervisor, operation_id))

        refused = asyncio.run(supervisor.inspect(operation_id))
        assert refused.lifecycle is OperationLifecycle.RUNNING
        assert refused.terminal_condition is None
        assert refused.terminal_receipt is None
        assert refused.revision == 1
        assert refused.phase_code is None
        assert refused.pending_interaction is None
        assert refused.effect is OperationEffect.NONE
        assert tuple(type(event) for event in refused.events) == (OperationNoticeEvent,)
        assert isinstance(refused.events[0], OperationNoticeEvent)
        assert refused.events[0].notice_code == "operation.started"
        if isinstance(executor, UndeclaredResourceExecutor):
            assert executor.resource is not None
            assert executor.resource.close_calls == 0


def test_start_settles_registered_executor_refusal_without_persisting_its_sensitive_detail(tmp_path: Path) -> None:
    """One registered refusal becomes its canonical code rather than captured exception prose."""
    storage_root = tmp_path / "durable-state"
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        supervisor = _supervisor(
            registry=_registry(executor_type=RegisteredRefusalExecutor, build=RegisteredRefusalExecutor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))
        terminal = asyncio.run(run_to_settlement(supervisor, operation_id))

        assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
        assert terminal.effect is OperationEffect.NONE
        assert terminal.terminal_receipt is not None
        assert terminal.terminal_receipt.refusal_ref == get_registered_error_code(AeatLiveReadNotEnabledError()).code
        assert terminal.terminal_receipt.failure_error_code is None
        assert terminal.terminal_receipt.diagnostic_ref is None
        assert len(terminal.events) == 1
        assert isinstance(terminal.events[0], OperationTerminalEvent)
        assert _SENSITIVE_EXCEPTION_DETAIL not in terminal.model_dump_json()
        _assert_sensitive_detail_absent_from_operation_bytes(storage_root)


def test_start_settles_unexpected_executor_failure_with_correlated_opaque_diagnostic(tmp_path: Path) -> None:
    """A real effectful executor preserves its effect, closes its resource, and leaks no failure detail."""
    storage_root = tmp_path / "durable-state"
    executor = UnexpectedFailureExecutor()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        supervisor = _supervisor(
            registry=_registry(
                executor_type=UnexpectedFailureExecutor,
                build=lambda: executor,
                capabilities=_capabilities(
                    owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK}),
                    permitted_effects=frozenset(
                        {OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}
                    ),
                ),
            ),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))
        terminal = asyncio.run(run_to_settlement(supervisor, operation_id))
        replay = asyncio.run(journal.read_after(operation_id, 0, limit=10))

        assert terminal.terminal_condition is OperationTerminalCondition.FAILED
        assert terminal.effect is OperationEffect.UPDATED
        assert terminal.terminal_receipt is not None
        assert terminal.terminal_receipt.failure_error_code is None
        correlation = terminal.terminal_receipt.diagnostic_ref
        assert correlation is not None and correlation.startswith("sha256:")
        assert correlation == "sha256:7941bacab17db1fdca826bf7e7e55a69919916975fb0cb7d31d9e2d8e3d06376"
        assert tuple(type(event) for event in terminal.events) == (
            OperationDiagnosticEvent,
            OperationTerminalEvent,
        )
        diagnostic = terminal.events[0]
        assert isinstance(diagnostic, OperationDiagnosticEvent)
        assert diagnostic.diagnostic_ref == correlation
        terminal_event = terminal.events[1]
        assert isinstance(terminal_event, OperationTerminalEvent)
        assert terminal_event.receipt.diagnostic_ref == correlation
        assert replay.events[-2:] == terminal.events
        assert executor.resource.close_calls == 1
        assert _SENSITIVE_EXCEPTION_DETAIL not in terminal.model_dump_json()
        assert _SENSITIVE_EXCEPTION_DETAIL.encode("utf-8") not in b"".join(
            event.model_dump_json().encode("utf-8") for event in replay.events
        )
        _assert_sensitive_detail_absent_from_operation_bytes(storage_root)


def test_start_normalizes_registered_non_refusal_error_to_safe_failed_diagnostic(tmp_path: Path) -> None:
    """A registered error category other than refusal fails closed without persisting its detail."""
    storage_root = tmp_path / "durable-state"
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        supervisor = _supervisor(
            registry=_registry(executor_type=RegisteredErrorExecutor, build=RegisteredErrorExecutor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))
        terminal = asyncio.run(run_to_settlement(supervisor, operation_id))
        replay = asyncio.run(journal.read_after(operation_id, 0, limit=10))

        assert get_registered_error_code(CoreError()).code == "ERROR_CADRUMO_CORE"
        assert terminal.terminal_condition is OperationTerminalCondition.FAILED
        assert terminal.terminal_receipt is not None
        assert terminal.terminal_receipt.refusal_ref is None
        assert terminal.terminal_receipt.failure_error_code == get_registered_error_code(CoreError()).code
        correlation = terminal.terminal_receipt.diagnostic_ref
        assert correlation is not None and correlation.startswith("sha256:")
        assert tuple(type(event) for event in terminal.events) == (
            OperationDiagnosticEvent,
            OperationTerminalEvent,
        )
        diagnostic, terminal_event = terminal.events
        assert isinstance(diagnostic, OperationDiagnosticEvent)
        assert diagnostic.diagnostic_ref == correlation
        assert isinstance(terminal_event, OperationTerminalEvent)
        assert terminal_event.receipt.diagnostic_ref == correlation
        assert _SENSITIVE_EXCEPTION_DETAIL not in terminal.model_dump_json()
        assert _SENSITIVE_EXCEPTION_DETAIL.encode("utf-8") not in b"".join(
            event.model_dump_json().encode("utf-8") for event in replay.events
        )
        _assert_sensitive_detail_absent_from_operation_bytes(storage_root)


def test_submit_conflict_does_not_publish_an_orphan_idempotency_claim(tmp_path: Path) -> None:
    """A real conflict leaves the retry key free until its journal exists."""
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
        )
        contender = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="3" * 64,
            token="4" * 64,
        )
        held_operation = asyncio.run(owner.submit(_request(subject_ref="subject:shared"), operation_id="5" * 64))
        retry_request = _request(subject_ref="subject:shared", idempotency_key="retry-after-conflict")

        with pytest.raises(OperationSubjectBusyError):
            asyncio.run(contender.submit(retry_request, operation_id="6" * 64))
        with pytest.raises(RepositoryError):
            asyncio.run(journal.load("6" * 64))

        held = asyncio.run(journal.load(held_operation))
        asyncio.run(
            owner.settle(
                held_operation,
                OperationTerminalReceipt(
                    identity=held.identity,
                    revision=held.revision + 1,
                    condition=OperationTerminalCondition.FAILED,
                    effect=OperationEffect.NONE,
                    settled_at=_NOW,
                ),
            )
        )
        created = asyncio.run(contender.submit(retry_request, operation_id="6" * 64))
        replayed = asyncio.run(contender.submit(retry_request, operation_id="7" * 64))

        assert created == replayed == "6" * 64
        assert asyncio.run(journal.load(created)).idempotency_claim is not None


def test_submit_journal_create_refusal_releases_the_exact_lease_for_retry(tmp_path: Path) -> None:
    """A post-acquisition journal refusal releases its exact lease before retry."""
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
        operation_id = "3" * 64
        request = _request()
        journal_root = storage_root / "operation-journals"
        journal_root.mkdir(parents=True)
        refused_path = journal_root / f"{operation_id}.json"
        refused_path.mkdir()

        with pytest.raises(RepositoryError, match="create already exists"):
            asyncio.run(supervisor.submit(request, operation_id=operation_id))
        observation = asyncio.run(
            leases.inspect(
                operation_conflict_scope_reference(
                    definition_id=request.definition_id,
                    subject_ref=request.subject_ref,
                ),
                operation_id,
                observed_at=_NOW,
            )
        )
        assert observation.current is None

        refused_path.rmdir()
        created = asyncio.run(supervisor.submit(request, operation_id=operation_id))
        assert created == operation_id
        assert asyncio.run(journal.load(created)).idempotency_claim is None
