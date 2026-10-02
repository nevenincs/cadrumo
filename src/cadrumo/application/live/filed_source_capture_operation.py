"""Guarded source-dependency filed capture for an exact profile worker."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from ...core.bucket_pointer import require_active_bucket_id
from ...core.filing_year import FilingYear
from ...core.identity.profile import canonical_profile_bucket_id
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.period import Period
from ...core.time.clock import now
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext, retain_failed_operation_resources
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filed_data_capture import capture_source_filed_data
from .filed_history_operation import (
    FiledHistoryBrowserResourcesFactory,
    FiledHistoryCompositionFactory,
    FiledHistoryProviderPreflight,
)
from .filed_single_capture_operation import (
    FiledCaptureNoticeV1,
    FiledReconciliationV1,
    public_filed_capture_notice,
    public_filed_reconciliation,
)
from .remote_state_models import SourceFiledDataCaptureReport
from .session import LiveSessionWriteReceipt

FILED_SOURCE_CAPTURE_DEFINITION_ID = "live.filed-capture.source"
_PHASES = ("filed-source.preflight", "filed-source.acquire", "filed-source.result")
_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class FiledSourceCaptureRequest(BaseModel):
    """One target filing whose declared registry dependencies must be captured."""

    model_config = _PUBLIC_CONFIG
    profile_id: UUID
    output_root: Path
    modelo: str = Field(min_length=1, max_length=8)
    year: FilingYear
    period: str = Field(min_length=1, max_length=8)


class FiledSourceCapturePublicResultV1(BaseModel):
    """Safe complete accounting for one source-dependency capture."""

    model_config = _PUBLIC_CONFIG
    output_root: str
    target_modelo: str
    target_year: int
    target_period: str
    captured_count: NonNegativeInt
    reached_count: NonNegativeInt
    observation_paths: tuple[str, ...]
    artefact_refs: tuple[str, ...]
    justificante_metadata_count: NonNegativeInt
    justificante_csvs: tuple[str, ...]
    filing_evidence_stamped_count: NonNegativeInt
    filing_record_ids: tuple[str, ...]
    filing_evidence_conflict_count: NonNegativeInt
    filing_evidence_conflict_record_ids: tuple[str, ...]
    casilla_count: NonNegativeInt
    calculation_observation_count: NonNegativeInt
    calculation_observation_keys: tuple[str, ...]
    evidence_notices: tuple[FiledCaptureNoticeV1, ...]
    reconciliations: tuple[FiledReconciliationV1, ...]


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
    """Return the full evidence tally without private capture objects."""
    del receipt
    report = SourceFiledDataCaptureReport.model_validate(result, strict=True)
    return FiledSourceCapturePublicResultV1(
        output_root=report.output_root,
        target_modelo=report.target_modelo,
        target_year=report.target_year,
        target_period=report.target_period.registry_token,
        captured_count=report.captured_count,
        reached_count=report.reached_count,
        observation_paths=report.observation_paths,
        artefact_refs=report.artefact_refs,
        justificante_metadata_count=report.justificante_metadata_count,
        justificante_csvs=report.justificante_csvs,
        filing_evidence_stamped_count=report.filing_evidence_stamped_count,
        filing_record_ids=report.filing_record_ids,
        filing_evidence_conflict_count=report.filing_evidence_conflict_count,
        filing_evidence_conflict_record_ids=report.filing_evidence_conflict_record_ids,
        casilla_count=report.casilla_count,
        calculation_observation_count=report.calculation_observation_count,
        calculation_observation_keys=report.calculation_observation_keys,
        evidence_notices=tuple(public_filed_capture_notice(notice) for notice in report.evidence_notices),
        reconciliations=tuple(public_filed_reconciliation(row) for row in report.reconciliation_results),
    )


class FiledSourceCaptureExecutor:
    """Acquire source bytes outside fences and guard every local write."""

    def __init__(
        self,
        composition_factory: FiledHistoryCompositionFactory,
        browser_resources_factory: FiledHistoryBrowserResourcesFactory,
        provider_preflight: FiledHistoryProviderPreflight,
    ) -> None:
        """Bind immutable worker-owned provider, ports, and browser cleanup."""
        self._composition_factory = composition_factory
        self._browser_resources_factory = browser_resources_factory
        self._provider_preflight = provider_preflight

    async def execute(
        self, request: OperationRequest[FiledSourceCaptureRequest], context: OperationExecutorContext
    ) -> str:
        """Capture registry dependencies and publish encrypted accounting."""
        payload = request.payload
        profile_id = canonical_profile_bucket_id(payload.profile_id)
        if require_active_bucket_id() != profile_id or request.subject_ref != profile_operation_subject(profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(_PHASES[0])
        self._provider_preflight(payload.profile_id, context.authority_operation)
        period = Period.from_year_and_code(payload.year, payload.period)
        composition = self._composition_factory(payload.output_root)
        resources = self._browser_resources_factory()
        context.cleanup.own(resources, family=OperationOwnedResource.PROCESS)
        await context.events.phase(_PHASES[1])
        await context.events.effect(OperationEffect.UNKNOWN)
        session_receipt = LiveSessionWriteReceipt(context.events.effect)
        with (
            retain_failed_operation_resources(context.cleanup, family=OperationOwnedResource.PROCESS),
            resources.activate(),
        ):
            report = await capture_source_filed_data(
                filed_data_port=composition.filed_data_port,
                modelo=payload.modelo,
                year=payload.year,
                period=period,
                output_root=payload.output_root,
                ports=composition.ports,
                effect_guard=context.cancellation.irreversible_section,
                on_session_write=session_receipt,
                operation=context.authority_operation,
            )
        effect = (
            OperationEffect.UPDATED
            if report.captured_count or report.calculation_observation_count or report.filing_evidence_stamped_count
            else OperationEffect.NONE
        )
        await context.events.phase(_PHASES[2])
        await context.events.effect(session_receipt.combine(effect))
        async with context.cancellation.irreversible_section():
            return await context.operands.put(report, written_at=now())


def build_filed_source_capture_definition(
    composition_factory: FiledHistoryCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare a recorded source capture with process cleanup and guarded writes."""

    def build() -> FiledSourceCaptureExecutor:
        return FiledSourceCaptureExecutor(composition_factory, browser_resources_factory, provider_preflight)

    return OperationDefinition(
        definition_id=FILED_SOURCE_CAPTURE_DEFINITION_ID,
        request_type=FiledSourceCaptureRequest,
        result_type=SourceFiledDataCaptureReport,
        executor_factory=OperationExecutorFactory(
            request_type=FiledSourceCaptureRequest,
            executor_type=FiledSourceCaptureExecutor,
            build=build,
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset({OperationOwnedResource.PROCESS}),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def resolve_filed_source_capture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile dependency access and a fresh COMMIT fence."""
    if request.definition_id != FILED_SOURCE_CAPTURE_DEFINITION_ID or not isinstance(
        request.payload, FiledSourceCaptureRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return replace(resolved, policy=policy)


def build_filed_source_capture_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind source capture public schemas to exact whole-profile access."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=FiledSourceCaptureRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=FiledSourceCapturePublicResultV1,
        ),
        result_projector=_project_result,
        access_resolver=resolve_filed_source_capture_access,
    )
