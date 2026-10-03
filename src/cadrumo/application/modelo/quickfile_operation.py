"""Run the existing five-stage quickfile chain under exact-profile worker authority."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from pathlib import Path
from typing import override

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.hashing import canonical_json_bytes
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ..ledger.commit_fence import LedgerCommitAttemptTracker, run_with_ledger_commit_fence
from ..operations.access_resolution import (
    COMMITTING_OPERATION_LIFECYCLE_ACTIONS,
    OBSERVATION_DISCLOSING_ACTIONS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access,
    operation_disclosures,
)
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import (
    OperationRequest,
    OperationTerminalReceipt,
    require_succeeded_receipt_references,
    require_terminal_receipt_match,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_errors import M303FilingEvidenceError
from .calculate_input import WorkCalculateInputBundle
from .m303_filing_evidence import m303_filing_evidence_failure
from .m303_ordinary_filing_evidence_authoring import author_ordinary_m303_evidence_for_work
from .quickfile import QuickfileCommand, QuickfileStage, run_modelo_quickfile
from .quickfile_operation_contracts import QuickfileRequest
from .quickfile_operation_ports import QuickfileOperationPorts, QuickfileOperationPortsFactory
from .quickfile_operation_projections import QuickfileProjection

QUICKFILE_OPERATION_DEFINITION_ID = "modelo.quickfile"


class QuickfileExecutionResult(BaseModel):
    """Retain the encrypted chain completion separately from its reviewed public schema."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: QuickfileProjection


class _Writes(LedgerCommitAttemptTracker):
    """Count completed concrete writes while preserving canonical uncertain outcomes."""

    def __init__(self) -> None:
        """Retain concrete confirmed writes independently of failed attempts."""
        super().__init__()
        self._count = 0
        self._count_lock = threading.Lock()

    @property
    def count(self) -> int:
        """Return the number of complete prepared writers that returned."""
        with self._count_lock:
            return self._count

    @override
    def call_writer(self, write: Callable[[], None]) -> None:
        """Count a confirmed writer after its complete commit boundary settles."""
        super().call_writer(write)
        with self._count_lock:
            self._count += 1

    def effect(self, *, incomplete: bool) -> OperationEffect:
        """Retain earlier writes when a later stage refuses or becomes uncertain."""
        if self.has_uncertain_write:
            return OperationEffect.UNKNOWN
        if self.confirmed_write:
            return OperationEffect.PARTIAL if incomplete else OperationEffect.UPDATED
        return OperationEffect.NONE


def _admit_quickfile_request(request: OperationRequest[QuickfileRequest], context: OperationExecutorContext) -> None:
    payload = request.payload
    if request.definition_id != QUICKFILE_OPERATION_DEFINITION_ID:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    require_operation_profile(request, context, payload.profile_id)
    if payload.bucket_id is not None and payload.bucket_id != payload.profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_ports(
    ports: QuickfileOperationPorts, request: QuickfileRequest, context: OperationExecutorContext
) -> None:
    profile_id = str(request.profile_id)
    if (
        ports.profile_id != request.profile_id
        or ports.operation is not context.authority_operation
        or str(ports.profile.record.profile_id) != profile_id
        or ports.calculation.operation is not context.authority_operation
        or ports.calculation.work_unit_repository.bucket_id != profile_id
        or ports.export.work_unit.bucket_id != profile_id
        or ports.verification.work_unit.bucket_id != profile_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _inputs(payload: QuickfileRequest, ports: QuickfileOperationPorts, work_unit_id: str) -> WorkCalculateInputBundle:
    unit = ports.calculation.work_unit_repository.load().get(work_unit_id)
    if unit is None or unit.bucket_id != str(payload.profile_id) or unit.period != payload.period.to_period():
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    supplied = payload.ordinary_m303_filing_evidence
    evidence = None
    if payload.modelo == "303":
        if supplied is None:
            raise M303FilingEvidenceError(
                precondition_failure=m303_filing_evidence_failure(
                    "missing", {"modelo": "303", "evidence_present": False}
                )
            )
        evidence = author_ordinary_m303_evidence_for_work(
            work_unit=unit,
            joint_return_elected=supplied.joint_return_elected,
            exonerado_390_attachment_id=supplied.m303_exonerado_390_attachment_id,
            exonerado_390_sha256=supplied.m303_exonerado_390_sha256,
            operation=ports.operation,
            open_attachment_store=lambda: ports.attachments,
            profile=ports.profile,
        )
    return payload.inputs.to_calculation_fields().build_bundle(
        work_unit_id=work_unit_id,
        ports=ports.calculation,
        profile=ports.profile,
        detail_rows=tuple(row.to_row() for row in payload.detail_rows),
        filing_instance_evidence=evidence,
    )


class QuickfileExecutor:
    """Own actual mutation fences and cancellation settlement without copying any stage."""

    def __init__(self, factory: QuickfileOperationPortsFactory) -> None:
        """Retain the exact-profile capabilities factory without resolving storage."""
        self._factory = factory

    async def execute(self, request: OperationRequest[QuickfileRequest], context: OperationExecutorContext) -> str:
        """Join the canonical synchronous chain and settle all admitted local writes."""
        payload = request.payload
        _admit_quickfile_request(request, context)
        writes = _Writes()
        loop = asyncio.get_running_loop()
        admission_failure: BaseException | None = None
        await context.events.phase(QUICKFILE_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        async def admit() -> None:
            nonlocal admission_failure
            if admission_failure is not None:
                raise admission_failure
            try:
                # Refresh authority briefly; no readiness, model, provider or
                # domain preparation runs while this boundary is held.
                async with context.cancellation.irreversible_section():
                    _admit_quickfile_request(request, context)
            except BaseException as error:
                admission_failure = error
                writes.abort()
                raise

        def before_stage(_stage: QuickfileStage) -> None:
            asyncio.run_coroutine_threadsafe(admit(), loop).result()

        def work() -> QuickfileProjection:
            before_stage(QuickfileStage.READINESS)
            with validating_governed_facts(context.authority_operation):
                ports = self._factory(
                    profile_id=payload.profile_id,
                    operation=context.authority_operation,
                    mutation_writer=writes.call_writer,
                )
                _require_ports(ports, payload, context)
                result = run_modelo_quickfile(
                    QuickfileCommand(
                        bucket_id=str(payload.profile_id),
                        modelo=payload.modelo,
                        filing_year=payload.period.to_period().filing_year,
                        period=payload.period.to_period(),
                        registry_revision_id=payload.revision_id,
                        output_path=Path(payload.output_path),
                        actor=payload.actor,
                        refund_election=payload.refund_election,
                        payment_election=payload.payment_election,
                        prior_domiciliation_election=payload.prior_domiciliation_election,
                    ),
                    certificate_secret_backend_factory=ports.certificate_secret_backend_factory,
                    operator_probe_ports=ports.operator_probe_ports,
                    operator_scope_ports=ports.operator_scope_ports,
                    operation=ports.operation,
                    verification_repositories=ports.verification,
                    calculation_action_ports=ports.calculation,
                    modelo_export_ports=ports.export,
                    read_ports=ports.read,
                    workflow_profile=ports.workflow_profile,
                    build_calculation_inputs=lambda work_unit_id: _inputs(payload, ports, work_unit_id),
                    profile=ports.profile,
                    before_stage=before_stage,
                    mutation_writer=writes.call_writer,
                )
                if admission_failure is not None:
                    raise admission_failure
                _admit_quickfile_request(request, context)
                if result.modelo != payload.modelo or result.period != payload.period.to_period():
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                return QuickfileProjection.from_result(
                    result,
                    profile_id=payload.profile_id,
                    write_count=writes.count,
                    effect=writes.effect(incomplete=not result.completed),
                )

        async def settle() -> str:
            try:
                result = await run_with_ledger_commit_fence(
                    work, tracker=writes, context=context, task_name=QUICKFILE_OPERATION_DEFINITION_ID
                )
                retained = QuickfileExecutionResult(projection=result)
                if len(canonical_json_bytes(retained.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                reference = await context.operands.put(retained, written_at=now())
                await context.events.effect(result.effect)
                return reference
            except BaseException:
                await context.events.effect(writes.effect(incomplete=True))
                raise

        return await await_cancellation_complete(settle(), task_name=QUICKFILE_OPERATION_DEFINITION_ID)


def project_quickfile_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> QuickfileProjection:
    """A stopped chain is result data; its confirmed and uncertain effects remain authoritative."""
    if not isinstance(result, QuickfileExecutionResult) or type(result) is not QuickfileExecutionResult:
        raise ValueError("invalid quickfile result")
    projection = result.projection
    require_terminal_receipt_match(
        receipt,
        definition_id=QUICKFILE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(projection.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=projection.effect,
        message="quickfile result contradicts its terminal receipt",
    )
    require_succeeded_receipt_references(receipt, message="quickfile result contradicts its terminal receipt")
    _require_quickfile_result_size(result)
    return projection


def _require_quickfile_result_size(result: QuickfileExecutionResult) -> None:
    if len(canonical_json_bytes(result.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
        raise ValueError("quickfile result contradicts its terminal receipt")


def build_quickfile_definition(factory: QuickfileOperationPortsFactory) -> OperationDefinition:
    """Register the existing local human chain with encrypted inputs and full effect settlement."""
    return build_single_phase_definition(
        definition_id=QUICKFILE_OPERATION_DEFINITION_ID,
        request_type=QuickfileRequest,
        result_type=QuickfileExecutionResult,
        executor_type=QuickfileExecutor,
        build=lambda: QuickfileExecutor(factory),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.COOPERATIVE,
            deadline=OperationDeadline.COOPERATIVE,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.REQUEST_BOUND,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset(
                {OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.PARTIAL, OperationEffect.UNKNOWN}
            ),
            close_policy=OperationClosePolicy.REQUEST_CANCEL,
        ),
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def build_quickfile_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the human destination, both value categories and exact natural filing period."""
    if (
        definition.definition_id != QUICKFILE_OPERATION_DEFINITION_ID
        or definition.request_type is not QuickfileRequest
        or definition.result_type is not QuickfileExecutionResult
    ):
        raise ValueError("invalid quickfile definition")

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = _quickfile_access_payload(request, context)
        periods = frozenset({payload.period.to_period()})
        _require_admitted_quickfile_request(request, context, periods)
        disclosures = operation_disclosures(
            context,
            observed_by=OBSERVATION_DISCLOSING_ACTIONS,
            result_categories=frozenset({DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES}),
            result_schema_id=None,
        )
        return _resolved_quickfile_access(request, context, periods, disclosures)

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=QuickfileProjection,
        result_projector=project_quickfile_result,
        access_resolver=resolve,
    )


def _quickfile_access_payload(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> QuickfileRequest:
    payload = request.payload
    if (
        request.definition_id != QUICKFILE_OPERATION_DEFINITION_ID
        or not isinstance(payload, QuickfileRequest)
        or context.frontend is not OperationFrontendProjection.CLI
        or context.authority_operation is None
        or context.contract.definition_id != QUICKFILE_OPERATION_DEFINITION_ID
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if (
        payload.profile_id != context.profile_id
        or request.subject_ref != profile_operation_subject(str(payload.profile_id))
        or (payload.bucket_id is not None and payload.bucket_id != payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return payload


def _require_admitted_quickfile_request(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    periods: frozenset[Period],
) -> None:
    admitted = context.admitted_request
    if admitted is not None and (
        admitted.profile_id != context.profile_id
        or admitted.definition_id != request.definition_id
        or admitted.action is not AccessAction.SUBMIT
        or admitted.periods != periods
        or admitted.period_independent
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def _resolved_quickfile_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    periods: frozenset[Period],
    disclosures: frozenset[DisclosurePermission],
) -> ResolvedOperationAccess:
    return bind_operation_access(
        context,
        profile_id=context.profile_id,
        definition_id=request.definition_id,
        actions=COMMITTING_OPERATION_LIFECYCLE_ACTIONS,
        disclosures=disclosures,
        periods=periods,
        period_independent=False,
        requires_all_periods=False,
        requires_human=True,
        provider=Availability.NOT_REQUIRED,
    )
