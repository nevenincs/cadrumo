"""Restart proofs against an owner process that was genuinely killed.

The first owner runs in a real child process holding real durable state. It is
killed outright -- no graceful teardown, no unwinding, no chance to release
its lease -- which is the state a crash actually leaves behind. A second owner
then reconciles from that state alone.

Simulating the crash in-process cannot reach this: the dead owner's task and
its in-memory bookkeeping would still exist, and the recovering supervisor
could lean on them. Here the only thing that survives the crash is what
reached disk.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from ....adapters.persistence.operations.journal import OperationJournalRepository
from ....adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.hashing import content_hash_hex
from ....core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ..capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..interactions import OperationInteractionRequest, OperationPendingInteraction
from ..models import (
    CredentialFreeOperationRequest,
    OperationIdentity,
    OperationReconciliationOutcome,
    OperationRequest,
)
from ..owner import OperationExecutorContext
from ..persistence.events import (
    OperationInteractionEvent,
    OperationNoticeEvent,
    OperationReconciliationEvent,
)
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
from ..supervisor import OperationSupervisor, _SupervisorExecutorContext

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 28, 13, tzinfo=UTC)
_DEFINITION_ID = "operation.supervisor.restart"
_RESUME_PHASE = "operation.phase.resumed"
_LEASE_DURATION = timedelta(minutes=1)

#: Read by the parent after the crash, so the recovering owner's clock is past
#: the dead owner's lease without depending on wall time.
_AFTER_LEASE_EXPIRY = _NOW + _LEASE_DURATION + timedelta(minutes=1)

_CRASHED_OWNER_ID = "1" * 64
_CRASHED_OWNER_TOKEN = "2" * 64
_RECOVERY_OWNER_ID = "4" * 64
_RECOVERY_OWNER_TOKEN = "5" * 64
_INTERACTION_ID = "f" * 64
_RESPONSE_TOKEN = "9" * 64

_READY_MARKER = "CHECKPOINT-DURABLE"

#: How long the parent waits for the child to publish its durable checkpoint.
_CHILD_READY_CEILING = 120.0


class RestartRequest(CredentialFreeOperationRequest):
    """Credential-free request, so a crashed owner needs no secure profile."""

    value: str = Field(min_length=1)


class RestartResult(BaseModel):
    """Registry result type for this restart operation."""

    model_config = STRICT_FROZEN_CONFIG

    reference: str = Field(min_length=1)


class RestartReviewedOperand(BaseModel):
    """Public review projection this REVIEW-bearing definition must declare."""

    model_config = STRICT_FROZEN_CONFIG

    observation: str = Field(min_length=1)


def _project_restart_review(operand: BaseModel, interaction: OperationInteractionRequest) -> BaseModel:
    """Project the reviewed operand for the public review contract."""
    del interaction
    return RestartReviewedOperand.model_validate(operand)


def _pending_interaction(identity: OperationIdentity) -> OperationPendingInteraction:
    """Build the exact durable checkpoint the pre-crash executor publishes."""
    request = OperationInteractionRequest(
        interaction_id=_INTERACTION_ID,
        identity=identity,
        revision=2,
        kind=OperationInteractionKind.REVIEW,
        presentation_code="operation.review.ready",
        response_schema_ref="schema:operation-review",
        continuation_digest=content_hash_hex({"continuation": "restart"}),
    )
    return OperationPendingInteraction.bind(
        request=request,
        response_token=_RESPONSE_TOKEN,
        reviewed_proposal_digest=content_hash_hex({"proposal": "restart"}),
        baseline_digest=content_hash_hex({"baseline": "restart"}),
        proposed_effect_digest=content_hash_hex({"effect": "restart"}),
    )


class CheckpointingExecutor:
    """Publish one durable checkpoint, then record any re-entry after it."""

    def __init__(self) -> None:
        self.resume_checkpoints: list[object] = []

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        assert isinstance(context, _SupervisorExecutorContext)
        await context.interactions.request(_pending_interaction(context.identity))
        return None

    async def resume(
        self,
        request: OperationRequest[BaseModel],
        checkpoint: object,
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        self.resume_checkpoints.append(checkpoint)
        await context.events.phase(_RESUME_PHASE)
        return None


def build_restart_registry(
    *,
    policy: OperationReconciliationPolicy,
    executor: CheckpointingExecutor | None = None,
) -> OperationRegistry:
    """Build the one registry both the crashed and recovering owners share."""
    bound = executor or CheckpointingExecutor()
    definition = OperationDefinition(
        definition_id=_DEFINITION_ID,
        request_type=RestartRequest,
        result_type=RestartResult,
        executor_factory=OperationExecutorFactory(
            request_type=RestartRequest,
            executor_type=CheckpointingExecutor,
            build=lambda: bound,
        ),
        phase_codes=(_RESUME_PHASE,),
        interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RESUMABLE,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.RESUMABLE,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset[OperationOwnedResource](),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=policy,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
    )
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.restart.request",
            schema_version=1,
            model_type=RestartRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.restart.result",
            schema_version=1,
            model_type=RestartResult,
        ),
        review_projection_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.restart.review",
            schema_version=1,
            model_type=RestartReviewedOperand,
        ),
        reviewed_operand_type=RestartReviewedOperand,
        review_projector=_project_restart_review,
    )
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


def build_supervisor(
    *,
    storage_root: Path,
    registry: OperationRegistry,
    owner_id: str,
    token: str,
    at: datetime,
) -> OperationSupervisor:
    """Compose one owner over durable filesystem state at a fixed instant."""
    return OperationSupervisor(
        registry=registry,
        journal=OperationJournalRepository(storage_root=storage_root),
        event_stream=OperationJournalRepository(storage_root=storage_root),
        leases=OperationLeaseFilesystemRepository(storage_root=storage_root),
        operands=None,
        owner_id=owner_id,
        lease_token_factory=lambda: token,
        clock=lambda: at,
        lease_duration=_LEASE_DURATION,
    )


def restart_request(*, subject_ref: str) -> OperationRequest[BaseModel]:
    """Build the credential-free request both owners agree on."""
    return OperationRequest[BaseModel](
        definition_id=_DEFINITION_ID,
        subject_ref=subject_ref,
        payload=RestartRequest(value="credential-free-restart-input"),
    )


def run_until_killed(storage_root: str, operation_id: str, subject_ref: str, policy: str) -> None:
    """Owner entry point for the child process; never returns on its own.

    Published as a module function because the child imports this module by
    name. It reaches a durable checkpoint, announces it, and then blocks so the
    parent can kill it at a known point.
    """
    supervisor = build_supervisor(
        storage_root=Path(storage_root),
        registry=build_restart_registry(policy=OperationReconciliationPolicy(policy)),
        owner_id=_CRASHED_OWNER_ID,
        token=_CRASHED_OWNER_TOKEN,
        at=_NOW,
    )

    async def reach_checkpoint() -> None:
        await supervisor.submit(restart_request(subject_ref=subject_ref), operation_id=operation_id)
        waiting = await supervisor.start(operation_id)
        print(json.dumps({"marker": _READY_MARKER, "lifecycle": waiting.lifecycle.value}), flush=True)
        await asyncio.Event().wait()

    asyncio.run(reach_checkpoint())


def _crash_an_owner_at_its_checkpoint(
    *,
    storage_root: Path,
    operation_id: str,
    subject_ref: str,
    policy: OperationReconciliationPolicy,
) -> None:
    """Drive a real owner process to a durable checkpoint, then kill it.

    The policy is handed to the child because the definition contract digest
    is pinned at submission: an owner that recovered under a different policy
    would be refused for contract drift, which is a different proof.
    """
    child = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-c",
            "import sys;"
            "from cadrumo.application.operations.tests.test_restart_reconciliation import run_until_killed;"
            "run_until_killed(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])",
            str(storage_root),
            operation_id,
            subject_ref,
            policy.value,
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        stdout = child.stdout
        assert stdout is not None
        announced = stdout.readline()
        if not announced:
            child.kill()
            child.wait(timeout=_CHILD_READY_CEILING)
            pytest.fail("the owner process exited before publishing a durable checkpoint")
        published = json.loads(announced)
        assert published["marker"] == _READY_MARKER
        assert published["lifecycle"] == OperationLifecycle.WAITING_FOR_INTERACTION.value
    finally:
        # Kill, never terminate: the owner gets no chance to release its lease
        # or unwind, which is the whole point of the crash.
        child.kill()
        child.wait(timeout=_CHILD_READY_CEILING)

    assert child.returncode is not None


def _read_journal(storage_root: Path, operation_id: str) -> OperationJournalRepository:
    return OperationJournalRepository(storage_root=storage_root)


def test_crashed_owner_checkpoint_is_taken_over_replayed_and_resumed(tmp_path: Path) -> None:
    """A killed owner's checkpoint survives, is taken over, and is re-entered."""
    storage_root = tmp_path / "durable-state"
    operation_id = "3" * 64
    subject_ref = "subject:resumable-crash"

    _crash_an_owner_at_its_checkpoint(
        storage_root=storage_root,
        operation_id=operation_id,
        subject_ref=subject_ref,
        policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
    )

    journal = _read_journal(storage_root, operation_id)
    survived = asyncio.run(journal.load(operation_id))

    # Only what reached disk before the kill is available.
    assert survived.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
    assert survived.pending_interaction is not None
    assert survived.pending_interaction.request.interaction_id == _INTERACTION_ID
    assert survived.terminal_receipt is None

    # Cursor replay reads the crashed owner's own events across the process
    # boundary, which is the only record of what it did.
    before = asyncio.run(journal.read_after(operation_id, 0, limit=64))
    assert any(isinstance(event, OperationNoticeEvent) for event in before.events)
    assert any(isinstance(event, OperationInteractionEvent) for event in before.events)
    assert not any(isinstance(event, OperationReconciliationEvent) for event in before.events)

    executor = CheckpointingExecutor()
    recovery = build_supervisor(
        storage_root=storage_root,
        registry=build_restart_registry(
            policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
            executor=executor,
        ),
        owner_id=_RECOVERY_OWNER_ID,
        token=_RECOVERY_OWNER_TOKEN,
        at=_AFTER_LEASE_EXPIRY,
    )
    resumed = asyncio.run(recovery.reconcile(operation_id))
    after = asyncio.run(journal.read_after(operation_id, 0, limit=64))
    leases = OperationLeaseFilesystemRepository(storage_root=storage_root)
    observed = asyncio.run(
        leases.inspect(
            operation_conflict_scope_reference(definition_id=_DEFINITION_ID, subject_ref=subject_ref),
            operation_id,
            observed_at=_AFTER_LEASE_EXPIRY,
        )
    )

    # Lease takeover: the dead owner no longer holds the scope.
    assert observed.current is not None
    assert observed.current.owner_id == _RECOVERY_OWNER_ID
    assert observed.current.owner_id != _CRASHED_OWNER_ID

    # Resume policy honoured, from exactly the persisted checkpoint.
    assert len(executor.resume_checkpoints) == 1
    assert executor.resume_checkpoints[0] == survived.pending_interaction
    assert resumed.pending_interaction is None

    # Reconciliation is reported, and the pre-crash events are still replayable
    # after it rather than being rewritten by the new owner.
    outcomes = tuple(event.outcome for event in after.events if isinstance(event, OperationReconciliationEvent))
    assert outcomes == (OperationReconciliationOutcome.RESUMED,)
    assert [type(event) for event in before.events] == [type(event) for event in after.events[: len(before.events)]]


def test_crashed_owner_under_interrupt_policy_is_reported_not_resumed(tmp_path: Path) -> None:
    """A definition that declares interruption never re-enters its executor."""
    storage_root = tmp_path / "durable-state"
    operation_id = "6" * 64
    subject_ref = "subject:interrupt-crash"

    _crash_an_owner_at_its_checkpoint(
        storage_root=storage_root,
        operation_id=operation_id,
        subject_ref=subject_ref,
        policy=OperationReconciliationPolicy.INTERRUPT,
    )

    executor = CheckpointingExecutor()
    recovery = build_supervisor(
        storage_root=storage_root,
        registry=build_restart_registry(
            policy=OperationReconciliationPolicy.INTERRUPT,
            executor=executor,
        ),
        owner_id=_RECOVERY_OWNER_ID,
        token=_RECOVERY_OWNER_TOKEN,
        at=_AFTER_LEASE_EXPIRY,
    )
    interrupted = asyncio.run(recovery.reconcile(operation_id))
    journal = _read_journal(storage_root, operation_id)
    replay = asyncio.run(journal.read_after(operation_id, 0, limit=64))

    assert executor.resume_checkpoints == []
    assert interrupted.lifecycle is OperationLifecycle.TERMINAL
    assert interrupted.terminal_condition is OperationTerminalCondition.INTERRUPTED
    assert interrupted.effect is OperationEffect.UNKNOWN
    outcomes = tuple(event.outcome for event in replay.events if isinstance(event, OperationReconciliationEvent))
    assert outcomes == (OperationReconciliationOutcome.INTERRUPTED,)


def test_crashed_owner_with_no_surviving_lease_is_reported_as_orphaned(tmp_path: Path) -> None:
    """A record whose lease is gone is classified orphaned, never quietly resumed."""
    storage_root = tmp_path / "durable-state"
    operation_id = "7" * 64
    subject_ref = "subject:orphan-crash"

    _crash_an_owner_at_its_checkpoint(
        storage_root=storage_root,
        operation_id=operation_id,
        subject_ref=subject_ref,
        policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
    )

    # The crashed owner's lease is lost independently of its journal record --
    # the state a partially surviving crash leaves behind.
    scope_ref = operation_conflict_scope_reference(definition_id=_DEFINITION_ID, subject_ref=subject_ref)
    leases = OperationLeaseFilesystemRepository(storage_root=storage_root)
    observed = asyncio.run(leases.inspect(scope_ref, operation_id, observed_at=_NOW))
    assert observed.current is not None
    asyncio.run(leases.release(observed.current, observed_at=_NOW))

    executor = CheckpointingExecutor()
    recovery = build_supervisor(
        storage_root=storage_root,
        registry=build_restart_registry(
            policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
            executor=executor,
        ),
        owner_id=_RECOVERY_OWNER_ID,
        token=_RECOVERY_OWNER_TOKEN,
        at=_AFTER_LEASE_EXPIRY,
    )
    orphaned = asyncio.run(recovery.reconcile(operation_id))
    journal = _read_journal(storage_root, operation_id)
    replay = asyncio.run(journal.read_after(operation_id, 0, limit=64))

    assert executor.resume_checkpoints == []
    assert orphaned.lifecycle is OperationLifecycle.TERMINAL
    assert orphaned.terminal_condition is OperationTerminalCondition.INTERRUPTED
    outcomes = tuple(event.outcome for event in replay.events if isinstance(event, OperationReconciliationEvent))
    assert outcomes == (OperationReconciliationOutcome.ORPHANED,)
