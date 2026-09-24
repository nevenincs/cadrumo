"""Settlement of an executor that returns no result, over real durable operation storage.

Returning no result is legitimate only when the executor left something else to
settle the operation: a pending interaction or external wait, a cancellation
request, or an acknowledged cancellation. Any other empty return is a contract
breach that nothing could ever settle, so the supervisor settles it as failed
with a registered code instead of leaving it running.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel

from cadrumo.adapters.outbound.aeat.browser.factory import default_browser_session_factory
from cadrumo.adapters.outbound.aeat.sede.censal_datos import fetch_censal_datos
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.application.operations.capabilities import OperationReplayPolicy
from cadrumo.application.operations.errors import OperationExecutorReturnedNoResultError
from cadrumo.application.operations.interactions import OperationConsumedInteraction, OperationPendingInteraction
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.persistence.events import OperationTerminalEvent
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.persistence.leases import (
    OperationLeaseObservationDisposition,
    operation_conflict_scope_reference,
)
from cadrumo.application.operations.registry import OperationReconciliationPolicy
from cadrumo.application.operations.supervisor_context import SupervisorExecutorContext
from cadrumo.application.user_profile.censal_operation import CensalOperationExecutor
from cadrumo.core.errors.error_codes import ErrorCategory, get_registered_error_code
from cadrumo.core.operations import (
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
)

from .supervision_support import run_to_settlement
from .test_censal_operation_executor import _NOW as _CENSAL_NOW
from .test_censal_operation_executor import (
    _OPERATOR_SCOPE_PORTS,
    _observation,
    _payload,
    _subject,
    _test_censal_operation_definition_id,
)
from .test_censal_operation_executor import _supervisor as _censal_supervisor
from .test_supervisor import (
    _NOW,
    ResumableReviewExecutor,
    ReviewExecutor,
    _capabilities,
    _pending_interaction,
    _registry,
    _repositories,
    _request,
    _response,
    _supervisor,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NO_RESULT_CODE = "INTERNAL_OPERATION_EXECUTOR_RETURNED_NO_RESULT"
_ANSWERED_RESULT_REF = "result:answered-review"


class EffectThenNoResultExecutor:
    """Publish an effect while running, then return no result without suspending."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        await context.events.effect(OperationEffect.UNKNOWN)
        return None


class AnsweredBeforeReturnExecutor:
    """Publish a review and return only after its response has been consumed.

    The resumed continuation stays live until released, so the moment the
    first execution returns, the journal shows a running operation with no
    pending interaction even though the execution genuinely suspended.
    """

    published: asyncio.Event
    release_execute: asyncio.Event
    resume_entered: asyncio.Event
    release_resume: asyncio.Event

    @classmethod
    def reset(cls) -> None:
        cls.published = asyncio.Event()
        cls.release_execute = asyncio.Event()
        cls.resume_entered = asyncio.Event()
        cls.release_resume = asyncio.Event()

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        assert isinstance(context, SupervisorExecutorContext)
        await context.interactions.request(_pending_interaction(context.identity))
        type(self).published.set()
        await type(self).release_execute.wait()
        return None

    async def resume(
        self,
        request: OperationRequest[BaseModel],
        checkpoint: OperationPendingInteraction | OperationConsumedInteraction,
        context: OperationExecutorContext,
    ) -> str | None:
        del request, checkpoint, context
        type(self).resume_entered.set()
        await type(self).release_resume.wait()
        return _ANSWERED_RESULT_REF


def test_the_no_result_code_is_a_registered_internal_failure() -> None:
    """The breach settles under a stable registered code, never a refusal."""
    registered = get_registered_error_code(OperationExecutorReturnedNoResultError())

    assert registered is not None
    assert registered.code == _NO_RESULT_CODE
    assert registered.category is ErrorCategory.INTERNAL


def test_running_executor_returning_no_result_settles_failed_with_its_registered_code(tmp_path: Path) -> None:
    """A running executor that returns nothing settles failed and releases its subject."""
    storage_root = tmp_path / "durable-state"
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        supervisor = _supervisor(
            registry=_registry(executor_type=EffectThenNoResultExecutor, build=EffectThenNoResultExecutor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )

        async def run() -> tuple[OperationPersistedSnapshot, OperationPersistedSnapshot]:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            await supervisor.start(operation_id)
            # The blocking caller gets the terminal snapshot, not an unsettled error.
            settled = await supervisor.settled(operation_id)
            return settled, await journal.load(operation_id)

        settled, persisted = asyncio.run(run())
        released = asyncio.run(
            leases.inspect(
                operation_conflict_scope_reference(
                    definition_id=settled.identity.definition_id,
                    subject_ref=settled.identity.subject_ref,
                ),
                settled.identity.operation_id,
                observed_at=_NOW,
            )
        )
        replay = asyncio.run(journal.read_after(settled.identity.operation_id, 0, limit=20))

    assert settled.lifecycle is OperationLifecycle.TERMINAL
    assert settled.terminal_condition is OperationTerminalCondition.FAILED
    assert settled.effect is OperationEffect.UNKNOWN
    receipt = settled.terminal_receipt
    assert receipt is not None
    assert receipt.failure_error_code == _NO_RESULT_CODE
    assert receipt.refusal_ref is None
    assert receipt.result_ref is None
    assert receipt.diagnostic_ref is not None and receipt.diagnostic_ref.startswith("sha256:")
    assert persisted == settled
    assert isinstance(replay.events[-1], OperationTerminalEvent)
    assert replay.events[-1].receipt == receipt
    assert released.disposition is OperationLeaseObservationDisposition.ABSENT


def test_resumed_executor_returning_no_result_settles_failed_with_its_registered_code(tmp_path: Path) -> None:
    """The recovery path applies the same rule to a resume that returns nothing while running."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        registry = _registry(
            executor_type=ResumableReviewExecutor,
            build=ResumableReviewExecutor,
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
        waiting = asyncio.run(run_to_settlement(owner, operation_id))
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

    assert waiting.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
    assert terminal.lifecycle is OperationLifecycle.TERMINAL
    assert terminal.terminal_condition is OperationTerminalCondition.FAILED
    assert terminal.phase_code == "operation.phase.declared"
    assert terminal.terminal_receipt is not None
    assert terminal.terminal_receipt.failure_error_code == _NO_RESULT_CODE


def test_executor_suspended_at_an_interaction_stays_unsettled(tmp_path: Path) -> None:
    """Returning nothing after publishing a checkpoint waits for the response instead of failing."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        supervisor = _supervisor(
            registry=_registry(
                executor_type=ReviewExecutor,
                build=ReviewExecutor,
                interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
            ),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))
        waiting = asyncio.run(run_to_settlement(supervisor, operation_id))
        persisted = asyncio.run(journal.load(operation_id))
        replay = asyncio.run(journal.read_after(operation_id, 0, limit=20))

    assert waiting.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
    assert waiting.pending_interaction is not None
    assert waiting.terminal_receipt is None
    assert persisted == waiting
    assert not any(isinstance(event, OperationTerminalEvent) for event in replay.events)


def test_suspended_executor_answered_before_it_returns_is_not_failed(tmp_path: Path) -> None:
    """A review consumed before its execution returns leaves settlement to the continuation."""
    AnsweredBeforeReturnExecutor.reset()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        supervisor = _supervisor(
            registry=_registry(
                executor_type=AnsweredBeforeReturnExecutor,
                build=AnsweredBeforeReturnExecutor,
                capabilities=_capabilities(
                    durability=OperationDurability.RESUMABLE,
                    replay=OperationReplayPolicy.RESUMABLE,
                ),
                interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
                reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
            ),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )

        async def answer_then_return() -> tuple[OperationPersistedSnapshot, OperationPersistedSnapshot]:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            start_task = asyncio.create_task(run_to_settlement(supervisor, operation_id))
            await AnsweredBeforeReturnExecutor.published.wait()
            waiting = await supervisor.inspect(operation_id)
            assert waiting.pending_interaction is not None
            await supervisor.respond(
                _response(
                    intent="apply", operation_id=operation_id, revision=waiting.pending_interaction.request.revision
                )
            )
            await AnsweredBeforeReturnExecutor.resume_entered.wait()
            AnsweredBeforeReturnExecutor.release_execute.set()
            returned = await start_task
            AnsweredBeforeReturnExecutor.release_resume.set()
            return returned, await supervisor.await_terminal(operation_id)

        returned, terminal = asyncio.run(answer_then_return())

    assert returned.lifecycle is OperationLifecycle.RUNNING
    assert returned.pending_interaction is None
    assert returned.terminal_receipt is None
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.terminal_receipt is not None
    assert terminal.terminal_receipt.result_ref == _ANSWERED_RESULT_REF
    assert terminal.terminal_receipt.failure_error_code is None


@pytest.mark.usefixtures("operation")
def test_censal_review_checkpoint_waits_for_its_response_instead_of_failing(tmp_path: Path) -> None:
    """The production censal executor suspends at its review, before and after owner recovery."""

    async def acquire():
        return _observation()

    with _subject(tmp_path) as (profile_id, objects, _session):
        durable_root = tmp_path / "operations"
        executor = CensalOperationExecutor(
            certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
            browser_session_factory=default_browser_session_factory,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            censal_fetch_port=fetch_censal_datos,
            acquire=acquire,
        )
        owner = _censal_supervisor(
            root=durable_root, objects=objects, executor=executor, owner="1" * 64, token="2" * 64
        )
        request = OperationRequest(
            definition_id=_test_censal_operation_definition_id(),
            subject_ref=profile_id,
            payload=_payload(profile_id),
        )

        async def run() -> tuple[OperationPersistedSnapshot, OperationPersistedSnapshot, OperationPersistedSnapshot]:
            operation_id = await owner.submit(request, operation_id="3" * 64)
            waiting = await run_to_settlement(owner, operation_id)
            recovery = _censal_supervisor(
                root=durable_root,
                objects=objects,
                executor=executor,
                owner="4" * 64,
                token="5" * 64,
                now=_CENSAL_NOW + timedelta(minutes=2),
            )
            # Recovery re-enters the executor with the still-unanswered
            # checkpoint; it returns nothing and the review stays open.
            recovered = await recovery.reconcile(operation_id)
            return waiting, recovered, await recovery.inspect(operation_id)

        waiting, recovered, persisted = asyncio.run(run())
        lease = asyncio.run(
            OperationLeaseFilesystemRepository(storage_root=durable_root).inspect(
                operation_conflict_scope_reference(
                    definition_id=_test_censal_operation_definition_id(),
                    subject_ref=profile_id,
                ),
                "3" * 64,
                observed_at=_CENSAL_NOW + timedelta(minutes=2),
            )
        )

    for snapshot in (waiting, recovered, persisted):
        assert snapshot.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
        assert snapshot.pending_interaction is not None
        assert snapshot.terminal_receipt is None
        assert snapshot.effect is OperationEffect.NONE
    assert persisted == recovered
    assert lease.current is not None
    assert lease.current.owner_id == "4" * 64
