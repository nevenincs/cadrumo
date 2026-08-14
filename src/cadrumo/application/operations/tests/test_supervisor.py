"""Real durable-operation proofs exercised through :class:`OperationSupervisor`."""

from __future__ import annotations

import asyncio
import sys
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
    STORAGE_NAMESPACE_REGISTRY,
    RepositoryError,
    SecureObjectNamespaceDefinition,
    SecureObjectRepository,
    StorageCustodyDisposition,
    StorageHierarchyRegistry,
    StorageNamespaceScope,
)
from ....core import STRICT_FROZEN_CONFIG
from ....core.classification import SensitivityClass
from ....tests.secure_sql import isolated_ephemeral_secure_sql, isolated_runtime_profile
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
    OperationLeaseDisposition,
    OperationLifecycle,
    OperationNoticeEvent,
    OperationOwnedResource,
    OperationPendingInteraction,
    OperationPersistedSnapshot,
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
    operation_conflict_scope_reference,
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
    cancellation: OperationCancellation = OperationCancellation.UNSUPPORTED,
    owned_resources: frozenset[OperationOwnedResource] = frozenset(),
    permitted_effects: frozenset[OperationEffect] = frozenset({OperationEffect.NONE}),
) -> OperationCapabilities:
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=cancellation,
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
    capabilities: OperationCapabilities | None = None,
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
        capabilities=_capabilities() if capabilities is None else capabilities,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
    )


def _registry(
    *,
    executor_type: type[object],
    build: Callable[[], object],
    capabilities: OperationCapabilities | None = None,
    interaction_kinds: frozenset[OperationInteractionKind] = frozenset(),
) -> OperationRegistry:
    return OperationRegistry(
        definitions=(
            _definition(
                executor_type=executor_type,
                build=build,
                capabilities=capabilities,
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
    clock: Callable[[], datetime] | None = None,
    lease_duration: timedelta = timedelta(minutes=10),
) -> OperationSupervisor:
    return OperationSupervisor(
        registry=registry,
        journal=journal,
        leases=leases,
        operands=operands,
        owner_id=owner_id,
        lease_token_factory=lambda: token,
        clock=(lambda: _NOW) if clock is None else clock,
        lease_duration=lease_duration,
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


def test_reconcile_takes_over_expired_owner_settles_and_releases_scope(tmp_path: Path) -> None:
    """A new real owner takes over expiry, settles interruption, and frees the scope."""
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
        assert released.current is None
        assert replacement == "6" * 64


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
