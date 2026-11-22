"""Registered exact-profile preview and reviewed write of one ledger batch edit."""

from __future__ import annotations

import asyncio
from dataclasses import replace

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.config import override_settings
from ...core.errors.hierarchy import InternalInvariantError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
)
from ..operations.execution_actor import OperationExecutionCallerReader, execution_actor_label
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts, LedgerActionPortsFactory, require_exact_ledger_action_ports
from .batch_update import (
    BatchUpdatePlan,
    LedgerBatchPlanChangedError,
    plan_batch_update,
    require_reviewed_plan,
    write_batch_update,
)
from .batch_update_contracts import (
    LEDGER_BATCH_UPDATE_OPERATION_DEFINITION_ID,
    LEDGER_BATCH_UPDATE_PLAN_CHANGED_REFUSAL_CODE,
    LEDGER_BATCH_UPDATE_PREVIEW_OPERATION_DEFINITION_ID,
    LedgerBatchUpdateExecutionResult,
    LedgerBatchUpdatePreviewRequest,
    LedgerBatchUpdateRequest,
    LedgerBatchUpdateResult,
    batch_counts,
)
from .commit_fence import (
    LedgerCommitAttemptTracker,
    RevisionGuardedTrackedLedgerTransactionRepository,
    run_with_ledger_commit_fence,
)
from .protocols import RevisionGuardedTransactionCatalogueCoCommitWriterProtocol
from .read_access import resolve_ledger_request_commit_access, resolve_ledger_request_read_access

_SOURCE_COMMAND = "ledger batch edit"


def _exact_ports(
    factory: LedgerActionPortsFactory, *, bucket_id: str, operation: PinnedAuthorityOperation
) -> tuple[LedgerActionPorts, RevisionGuardedTransactionCatalogueCoCommitWriterProtocol]:
    ports = factory(bucket_id=bucket_id, operation=operation)
    require_exact_ledger_action_ports(ports, bucket_id=bucket_id, operation=operation)
    if not isinstance(ports.transaction_repository, RevisionGuardedTransactionCatalogueCoCommitWriterProtocol):
        raise InternalInvariantError("a batch edit requires revision-guarded catalogue custody")
    return ports, ports.transaction_repository


def _result(
    payload: LedgerBatchUpdatePreviewRequest | LedgerBatchUpdateRequest,
    plan: BatchUpdatePlan,
    *,
    outcome: str,
    event_ids: tuple[str, ...] = (),
) -> LedgerBatchUpdateExecutionResult:
    return LedgerBatchUpdateExecutionResult(
        result=LedgerBatchUpdateResult.model_validate(
            {
                "profile_id": payload.profile_id,
                "outcome": outcome,
                "plan_digest": plan.digest,
                "rows": plan.rows,
                "counts": batch_counts(plan.rows),
                "bucket_event_ids": event_ids,
            }
        )
    )


class LedgerBatchUpdatePreviewExecutor:
    """Answer what a batch edit would do to each row, writing nothing."""

    def __init__(
        self,
        ports_factory: LedgerActionPortsFactory,
        *,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Retain the trusted exact-profile ledger composition."""
        self._ports_factory = ports_factory
        self._execution_caller_reader = execution_caller_reader

    async def execute(
        self,
        request: OperationRequest[LedgerBatchUpdatePreviewRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Plan every row against one load of the catalogue."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_BATCH_UPDATE_PREVIEW_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_BATCH_UPDATE_PREVIEW_OPERATION_DEFINITION_ID)
        actor = execution_actor_label(self._execution_caller_reader, context, supplied=bucket_id)
        operation = context.authority_operation

        def preview() -> BatchUpdatePlan:
            ports, _ = _exact_ports(self._ports_factory, bucket_id=bucket_id, operation=operation)
            # Row refusals cross the worker boundary already said, in this request's language.
            with override_settings(cadrumo_output_language=payload.output_language.value):
                return plan_batch_update(
                    bucket_id=bucket_id,
                    rows=payload.rows,
                    actor=actor,
                    source_command=_SOURCE_COMMAND,
                    ports=ports,
                    now=now(),
                )

        plan = await asyncio.to_thread(preview)
        await context.events.effect(OperationEffect.NONE)
        return await context.operands.put(_result(payload, plan, outcome="previewed"), written_at=now())


class LedgerBatchUpdateExecutor:
    """Write the reviewed plan in one guarded save, or refuse a plan that changed."""

    def __init__(
        self,
        ports_factory: LedgerActionPortsFactory,
        *,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Retain the trusted exact-profile ledger composition."""
        self._ports_factory = ports_factory
        self._execution_caller_reader = execution_caller_reader

    async def execute(
        self,
        request: OperationRequest[LedgerBatchUpdateRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Re-plan against current storage and write only the reviewed plan."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_BATCH_UPDATE_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_BATCH_UPDATE_OPERATION_DEFINITION_ID)
        actor = execution_actor_label(self._execution_caller_reader, context, supplied=payload.actor or bucket_id)
        operation = context.authority_operation
        ports, repository = await asyncio.to_thread(
            _exact_ports, self._ports_factory, bucket_id=bucket_id, operation=operation
        )
        tracker = LedgerCommitAttemptTracker()
        tracked = replace(
            ports, transaction_repository=RevisionGuardedTrackedLedgerTransactionRepository(repository, tracker)
        )

        def apply() -> tuple[BatchUpdatePlan, tuple[str, ...]]:
            with override_settings(cadrumo_output_language=payload.output_language.value):
                plan = plan_batch_update(
                    bucket_id=bucket_id,
                    rows=payload.rows,
                    actor=actor,
                    source_command=_SOURCE_COMMAND,
                    ports=tracked,
                    now=now(),
                )
            require_reviewed_plan(plan, payload.reviewed_plan_digest)
            return plan, write_batch_update(bucket_id=bucket_id, plan=plan, ports=tracked)

        try:
            plan, event_ids = await run_with_ledger_commit_fence(
                apply, tracker=tracker, context=context, task_name=LEDGER_BATCH_UPDATE_OPERATION_DEFINITION_ID
            )
        except LedgerBatchPlanChangedError as changed:
            if tracker.attempt_count or tracker.has_possible_write:
                raise InternalInvariantError("a changed batch plan reached the writer") from changed
            await context.events.effect(OperationEffect.NONE)
            detail = _result(payload, changed.plan, outcome="plan_changed")
            detail_ref = await context.operands.put(detail, written_at=now())
            return OperationRefusalEvidence(
                refusal_code=LEDGER_BATCH_UPDATE_PLAN_CHANGED_REFUSAL_CODE, detail_ref=detail_ref
            )
        if tracker.has_uncertain_write or bool(event_ids) != tracker.confirmed_write:
            raise InternalInvariantError("batch edit writer receipt disagrees with its plan")
        await context.events.effect(OperationEffect.UPDATED if event_ids else OperationEffect.NONE)
        return await context.operands.put(
            _result(payload, plan, outcome="applied", event_ids=event_ids), written_at=now()
        )


def _require_identity(
    result: BaseModel, receipt: OperationTerminalReceipt, definition_id: str
) -> LedgerBatchUpdateResult:
    if type(result) is not LedgerBatchUpdateExecutionResult or receipt.identity.definition_id != definition_id:
        raise ValueError("invalid batch edit result or terminal definition")
    projected = result.result
    if receipt.identity.subject_ref != profile_operation_subject(str(projected.profile_id)):
        raise ValueError("batch edit result belongs to another profile")
    return projected


def _require_success(receipt: OperationTerminalReceipt, effect: OperationEffect) -> None:
    if (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.diagnostic_ref is not None
        or receipt.effect is not effect
    ):
        raise ValueError("batch edit success has an incompatible terminal receipt")


def project_batch_update_preview_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release a preview only as a no-effect success."""
    projected = _require_identity(result, receipt, LEDGER_BATCH_UPDATE_PREVIEW_OPERATION_DEFINITION_ID)
    if projected.outcome != "previewed":
        raise ValueError("a batch preview releases only its plan")
    _require_success(receipt, OperationEffect.NONE)
    return projected


def project_batch_update_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release a written plan, or the changed plan an apply refused, against its receipt."""
    projected = _require_identity(result, receipt, LEDGER_BATCH_UPDATE_OPERATION_DEFINITION_ID)
    if projected.outcome == "applied":
        _require_success(receipt, OperationEffect.UPDATED if projected.bucket_event_ids else OperationEffect.NONE)
        return projected
    if (
        projected.outcome != "plan_changed"
        or receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.refusal_ref != LEDGER_BATCH_UPDATE_PLAN_CHANGED_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
        or receipt.diagnostic_ref is not None
        or receipt.effect is not OperationEffect.NONE
    ):
        raise ValueError("batch edit refusal has an incompatible terminal receipt")
    return projected


def build_ledger_batch_update_preview_definition(
    ports_factory: LedgerActionPortsFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Declare the no-effect, exact-profile plan of a batch edit."""
    return build_single_phase_definition(
        definition_id=LEDGER_BATCH_UPDATE_PREVIEW_OPERATION_DEFINITION_ID,
        request_type=LedgerBatchUpdatePreviewRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerBatchUpdateExecutionResult,
        executor_type=LedgerBatchUpdatePreviewExecutor,
        build=lambda: LedgerBatchUpdatePreviewExecutor(ports_factory, execution_caller_reader=execution_caller_reader),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    )


def build_ledger_batch_update_definition(
    ports_factory: LedgerActionPortsFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Declare the reviewed, exact-profile write of a batch edit."""
    return build_single_phase_definition(
        definition_id=LEDGER_BATCH_UPDATE_OPERATION_DEFINITION_ID,
        request_type=LedgerBatchUpdateRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerBatchUpdateExecutionResult,
        executor_type=LedgerBatchUpdateExecutor,
        build=lambda: LedgerBatchUpdateExecutor(ports_factory, execution_caller_reader=execution_caller_reader),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        refusal_detail_codes=frozenset({LEDGER_BATCH_UPDATE_PLAN_CHANGED_REFUSAL_CODE}),
    )


def resolve_ledger_batch_update_preview_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact whole-profile disclosure for a preview."""
    return resolve_ledger_request_read_access(
        request,
        context,
        definition_id=LEDGER_BATCH_UPDATE_PREVIEW_OPERATION_DEFINITION_ID,
        request_type=LedgerBatchUpdatePreviewRequest,
    )


def resolve_ledger_batch_update_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact whole-profile disclosure and COMMIT for the write."""
    return resolve_ledger_request_commit_access(
        request,
        context,
        definition_id=LEDGER_BATCH_UPDATE_OPERATION_DEFINITION_ID,
        request_type=LedgerBatchUpdateRequest,
    )


def build_ledger_batch_update_preview_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the preview's exact request, plan result and read access."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerBatchUpdateResult,
        result_projector=project_batch_update_preview_result,
        access_resolver=resolve_ledger_batch_update_preview_access,
    )


def build_ledger_batch_update_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the write's exact request, per-row result and commit access."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerBatchUpdateResult,
        result_projector=project_batch_update_result,
        access_resolver=resolve_ledger_batch_update_access,
    )


__all__ = [
    "LedgerBatchUpdateExecutor",
    "LedgerBatchUpdatePreviewExecutor",
    "build_ledger_batch_update_definition",
    "build_ledger_batch_update_preview_definition",
    "build_ledger_batch_update_preview_registration",
    "build_ledger_batch_update_registration",
    "project_batch_update_preview_result",
    "project_batch_update_result",
    "resolve_ledger_batch_update_access",
    "resolve_ledger_batch_update_preview_access",
]
