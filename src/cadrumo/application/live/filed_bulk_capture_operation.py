"""Recorded bulk filed capture for an exact profile and authority snapshot."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from ...core.bucket_pointer import require_active_bucket_id
from ...core.filing_year import FilingYear
from ...core.operations import OperationEffect
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    RECORDED_IDEMPOTENT_SECURE_INPUT_PROCESS_UPDATE_CAPABILITIES,
    OperationOwnedResource,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition
from ..operations.owner import OperationExecutorContext, retain_failed_operation_resources
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from .filed_data_capture import capture_filed_data_bulk
from .filed_history_operation import (
    FiledHistoryBrowserResourcesFactory,
    FiledHistoryCompositionFactory,
    FiledHistoryProviderPreflight,
    FiledHistorySyncRunRepositoryFactory,
)
from .filed_single_capture_operation import (
    FiledCaptureNoticeV1,
    FiledReconciliationV1,
    public_filed_capture_notice,
    public_filed_capture_tally,
)
from .live_operation_execution import (
    prepare_provider_capture,
    publish_live_capture_report,
    require_exact_profile_worker,
)
from .live_operation_registration import build_live_operation_definition, resolve_whole_profile_capture_access
from .remote_state_models import BulkFiledDataCaptureReport, FiledCapturePairOutcome

FILED_BULK_CAPTURE_DEFINITION_ID = "live.filed-capture.bulk"
_PHASES = ("filed-bulk.preflight", "filed-bulk.acquire", "filed-bulk.result")
_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class FiledBulkCaptureRequest(BaseModel):
    """One selected modelo/year range and its preview or persistence mode."""

    model_config = _PUBLIC_CONFIG
    profile_id: UUID
    output_root: Path
    year_from: FilingYear
    year_to: FilingYear
    modelos: tuple[str, ...] | None = None
    limit: int | None = Field(default=None, ge=1)
    dry_run: bool = False


class FiledBulkFailureV1(BaseModel):
    """A failed pair with the same bounded coordinates presented by the CLI."""

    model_config = _PUBLIC_CONFIG
    modelo: str
    year: int
    period: str | None
    expediente_id: str | None
    error_type: str
    message: str


class FiledBulkSkippedCasillaV1(BaseModel):
    """Non-numeric casilla omission without its sensitive value."""

    model_config = _PUBLIC_CONFIG
    modelo: str
    year: int
    period: str | None
    expediente_id: str | None
    casilla_id: str
    label: str
    value_kind: str
    reason: str


class FiledBulkCapturePublicResultV1(BaseModel):
    """Complete scalar accounting for a bulk or preview capture."""

    model_config = _PUBLIC_CONFIG
    output_root: str
    modelos: tuple[str, ...]
    year_from: int
    year_to: int
    dry_run: bool
    captured_count: NonNegativeInt
    reached_count: NonNegativeInt
    pair_outcomes: tuple[FiledCapturePairOutcome, ...]
    failed_count: NonNegativeInt
    sync_run_ref: str | None
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
    failures: tuple[FiledBulkFailureV1, ...]
    skipped_casillas: tuple[FiledBulkSkippedCasillaV1, ...]
    recapture_notices: tuple[FiledCaptureNoticeV1, ...]


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
    """Project every report lane, keeping casilla values out of public frames."""
    del receipt
    report = BulkFiledDataCaptureReport.model_validate(result, strict=True)
    report.require_consistent()
    return FiledBulkCapturePublicResultV1(
        output_root=report.output_root,
        modelos=report.modelos,
        year_from=report.year_from,
        year_to=report.year_to,
        dry_run=report.dry_run,
        pair_outcomes=report.pair_outcomes,
        failed_count=report.failed_count,
        sync_run_ref=report.sync_run_ref,
        **public_filed_capture_tally(report),
        failures=tuple(
            FiledBulkFailureV1(
                modelo=row.modelo,
                year=row.year,
                period=row.period.registry_token if row.period is not None else None,
                expediente_id=row.expediente_id,
                error_type=row.error_type,
                message=row.message,
            )
            for row in report.failures
        ),
        skipped_casillas=tuple(
            FiledBulkSkippedCasillaV1(
                modelo=row.modelo,
                year=row.year,
                period=row.period.registry_token if row.period is not None else None,
                expediente_id=row.expediente_id,
                casilla_id=row.casilla_id,
                label=row.label,
                value_kind=row.value_kind,
                reason=row.reason,
            )
            for row in report.skipped_casillas
        ),
        recapture_notices=tuple(public_filed_capture_notice(row) for row in report.recapture_notices),
    )


class FiledBulkCaptureExecutor:
    """Run bulk acquisition in one worker with guarded persistence effects."""

    def __init__(
        self,
        composition_factory: FiledHistoryCompositionFactory,
        browser_resources_factory: FiledHistoryBrowserResourcesFactory,
        provider_preflight: FiledHistoryProviderPreflight,
        sync_run_repository_factory: FiledHistorySyncRunRepositoryFactory,
    ) -> None:
        """Bind worker-owned capabilities for each invocation."""
        self._composition_factory = composition_factory
        self._browser_resources_factory = browser_resources_factory
        self._provider_preflight = provider_preflight
        self._sync_run_repository_factory = sync_run_repository_factory

    async def execute(
        self, request: OperationRequest[FiledBulkCaptureRequest], context: OperationExecutorContext
    ) -> str:
        """Settle the bulk report after local effects pass fresh authority fences."""
        payload = request.payload
        require_exact_profile_worker(
            payload.profile_id, request.subject_ref, active_bucket_id=require_active_bucket_id()
        )
        composition, resources, session_receipt = await prepare_provider_capture(
            context,
            payload.profile_id,
            payload.output_root,
            self._composition_factory,
            self._browser_resources_factory,
            self._provider_preflight,
            preflight_phase=_PHASES[0],
            acquire_phase=_PHASES[1],
            may_write=not payload.dry_run,
        )
        with (
            retain_failed_operation_resources(context.cleanup, family=OperationOwnedResource.PROCESS),
            resources.activate(),
        ):
            report = await capture_filed_data_bulk(
                filed_data_port=composition.filed_data_port,
                year_from=payload.year_from,
                year_to=payload.year_to,
                output_root=payload.output_root,
                ports=composition.ports,
                modelos=payload.modelos,
                limit=payload.limit,
                dry_run=payload.dry_run,
                sync_run_repository=self._sync_run_repository_factory() if not payload.dry_run else None,
                effect_guard=context.cancellation.irreversible_section,
                on_session_write=session_receipt,
                operation=context.authority_operation,
            )
        effect = OperationEffect.UPDATED if report.sync_run_ref is not None else OperationEffect.NONE
        return await publish_live_capture_report(
            context, report, result_phase=_PHASES[2], effect=session_receipt.combine(effect)
        )


def build_filed_bulk_capture_definition(
    composition_factory: FiledHistoryCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
    sync_run_repository_factory: FiledHistorySyncRunRepositoryFactory,
) -> OperationDefinition:
    """Declare recorded bulk capture with process cleanup and guarded writes."""

    def build() -> FiledBulkCaptureExecutor:
        return FiledBulkCaptureExecutor(
            composition_factory, browser_resources_factory, provider_preflight, sync_run_repository_factory
        )

    return build_live_operation_definition(
        definition_id=FILED_BULK_CAPTURE_DEFINITION_ID,
        request_type=FiledBulkCaptureRequest,
        result_type=BulkFiledDataCaptureReport,
        executor_type=FiledBulkCaptureExecutor,
        build=build,
        phase_codes=_PHASES,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_PROCESS_UPDATE_CAPABILITIES,
    )


def resolve_filed_bulk_capture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile access for a sweep that may cross any period."""
    return resolve_whole_profile_capture_access(
        request, context, definition_id=FILED_BULK_CAPTURE_DEFINITION_ID, payload_type=FiledBulkCaptureRequest
    )


def build_filed_bulk_capture_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind bulk capture schemas and exact-profile access resolution."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=FiledBulkCapturePublicResultV1,
        result_projector=_project_result,
        access_resolver=resolve_filed_bulk_capture_access,
    )
