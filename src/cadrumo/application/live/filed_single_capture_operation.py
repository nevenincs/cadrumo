"""Guarded single-pair filed capture behind one immutable profile worker."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from ...core.bucket_pointer import require_active_bucket_id
from ...core.filing_year import FilingYear
from ...core.identity.profile import canonical_profile_bucket_id
from ...core.json_contract import Notice, NoticeSeverity
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
from ..modelo.filing_chain_reconciliation import FilingReconciliationResult
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
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext, retain_failed_operation_resources
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filed_data_capture import capture_filed_data
from .filed_history_operation import (
    FiledHistoryBrowserResourcesFactory,
    FiledHistoryCompositionFactory,
    FiledHistoryProviderPreflight,
)
from .remote_state_models import FiledDataCaptureReport
from .session import LiveSessionWriteReceipt

FILED_SINGLE_CAPTURE_DEFINITION_ID = "live.filed-capture.single"
_PHASES = ("filed-capture.preflight", "filed-capture.acquire", "filed-capture.result")
_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class FiledSingleCaptureRequest(BaseModel):
    """The exact profile, pair and optional register selection to capture."""

    model_config = _PUBLIC_CONFIG
    profile_id: UUID
    output_root: Path
    modelo: str = Field(min_length=1, max_length=8)
    year: FilingYear
    period: str | None = Field(default=None, min_length=1, max_length=8)
    expediente_id: str | None = Field(default=None, min_length=1, max_length=128)
    limit: int | None = Field(default=None, ge=1)


class FiledCaptureNoticeV1(BaseModel):
    """Operator notice with safe string context and no executable action."""

    model_config = _PUBLIC_CONFIG
    severity: NoticeSeverity
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    context: tuple[tuple[str, str], ...] | None = None


class FiledReconciliationNoticeV1(BaseModel):
    """Stable reconciliation condition and its identifier-only coordinates."""

    model_config = _PUBLIC_CONFIG
    code: str = Field(min_length=1)
    context: tuple[tuple[str, str], ...]


class FiledReconciliationV1(BaseModel):
    """Explicit public scalar projection of one filing-chain outcome."""

    model_config = _PUBLIC_CONFIG
    outcome: str = Field(min_length=1)
    bucket_id: str = Field(min_length=1)
    modelo: str = Field(min_length=1)
    filing_year: int
    period: str = Field(min_length=1)
    member_nif: str | None = None
    filing_record_id: str | None = None
    affected_filing_record_ids: tuple[str, ...] = ()
    differing_casilla_ids: tuple[str, ...] = ()
    evidence_basis: str | None = None
    notices: tuple[FiledReconciliationNoticeV1, ...] = ()


class FiledSingleCapturePublicResultV1(BaseModel):
    """Safe complete accounting needed by the existing CLI filed-pull report."""

    model_config = _PUBLIC_CONFIG
    output_root: str
    modelo: str
    year: int
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


def public_filed_capture_notice(notice: Notice) -> FiledCaptureNoticeV1:
    """Project one capture notice without exposing private adapter state."""
    return FiledCaptureNoticeV1(
        severity=notice.severity,
        code=notice.code,
        message=notice.message,
        context=None if notice.context is None else tuple(sorted(notice.context.items())),
    )


def public_filed_reconciliation(row: FilingReconciliationResult) -> FiledReconciliationV1:
    """Project one filing-chain result with stable scalar coordinates."""
    return FiledReconciliationV1(
        outcome=row.outcome.value,
        bucket_id=row.bucket_id,
        modelo=row.modelo,
        filing_year=row.filing_year,
        period=row.period.registry_token,
        member_nif=row.member_nif,
        filing_record_id=row.filing_record_id,
        affected_filing_record_ids=row.affected_filing_record_ids,
        differing_casilla_ids=tuple(row.differing_casilla_ids),
        evidence_basis=row.evidence_basis,
        notices=tuple(
            FiledReconciliationNoticeV1(code=notice.code.value, context=tuple(sorted(notice.context.items())))
            for notice in row.notices
        ),
    )


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
    """Expose only the complete, explicitly declared safe result fields."""
    del receipt
    report = FiledDataCaptureReport.model_validate(result, strict=True)
    return FiledSingleCapturePublicResultV1(
        output_root=report.output_root,
        modelo=report.modelo,
        year=report.year,
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


class FiledSingleCaptureExecutor:
    """Capture AEAT bytes without a fence and guard every subsequent local effect."""

    def __init__(
        self,
        composition_factory: FiledHistoryCompositionFactory,
        browser_resources_factory: FiledHistoryBrowserResourcesFactory,
        provider_preflight: FiledHistoryProviderPreflight,
    ) -> None:
        """Bind worker-owned provider, composition and browser cleanup capabilities."""
        self._composition_factory = composition_factory
        self._browser_resources_factory = browser_resources_factory
        self._provider_preflight = provider_preflight

    async def execute(
        self, request: OperationRequest[FiledSingleCaptureRequest], context: OperationExecutorContext
    ) -> str:
        """Capture one selected pair and publish its complete encrypted accounting."""
        payload = request.payload
        profile_id = canonical_profile_bucket_id(payload.profile_id)
        if require_active_bucket_id() != profile_id or request.subject_ref != profile_operation_subject(profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(_PHASES[0])
        self._provider_preflight(payload.profile_id, context.authority_operation)
        period = Period.from_year_and_code(payload.year, payload.period) if payload.period is not None else None
        composition = self._composition_factory(payload.output_root, operation=context.authority_operation)
        resources = self._browser_resources_factory()
        context.cleanup.own(resources, family=OperationOwnedResource.PROCESS)
        await context.events.phase(_PHASES[1])
        # Remote acquisition and any local writes can be interrupted at distinct
        # points. Until a report settles, the committed effect is unknown.
        await context.events.effect(OperationEffect.UNKNOWN)
        session_receipt = LiveSessionWriteReceipt(context.events.effect)
        with (
            retain_failed_operation_resources(context.cleanup, family=OperationOwnedResource.PROCESS),
            resources.activate(),
        ):
            report = await capture_filed_data(
                filed_data_port=composition.filed_data_port,
                modelo=payload.modelo,
                year=payload.year,
                output_root=payload.output_root,
                ports=composition.ports,
                period=period,
                expediente_id=payload.expediente_id,
                limit=payload.limit,
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


def build_filed_single_capture_definition(
    composition_factory: FiledHistoryCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare one recorded process-owning capture with guarded local effects."""

    def build() -> FiledSingleCaptureExecutor:
        return FiledSingleCaptureExecutor(composition_factory, browser_resources_factory, provider_preflight)

    return OperationDefinition(
        definition_id=FILED_SINGLE_CAPTURE_DEFINITION_ID,
        request_type=FiledSingleCaptureRequest,
        result_type=FiledDataCaptureReport,
        executor_factory=OperationExecutorFactory(
            request_type=FiledSingleCaptureRequest,
            executor_type=FiledSingleCaptureExecutor,
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


def resolve_filed_single_capture_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile capture authority and a fresh COMMIT fence."""
    if request.definition_id != FILED_SINGLE_CAPTURE_DEFINITION_ID or not isinstance(
        request.payload, FiledSingleCaptureRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return replace(resolved, policy=policy)


def build_filed_single_capture_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind stable public request/result schemas and whole-profile access."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=FiledSingleCaptureRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=FiledSingleCapturePublicResultV1,
        ),
        result_projector=_project_result,
        access_resolver=resolve_filed_single_capture_access,
    )
