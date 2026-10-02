"""Registered cross-domain pipeline inspection under whole-profile authority."""

from __future__ import annotations

import asyncio
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.config import override_settings
from ...core.external_constants import OutputLanguage
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.verification_report import VerificationReport
from ..calculations.verification_report_gate import require_verification_report_coordinates_current
from ..ledger.actions_manual import summarize_manual_transactions
from ..ledger.read_access import resolve_ledger_read_access
from ..modelo.calculation_actions import get_recorded_calculation_revision
from ..modelo.work_lifecycle import list_work_units
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.public_period import PublicPeriod
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .pipeline_health import build_pipeline_health_report
from .pipeline_projection import PipelineHealthSnapshot
from .pipeline_read_ports import PipelineReadPortsFactory

OVERVIEW_PIPELINE_OPERATION_DEFINITION_ID = "overview.pipeline"


class OverviewPipelineRequest(CredentialFreeOperationRequest):
    """One selected reporting period; ledger counters retain global scope."""

    profile_id: UUID
    period: PublicPeriod
    output_language: OutputLanguage


class OverviewPipelineResult(BaseModel):
    """Encrypted canonical capture, separate from its public projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    period: PublicPeriod
    output_language: OutputLanguage
    report: PipelineHealthSnapshot


class OverviewPipelineProjection(BaseModel):
    """Authorized pipeline report released through the registered result door."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    period: PublicPeriod
    output_language: OutputLanguage
    report: PipelineHealthSnapshot


def project_overview_pipeline_result(
    result: BaseModel, _receipt: OperationTerminalReceipt, /
) -> OverviewPipelineProjection:
    """Project only coherent exact-profile facts from the stored result."""
    if (
        not isinstance(result, OverviewPipelineResult)
        or result.profile_id != result.report.profile_id
        or result.period != result.report.period
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return OverviewPipelineProjection(
        profile_id=result.profile_id,
        period=result.period,
        output_language=result.output_language,
        report=result.report,
    )


class OverviewPipelineExecutor:
    """Compose existing read models without migration or filing capabilities."""

    def __init__(self, factory: PipelineReadPortsFactory) -> None:
        """Retain the narrow reader factory for this registered operation."""
        self._factory = factory

    def _capture(self, payload: OverviewPipelineRequest, operation: PinnedAuthorityOperation) -> OverviewPipelineResult:
        bucket_id = str(payload.profile_id)
        ports = self._factory(bucket_id=bucket_id, operation=operation)
        if (
            ports.bucket_id != bucket_id
            or ports.ledger.operation is not operation
            or ports.calculation.operation is not operation
            or ports.ledger.transaction_repository.bucket_id != bucket_id
            or ports.calculation.work_unit_repository.bucket_id != bucket_id
            or ports.calculation.work_lifecycle_ports.work_unit_repository.bucket_id != bucket_id
            or ports.calculation.calculation_repository.bucket_id != bucket_id
            or ports.verification.bucket_id != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        period = payload.period.to_period()
        with override_settings(cadrumo_output_language=payload.output_language.value):
            ledger = summarize_manual_transactions(bucket_id=bucket_id, period=period, ports=ports.ledger)
            units = tuple(
                unit
                for unit in list_work_units(
                    bucket_id=bucket_id, include_discarded=False, ports=ports.calculation.work_lifecycle_ports
                )
                if unit.filing_year == period.filing_year and unit.period.registry_token == period.registry_token
            )
            revisions: dict[str, CalculationRevision] = {}
            reports: dict[str, tuple[VerificationReport, ...]] = {}
            verification_reports = (
                tuple(
                    require_verification_report_coordinates_current(
                        ports.verification.load(operation=operation), operation=operation
                    ).reports.values()
                )
                if any(unit.current_calculation_revision_id is not None for unit in units)
                else ()
            )
            for unit in units:
                if unit.current_calculation_revision_id is None:
                    continue
                revision = get_recorded_calculation_revision(
                    unit.current_calculation_revision_id, ports=ports.calculation
                )
                coordinates = revision.registry_snapshot_ref
                if (
                    revision.work_unit_id != unit.work_unit_id
                    or coordinates.modelo != unit.modelo
                    or coordinates.modelo_year != unit.filing_year
                    or coordinates.period != unit.period.registry_token
                ):
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
                revisions[revision.calculation_revision_id] = revision
                reports[revision.calculation_revision_id] = tuple(
                    sorted(
                        (
                            report
                            for report in verification_reports
                            if report.calculation_revision_id == revision.calculation_revision_id
                        ),
                        key=lambda report: (report.calculation_revision_id, report.run_at),
                    )
                )
            report = build_pipeline_health_report(
                bucket_id=bucket_id,
                filing_year=period.filing_year,
                period=period,
                ledger_report=ledger,
                work_units=units,
                revisions_by_id=revisions,
                reports_by_revision_id=reports,
            )
        return OverviewPipelineResult(
            profile_id=payload.profile_id,
            period=payload.period,
            output_language=payload.output_language,
            report=PipelineHealthSnapshot.from_report(report),
        )

    async def execute(
        self, request: OperationRequest[OverviewPipelineRequest], context: OperationExecutorContext
    ) -> str:
        """Retain ownership until read and encrypted publication have settled."""
        payload = request.payload
        if (
            request.definition_id != OVERVIEW_PIPELINE_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(OVERVIEW_PIPELINE_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            result = await asyncio.to_thread(self._capture, payload, context.authority_operation)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="overview-pipeline-read")


def build_overview_pipeline_definition(factory: PipelineReadPortsFactory) -> OperationDefinition:
    """Register the read with honest no-effect and interruption semantics."""
    return OperationDefinition(
        definition_id=OVERVIEW_PIPELINE_OPERATION_DEFINITION_ID,
        request_type=OverviewPipelineRequest,
        result_type=OverviewPipelineResult,
        executor_factory=OperationExecutorFactory(
            request_type=OverviewPipelineRequest,
            executor_type=OverviewPipelineExecutor,
            build=lambda: OverviewPipelineExecutor(factory),
        ),
        phase_codes=(OVERVIEW_PIPELINE_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
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
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def resolve_overview_pipeline_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require all periods because the reused ledger counters are global."""
    payload = request.payload
    if request.definition_id != OVERVIEW_PIPELINE_OPERATION_DEFINITION_ID or not isinstance(
        payload, OverviewPipelineRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=frozenset())


def build_overview_pipeline_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Declare independent schemas and explicit authorized result projection."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=OverviewPipelineRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=OverviewPipelineProjection
        ),
        access_resolver=resolve_overview_pipeline_access,
        result_projector=project_overview_pipeline_result,
    )
