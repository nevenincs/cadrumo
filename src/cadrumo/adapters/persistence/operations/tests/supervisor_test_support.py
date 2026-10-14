"""Test-only executors, fixtures-in-spirit, and builders for supervisor proofs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel, Field

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import (
    OperationSecureReferenceRepository,
    operation_secure_reference_repository,
)
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_runtime_profile,
)
from cadrumo.application.operations.authorization import OperationExecutionAuthority
from cadrumo.application.operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from cadrumo.application.operations.interactions import (
    OperationApplyResponse,
    OperationConsumedInteraction,
    OperationInteractionRequest,
    OperationPendingInteraction,
    OperationRejectResponse,
)
from cadrumo.application.operations.models import (
    OperationIdentity,
    OperationRequest,
    OperationTerminalReceipt,
)
from cadrumo.application.operations.operation_definition import OperationDefinition, OperationExecutorFactory
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.persistence.journal import (
    OperationPersistedSnapshot,
    OperationSecureReferenceStore,
)
from cadrumo.application.operations.persistence.leases import (
    OperationLeaseDisposition,
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from cadrumo.application.operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from cadrumo.application.operations.subject_reference import OperationSubjectReferenceV1
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.operations.supervisor_context import SupervisorExecutorContext
from cadrumo.application.operations.tests.authority_test_support import unread_authority_operation
from cadrumo.application.operator_actions.models import ActionReference
from cadrumo.core.access_gate.errors import AeatLiveReadNotEnabledError
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.errors.hierarchy import CoreError
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
)
from cadrumo.tests.aeat_literal_fixtures import REDACTION_TOKEN_QUERY_URL_CANARY

from .supervision_support import run_to_settlement

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
    recovered_resume_entered: asyncio.Event
    release_recovered_resume: asyncio.Event
    resume_checkpoints: list[OperationPendingInteraction | OperationConsumedInteraction]
    recovered_result_ref = "result:recovered-continuation"

    def __init__(self) -> None:
        if not hasattr(type(self), "resumed"):
            type(self).reset()

    @classmethod
    def reset(cls) -> None:
        cls.acquisitions = 0
        cls.resumed = asyncio.Event()
        cls.hold_first_resume = asyncio.Event()
        cls.recovered_resume_entered = asyncio.Event()
        cls.release_recovered_resume = asyncio.Event()
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
        type(self).recovered_resume_entered.set()
        await type(self).release_recovered_resume.wait()
        return type(self).recovered_result_ref


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
    """Concrete executor that transfers one declared resource, then stays live until released."""

    def __init__(self, *, result_ref: str | None = None) -> None:
        self.resource: TrackedAsyncResource | None = None
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self._result_ref = result_ref

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        resource = TrackedAsyncResource()
        self.resource = resource
        context.cleanup.own(resource, family=OperationOwnedResource.ASYNC_TASK)
        self.started.set()
        await self.release.wait()
        return self._result_ref


class UndeclaredInteractionExecutor:
    """Concrete executor that attempts an interaction outside its definition."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        assert isinstance(context, SupervisorExecutorContext)
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
        assert isinstance(context, SupervisorExecutorContext)
        await context.interactions.request(_pending_interaction(context.identity))
        return None


class ResumableReviewExecutor:
    """A real declared checkpoint executor that proves supervisor re-entry.

    With ``resume_entered`` and ``release_resume`` the resumed executor stays
    live after its phase until the test releases it, so the recovered running
    state can be observed before the resume settles.
    """

    def __init__(
        self,
        *,
        result_ref: str | None = None,
        resume_entered: asyncio.Event | None = None,
        release_resume: asyncio.Event | None = None,
    ) -> None:
        self.resume_checkpoints: list[OperationPendingInteraction] = []
        self._result_ref = result_ref
        self._resume_entered = resume_entered
        self._release_resume = release_resume

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
        assert isinstance(context, SupervisorExecutorContext)
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
        if self._resume_entered is not None:
            self._resume_entered.set()
        if self._release_resume is not None:
            await self._release_resume.wait()
        return self._result_ref


class ResumableIdleExecutor:
    """A resumable declaration whose initial execution publishes no checkpoint and stays live."""

    started: asyncio.Event
    release: asyncio.Event

    @classmethod
    def reset(cls) -> None:
        cls.started = asyncio.Event()
        cls.release = asyncio.Event()

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request, context
        type(self).started.set()
        await type(self).release.wait()
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

    def __init__(self, *, started: asyncio.Event, release: asyncio.Event, result_ref: str | None = None) -> None:
        self.started = started
        self.release = release
        self.cancelled = False
        self._result_ref = result_ref

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
        return self._result_ref


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


async def _close_host_over_live_executor(
    supervisor: OperationSupervisor,
    operation_id: str,
    started: asyncio.Event,
) -> OperationPersistedSnapshot:
    """Start one operation and close its host once the executor is live.

    A closing host cancels a detachable operation's executor mid-work and
    settles nothing, so the journal keeps the running record and the lease for
    a later hand settlement or owner recovery.
    """
    waiter = asyncio.create_task(run_to_settlement(supervisor, operation_id))
    await started.wait()
    waiter.cancel()
    with suppress(asyncio.CancelledError):
        await waiter
    await supervisor.shutdown()
    return await supervisor.inspect(operation_id)


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
    close_policy: OperationClosePolicy = OperationClosePolicy.DETACH_ALLOWED,
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
        close_policy=close_policy,
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
        subject_reference=OperationSubjectReferenceV1.profile(),
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
        update={"action_reference": ActionReference(action_id="operator.contract.drift")}
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
    execution_authority: OperationExecutionAuthority | None = None,
) -> OperationSupervisor:
    return OperationSupervisor(
        authority_operation=unread_authority_operation(),
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
        execution_authority=execution_authority,
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


class UnregisteredSupervisorRequestRefinement(SupervisorRequest):
    """Is-a registered request, with identical fields, without being the registered request type."""


class PayloadTypeRecordingExecutor:
    """Record the concrete payload type the supervisor hands its executor."""

    def __init__(self) -> None:
        self.payload_types: list[type[BaseModel]] = []

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del context
        self.payload_types.append(type(request.payload))
        return "result:exact-payload"


class SubclassResolvingOperands:
    """Real encrypted store whose resolve breaks the port by answering with a subclass of the asked type."""

    def __init__(self, store: OperationSecureReferenceRepository) -> None:
        self._store = store

    async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
        return await self._store.put(operand, written_at=written_at)

    async def resolve[OperandT: BaseModel](self, reference: str, operand_type: type[OperandT]) -> OperandT:
        resolved = await self._store.resolve(reference, operand_type)
        if operand_type is not SupervisorRequest:
            return resolved
        return cast(OperandT, UnregisteredSupervisorRequestRefinement.model_validate(resolved.model_dump()))


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


def _admission_supervisor(
    tmp_path: Path,
    profile_objects: SecureObjectRepository,
    *,
    executor_type: type[object],
    build: Callable[[], object],
    capabilities: OperationCapabilities | None = None,
) -> tuple[OperationSupervisor, OperationJournalRepository]:
    journal, leases, operands = _repositories(storage_root=tmp_path / "durable-state", profile_objects=profile_objects)
    supervisor = _supervisor(
        registry=_registry(executor_type=executor_type, build=build, capabilities=capabilities),
        journal=journal,
        leases=leases,
        operands=operands,
        owner_id="1" * 64,
        token="2" * 64,
    )
    return supervisor, journal


def _start_and_walk_away(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> OperationPersistedSnapshot:
    """Start a failing operation, never await it, and let every reference to its task go."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        supervisor, journal = _admission_supervisor(
            tmp_path, profile.repository, executor_type=UndeclaredPhaseExecutor, build=UndeclaredPhaseExecutor
        )

        async def scenario() -> OperationPersistedSnapshot:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            await supervisor.start(operation_id)
            for _ in range(500):
                if _failure_logged(caplog):
                    break
                await asyncio.sleep(0.01)
            return await journal.load(operation_id)

        return asyncio.run(scenario())


def _failure_logged(caplog: pytest.LogCaptureFixture) -> bool:
    return any("stopped without settlement" in record.getMessage() for record in caplog.records)


_SHARED_SUBJECT = "subject:shared"


def _shared_scope_holder(
    leases: OperationLeaseFilesystemRepository,
    *,
    observed_at: datetime,
) -> OperationOwnerLease | None:
    """Return whichever lease currently holds the shared definition subject."""
    request = _request(subject_ref=_SHARED_SUBJECT)
    observed = asyncio.run(
        leases.inspect(
            operation_conflict_scope_reference(definition_id=request.definition_id, subject_ref=request.subject_ref),
            "0" * 64,
            observed_at=observed_at,
        )
    )
    return observed.current


def _settle_failed(supervisor: OperationSupervisor, operation_id: str) -> OperationPersistedSnapshot:
    created = asyncio.run(supervisor.inspect(operation_id))
    return asyncio.run(
        supervisor.settle(
            operation_id,
            OperationTerminalReceipt(
                identity=created.identity,
                revision=created.revision + 1,
                condition=OperationTerminalCondition.FAILED,
                effect=OperationEffect.NONE,
                settled_at=_NOW,
            ),
        )
    )


def _leave_settlement_lease_behind(
    leases: OperationLeaseFilesystemRepository,
    terminal: OperationPersistedSnapshot,
) -> OperationOwnerLease:
    """Recreate the state of a process that died between the terminal write and the lease release.

    Settlement writes both inside one lock hold, so only a crash inside that
    section reaches this state; the real lease repository writes the owner's
    lease back beside the real terminal journal.
    """
    leftover = OperationOwnerLease(
        operation_id=terminal.identity.operation_id,
        scope_ref=operation_conflict_scope_reference(
            definition_id=terminal.identity.definition_id,
            subject_ref=terminal.identity.subject_ref,
        ),
        owner_id="1" * 64,
        token="2" * 64,
        acquired_at=_NOW,
        expires_at=_NOW + timedelta(minutes=10),
    )
    written = asyncio.run(leases.acquire(leftover, observed_at=_NOW))
    assert written.disposition is OperationLeaseDisposition.ACQUIRED
    return leftover


def _abandon_running_operation(
    tmp_path: Path, profile_objects: SecureObjectRepository
) -> tuple[OperationJournalRepository, OperationLeaseFilesystemRepository, OperationSecureReferenceRepository, str]:
    """Leave a started operation whose host closed mid-run, with a one-minute lease nobody renews."""
    journal, leases, operands = _repositories(storage_root=tmp_path / "durable-state", profile_objects=profile_objects)
    started = asyncio.Event()
    executor = WaitingExecutor(started=started, release=asyncio.Event())
    owner = _supervisor(
        registry=_registry(executor_type=WaitingExecutor, build=lambda: executor),
        journal=journal,
        leases=leases,
        operands=operands,
        owner_id="1" * 64,
        token="2" * 64,
        lease_duration=timedelta(minutes=1),
    )
    operation_id = asyncio.run(owner.submit(_request(subject_ref=_SHARED_SUBJECT), operation_id="3" * 64))
    abandoned = asyncio.run(_close_host_over_live_executor(owner, operation_id, started))
    assert abandoned.lifecycle is OperationLifecycle.RUNNING
    return journal, leases, operands, operation_id


def _lapse_settler(
    *,
    journal: OperationJournalRepository,
    leases: OperationLeaseFilesystemRepository,
    operands: OperationSecureReferenceRepository,
    at: datetime,
    registry: OperationRegistry | None = None,
) -> OperationSupervisor:
    return _supervisor(
        registry=_registry(executor_type=WaitingExecutor, build=IdleExecutor) if registry is None else registry,
        journal=journal,
        leases=leases,
        operands=operands,
        owner_id="4" * 64,
        token="5" * 64,
        clock=lambda: at,
    )


class ImmediateResultExecutor:
    """Registered executor that returns its result reference as soon as it runs."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request, context
        return "result:settled-immediately"
