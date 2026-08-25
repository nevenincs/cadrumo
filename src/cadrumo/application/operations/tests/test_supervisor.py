"""Real durable-operation proofs exercised through :class:`OperationSupervisor`."""

from __future__ import annotations

import asyncio
import json
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
from ....adapters.persistence.storage import (
    STORAGE_NAMESPACE_REGISTRY,
    RepositoryError,
    SecureObjectRepository,
)
from ....core import STRICT_FROZEN_CONFIG, scan_directory
from ....core.access_gate import AeatLiveReadNotEnabledError
from ....core.errors import CoreError, get_registered_error_code
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
from ....tests.aeat_literal_fixtures import REDACTION_TOKEN_QUERY_URL_CANARY
from ....tests.secure_sql import isolated_ephemeral_secure_sql, isolated_runtime_profile
from ..capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..errors import OperationDeclarationError
from ..frontend_contracts import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from ..interactions import (
    OperationApplyResponse,
    OperationConsumedInteraction,
    OperationInteractionRequest,
    OperationPendingInteraction,
    OperationRejectResponse,
)
from ..models import (
    OperationIdentity,
    OperationReconciliationOutcome,
    OperationRequest,
    OperationTerminalReceipt,
)
from ..observation import OperationObservationService
from ..owner import OperationExecutor, OperationExecutorContext
from ..persistence.events import (
    OperationDiagnosticEvent,
    OperationNoticeEvent,
    OperationReconciliationEvent,
    OperationTerminalEvent,
)
from ..persistence.journal import (
    OperationPersistedSnapshot,
    OperationSecureReferenceStore,
)
from ..persistence.leases import (
    OperationLeaseDisposition,
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
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

_NOW = datetime(2026, 8, 14, 15, tzinfo=UTC)
_CONTINUATION_DIGEST = "a" * 64
_RESPONSE_TOKEN = "b" * 64
_REVIEWED_PROPOSAL_DIGEST = "c" * 64
_BASELINE_DIGEST = "d" * 64
_PROPOSED_EFFECT_DIGEST = "e" * 64
_SENSITIVE_EXCEPTION_DETAIL = (
    f"B12345674 {REDACTION_TOKEN_QUERY_URL_CANARY} "
    "C:/Users/operator/private-key.p12 Bearer correct-horse-battery-staple"
)


class SupervisorRequest(BaseModel):
    """Concrete encrypted operand used only through the real secure adapter."""

    model_config = STRICT_FROZEN_CONFIG

    value: str = Field(min_length=1)


class SupervisorResult(BaseModel):
    """Concrete result schema required by the operation registry."""

    model_config = STRICT_FROZEN_CONFIG

    reference: str = Field(min_length=1)


class ReviewedOperand(BaseModel):
    """Typed confidential result produced after initial operation submission."""

    model_config = STRICT_FROZEN_CONFIG

    observation: str = Field(min_length=1)


class DurableContinuationExecutor:
    """Publish and resume one real secure review continuation."""

    acquisitions = 0
    resumed: asyncio.Event
    hold_first_resume: asyncio.Event
    resume_checkpoints: list[OperationPendingInteraction | OperationConsumedInteraction]

    def __init__(self) -> None:
        if not hasattr(type(self), "resumed"):
            type(self).resumed = asyncio.Event()
            type(self).hold_first_resume = asyncio.Event()
            type(self).resume_checkpoints = []

    @classmethod
    def reset(cls) -> None:
        cls.acquisitions = 0
        cls.resumed = asyncio.Event()
        cls.hold_first_resume = asyncio.Event()
        cls.resume_checkpoints = []

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        type(self).acquisitions += 1
        await context.interactions.publish_review(
            interaction_id="f" * 64,
            identity=context.identity,
            revision=context.revision + 1,
            presentation_code="operation.review.ready",
            response_schema_ref="schema:operation-review",
            continuation_digest=_CONTINUATION_DIGEST,
            expires_at=None,
            reviewed_operand=ReviewedOperand(observation="encrypted post-submission observation"),
            baseline_digest=_BASELINE_DIGEST,
            proposed_effect_digest=_PROPOSED_EFFECT_DIGEST,
        )
        return None

    async def resume(
        self,
        request: OperationRequest[BaseModel],
        checkpoint: OperationPendingInteraction | OperationConsumedInteraction,
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        type(self).resume_checkpoints.append(checkpoint)
        if len(type(self).resume_checkpoints) == 1:
            type(self).resumed.set()
            await type(self).hold_first_resume.wait()
            return None
        await context.events.phase("operation.phase.declared")
        return None


class IdleExecutor:
    """Registered executor used when a test exercises submission only."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request, context
        return None


class UndeclaredPhaseExecutor:
    """Concrete executor that attempts one definition-undeclared phase."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        await context.events.phase("operation.phase.undeclared")
        return None


class UndeclaredEffectExecutor:
    """Concrete executor that attempts one definition-undeclared effect."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        await context.events.effect(OperationEffect.UPDATED)
        return None


class TrackedAsyncResource:
    """A real closeable resource that records whether ownership was transferred."""

    def __init__(self) -> None:
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1


class UndeclaredResourceExecutor:
    """Concrete executor that attempts an undeclared resource-family handoff."""

    def __init__(self) -> None:
        self.resource: TrackedAsyncResource | None = None

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        resource = TrackedAsyncResource()
        self.resource = resource
        context.cleanup.own(resource, family=OperationOwnedResource.ASYNC_TASK)
        return None


class DeclaredResourceExecutor:
    """Concrete executor that transfers one declared resource to settlement."""

    def __init__(self) -> None:
        self.resource: TrackedAsyncResource | None = None

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        resource = TrackedAsyncResource()
        self.resource = resource
        context.cleanup.own(resource, family=OperationOwnedResource.ASYNC_TASK)
        return None


class UndeclaredInteractionExecutor:
    """Concrete executor that attempts an interaction outside its definition."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        assert isinstance(context, _SupervisorExecutorContext)
        await context.interactions.request(_pending_interaction(context.identity))
        return None


class ReviewExecutor:
    """Concrete executor that produces one exact, persisted review checkpoint."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        assert isinstance(context, _SupervisorExecutorContext)
        await context.interactions.request(_pending_interaction(context.identity))
        return None


class ResumableReviewExecutor:
    """A real declared checkpoint executor that proves supervisor re-entry."""

    def __init__(self, *, result_ref: str | None = None) -> None:
        self.resume_checkpoints: list[OperationPendingInteraction] = []
        self._result_ref = result_ref

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
        checkpoint: OperationPendingInteraction,
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        self.resume_checkpoints.append(checkpoint)
        await context.events.phase("operation.phase.declared")
        return self._result_ref


class ResumableIdleExecutor:
    """A resumable declaration whose initial execution publishes no checkpoint."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request, context
        return None

    async def resume(
        self,
        request: OperationRequest[BaseModel],
        checkpoint: OperationPendingInteraction,
        context: OperationExecutorContext,
    ) -> str | None:
        del request, checkpoint
        await context.events.phase("operation.phase.declared")
        return None


class WaitingExecutor:
    """Concrete executor that holds real asynchronous work until released."""

    def __init__(self, *, started: asyncio.Event, release: asyncio.Event) -> None:
        self.started = started
        self.release = release
        self.cancelled = False

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request, context
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return None


class DeadlineAcknowledgingExecutor:
    """Concrete executor that reaches its declared safe stop after a deadline request."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.resource = TrackedAsyncResource()

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        context.cleanup.own(self.resource, family=OperationOwnedResource.ASYNC_TASK)
        self.started.set()
        while not context.cancellation.cancellation_requested:
            await asyncio.sleep(0)
        await context.cancellation.acknowledge_cancellation()
        return None


class UnacknowledgedCancellationExecutor:
    """Concrete executor that stops without asserting the cooperative safe-stop fact."""

    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        self.started.set()
        while not context.cancellation.cancellation_requested:
            await asyncio.sleep(0)
        return None


class IrreversibleSectionExecutor:
    """Concrete executor that holds one real cooperative-stop exclusion boundary."""

    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.exit_requested = asyncio.Event()
        self.context: OperationExecutorContext | None = None

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        self.context = context
        async with context.cancellation.irreversible_section():
            self.entered.set()
            await self.exit_requested.wait()
        await context.cancellation.acknowledge_cancellation()
        return None


class CleanupDeadlineExecutor:
    """Concrete executor that retains running work after the supervisor requests cancellation."""

    def __init__(self) -> None:
        self.cancellation_observed = asyncio.Event()
        self.release = asyncio.Event()

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        while not context.cancellation.cancellation_requested:
            await asyncio.sleep(0)
        self.cancellation_observed.set()
        await self.release.wait()
        return None


class RegisteredRefusalExecutor:
    """Concrete executor that raises one registered refusal with planted sensitive detail."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request, context
        raise AeatLiveReadNotEnabledError(_SENSITIVE_EXCEPTION_DETAIL)


class RegisteredErrorExecutor:
    """Concrete executor that raises a registered non-refusal error safely."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request, context
        raise CoreError(_SENSITIVE_EXCEPTION_DETAIL)


class CancellableResourceExecutor:
    """Concrete executor whose real owned resource is closed by controlled settlement."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = False
        self.resource = TrackedAsyncResource()

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        context.cleanup.own(self.resource, family=OperationOwnedResource.ASYNC_TASK)
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return None


class UnexpectedFailureExecutor:
    """Concrete executor that commits a declared effect then raises a sensitive failure."""

    def __init__(self) -> None:
        self.resource = TrackedAsyncResource()

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        context.cleanup.own(self.resource, family=OperationOwnedResource.ASYNC_TASK)
        await context.events.effect(OperationEffect.UPDATED)
        raise RuntimeError(_SENSITIVE_EXCEPTION_DETAIL)


def _assert_sensitive_detail_absent_from_operation_bytes(storage_root: Path) -> None:
    forbidden = _SENSITIVE_EXCEPTION_DETAIL.encode("utf-8")
    persisted = b"".join(path.read_bytes() for path in scan_directory(storage_root, recursive=True) if path.is_file())
    assert forbidden not in persisted


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
            start_task = asyncio.create_task(supervisor.start(operation_id))
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
            release.set()
            stopped = await start_task
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
            start_task = asyncio.create_task(supervisor.start(operation_id))
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
            asyncio.run(restarted.start(operation_id))
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
                await restarted._acknowledge_cancellation(snapshot)
            elif route == "escalate_cleanup_deadline":
                await restarted._escalate_cleanup_deadline(operation_id)
            else:
                await getattr(restarted, route)(operation_id)

        with pytest.raises(ValueError, match="no longer reproduces"):
            asyncio.run(invoke())
        assert journal_path.read_bytes() == original_bytes


def _pending_interaction(identity: OperationIdentity) -> OperationPendingInteraction:
    """Build the exact response checkpoint an executor may publish after start."""
    request = OperationInteractionRequest(
        interaction_id="f" * 64,
        identity=identity,
        revision=2,
        kind=OperationInteractionKind.REVIEW,
        presentation_code="operation.review.ready",
        response_schema_ref="schema:operation-review",
        continuation_digest=_CONTINUATION_DIGEST,
    )
    return OperationPendingInteraction.bind(
        request=request,
        response_token=_RESPONSE_TOKEN,
        reviewed_proposal_digest=_REVIEWED_PROPOSAL_DIGEST,
        baseline_digest=_BASELINE_DIGEST,
        proposed_effect_digest=_PROPOSED_EFFECT_DIGEST,
    )


def _capabilities(
    *,
    cancellation: OperationCancellation = OperationCancellation.UNSUPPORTED,
    deadline: OperationDeadline = OperationDeadline.ABSENT,
    owned_resources: frozenset[OperationOwnedResource] = frozenset(),
    permitted_effects: frozenset[OperationEffect] = frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
    durability: OperationDurability = OperationDurability.RECORDED,
    replay: OperationReplayPolicy = OperationReplayPolicy.IDEMPOTENT_SUBMIT,
) -> OperationCapabilities:
    return OperationCapabilities(
        durability=durability,
        cancellation=cancellation,
        deadline=deadline,
        replay=replay,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=owned_resources,
        permitted_effects=permitted_effects,
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def _definition(
    *,
    executor_type: type[object],
    build: Callable[[], object],
    capabilities: OperationCapabilities | None = None,
    interaction_kinds: frozenset[OperationInteractionKind] = frozenset(),
    reconciliation_policy: OperationReconciliationPolicy = OperationReconciliationPolicy.INTERRUPT,
) -> OperationDefinition:
    return OperationDefinition(
        definition_id="operation.supervisor.test",
        request_type=SupervisorRequest,
        result_type=SupervisorResult,
        executor_factory=OperationExecutorFactory(
            request_type=SupervisorRequest,
            executor_type=executor_type,
            build=build,
        ),
        phase_codes=("operation.phase.declared",),
        interaction_kinds=interaction_kinds,
        capabilities=_capabilities() if capabilities is None else capabilities,
        reconciliation_policy=reconciliation_policy,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
    )


def _registry(
    *,
    executor_type: type[object],
    build: Callable[[], object],
    capabilities: OperationCapabilities | None = None,
    interaction_kinds: frozenset[OperationInteractionKind] = frozenset(),
    reconciliation_policy: OperationReconciliationPolicy = OperationReconciliationPolicy.INTERRUPT,
) -> OperationRegistry:
    item = _definition(
        executor_type=executor_type,
        build=build,
        capabilities=capabilities,
        interaction_kinds=interaction_kinds,
        reconciliation_policy=reconciliation_policy,
    )
    request_schema = OperationSchemaBindingV1.bind(
        schema_id="operation.supervisor.test.request",
        schema_version=1,
        model_type=SupervisorRequest,
    )
    result_schema = OperationSchemaBindingV1.bind(
        schema_id="operation.supervisor.test.result",
        schema_version=1,
        model_type=SupervisorResult,
    )
    review_schema = (
        OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.test.review",
            schema_version=1,
            model_type=ReviewedOperand,
        )
        if OperationInteractionKind.REVIEW in interaction_kinds
        else None
    )

    def review_projector(operand: BaseModel, interaction: OperationInteractionRequest) -> BaseModel:
        del interaction
        return ReviewedOperand.model_validate(operand)

    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=item,
        request_schema=request_schema,
        result_schema=result_schema,
        review_projection_schema=review_schema,
        reviewed_operand_type=ReviewedOperand if review_schema is not None else None,
        review_projector=review_projector if review_schema is not None else None,
    )
    return OperationRegistry(
        definitions=(item,),
        public_registrations=(registration,),
    )


def _drifted_registry(registry: OperationRegistry) -> OperationRegistry:
    item = registry.lookup("operation.supervisor.test").model_copy(
        update={"permitted_frontends": frozenset({OperationFrontendProjection.CLI})}
    )
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=item,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.test.request",
            schema_version=1,
            model_type=SupervisorRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.test.result",
            schema_version=1,
            model_type=SupervisorResult,
        ),
    )
    return OperationRegistry(definitions=(item,), public_registrations=(registration,))


def _supervisor(
    *,
    registry: OperationRegistry,
    journal: OperationJournalRepository,
    leases: OperationLeaseFilesystemRepository,
    operands: OperationSecureReferenceStore,
    owner_id: str,
    token: str,
    clock: Callable[[], datetime] | None = None,
    lease_duration: timedelta = timedelta(minutes=10),
    execution_timeout: timedelta | None = None,
    cleanup_timeout: timedelta | None = timedelta(minutes=1),
) -> OperationSupervisor:
    return OperationSupervisor(
        registry=registry,
        journal=journal,
        event_stream=journal,
        leases=leases,
        operands=operands,
        owner_id=owner_id,
        lease_token_factory=lambda: token,
        clock=(lambda: _NOW) if clock is None else clock,
        lease_duration=lease_duration,
        execution_timeout=execution_timeout,
        cleanup_timeout=cleanup_timeout,
        response_token_factory=lambda: _RESPONSE_TOKEN,
    )


def _request(*, subject_ref: str = "subject:one", idempotency_key: str | None = None) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id="operation.supervisor.test",
        subject_ref=subject_ref,
        payload=SupervisorRequest(value="encrypted-operation-input"),
        idempotency_key=idempotency_key,
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
        with pytest.raises(ValueError, match="conflict lease"):
            asyncio.run(second.submit(_request(subject_ref="subject:shared"), operation_id="6" * 64))
        separate_operation = asyncio.run(second.submit(_request(subject_ref="subject:separate"), operation_id="7" * 64))

        assert asyncio.run(journal.load(first_operation)).identity.subject_ref == "subject:shared"
        assert asyncio.run(journal.load(separate_operation)).identity.subject_ref == "subject:separate"


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
            asyncio.run(supervisor.start(operation_id))

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
        terminal = asyncio.run(supervisor.start(operation_id))

        assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
        assert terminal.effect is OperationEffect.NONE
        assert terminal.terminal_receipt is not None
        assert terminal.terminal_receipt.refusal_ref == get_registered_error_code(AeatLiveReadNotEnabledError()).code
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
        terminal = asyncio.run(supervisor.start(operation_id))
        replay = asyncio.run(journal.read_after(operation_id, 0, limit=10))

        assert terminal.terminal_condition is OperationTerminalCondition.FAILED
        assert terminal.effect is OperationEffect.UPDATED
        assert terminal.terminal_receipt is not None
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
        terminal = asyncio.run(supervisor.start(operation_id))
        replay = asyncio.run(journal.read_after(operation_id, 0, limit=10))

        assert get_registered_error_code(CoreError()).code == "ERROR_CADRUMO_CORE"
        assert terminal.terminal_condition is OperationTerminalCondition.FAILED
        assert terminal.terminal_receipt is not None
        assert terminal.terminal_receipt.refusal_ref is None
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


def test_start_cancellation_propagates_without_false_terminal_artifacts(tmp_path: Path) -> None:
    """Cancelling start crosses the executor boundary and leaves controlled settlement to the caller."""
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
            start_task = asyncio.create_task(supervisor.start(operation_id))
            await executor.started.wait()
            start_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await start_task

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
        waiting = asyncio.run(supervisor.start(operation_id))
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

        with pytest.raises(ValueError, match="conflict lease"):
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


def test_supervisor_renews_exact_lease_before_expiry_and_settles_beyond_original_duration(tmp_path: Path) -> None:
    """A renewal made while live retains exclusive settlement beyond the original window."""
    observed_at = [_NOW]
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
            clock=lambda: observed_at[0],
            lease_duration=timedelta(minutes=1),
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))

        observed_at[0] = _NOW + timedelta(seconds=30)
        running = asyncio.run(supervisor.start(operation_id))
        scope_ref = operation_conflict_scope_reference(
            definition_id=running.identity.definition_id,
            subject_ref=running.identity.subject_ref,
        )
        renewed = asyncio.run(leases.inspect(scope_ref, operation_id, observed_at=observed_at[0]))

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
        executor = WaitingExecutor(started=started, release=release)
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
            start_task = asyncio.create_task(supervisor.start(operation_id))
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
            with pytest.raises(ValueError, match="conflict lease"):
                await contender.submit(_request(), operation_id="6" * 64)

            release.set()
            finished = await start_task
            return await supervisor.settle(
                operation_id,
                OperationTerminalReceipt(
                    identity=finished.identity,
                    revision=finished.revision + 1,
                    condition=OperationTerminalCondition.SUCCEEDED,
                    effect=OperationEffect.NONE,
                    settled_at=observed_at[0],
                    result_ref="result:heartbeat-settlement",
                ),
            )

        terminal = asyncio.run(run_quiet_executor())
        assert terminal.lifecycle is OperationLifecycle.TERMINAL


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
            start_task = asyncio.create_task(owner.start(operation_id))
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

            with pytest.raises(ValueError, match="renewal was refused"):
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
            asyncio.run(owner.start(operation_id))

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
        executors: list[DeclaredResourceExecutor] = []

        def build_executor() -> DeclaredResourceExecutor:
            executor = DeclaredResourceExecutor()
            executors.append(executor)
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
        running = asyncio.run(owner.start(operation_id))
        assert len(executors) == 1
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

        winner_running = asyncio.run(contender.start(winner_id))
        assert len(executors) == 2
        winner_resource = executors[1].resource
        assert winner_resource is not None
        terminal = asyncio.run(
            contender.settle(
                winner_id,
                OperationTerminalReceipt(
                    identity=winner_running.identity,
                    revision=winner_running.revision + 1,
                    condition=OperationTerminalCondition.SUCCEEDED,
                    effect=OperationEffect.NONE,
                    settled_at=_NOW,
                    result_ref="result:winner-settlement",
                ),
            )
        )

        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert stale_resource.close_calls == 0
        assert winner_resource.close_calls == 1


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

        def audit_open(event: str, arguments: tuple[object, ...]) -> None:
            if event != "open" or not arguments:
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

        asyncio.run(sustain_non_terminal_wait())


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
        waiting = asyncio.run(owner.start(operation_id))
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
        registry = _registry(
            executor_type=IdleExecutor,
            build=IdleExecutor,
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
        running = asyncio.run(supervisor.start(operation_id))
        cancellation = asyncio.run(supervisor.request_cancel(operation_id))

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
            start_task = asyncio.create_task(supervisor.start(operation_id))
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
            start_task = asyncio.create_task(supervisor.start(operation_id))
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
            start_task = asyncio.create_task(supervisor.start(operation_id))
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
            start_task = asyncio.create_task(supervisor.start(operation_id))
            await executor.cancellation_observed.wait()
            await asyncio.sleep(0.08)
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


def test_reconcile_takes_over_expired_owner_settles_and_releases_scope(tmp_path: Path) -> None:
    """A new owner with no local task admits genuine owner-loss interruption and frees the scope."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        registry = _registry(
            executor_type=IdleExecutor,
            build=IdleExecutor,
            capabilities=_capabilities(permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})),
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
        operation_id = asyncio.run(owner.submit(_request(subject_ref="subject:shared"), operation_id="3" * 64))
        asyncio.run(owner.start(operation_id))
        recovered_at = _NOW + timedelta(minutes=2)
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: recovered_at,
        )

        assert operation_id not in recovery._executor_tasks
        terminal = asyncio.run(recovery.reconcile(operation_id))
        released = asyncio.run(
            leases.inspect(
                operation_conflict_scope_reference(
                    definition_id=terminal.identity.definition_id,
                    subject_ref=terminal.identity.subject_ref,
                ),
                terminal.identity.operation_id,
                observed_at=recovered_at,
            )
        )
        replacement = asyncio.run(recovery.submit(_request(subject_ref="subject:shared"), operation_id="6" * 64))

        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert terminal.terminal_condition is OperationTerminalCondition.INTERRUPTED
        assert terminal.effect is OperationEffect.UNKNOWN
        replayed = asyncio.run(journal.read_after(operation_id, 0, limit=20))
        outcomes = tuple(event.outcome for event in replayed.events if isinstance(event, OperationReconciliationEvent))
        assert outcomes == (OperationReconciliationOutcome.INTERRUPTED,)
        assert released.current is None
        assert replacement == "6" * 64


def test_reconcile_foreign_expired_lease_orphans_target_without_mutating_foreign_journal(tmp_path: Path) -> None:
    """A target owns only its acquired takeover; the foreign operation record is untouched."""
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
            lease_duration=timedelta(minutes=1),
        )
        target_id = asyncio.run(owner.submit(_request(subject_ref="subject:shared"), operation_id="3" * 64))
        target = asyncio.run(journal.load(target_id))
        scope_ref = operation_conflict_scope_reference(
            definition_id=target.identity.definition_id,
            subject_ref=target.identity.subject_ref,
        )
        target_lease = asyncio.run(leases.inspect(scope_ref, target_id, observed_at=_NOW)).current
        assert target_lease is not None
        foreign_at = _NOW + timedelta(minutes=2)
        foreign_lease = OperationOwnerLease(
            operation_id="6" * 64,
            scope_ref=scope_ref,
            owner_id="7" * 64,
            token="8" * 64,
            acquired_at=foreign_at,
            expires_at=foreign_at + timedelta(minutes=1),
        )
        assert (
            asyncio.run(leases.compare_and_swap(target_lease, foreign_lease, observed_at=foreign_at)).disposition
            is OperationLeaseDisposition.TAKEN_OVER
        )
        foreign_snapshot = OperationPersistedSnapshot(
            identity=OperationIdentity(
                operation_id=foreign_lease.operation_id,
                definition_id=target.identity.definition_id,
                subject_ref=target.identity.subject_ref,
            ),
            definition_contract_digest=target.definition_contract_digest,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            request_reference=target.request_reference,
            revision=0,
            lifecycle=OperationLifecycle.CREATED,
            started_at=foreign_at,
            updated_at=foreign_at,
            execution_deadline=None,
            cleanup_deadline=None,
            cancellation_requested_at=None,
            cancellation_acknowledged_at=None,
            cancellation_deferred=False,
        )
        asyncio.run(journal.create(foreign_snapshot, lease=foreign_lease))
        foreign_path = storage_root / "operation-journals" / f"{foreign_lease.operation_id}.json"
        foreign_before = foreign_path.read_bytes()
        recovered_at = foreign_at + timedelta(minutes=2)
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: recovered_at,
        )

        terminal = asyncio.run(recovery.reconcile(target_id))
        released = asyncio.run(leases.inspect(scope_ref, target_id, observed_at=recovered_at))
        replayed = asyncio.run(journal.read_after(target_id, 0, limit=20))

    assert terminal.terminal_condition is OperationTerminalCondition.INTERRUPTED
    assert terminal.effect is OperationEffect.UNKNOWN
    assert tuple(event.outcome for event in replayed.events if isinstance(event, OperationReconciliationEvent)) == (
        OperationReconciliationOutcome.ORPHANED,
    )
    assert foreign_path.read_bytes() == foreign_before
    assert asyncio.run(journal.load(foreign_lease.operation_id)) == foreign_snapshot
    assert released.current is None


def test_reconcile_recovers_an_unstarted_expired_entry_with_new_durable_ownership(tmp_path: Path) -> None:
    """A separate startup supervisor re-establishes only a provably effect-free created entry."""
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
        operation_id = asyncio.run(owner.submit(_request(), operation_id="3" * 64))
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: _NOW + timedelta(minutes=2),
        )

        recovered = asyncio.run(recovery.reconcile(operation_id))
        restarted = asyncio.run(recovery.start(operation_id))

    assert recovered.lifecycle is OperationLifecycle.CREATED
    assert isinstance(recovered.events[0], OperationReconciliationEvent)
    assert recovered.events[0].outcome is OperationReconciliationOutcome.RECOVERED
    assert len(recovered.events[0].lease_evidence_ref) == 64
    assert restarted.lifecycle is OperationLifecycle.RUNNING


def test_reconcile_reenters_only_a_declared_valid_checkpoint(tmp_path: Path) -> None:
    """A resumable definition resumes its actual executor, not merely its old snapshot."""
    executors: list[ResumableReviewExecutor] = []

    def build() -> ResumableReviewExecutor:
        executor = ResumableReviewExecutor()
        executors.append(executor)
        return executor

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        registry = _registry(
            executor_type=ResumableReviewExecutor,
            build=build,
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
        waiting = asyncio.run(owner.start(operation_id))
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: _NOW + timedelta(minutes=2),
        )

        resumed = asyncio.run(recovery.reconcile(operation_id))
        replayed = asyncio.run(journal.read_after(operation_id, 0, limit=20))

    assert waiting.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
    assert len(executors) == 2
    assert executors[1].resume_checkpoints == [waiting.pending_interaction]
    assert resumed.lifecycle is OperationLifecycle.RUNNING
    assert resumed.pending_interaction is None
    assert tuple(event.outcome for event in replayed.events if isinstance(event, OperationReconciliationEvent)) == (
        OperationReconciliationOutcome.RESUMED,
    )


def test_resumed_executor_result_reference_settles_the_recovered_operation(tmp_path: Path) -> None:
    """A resumed executor's domain reference follows the same terminal join as start."""
    executors: list[ResumableReviewExecutor] = []
    result_ref = "result:resumed-operation"

    def build() -> ResumableReviewExecutor:
        executor = ResumableReviewExecutor(result_ref=result_ref if executors else None)
        executors.append(executor)
        return executor

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "resumed-result-state",
            profile_objects=profile.repository,
        )
        registry = _registry(
            executor_type=ResumableReviewExecutor,
            build=build,
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
        waiting = asyncio.run(owner.start(operation_id))
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
        reloaded = asyncio.run(journal.load(operation_id))

    assert waiting.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
    assert len(executors) == 2
    assert terminal.lifecycle is OperationLifecycle.TERMINAL
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.terminal_receipt is not None
    assert terminal.terminal_receipt.result_ref == result_ref
    assert reloaded == terminal


def test_reconcile_refuses_changed_definition_digest_before_reentry(tmp_path: Path) -> None:
    """A checkpoint valid for the old registry cannot enter a changed definition."""
    executors: list[ResumableReviewExecutor] = []

    def build() -> ResumableReviewExecutor:
        executor = ResumableReviewExecutor()
        executors.append(executor)
        return executor

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        owner_registry = _registry(
            executor_type=ResumableReviewExecutor,
            build=build,
            capabilities=_capabilities(
                durability=OperationDurability.RESUMABLE,
                replay=OperationReplayPolicy.RESUMABLE,
            ),
            interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
            reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
        )
        owner = _supervisor(
            registry=owner_registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            lease_duration=timedelta(minutes=1),
        )
        operation_id = asyncio.run(owner.submit(_request(), operation_id="3" * 64))
        waiting = asyncio.run(owner.start(operation_id))
        changed_registry = _registry(
            executor_type=ResumableReviewExecutor,
            build=build,
            capabilities=_capabilities(
                durability=OperationDurability.RESUMABLE,
                replay=OperationReplayPolicy.RESUMABLE,
            ),
            interaction_kinds=frozenset({OperationInteractionKind.INPUT}),
            reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
        )
        recovery = _supervisor(
            registry=changed_registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: _NOW + timedelta(minutes=2),
        )

        journal_path = tmp_path / "durable-state" / "operation-journals" / f"{operation_id}.json"
        before_response = journal_path.read_bytes()
        with pytest.raises(ValueError, match="no longer reproduces"):
            asyncio.run(
                recovery.respond(_response(intent="apply", operation_id=operation_id, revision=waiting.revision))
            )
        assert journal_path.read_bytes() == before_response
        with pytest.raises(ValueError, match="no longer reproduces"):
            asyncio.run(recovery.reconcile(operation_id))
        reloaded = asyncio.run(journal.load(operation_id))

    assert waiting.pending_interaction is not None
    assert reloaded == waiting
    assert len(executors) == 1


def test_reconcile_refuses_resume_without_a_declared_valid_checkpoint(tmp_path: Path) -> None:
    """An expired resumable definition without a checkpoint settles unknown interruption."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        registry = _registry(
            executor_type=ResumableIdleExecutor,
            build=ResumableIdleExecutor,
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
        asyncio.run(owner.start(operation_id))
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

    assert terminal.terminal_condition is OperationTerminalCondition.INTERRUPTED
    assert terminal.effect is OperationEffect.UNKNOWN


def test_reconcile_classifies_absent_lease_as_orphan_before_unknown_interruption(tmp_path: Path) -> None:
    """An existing journal without a current durable lease cannot become a resumed operation."""
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
        operation_id = asyncio.run(owner.submit(_request(), operation_id="3" * 64))
        scope_ref = operation_conflict_scope_reference(
            definition_id="operation.supervisor.test", subject_ref="subject:one"
        )
        observed = asyncio.run(leases.inspect(scope_ref, operation_id, observed_at=_NOW))
        assert observed.current is not None
        assert (
            asyncio.run(leases.release(observed.current, observed_at=_NOW)).disposition
            is OperationLeaseDisposition.RELEASED
        )
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
        )

        terminal = asyncio.run(recovery.reconcile(operation_id))
        replayed = asyncio.run(journal.read_after(operation_id, 0, limit=20))

    assert terminal.terminal_condition is OperationTerminalCondition.INTERRUPTED
    assert terminal.effect is OperationEffect.UNKNOWN
    assert tuple(event.outcome for event in replayed.events if isinstance(event, OperationReconciliationEvent)) == (
        OperationReconciliationOutcome.ORPHANED,
    )


def test_secure_review_publication_and_consumed_continuation_recover_without_reacquisition(
    tmp_path: Path,
) -> None:
    """A consumed secure review resumes after restart without repeating initial acquisition."""
    DurableContinuationExecutor.reset()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        storage_root = tmp_path / "durable-state"
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        registry = _registry(
            executor_type=DurableContinuationExecutor,
            build=DurableContinuationExecutor,
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

        async def publish_consume_and_schedule() -> tuple[str, OperationConsumedInteraction]:
            operation_id = await owner.submit(_request(), operation_id="3" * 64)
            waiting = await owner.start(operation_id)
            pending = waiting.pending_interaction
            assert pending is not None
            secured = await operands.resolve(pending.reviewed_proposal_digest, ReviewedOperand)
            assert secured == ReviewedOperand(observation="encrypted post-submission observation")
            consumed = await owner.respond(
                OperationApplyResponse(
                    interaction_id=pending.request.interaction_id,
                    operation_id=operation_id,
                    revision=pending.request.revision,
                    response_token=_RESPONSE_TOKEN,
                    continuation_digest=pending.request.continuation_digest,
                    reviewed_proposal_digest=pending.reviewed_proposal_digest,
                    actor_ref="operator:integration",
                    responded_at=_NOW,
                    baseline_digest=_BASELINE_DIGEST,
                    proposed_effect_digest=_PROPOSED_EFFECT_DIGEST,
                )
            )
            await DurableContinuationExecutor.resumed.wait()
            return operation_id, consumed

        operation_id, consumed = asyncio.run(publish_consume_and_schedule())
        persisted = asyncio.run(journal.load(operation_id))
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
            clock=lambda: _NOW + timedelta(minutes=2),
        )
        resumed = asyncio.run(recovery.reconcile(operation_id))

    assert persisted.pending_interaction is None
    assert persisted.consumed_interactions == (consumed,)
    assert consumed.intent.value == "apply"
    assert (
        consumed.checkpoint.reviewed_proposal_digest
        == persisted.consumed_interactions[0].checkpoint.reviewed_proposal_digest
    )
    assert DurableContinuationExecutor.acquisitions == 1
    assert DurableContinuationExecutor.resume_checkpoints == [consumed, consumed]
    assert resumed.lifecycle is OperationLifecycle.RUNNING
    assert resumed.phase_code == "operation.phase.declared"


def test_reconcile_refuses_active_or_corrupt_lease_without_journal_mutation(tmp_path: Path) -> None:
    """Live or unreadable owner evidence never authorizes a reconciliation transition."""
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
        journal_path = storage_root / "operation-journals" / f"{operation_id}.json"
        journal_before = journal_path.read_bytes()
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="4" * 64,
            token="5" * 64,
        )

        with pytest.raises(ValueError, match="active owner"):
            asyncio.run(recovery.reconcile(operation_id))
        assert journal_path.read_bytes() == journal_before

        scope_ref = operation_conflict_scope_reference(
            definition_id="operation.supervisor.test", subject_ref="subject:one"
        )
        lease_path = storage_root / "operation-journals" / f"{scope_ref}.lease.json"
        lease_path.write_bytes(b"invalid durable lease")
        with pytest.raises(RepositoryError, match="invalid operation lease"):
            asyncio.run(recovery.reconcile(operation_id))
        assert journal_path.read_bytes() == journal_before


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
        running = asyncio.run(supervisor.start(operation_id))

        with pytest.raises(ValueError, match="terminal receipt effect is not declared"):
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


def _response(
    *,
    intent: str,
    operation_id: str,
    revision: int,
) -> OperationApplyResponse | OperationRejectResponse:
    if intent == "apply":
        return OperationApplyResponse(
            interaction_id="f" * 64,
            operation_id=operation_id,
            revision=revision,
            response_token=_RESPONSE_TOKEN,
            continuation_digest=_CONTINUATION_DIGEST,
            reviewed_proposal_digest=_REVIEWED_PROPOSAL_DIGEST,
            actor_ref="operator:reviewer",
            responded_at=_NOW,
            baseline_digest=_BASELINE_DIGEST,
            proposed_effect_digest=_PROPOSED_EFFECT_DIGEST,
        )
    if intent == "reject":
        return OperationRejectResponse(
            interaction_id="f" * 64,
            operation_id=operation_id,
            revision=revision,
            response_token=_RESPONSE_TOKEN,
            continuation_digest=_CONTINUATION_DIGEST,
            reviewed_proposal_digest=_REVIEWED_PROPOSAL_DIGEST,
            actor_ref="operator:reviewer",
            responded_at=_NOW,
            reason_code="operation.review.rejected",
        )
    raise ValueError(f"unsupported test response intent: {intent}")
