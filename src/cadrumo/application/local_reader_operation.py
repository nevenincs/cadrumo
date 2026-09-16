"""Supervised operation for provisioning the local document reader from any frontend.

One definition, ``local-reader.provision``, carries the three actions a status
area offers -- start the runtime, pull reader models, verify them -- so a TUI
runs exactly what ``aeat config provision start|pull|verify`` runs. Install is
deliberately absent: it runs a package manager with the operator's consent,
and that consent is given at the CLI, not through a modal button.

Process control is injected. The application layer never spawns a process
itself; the entrypoint composition binds the outbound adapter.
"""

from __future__ import annotations

import asyncio
import threading
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from ..core.model_catalogue import ModelRole
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ..core.time.clock import now
from .local_reader import RoleModelTarget, role_model_targets
from .operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from .operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from .operations.owner import OperationEventEmitter, OperationExecutorContext
from .operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from .provisioning_host import RuntimeSpawner, start_runtime
from .provisioning_runtime import PullProgress, pull_runtime_model, verify_model_ready

__all__ = [
    "LOCAL_READER_OPERATION_DEFINITION_ID",
    "LOCAL_READER_OPERATION_SUBJECT",
    "LOCAL_READER_PULL_PROGRESS_UNIT",
    "LocalReaderModelOutcome",
    "LocalReaderModelOutcomeV1",
    "LocalReaderProvisionAction",
    "LocalReaderProvisionExecutor",
    "LocalReaderProvisionOutcome",
    "LocalReaderProvisionPublicResultV1",
    "LocalReaderProvisionRequest",
    "build_local_reader_operation_definition",
    "build_local_reader_operation_registration",
    "build_local_reader_pull_request",
    "build_local_reader_start_request",
    "build_local_reader_verify_request",
]

LOCAL_READER_OPERATION_DEFINITION_ID = "local-reader.provision"
#: The runtime is one per host, so every provisioning request shares one
#: subject and the definition-subject lease serialises them.
LOCAL_READER_OPERATION_SUBJECT = "local-reader:runtime"
LOCAL_READER_PULL_PROGRESS_UNIT = "local-reader.bytes"
_PHASES = (
    "local-reader.provision.preflight",
    "local-reader.provision.execute",
    "local-reader.provision.settlement",
)
_PROGRESS_POLL_S = 0.5


class LocalReaderProvisionAction(StrEnum):
    """What one provisioning operation does."""

    START = "start"
    PULL = "pull"
    VERIFY = "verify"


class LocalReaderProvisionRequest(CredentialFreeOperationRequest):
    """One provisioning action, over one role's model or every role's."""

    action: LocalReaderProvisionAction
    role: ModelRole | None = None


def _request(
    action: LocalReaderProvisionAction, role: ModelRole | None
) -> OperationRequest[LocalReaderProvisionRequest]:
    return OperationRequest(
        definition_id=LOCAL_READER_OPERATION_DEFINITION_ID,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        payload=LocalReaderProvisionRequest(action=action, role=role),
    )


def build_local_reader_start_request() -> OperationRequest[LocalReaderProvisionRequest]:
    """Build the request that starts the local runtime when it is not answering."""
    return _request(LocalReaderProvisionAction.START, None)


def build_local_reader_pull_request(role: ModelRole | None = None) -> OperationRequest[LocalReaderProvisionRequest]:
    """Build the request that pulls ``role``'s model, or every reader role's model."""
    return _request(LocalReaderProvisionAction.PULL, role)


def build_local_reader_verify_request(role: ModelRole | None = None) -> OperationRequest[LocalReaderProvisionRequest]:
    """Build the request that verifies ``role``'s model, or every reader role's model."""
    return _request(LocalReaderProvisionAction.VERIFY, role)


class LocalReaderModelOutcome(BaseModel):
    """What happened to one model, or to one role whose selection refused."""

    model_config = STRICT_FROZEN_CONFIG

    model: str | None = None
    roles: tuple[ModelRole, ...]
    succeeded: bool
    bytes_fetched: int | None = Field(default=None, ge=0)
    failed_condition_id: str | None = None


class LocalReaderProvisionOutcome(BaseModel):
    """The settled result of one provisioning operation."""

    model_config = STRICT_FROZEN_CONFIG

    action: LocalReaderProvisionAction
    succeeded: bool
    runtime_started: bool = False
    failed_condition_id: str | None = None
    models: tuple[LocalReaderModelOutcome, ...] = ()


class LocalReaderModelOutcomeV1(BaseModel):
    """Public projection of one model outcome."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    model: str | None = Field(default=None, min_length=1, max_length=256)
    roles: tuple[ModelRole, ...]
    succeeded: bool
    bytes_fetched: NonNegativeInt | None = None
    failed_condition_id: str | None = Field(default=None, min_length=1, max_length=128)


class LocalReaderProvisionPublicResultV1(BaseModel):
    """Public projection of a settled provisioning operation."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    action: LocalReaderProvisionAction
    succeeded: bool
    runtime_started: bool
    failed_condition_id: str | None = Field(default=None, min_length=1, max_length=128)
    models: tuple[LocalReaderModelOutcomeV1, ...]


def _project_result(result: BaseModel, terminal_receipt: OperationTerminalReceipt) -> BaseModel:
    del terminal_receipt
    outcome = LocalReaderProvisionOutcome.model_validate(result, strict=True)
    return LocalReaderProvisionPublicResultV1(
        action=outcome.action,
        succeeded=outcome.succeeded,
        runtime_started=outcome.runtime_started,
        failed_condition_id=outcome.failed_condition_id,
        models=tuple(
            LocalReaderModelOutcomeV1(
                model=item.model,
                roles=item.roles,
                succeeded=item.succeeded,
                bytes_fetched=item.bytes_fetched,
                failed_condition_id=item.failed_condition_id,
            )
            for item in outcome.models
        ),
    )


def _refused_target(target: RoleModelTarget) -> LocalReaderModelOutcome:
    verdict = target.selection_verdict
    return LocalReaderModelOutcome(
        roles=target.roles,
        succeeded=False,
        failed_condition_id=verdict.failed_condition_id if verdict is not None else None,
    )


class _ProgressRelay:
    """Carries the latest fetch progress from the worker thread to the event loop."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: PullProgress | None = None
        self._published: tuple[int, int] | None = None

    def record(self, progress: PullProgress) -> None:
        with self._lock:
            self._latest = progress

    async def publish(self, events: OperationEventEmitter) -> None:
        with self._lock:
            latest = self._latest
        if latest is None or latest.total_bytes is None or latest.completed_bytes is None:
            return
        reading = (min(latest.completed_bytes, latest.total_bytes), latest.total_bytes)
        if reading == self._published or reading[1] == 0:
            return
        self._published = reading
        await events.progress(completed=reading[0], total=reading[1], unit_code=LOCAL_READER_PULL_PROGRESS_UNIT)


class LocalReaderProvisionExecutor:
    """Run one start, pull or verify through the same application doors as the CLI."""

    def __init__(self, *, spawn: RuntimeSpawner) -> None:
        """Bind the injected runtime spawner."""
        self._spawn = spawn

    async def execute(
        self,
        request: OperationRequest[LocalReaderProvisionRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Execute the requested action and persist its settled outcome."""
        if request.subject_ref != LOCAL_READER_OPERATION_SUBJECT:
            raise ValueError("local-reader operation subject must name the local runtime")
        payload = request.payload
        await context.events.phase(_PHASES[0])
        await context.events.phase(_PHASES[1])
        if payload.action is LocalReaderProvisionAction.START:
            outcome = await self._start(context)
        elif payload.action is LocalReaderProvisionAction.PULL:
            outcome = await self._pull(payload.role, context)
        else:
            outcome = await self._verify(payload.role)
        await context.events.phase(_PHASES[2])
        return await context.operands.put(outcome, written_at=now())

    async def _start(self, context: OperationExecutorContext) -> LocalReaderProvisionOutcome:
        await context.events.effect(OperationEffect.UNKNOWN)
        started = await asyncio.to_thread(start_runtime, spawn=self._spawn)
        spawned = started.running and not started.already_running
        await context.events.effect(OperationEffect.UPDATED if spawned else OperationEffect.NONE)
        verdict = started.precondition_verdict
        return LocalReaderProvisionOutcome(
            action=LocalReaderProvisionAction.START,
            succeeded=started.running,
            runtime_started=spawned,
            failed_condition_id=verdict.failed_condition_id if verdict is not None else None,
        )

    async def _pull(self, role: ModelRole | None, context: OperationExecutorContext) -> LocalReaderProvisionOutcome:
        targets = role_model_targets(None if role is None else (role,))
        items: list[LocalReaderModelOutcome] = []
        fetched_any = False
        await context.events.effect(OperationEffect.UNKNOWN)
        for target in targets:
            if target.model is None or target.requirement_bytes is None:
                items.append(_refused_target(target))
                continue
            relay = _ProgressRelay()
            task = asyncio.create_task(
                asyncio.to_thread(pull_runtime_model, target.model, target.requirement_bytes, on_progress=relay.record)
            )
            while not task.done():
                await asyncio.wait({task}, timeout=_PROGRESS_POLL_S)
                await relay.publish(context.events)
            pulled = task.result()
            fetched_any = fetched_any or pulled.pulled
            verdict = pulled.precondition_verdict
            items.append(
                LocalReaderModelOutcome(
                    model=pulled.model,
                    roles=target.roles,
                    succeeded=pulled.pulled,
                    bytes_fetched=pulled.bytes_fetched,
                    failed_condition_id=verdict.failed_condition_id if verdict is not None else None,
                )
            )
        await context.events.effect(OperationEffect.UPDATED if fetched_any else OperationEffect.NONE)
        return _settled(LocalReaderProvisionAction.PULL, items)

    async def _verify(self, role: ModelRole | None) -> LocalReaderProvisionOutcome:
        items: list[LocalReaderModelOutcome] = []
        for target in role_model_targets(None if role is None else (role,)):
            if target.model is None:
                items.append(_refused_target(target))
                continue
            ready = await asyncio.to_thread(verify_model_ready, target.model)
            verdict = ready.precondition_verdict
            items.append(
                LocalReaderModelOutcome(
                    model=ready.model,
                    roles=target.roles,
                    succeeded=ready.ready,
                    failed_condition_id=verdict.failed_condition_id if verdict is not None else None,
                )
            )
        return _settled(LocalReaderProvisionAction.VERIFY, items)


def _settled(action: LocalReaderProvisionAction, items: list[LocalReaderModelOutcome]) -> LocalReaderProvisionOutcome:
    failed = next((item.failed_condition_id for item in items if not item.succeeded), None)
    return LocalReaderProvisionOutcome(
        action=action,
        succeeded=bool(items) and all(item.succeeded for item in items),
        failed_condition_id=failed,
        models=tuple(items),
    )


def build_local_reader_operation_definition(*, spawn: RuntimeSpawner) -> OperationDefinition:
    """Bind the injected runtime spawner to the canonical provisioning operation."""

    def build() -> LocalReaderProvisionExecutor:
        return LocalReaderProvisionExecutor(spawn=spawn)

    return OperationDefinition(
        definition_id=LOCAL_READER_OPERATION_DEFINITION_ID,
        request_type=LocalReaderProvisionRequest,
        result_type=LocalReaderProvisionOutcome,
        executor_factory=OperationExecutorFactory(
            request_type=LocalReaderProvisionRequest,
            executor_type=LocalReaderProvisionExecutor,
            build=build,
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.MCP, OperationFrontendProjection.TUI}
        ),
    )


def build_local_reader_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the provisioning definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{LOCAL_READER_OPERATION_DEFINITION_ID}.request",
            schema_version=1,
            model_type=LocalReaderProvisionRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{LOCAL_READER_OPERATION_DEFINITION_ID}.result",
            schema_version=1,
            model_type=LocalReaderProvisionPublicResultV1,
        ),
        result_projector=_project_result,
    )
