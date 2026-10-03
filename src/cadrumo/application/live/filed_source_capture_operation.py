"""Guarded source-dependency filed capture for an exact profile worker."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from ...core.bucket_pointer import require_active_bucket_id
from ...core.filing_year import FilingYear
from ...core.period import Period
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    RECORDED_IDEMPOTENT_SECURE_INPUT_PROCESS_UPDATE_CAPABILITIES,
    OperationOwnedResource,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition
from ..operations.owner import OperationExecutorContext, retain_failed_operation_resources
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from .filed_data_capture import capture_source_filed_data
from .filed_history_operation import (
    FiledHistoryBrowserResourcesFactory,
    FiledHistoryCompositionFactory,
    FiledHistoryProviderPreflight,
)
from .filed_single_capture_operation import (
    FiledCaptureNoticeV1,
    FiledReconciliationV1,
    filed_capture_tally_effect,
    public_filed_capture_tally,
)
from .live_operation_execution import (
    own_provider_browser,
    publish_live_capture_report,
    require_exact_profile_worker,
    track_capture_session,
)
from .live_operation_registration import build_live_operation_definition, resolve_whole_profile_capture_access
from .remote_state_models import SourceFiledDataCaptureReport

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
        **public_filed_capture_tally(report),
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
        require_exact_profile_worker(
            payload.profile_id, request.subject_ref, active_bucket_id=require_active_bucket_id()
        )
        await context.events.phase(_PHASES[0])
        self._provider_preflight(payload.profile_id, context.authority_operation)
        period = Period.from_year_and_code(payload.year, payload.period)
        composition = self._composition_factory(payload.output_root, operation=context.authority_operation)
        resources = await own_provider_browser(context, self._browser_resources_factory, acquire_phase=_PHASES[1])
        session_receipt = await track_capture_session(context, may_write=True)
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
        return await publish_live_capture_report(
            context, report, result_phase=_PHASES[2], effect=session_receipt.combine(filed_capture_tally_effect(report))
        )


def build_filed_source_capture_definition(
    composition_factory: FiledHistoryCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare a recorded source capture with process cleanup and guarded writes."""

    def build() -> FiledSourceCaptureExecutor:
        return FiledSourceCaptureExecutor(composition_factory, browser_resources_factory, provider_preflight)

    return build_live_operation_definition(
        definition_id=FILED_SOURCE_CAPTURE_DEFINITION_ID,
        request_type=FiledSourceCaptureRequest,
        result_type=SourceFiledDataCaptureReport,
        executor_type=FiledSourceCaptureExecutor,
        build=build,
        phase_codes=_PHASES,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_PROCESS_UPDATE_CAPABILITIES,
    )


def resolve_filed_source_capture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile dependency access and a fresh COMMIT fence."""
    return resolve_whole_profile_capture_access(
        request, context, definition_id=FILED_SOURCE_CAPTURE_DEFINITION_ID, payload_type=FiledSourceCaptureRequest
    )


def build_filed_source_capture_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind source capture public schemas to exact whole-profile access."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=FiledSourceCapturePublicResultV1,
        result_projector=_project_result,
        access_resolver=resolve_filed_source_capture_access,
    )
