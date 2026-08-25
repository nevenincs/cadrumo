"""Production-supervisor contracts for definition-bound executor mutations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import (
    OperationSecureReferenceRepository,
    operation_secure_reference_repository,
)
from cadrumo.application.operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from cadrumo.application.operations.models import (
    OperationRequest,
    OperationTerminalReceipt,
)
from cadrumo.application.operations.persistence.events import OperationNoticeEvent
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from cadrumo.core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)

from ....adapters.persistence.storage import (
    SecureObjectRepository,
)
from ....core import STRICT_FROZEN_CONFIG
from ....tests.secure_sql import isolated_runtime_profile
from ..owner import OperationExecutorContext
from ..supervisor import OperationSupervisor, _SupervisorExecutorContext

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 14, 16, tzinfo=UTC)
_DEFINITION_ID = "operation.executor.contract"


class ExecutorContractRequest(BaseModel):
    """Concrete secure operand submitted to the production supervisor."""

    model_config = STRICT_FROZEN_CONFIG

    value: str = Field(min_length=1)


class IdleExecutor:
    """Concrete executor used only to form a valid registered definition."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> None:
        del request, context


class UndeclaredPhaseExecutor:
    """Concrete executor that claims a phase omitted from its definition."""

    def __init__(self) -> None:
        self.snapshot_before_attempt: OperationPersistedSnapshot | None = None

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> None:
        del request
        assert isinstance(context, _SupervisorExecutorContext)
        self.snapshot_before_attempt = context.snapshot
        await context.events.phase("operation.phase.undeclared")


class UndeclaredEffectExecutor:
    """Concrete executor that claims an effect omitted from its definition."""

    def __init__(self) -> None:
        self.snapshot_before_attempt: OperationPersistedSnapshot | None = None

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> None:
        del request
        assert isinstance(context, _SupervisorExecutorContext)
        self.snapshot_before_attempt = context.snapshot
        await context.events.effect(OperationEffect.UPDATED)


class CloseProbe:
    """Concrete asynchronous resource whose close call is observable after settlement."""

    def __init__(self) -> None:
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1


class UndeclaredResourceExecutor:
    """Concrete executor that transfers an undeclared resource family."""

    def __init__(self) -> None:
        self.snapshot_before_attempt: OperationPersistedSnapshot | None = None
        self.resource: CloseProbe | None = None

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> None:
        del request
        assert isinstance(context, _SupervisorExecutorContext)
        self.snapshot_before_attempt = context.snapshot
        self.resource = CloseProbe()
        context.cleanup.own(self.resource, family=OperationOwnedResource.ASYNC_TASK)


def _capabilities() -> OperationCapabilities:
    """Declare the narrow valid contract that omits the tested mutations."""
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def _definition(*, executor_type: type[object], build: Callable[[], object]) -> OperationDefinition:
    """Build one public registered operation definition with narrow declarations."""
    return OperationDefinition(
        definition_id=_DEFINITION_ID,
        request_type=ExecutorContractRequest,
        result_type=None,
        executor_factory=OperationExecutorFactory(
            request_type=ExecutorContractRequest,
            executor_type=executor_type,
            build=build,
        ),
        phase_codes=("operation.phase.declared",),
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
    )


def _registry(*, executor_type: type[object], build: Callable[[], object]) -> OperationRegistry:
    definition = _definition(executor_type=executor_type, build=build)
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.executor.contract.request",
            schema_version=1,
            model_type=ExecutorContractRequest,
        ),
    )
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


def _supervisor(
    *,
    registry: OperationRegistry,
    journal: OperationJournalRepository,
    leases: OperationLeaseFilesystemRepository,
    operands: OperationSecureReferenceRepository,
) -> OperationSupervisor:
    """Construct the public supervisor over the real persistence adapters."""
    return OperationSupervisor(
        registry=registry,
        journal=journal,
        event_stream=journal,
        leases=leases,
        operands=operands,
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: _NOW,
        lease_duration=timedelta(minutes=10),
    )


def _request() -> OperationRequest[BaseModel]:
    """Create one real encrypted operand submission."""
    return OperationRequest[BaseModel](
        definition_id=_DEFINITION_ID,
        subject_ref="subject:executor-contract",
        payload=ExecutorContractRequest(value="encrypted-operation-input"),
        idempotency_key=None,
    )


def _repositories(
    *,
    storage_root: Path,
    profile_objects: SecureObjectRepository,
) -> tuple[OperationJournalRepository, OperationLeaseFilesystemRepository, OperationSecureReferenceRepository]:
    """Build real filesystem and encrypted persistence adapters."""
    return (
        OperationJournalRepository(storage_root=storage_root),
        OperationLeaseFilesystemRepository(storage_root=storage_root),
        operation_secure_reference_repository(objects=profile_objects),
    )


def test_operation_registry_rejects_duplicate_definition_identities() -> None:
    """Canonical definitions may not share one immutable registry identity."""
    definition = _definition(executor_type=IdleExecutor, build=IdleExecutor)
    conflicting_identity = definition.model_copy(update={"phase_codes": ("operation.phase.alternate",)})

    with pytest.raises(ValueError, match="definition IDs must be unique"):
        OperationRegistry(definitions=(definition, conflicting_identity))


@pytest.mark.parametrize(
    "executor",
    (UndeclaredPhaseExecutor(), UndeclaredEffectExecutor()),
    ids=("phase", "effect"),
)
def test_supervisor_context_refuses_undeclared_event_claims_without_journal_mutation(
    tmp_path: Path,
    executor: UndeclaredPhaseExecutor | UndeclaredEffectExecutor,
) -> None:
    """Phase and effect refusals retain the exact pre-attempt persisted history."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        supervisor = _supervisor(
            registry=_registry(executor_type=type(executor), build=lambda: executor),
            journal=journal,
            leases=leases,
            operands=operands,
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))

        with pytest.raises(ValueError, match="not declared"):
            asyncio.run(supervisor.start(operation_id))

        after_refusal = asyncio.run(supervisor.inspect(operation_id))
        assert executor.snapshot_before_attempt is not None
        assert after_refusal == executor.snapshot_before_attempt
        assert after_refusal.lifecycle is OperationLifecycle.RUNNING
        assert after_refusal.event_cursor == 1
        assert len(after_refusal.events) == 1
        assert isinstance(after_refusal.events[0], OperationNoticeEvent)
        assert after_refusal.events[0].notice_code == "operation.started"


def test_supervisor_context_refuses_undeclared_resource_ownership_without_journal_mutation(tmp_path: Path) -> None:
    """A refused resource-family handoff neither persists nor reaches settlement cleanup."""
    executor = UndeclaredResourceExecutor()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        supervisor = _supervisor(
            registry=_registry(executor_type=type(executor), build=lambda: executor),
            journal=journal,
            leases=leases,
            operands=operands,
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))

        with pytest.raises(ValueError, match="not declared"):
            asyncio.run(supervisor.start(operation_id))

        after_refusal = asyncio.run(supervisor.inspect(operation_id))
        assert executor.snapshot_before_attempt is not None
        assert after_refusal == executor.snapshot_before_attempt
        assert executor.resource is not None

        terminal = asyncio.run(
            supervisor.settle(
                operation_id,
                OperationTerminalReceipt(
                    identity=after_refusal.identity,
                    revision=after_refusal.revision + 1,
                    condition=OperationTerminalCondition.FAILED,
                    effect=OperationEffect.NONE,
                    settled_at=_NOW,
                ),
            )
        )
        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert executor.resource.close_calls == 0
