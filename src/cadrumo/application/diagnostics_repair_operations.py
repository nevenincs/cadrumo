"""Registered operations for the repair work that needs one profile's stores.

Checking and quarantining secure-object rows, resetting saved command
progress and probing connectivity all run inside the worker of the profile
they act for. Each executor calls the function the command line calls for the
same work, and each result is the document that command prints, with the
real identifiers the command line shows when they are revealed, so a frontend
shows the result and renders nothing of its own.

A request that only measures binds no commit door. A request that moves rows
or deletes saved progress binds one, and enters the runtime's irreversible
section before it writes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Annotated, Protocol
from uuid import UUID

from pydantic import BaseModel, StringConstraints

from ..core.async_cleanup import await_cancellation_complete
from ..core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..core.operations import OperationEffect
from ..core.time.clock import now
from .connectivity_probe import ConnectivityProbePort, probe_connectivity
from .diagnostics_ports import DiagnosticsPorts
from .diagnostics_repair import (
    WORKFLOW_PROGRESS_RESET_ACTOR,
    check_secure_object_integrity,
    run_secure_object_quarantine,
    run_workflow_progress_reset,
)
from .diagnostics_repair_documents import (
    RepairConnectivityDocument,
    RepairIntegrityObjectsDocument,
    RepairQuarantineDocument,
    RepairResetProgressDocument,
    connectivity_document,
    integrity_objects_document,
    printed,
    quarantine_document,
    reset_progress_document,
)
from .operations.access_resolution import (
    LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_replayed_period_independent_access,
    with_commit_action,
)
from .operations.capabilities import (
    RECORDED_NON_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES,
    RECORDED_NON_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_READ_CAPABILITIES,
)
from .operations.execution_actor import OperationExecutionCallerReader, execution_actor_label
from .operations.models import CredentialFreeOperationRequest, OperationRequest
from .operations.operation_definition import OperationDefinition, build_single_phase_definition
from .operations.owner import OperationExecutorContext
from .operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from .operations.registry import OperationPublicDefinitionRegistrationV1
from .operations.subject_reference import OperationSubjectReferenceV1
from .user_profile.access_contracts import AccessDenialCode
from .user_profile.access_errors import ProfileAccessRefusedError

SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID = "diagnostics.secure-objects.check"
SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID = "diagnostics.secure-objects.quarantine"
WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID = "diagnostics.workflow-progress.reset"
CONNECTIVITY_PROBE_OPERATION_DEFINITION_ID = "diagnostics.connectivity.probe"

type _NamespaceName = Annotated[str, StringConstraints(min_length=1, max_length=256)]


class DiagnosticsPortsFactory(Protocol):
    """Bind the secure-object diagnostics of exactly one profile."""

    def __call__(self, *, profile_id: UUID) -> DiagnosticsPorts:
        """Return the diagnostics ports of ``profile_id``'s own store."""
        ...


class _ProfileRepairRequest(CredentialFreeOperationRequest):
    """The profile whose stores one repair request acts on."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class SecureObjectsCheckRequest(_ProfileRepairRequest):
    """Count one profile's readable and unreadable secure-object rows.

    ``namespace`` narrows the count to that namespace.
    """

    namespace: _NamespaceName | None = None


class SecureObjectsQuarantineRequest(_ProfileRepairRequest):
    """Move one profile's unreadable secure-object rows into quarantine.

    With ``dry_run`` nothing moves and the result counts what would.
    """

    dry_run: bool


class WorkflowProgressResetRequest(_ProfileRepairRequest):
    """Discard one profile's saved interrupted-command progress.

    With ``dry_run`` nothing is discarded and the result describes the stored record.
    """

    dry_run: bool


class ConnectivityProbeRequest(_ProfileRepairRequest):
    """Browse once to the tax agency's public landing page and classify its answer."""


class SecureObjectsCheckExecutor:
    """Run the integrity sweep the command line runs, changing nothing."""

    def __init__(self, factory: DiagnosticsPortsFactory) -> None:
        """Keep the composition's factory; no store is opened until a request runs."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[SecureObjectsCheckRequest], context: OperationExecutorContext
    ) -> str:
        """Count the profile's rows in its own worker and retain the verdict."""
        payload = _admitted_payload(request, context, SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID)
        await context.events.phase(SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        def check() -> RepairIntegrityObjectsDocument:
            verdict = check_secure_object_integrity(
                ports=self._factory(profile_id=payload.profile_id), namespace=payload.namespace
            )
            return printed(integrity_objects_document(verdict))

        return await context.operands.put(await asyncio.to_thread(check), written_at=now())


class SecureObjectsQuarantineExecutor:
    """Run the quarantine the command line runs, under the runtime's commit fence."""

    def __init__(self, factory: DiagnosticsPortsFactory) -> None:
        """Keep the composition's factory; no store is opened until a request runs."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[SecureObjectsQuarantineRequest], context: OperationExecutorContext
    ) -> str:
        """Preview without a commit door, or move the unreadable rows inside one."""
        payload = _admitted_payload(request, context, SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID)
        await context.events.phase(SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID)

        def quarantine() -> tuple[RepairQuarantineDocument, bool]:
            report = run_secure_object_quarantine(
                ports=self._factory(profile_id=payload.profile_id), dry_run=payload.dry_run
            )
            return printed(quarantine_document(report, dry_run=payload.dry_run)), report.unreadable_total > 0

        if payload.dry_run:
            await context.events.effect(OperationEffect.NONE)
            previewed, _would_move = await asyncio.to_thread(quarantine)
            return await context.operands.put(previewed, written_at=now())

        async def commit() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                result, moved = await asyncio.to_thread(quarantine)
                # A run that found nothing unreadable moved no row.
                await context.events.effect(OperationEffect.UPDATED if moved else OperationEffect.NONE)
                return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(commit(), task_name="secure-objects-quarantine-publication")


class WorkflowProgressResetExecutor:
    """Run the progress reset the command line runs, under the runtime's commit fence."""

    def __init__(self, *, execution_caller_reader: OperationExecutionCallerReader | None = None) -> None:
        """Keep the session host's caller reader, when a session host composed this operation."""
        self._execution_caller_reader = execution_caller_reader

    async def execute(
        self, request: OperationRequest[WorkflowProgressResetRequest], context: OperationExecutorContext
    ) -> str:
        """Fingerprint without a commit door, or record and discard the progress inside one."""
        payload = _admitted_payload(request, context, WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID)
        await context.events.phase(WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID)

        def reset(actor: str) -> RepairResetProgressDocument:
            fingerprint = run_workflow_progress_reset(dry_run=payload.dry_run, actor=actor)
            return printed(reset_progress_document(fingerprint, dry_run=payload.dry_run))

        if payload.dry_run:
            await context.events.effect(OperationEffect.NONE)
            described = await asyncio.to_thread(reset, WORKFLOW_PROGRESS_RESET_ACTOR)
            return await context.operands.put(described, written_at=now())

        actor = execution_actor_label(self._execution_caller_reader, context, supplied=WORKFLOW_PROGRESS_RESET_ACTOR)

        async def commit() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                discarded = await asyncio.to_thread(reset, actor)
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(discarded, written_at=now())

        return await await_cancellation_complete(commit(), task_name="workflow-progress-reset-publication")


class ConnectivityProbeExecutor:
    """Run the connectivity probe the command line runs, through the composed browser port."""

    def __init__(self, probe: ConnectivityProbePort) -> None:
        """Keep the composition's probe; no browser starts until a request runs."""
        self._probe = probe

    async def execute(
        self, request: OperationRequest[ConnectivityProbeRequest], context: OperationExecutorContext
    ) -> str:
        """Observe the site once; the probe changes no record."""
        _admitted_payload(request, context, CONNECTIVITY_PROBE_OPERATION_DEFINITION_ID)
        await context.events.phase(CONNECTIVITY_PROBE_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        def probe() -> RepairConnectivityDocument:
            return printed(connectivity_document(probe_connectivity(self._probe)))

        return await context.operands.put(await asyncio.to_thread(probe), written_at=now())


def _admitted_payload[PayloadT: _ProfileRepairRequest](
    request: OperationRequest[PayloadT], context: OperationExecutorContext, definition_id: str
) -> PayloadT:
    """Return the payload once the request, the executor identity and the worker agree on the profile."""
    if request.definition_id != definition_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    require_operation_profile(request, context, request.payload.profile_id)
    return request.payload


def _resolve_profile_repair_access[PayloadT: _ProfileRepairRequest](
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    payload_type: type[PayloadT],
    commits: Callable[[PayloadT], bool],
) -> ResolvedOperationAccess:
    """Bind period-independent access to the session's own profile, with COMMIT where ``commits`` says so.

    The decision reads the request and the session's profile and nothing
    else, so every frontend that submits the same request is answered alike.
    """
    payload = require_access_request_profile_payload(
        request, definition_id=definition_id, payload_type=payload_type, access_profile_id=context.profile_id
    )
    if context.contract.definition_id != definition_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = bind_replayed_period_independent_access(
        context, LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS, definition_id=definition_id
    )
    return with_commit_action(resolved) if commits(payload) else resolved


def resolve_secure_objects_check_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind a read of the profile's own row counts; the sweep opens no commit door."""
    return _resolve_profile_repair_access(
        request,
        context,
        definition_id=SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID,
        payload_type=SecureObjectsCheckRequest,
        commits=lambda _payload: False,
    )


def resolve_secure_objects_quarantine_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind the quarantine with COMMIT, and its dry run without."""
    return _resolve_profile_repair_access(
        request,
        context,
        definition_id=SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID,
        payload_type=SecureObjectsQuarantineRequest,
        commits=lambda payload: not payload.dry_run,
    )


def resolve_workflow_progress_reset_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind the progress reset with COMMIT, and its dry run without."""
    return _resolve_profile_repair_access(
        request,
        context,
        definition_id=WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID,
        payload_type=WorkflowProgressResetRequest,
        commits=lambda payload: not payload.dry_run,
    )


def resolve_connectivity_probe_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind one observation of the public site; the probe opens no commit door."""
    return _resolve_profile_repair_access(
        request,
        context,
        definition_id=CONNECTIVITY_PROBE_OPERATION_DEFINITION_ID,
        payload_type=ConnectivityProbeRequest,
        commits=lambda _payload: False,
    )


def build_secure_objects_check_definition(factory: DiagnosticsPortsFactory) -> OperationDefinition:
    """Enroll the read-only secure-object integrity sweep of one profile."""
    return build_single_phase_definition(
        definition_id=SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID,
        request_type=SecureObjectsCheckRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=RepairIntegrityObjectsDocument,
        executor_type=SecureObjectsCheckExecutor,
        build=lambda: SecureObjectsCheckExecutor(factory),
        capabilities=RECORDED_NON_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_READ_CAPABILITIES,
    )


def build_secure_objects_quarantine_definition(factory: DiagnosticsPortsFactory) -> OperationDefinition:
    """Enroll the quarantine of one profile's unreadable secure-object rows."""
    return build_single_phase_definition(
        definition_id=SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID,
        request_type=SecureObjectsQuarantineRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=RepairQuarantineDocument,
        executor_type=SecureObjectsQuarantineExecutor,
        build=lambda: SecureObjectsQuarantineExecutor(factory),
        capabilities=RECORDED_NON_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES,
    )


def build_workflow_progress_reset_definition(
    *, execution_caller_reader: OperationExecutionCallerReader | None = None
) -> OperationDefinition:
    """Enroll the reset of one profile's saved interrupted-command progress."""
    return build_single_phase_definition(
        definition_id=WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID,
        request_type=WorkflowProgressResetRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=RepairResetProgressDocument,
        executor_type=WorkflowProgressResetExecutor,
        build=lambda: WorkflowProgressResetExecutor(execution_caller_reader=execution_caller_reader),
        capabilities=RECORDED_NON_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES,
    )


def build_connectivity_probe_definition(probe: ConnectivityProbePort) -> OperationDefinition:
    """Enroll the connectivity probe, which reaches the network and changes no record."""
    return build_single_phase_definition(
        definition_id=CONNECTIVITY_PROBE_OPERATION_DEFINITION_ID,
        request_type=ConnectivityProbeRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=RepairConnectivityDocument,
        executor_type=ConnectivityProbeExecutor,
        build=lambda: ConnectivityProbeExecutor(probe),
        capabilities=RECORDED_NON_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_READ_CAPABILITIES,
    )


def build_secure_objects_check_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the sweep's request and result schemas and its access resolver."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=RepairIntegrityObjectsDocument,
        access_resolver=resolve_secure_objects_check_access,
    )


def build_secure_objects_quarantine_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the quarantine's request and result schemas and its access resolver."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=RepairQuarantineDocument,
        access_resolver=resolve_secure_objects_quarantine_access,
    )


def build_workflow_progress_reset_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the reset's request and result schemas and its access resolver."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=RepairResetProgressDocument,
        access_resolver=resolve_workflow_progress_reset_access,
    )


def build_connectivity_probe_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the probe's request and result schemas and its access resolver."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=RepairConnectivityDocument,
        access_resolver=resolve_connectivity_probe_access,
    )
