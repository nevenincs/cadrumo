"""Real durable-operation proofs exercised through :class:`OperationSupervisor`."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
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
    StorageHierarchyRegistry,
    StorageNamespaceScope,
)
from ....core import STRICT_FROZEN_CONFIG
from ....core.classification import SensitivityClass
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    OperationApplyResponse,
    OperationBaselinePolicy,
    OperationCancellation,
    OperationCapabilities,
    OperationClosePolicy,
    OperationConflictScope,
    OperationDeadline,
    OperationDefinition,
    OperationDurability,
    OperationEffect,
    OperationExecutor,
    OperationExecutorContext,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationIdentity,
    OperationInteractionKind,
    OperationInteractionRequest,
    OperationLifecycle,
    OperationNoticeEvent,
    OperationOwnedResource,
    OperationPendingInteraction,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationRejectResponse,
    OperationReplayPolicy,
    OperationRequest,
    OperationSecureReferenceStore,
    OperationSensitiveInputPolicy,
    OperationSupervisor,
    OperationTerminalCondition,
    OperationTerminalReceipt,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 14, 15, tzinfo=UTC)
_NAMESPACE = SecureObjectNamespaceDefinition(
    key="operation_supervisor_test",
    namespace="cadrumo-test.operations.supervisor",
    owner="cadrumo.application.operations.tests.test_supervisor",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=1,
    object_key_grammar="{content_digest}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)
_CONTINUATION_DIGEST = "a" * 64
_RESPONSE_TOKEN = "b" * 64
_REVIEWED_PROPOSAL_DIGEST = "c" * 64
_BASELINE_DIGEST = "d" * 64
_PROPOSED_EFFECT_DIGEST = "e" * 64


class SupervisorRequest(BaseModel):
    """Concrete encrypted operand used only through the real secure adapter."""

    model_config = STRICT_FROZEN_CONFIG

    value: str = Field(min_length=1)


class SupervisorResult(BaseModel):
    """Concrete result schema required by the operation registry."""

    model_config = STRICT_FROZEN_CONFIG

    reference: str = Field(min_length=1)


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


class UndeclaredInteractionExecutor:
    """Concrete executor that attempts an interaction outside its definition."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request
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
        await context.interactions.request(_pending_interaction(context.identity))
        return None


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


def _registered_objects(profile_objects: SecureObjectRepository) -> SecureObjectRepository:
    """Register the test-only namespace on the genuine active-profile repository."""
    registry = profile_objects.namespace_registry
    assert registry is not None
    return SecureObjectRepository(
        engine=profile_objects.engine,
        namespace_registry=StorageHierarchyRegistry(
            namespaces=(*registry.namespaces, _NAMESPACE),
            paths=registry.paths,
        ),
    )


def _capabilities(
    *,
    owned_resources: frozenset[OperationOwnedResource] = frozenset(),
    permitted_effects: frozenset[OperationEffect] = frozenset({OperationEffect.NONE}),
) -> OperationCapabilities:
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.NONE,
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
    interaction_kinds: frozenset[OperationInteractionKind] = frozenset(),
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
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
    )


def _registry(
    *,
    executor_type: type[object],
    build: Callable[[], object],
    interaction_kinds: frozenset[OperationInteractionKind] = frozenset(),
) -> OperationRegistry:
    return OperationRegistry(
        definitions=(
            _definition(
                executor_type=executor_type,
                build=build,
                interaction_kinds=interaction_kinds,
            ),
        )
    )


def _supervisor(
    *,
    registry: OperationRegistry,
    journal: OperationJournalRepository,
    leases: OperationLeaseFilesystemRepository,
    operands: OperationSecureReferenceStore,
    owner_id: str,
    token: str,
) -> OperationSupervisor:
    return OperationSupervisor(
        registry=registry,
        journal=journal,
        leases=leases,
        operands=operands,
        owner_id=owner_id,
        lease_token_factory=lambda: token,
        clock=lambda: _NOW,
        lease_duration=timedelta(minutes=10),
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
        OperationSecureReferenceRepository(objects=_registered_objects(profile_objects), namespace=_NAMESPACE),
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
    """The context refuses executor mutation beyond the one safe started event."""
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

        with pytest.raises(ValueError, match="not declared"):
            asyncio.run(supervisor.start(operation_id))

        after_refusal = asyncio.run(journal.load(operation_id))
        assert after_refusal.lifecycle is OperationLifecycle.RUNNING
        assert after_refusal.revision == 1
        assert len(after_refusal.events) == 1
        assert isinstance(after_refusal.events[0], OperationNoticeEvent)
        assert after_refusal.events[0].notice_code == "operation.started"
        assert after_refusal.event_cursor == 1
        assert after_refusal.phase_code is None
        assert after_refusal.pending_interaction is None
        assert after_refusal.effect is OperationEffect.NONE

        receipt = OperationTerminalReceipt(
            identity=after_refusal.identity,
            revision=2,
            condition=OperationTerminalCondition.FAILED,
            effect=OperationEffect.NONE,
            settled_at=_NOW,
        )
        terminal = asyncio.run(supervisor.settle(operation_id, receipt))
        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        if isinstance(executor, UndeclaredResourceExecutor):
            assert executor.resource is not None
            assert executor.resource.close_calls == 0


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
