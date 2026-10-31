"""Assert public settlement, result projections, and operation-specific effects."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...application.actividad_asset.activity_asset_projections import (
    ActivityAssetAcquisitionCandidatesProjection,
    ActivityAssetClaimProjection,
    ActivityAssetCorrectProjection,
    ActivityAssetCreateProjection,
    ActivityAssetDescribeProjection,
    ActivityAssetDisposalCalculateProjection,
    ActivityAssetDisposeProjection,
    ActivityAssetFilingHandoffProjection,
    ActivityAssetForecastProjection,
    ActivityAssetFormOptionsProjection,
    ActivityAssetInspectProjection,
    ActivityAssetListProjection,
    ActivityAssetPlanProjection,
    ActivityAssetTimelineProjection,
)
from ...application.auth.auth_read_contracts import (
    AUTH_READ_OPERATION_DEFINITION_ID,
    AuthReadProjection,
    AuthReadRequest,
)
from ...application.auth.certificate_source_operations import list_operator_certificate_sources
from ...application.auth.credential_operations import AuthCredentialSaveResult
from ...application.auth.credentials import CLAVE_PERMANENTE_PASSWORD_SECRET_NAME
from ...application.bienes_inversion.registered_result_contracts import (
    BienesInversionDeclareProjection,
    BienesInversionListProjection,
    BienInversionRecordProjection,
)
from ...application.bucket_event_repository import bucket_event_history_repository
from ...application.inventory.registered_projections import (
    InventoryClosingAuthorityOperationProjection,
    InventoryCreateProjection,
    InventoryInspectProjection,
    InventoryLedgerChangeProjection,
    InventoryLedgerProjection,
    InventoryListProjection,
    InventoryMovementAddProjection,
    InventoryValuationOperationProjection,
)
from ...application.inventory.registered_specs import INVENTORY_LEDGER_CHANGE_REQUEST_TYPES
from ...application.ledger.attachment_mutation_operation import LedgerAttachmentOperationResult
from ...application.ledger.invoice_evidence_confirm_operation import LedgerEvidenceConfirmProjection
from ...application.ledger.lifecycle_contracts import LedgerLifecycleOperationResult
from ...application.ledger.rule_contracts import LedgerRuleAddProjection
from ...application.ledger.usage_ratio_repository import load_usage_ratio_profile
from ...application.modelo.invoice_withholding_capture_contracts import ModeloInvoiceWithholdingCaptureProjection
from ...application.modelo.query_read_contracts import (
    ModeloBindingsListProjection,
    ModeloBindingsResolveProjection,
    ModeloReadinessProjection,
    ModeloRequiresProjection,
)
from ...application.modelo.review_package_recipient_operations import ReviewPackageRecipientAddProjection
from ...application.modelo.typed_query_contracts import (
    ModeloBindingsResolveTypedProjection,
    ModeloReadinessSummaryProjection,
)
from ...application.operations.composition import OperationSubmission
from ...application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationReviewAvailableInteractionV1,
)
from ...application.operations.frontend_requests import OperationObservationSuccessV1, OperationPublicPhaseEventV1
from ...application.operations.operation_definition import OperationDefinition
from ...application.operations.public_period import PublicPeriod
from ...application.operations.registry import OperationRegistry
from ...application.overview.pipeline_operation import OverviewPipelineProjection, OverviewPipelineRequest
from ...application.overview.pipeline_projection import PipelineHealthSnapshot
from ...application.overview.read_payload import (
    OverviewAgendaRead,
    OverviewBacklogRead,
    OverviewCalendarRead,
    OverviewExplainRead,
    OverviewPrepareRead,
    OverviewStatusRead,
)
from ...application.overview.read_request import OVERVIEW_READ_DEFINITION_IDS, OverviewReadKind, OverviewReadRequest
from ...application.overview.read_result import OverviewReadProjection
from ...application.prorrata_register.projection_contracts import ProrrataListProjection, ProrrataMutationProjection
from ...application.user_profile.recovery_custody import profile_recovery_status
from ...application.user_profile.recovery_status_operation import RecoveryStatusProjection
from ...application.workflow.abort import WorkflowAbortReason
from ...application.workflow.persistence import WorkflowRunRepository, workflow_state_repository
from ...application.workflow.resume_contracts import (
    WorkflowResumeProjection,
    WorkflowResumeRequest,
    WorkflowResumeSuccess,
)
from ...application.workflow.resume_operation import WORKFLOW_RESUME_OPERATION_DEFINITION_ID
from ...application.workflow.run_read_operation import (
    WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID,
    WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,
    WorkflowRunListProjection,
    WorkflowRunListRequest,
    WorkflowRunReadProjection,
    WorkflowRunReadRequest,
)
from ...core.config import load_settings
from ...core.external_constants import OutputLanguage
from ...core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.period import Period
from ...domain.buckets.event import BucketEventType
from ...domain.categories.spending_category_catalogue import require_spending_category
from ..adapter_composition_ports import build_bienes_inversion_repository, build_prorrata_register_repository
from ..adapter_composition_work_ports import build_verification_repository_bundle
from .activity_asset_operation_test_support import assert_activity_asset_conformance_result
from .conformance_family_contract import RegisteredExecutorConformanceCase
from .invoice_evidence_operation_test_support import assert_invoice_evidence_confirmation_persisted
from .invoice_withholding_operation_test_support import (
    assert_invoice_withholding_conformance_write,
    read_invoice_withholding_conformance_case,
)
from .ledger_attachment_operation_test_support import assert_ledger_attachment_operation_conformance_result
from .ledger_lifecycle_operation_test_support import assert_ledger_lifecycle_operation_conformance_result
from .ledger_rule_operation_test_support import assert_ledger_rule_operation_conformance_result
from .prorrata_bienes_operation_test_support import (
    bienes_inversion_conformance_record,
    read_bienes_inversion_operation_conformance_register,
)
from .prorrata_operation_test_support import read_prorrata_operation_conformance_register
from .recipient_operation_test_support import assert_recipient_operation_conformance_result
from .registered_executor_case_support import (
    OperationRuntimeCloseWitness,
    _ExecutionDriver,
    _judge_family_outcome,
    _resolve_result_projection,
)
from .registered_executor_outcome_context import ExecutorOutcome
from .registered_executor_outcome_ledger import LEDGER_OUTCOME_ASSERTIONS
from .registered_executor_outcome_modelo import MODELO_OUTCOME_ASSERTIONS
from .registered_executor_scenario_constants import (
    _CREDENTIAL_INPUT,
)


def assert_expected_reads(ctx: ExecutorOutcome) -> None:
    """Compare each expected typed read with the resolved result."""
    for expected_read in (
        ctx.projection_history_case.expected_projection if ctx.projection_history_case is not None else None,
        ctx.query_case.expected_projection if ctx.query_case is not None else None,
        ctx.review_case.expected_read if ctx.review_case is not None else None,
        ctx.followup_case.expected_read if ctx.followup_case is not None else None,
    ):
        if expected_read is not None:
            actual_read = ctx.resolve(type(expected_read))
            if ctx.query_case is not None:
                assert isinstance(
                    actual_read,
                    (
                        ModeloBindingsListProjection,
                        ModeloBindingsResolveProjection,
                        ModeloBindingsResolveTypedProjection,
                        ModeloRequiresProjection,
                        ModeloReadinessProjection,
                        ModeloReadinessSummaryProjection,
                    ),
                )
                assert actual_read.authority_generation == ctx.operation.generation.logical_generation
            actual_fields = actual_read.model_dump(mode="json")
            expected_fields = expected_read.model_dump(mode="json")
            assert actual_read == expected_read, {
                key: (actual_fields[key], expected_fields[key])
                for key in actual_fields
                if actual_fields[key] != expected_fields[key]
            }


def assert_attachment_effects(ctx: ExecutorOutcome) -> None:
    """Check the persisted effects bound to `attachment_case`."""
    attachment_result = ctx.resolve(LedgerAttachmentOperationResult)
    assert isinstance(attachment_result, LedgerAttachmentOperationResult)
    assert attachment_result.outcome == "updated"
    assert attachment_result.result is not None
    assert_ledger_attachment_operation_conformance_result(
        ctx.attachment_case, attachment_result.result, operation_run_id=ctx.submitted.receipt.operation_id
    )


def assert_lifecycle_effects(ctx: ExecutorOutcome) -> None:
    """Check the persisted effects bound to `lifecycle_case`."""
    lifecycle_result = ctx.resolve(LedgerLifecycleOperationResult)
    assert isinstance(lifecycle_result, LedgerLifecycleOperationResult)
    assert lifecycle_result.outcome == "updated"
    assert lifecycle_result.result is not None
    assert_ledger_lifecycle_operation_conformance_result(
        ctx.lifecycle_case, lifecycle_result.result, operation_run_id=ctx.submitted.receipt.operation_id
    )


def assert_rule_effects(ctx: ExecutorOutcome) -> None:
    """Check the persisted effects bound to `rule_case`."""
    rule_result = ctx.resolve(
        type(ctx.rule_case.expected_projection)
        if ctx.rule_case.expected_projection is not None
        else LedgerRuleAddProjection
    )
    assert_ledger_rule_operation_conformance_result(
        ctx.rule_case, rule_result, operation_run_id=ctx.submitted.receipt.operation_id
    )


def assert_recipient_effects(ctx: ExecutorOutcome) -> None:
    """Check the persisted effects bound to `recipient_case`."""
    recipient_result = ctx.resolve(
        type(ctx.recipient_case.expected_projection)
        if ctx.recipient_case.expected_projection is not None
        else ReviewPackageRecipientAddProjection
    )
    assert_recipient_operation_conformance_result(
        ctx.recipient_case, recipient_result, profile_id=ctx.profile_id, operation_id=ctx.submitted.receipt.operation_id
    )


def assert_evidence_effects(ctx: ExecutorOutcome) -> None:
    """Check the persisted effects bound to `evidence_case`."""
    result_type = (
        type(ctx.evidence_case.expected_read)
        if ctx.evidence_case.expected_read is not None
        else LedgerEvidenceConfirmProjection
    )
    evidence_result = ctx.resolve(result_type)
    if ctx.evidence_case.expected_read is not None:
        assert evidence_result == ctx.evidence_case.expected_read
        assert InvoiceCatalogueRepository(bucket_id=str(ctx.profile_id)).load().invoices == {}
    else:
        assert isinstance(evidence_result, LedgerEvidenceConfirmProjection)
        assert evidence_result.profile_id == ctx.profile_id
        assert_invoice_evidence_confirmation_persisted(
            ctx.evidence_case, evidence_result, operation_id=ctx.submitted.receipt.operation_id
        )


def assert_prorrata_effects(ctx: ExecutorOutcome) -> None:
    """Check the persisted effects bound to `prorrata_case`."""
    assert ctx.prorrata_before is not None
    prorrata_after = read_prorrata_operation_conformance_register(
        ctx.profile_id, repository_factory=build_prorrata_register_repository, operation=ctx.operation
    )
    assert prorrata_after == ctx.prorrata_case.expected_register
    prorrata_result = ctx.resolve(type(ctx.prorrata_case.expected_projection))
    assert prorrata_result == ctx.prorrata_case.expected_projection
    assert isinstance(prorrata_result, (ProrrataListProjection, ProrrataMutationProjection))
    assert prorrata_result.profile_id == ctx.profile_id
    assert prorrata_result.count == ctx.prorrata_case.expected_count
    assert ctx.observed.projection.effect is ctx.prorrata_case.expected_effect
    if ctx.prorrata_case.operation_id == "list":
        assert prorrata_after == ctx.prorrata_before
        assert prorrata_result.count == len(prorrata_after.entries)
    else:
        assert prorrata_after != ctx.prorrata_before
        assert prorrata_result.count == (
            len(prorrata_after.sector_definitions)
            if ctx.prorrata_case.operation_id == "declare_sector"
            else len(prorrata_after.entries)
        )


def assert_withholding_effects(ctx: ExecutorOutcome) -> None:
    """Check the persisted effects bound to `withholding_seed`."""
    withholding_result = ctx.resolve(ModeloInvoiceWithholdingCaptureProjection)
    assert isinstance(withholding_result, ModeloInvoiceWithholdingCaptureProjection)
    assert withholding_result.profile_id == ctx.profile_id
    assert withholding_result.outcome == "captured"
    assert withholding_result.modelo == ctx.withholding_seed.request.command.modelo
    assert withholding_result.period.to_period() == ctx.withholding_seed.period
    withholding_after = read_invoice_withholding_conformance_case(ctx.profile_id, ctx.withholding_seed)
    assert_invoice_withholding_conformance_write(
        withholding_after, ctx.withholding_seed, profile_id=ctx.profile_id, operation=ctx.operation
    )
    assert withholding_result.observation_count == len(withholding_after.observations)
    assert withholding_result.withholding_window is not None
    assert withholding_result.withholding_window.generation == withholding_after.generation


def assert_asset_effects(ctx: ExecutorOutcome) -> None:
    """Check the persisted effects bound to `asset_repository`."""
    assert ctx.asset_before is not None
    asset_projection_type = {
        "ledger.actividad-asset.create": ActivityAssetCreateProjection,
        "ledger.actividad-asset.inspect": ActivityAssetInspectProjection,
        "ledger.actividad-asset.correct": ActivityAssetCorrectProjection,
        "ledger.actividad-asset.forecast": ActivityAssetForecastProjection,
        "ledger.actividad-asset.claim": ActivityAssetClaimProjection,
        "ledger.actividad-asset.filing-handoff": ActivityAssetFilingHandoffProjection,
        "ledger.actividad-asset.describe": ActivityAssetDescribeProjection,
        "ledger.actividad-asset.dispose": ActivityAssetDisposeProjection,
        "ledger.actividad-asset.disposal-calculate": ActivityAssetDisposalCalculateProjection,
        "ledger.actividad-asset.list": ActivityAssetListProjection,
        "ledger.actividad-asset.plan": ActivityAssetPlanProjection,
        "ledger.actividad-asset.timeline": ActivityAssetTimelineProjection,
        "ledger.actividad-asset.form-options": ActivityAssetFormOptionsProjection,
        "ledger.actividad-asset.acquisition-candidates": ActivityAssetAcquisitionCandidatesProjection,
    }[ctx.case.definition_id]
    asset_projection = ctx.resolve(asset_projection_type)
    assert_activity_asset_conformance_result(
        definition_id=ctx.case.definition_id,
        payload=ctx.payload,
        projection=asset_projection,
        before=ctx.asset_before,
        after=ctx.asset_repository.load(),
        operation=ctx.operation,
    )


def assert_bienes_effects(ctx: ExecutorOutcome) -> None:
    """Check the persisted effects bound to `bienes_before`."""
    bienes_after = read_bienes_inversion_operation_conformance_register(
        ctx.profile_id, repository_factory=build_bienes_inversion_repository
    )
    expected_record = bienes_inversion_conformance_record(ctx.case.definition_id, operation=ctx.operation)
    assert bienes_after.records == (expected_record,)
    bienes_projection_type = (
        BienesInversionListProjection if ctx.case.definition_id.endswith(".list") else BienesInversionDeclareProjection
    )
    bienes_result = ctx.resolve(bienes_projection_type)
    assert isinstance(bienes_result, BienesInversionListProjection | BienesInversionDeclareProjection)
    assert bienes_result.profile_id == ctx.profile_id
    expected_projection = BienInversionRecordProjection.from_record(expected_record)
    if isinstance(bienes_result, BienesInversionListProjection):
        assert bienes_after == ctx.bienes_before
        assert bienes_result.rows == (expected_projection,)
    else:
        assert ctx.bienes_before.records == ()
        assert bienes_result.outcome == "declared"
        assert bienes_result.refusal is None
        assert bienes_result.count == 1
        assert bienes_result.record == expected_projection


def assert_inventory_effects(ctx: ExecutorOutcome) -> None:
    """Check the persisted effects bound to `inventory_repository`."""
    if ctx.family_preparation is not None:
        return
    projection_type = {
        "ledger.inventory.list": InventoryListProjection,
        "ledger.inventory.create": InventoryCreateProjection,
        "ledger.inventory.movement.add": InventoryMovementAddProjection,
        "ledger.inventory.valuation.preview": InventoryValuationOperationProjection,
        "ledger.inventory.closing-authority.record": InventoryClosingAuthorityOperationProjection,
        "ledger.inventory.inspect": InventoryInspectProjection,
        **dict.fromkeys(INVENTORY_LEDGER_CHANGE_REQUEST_TYPES, InventoryLedgerChangeProjection),
    }[ctx.case.definition_id]
    inventory_result = ctx.resolve(projection_type)
    inventory_after = ctx.inventory_repository.load()
    assert len(inventory_after.ledgers) == 1
    ledger = inventory_after.ledgers[0]
    if isinstance(inventory_result, InventoryListProjection):
        assert inventory_result.profile_id == ctx.profile_id
        assert len(inventory_result.rows) == 1
        assert inventory_result.rows[0].actividad_id == ledger.actividad_id
        assert inventory_after == ctx.inventory_before
    elif isinstance(inventory_result, InventoryInspectProjection):
        assert inventory_result.profile_id == ctx.profile_id and inventory_result.outcome == "found"
        assert inventory_result.ledger == InventoryLedgerProjection.from_ledger(ledger)
        assert inventory_after == ctx.inventory_before
    elif isinstance(inventory_result, InventoryLedgerChangeProjection):
        assert inventory_result.profile_id == ctx.profile_id and inventory_result.outcome == "applied"
        assert inventory_result.ledger == InventoryLedgerProjection.from_ledger(
            ledger, bucket_event_ids=inventory_result.bucket_event_ids
        )
        assert len(ledger.history) > len(ctx.inventory_before.ledgers[0].history)
        events = bucket_event_history_repository(bucket_id=str(ctx.profile_id)).load().events
        assert all(event_id in events for event_id in inventory_result.bucket_event_ids)
    elif isinstance(inventory_result, InventoryCreateProjection | InventoryMovementAddProjection):
        assert inventory_result.profile_id == ctx.profile_id and inventory_result.ledger is not None
        assert inventory_result.ledger == InventoryLedgerProjection.from_ledger(
            ledger, bucket_event_ids=inventory_result.bucket_event_ids
        )
        expected_movements = 1 if isinstance(inventory_result, InventoryMovementAddProjection) else 0
        assert len(ledger.period_movements) == expected_movements
        events = bucket_event_history_repository(bucket_id=str(ctx.profile_id)).load().events
        assert all(event_id in events for event_id in inventory_result.bucket_event_ids)
    elif isinstance(inventory_result, InventoryValuationOperationProjection):
        assert inventory_result.preview is not None and inventory_result.preview.profile_id == ctx.profile_id
        assert Decimal(inventory_result.preview.derived_closing_value.decimal) == Decimal("100.00")
        assert inventory_after == ctx.inventory_before
        events = bucket_event_history_repository(bucket_id=str(ctx.profile_id)).load().events
        assert all(event_id in events for event_id in inventory_result.preview.bucket_event_ids)
    else:
        assert isinstance(inventory_result, InventoryClosingAuthorityOperationProjection)
        assert inventory_result.record is not None and inventory_result.record.profile_id == ctx.profile_id
        assert ledger.closing_authority_record is not None
        assert inventory_result.record.authority_record_fingerprint == ledger.closing_authority_record.fingerprint
        assert inventory_result.record.changed is True


def assert_user_profile_recovery_status_outcome(ctx: ExecutorOutcome) -> None:
    """Check the user-profile.recovery.status public result and effects."""
    recovery = ctx.resolve(RecoveryStatusProjection)
    assert isinstance(recovery, RecoveryStatusProjection)
    assert recovery.profile_id == ctx.profile_id
    assert recovery.enrolled is True
    assert recovery.enrolled == profile_recovery_status(profile_id=ctx.profile_id).enrolled


def assert_auth_credential_save_outcome(ctx: ExecutorOutcome) -> None:
    """Check the auth.credential.save public result and effects."""
    result = ctx.resolve(AuthCredentialSaveResult)
    assert isinstance(result, AuthCredentialSaveResult)
    assert result.saved and result.provider == "clave_permanente"
    assert _CREDENTIAL_INPUT not in result.model_dump_json()
    stored = build_certificate_secret_backend(bucket_id=str(ctx.profile_id), settings=load_settings()).get(
        CLAVE_PERMANENTE_PASSWORD_SECRET_NAME
    )
    assert stored is not None and stored.get_secret_value() == _CREDENTIAL_INPUT


def _assert_certificate_source_outcome(ctx: ExecutorOutcome, document: dict[str, Any]) -> None:
    sources = list_operator_certificate_sources()
    if ctx.case.definition_id == "auth.certificate.source.remove":
        assert sources.sources == ()
        assert document["result"]["removed"] is True
    elif ctx.case.definition_id == "auth.certificate.source.list":
        assert document["result"] == sources.model_dump(mode="json")
    elif ctx.case.definition_id == "auth.certificate.source.check":
        assert document["result"]["entries"][0]["result"] == "file_missing"
        assert document["result"]["has_warnings"] is False
    else:
        assert len(sources.sources) == 1
        assert sources.sources[0].name == "supervisor-certificate"
        assert sources.sources[0].certificate_path == str(
            ctx.tmp_path / ctx.case.definition_id / "absent-certificate.p12"
        )
        if ctx.case.definition_id == "auth.certificate.source.select":
            assert sources.active_source == "supervisor-certificate"
    if ctx.certificate_state_before is not None:
        assert workflow_state_repository().load() == ctx.certificate_state_before


def _assert_certificate_secret_outcome(ctx: ExecutorOutcome, document: dict[str, Any]) -> None:
    stored = build_certificate_secret_backend(bucket_id=str(ctx.profile_id), settings=load_settings()).get(
        "supervisor-certificate"
    )
    if ctx.case.definition_id == "auth.certificate.secret.set":
        assert stored is not None and stored.get_secret_value() == _CREDENTIAL_INPUT
    else:
        assert stored is None
        assert document["result"]["removed"] is True


def _assert_eligible_ratio_rows(document: dict[str, Any]) -> None:
    served = {row["category"]: row for row in document["rows"]}
    assert document["count"] == len(served) > 0
    assert served["ibi_vivienda_afecto"]["label"] == "Property tax (IBI) on home used for business"
    assert served["ibi_vivienda_afecto"]["notes"] == (
        "Deductible in proportion to the home's floor area used for the business and to your "
        "ownership share in it; the 30% supplies factor does not apply (Ley 35/2006 art. 29.2, "
        "Reglamento IRPF art. 22.3, property tax on the home used for business)."
    )
    assert served["ibi_vivienda_afecto"]["proportionality_kind"] == "usage_ratio_home_area"
    assert "amortizacion_vivienda_afecto" not in served
    assert "vehiculo_combustible" not in served
    assert served["suministros_home_office_luz"]["label"] == "Home-office electricity"
    assert served["suministros_home_office_luz"]["proportionality_kind"] == "usage_ratio_home_area"


def _assert_ratios_outcome(ctx: ExecutorOutcome, document: dict[str, Any]) -> None:
    ratios_after = load_usage_ratio_profile(bucket_id=str(ctx.profile_id), operation=ctx.operation)
    events_after = bucket_event_history_repository(bucket_id=str(ctx.profile_id)).load()
    category = require_spending_category("arrendamiento_vivienda_afecto", authority=ctx.operation)
    if ctx.case.definition_id == "ledger.ratios.set":
        assert ratios_after.ratios[category] == Decimal("0.5")
        assert any(event.event_type is BucketEventType.LEDGER_RATIOS_SET for event in events_after.events.values())
    elif ctx.case.definition_id == "ledger.ratios.unset":
        assert category not in ratios_after.ratios
        assert any(event.event_type is BucketEventType.LEDGER_RATIOS_UNSET for event in events_after.events.values())
    else:
        assert (ratios_after, events_after) == ctx.ratios_before
    if ctx.case.definition_id == "ledger.ratios.eligible":
        _assert_eligible_ratio_rows(document)


_CERTIFICATE_OR_RATIOS_ASSERTIONS: tuple[tuple[str, Callable[[ExecutorOutcome, dict[str, Any]], None]], ...] = (
    ("auth.certificate.source.", _assert_certificate_source_outcome),
    ("auth.certificate.secret.", _assert_certificate_secret_outcome),
    ("", _assert_ratios_outcome),
)


def assert_certificate_or_ratios_outcome(ctx: ExecutorOutcome) -> None:
    """Check the certificate or ratios result and effects."""
    contract = ctx.registry.lookup_public_contract(ctx.case.definition_id)
    assert contract.result_schema is not None
    result = ctx.resolve(ctx.registry.lookup_public_schema_binding(contract.result_schema).model_type)
    document = result.model_dump(mode="json")
    assert document["profile_id"] == str(ctx.profile_id)
    assert _CREDENTIAL_INPUT not in result.model_dump_json()
    for prefix, assertion in _CERTIFICATE_OR_RATIOS_ASSERTIONS:
        if ctx.case.definition_id.startswith(prefix):
            assertion(ctx, document)
            break


def assert_workflow_run_read_outcome(ctx: ExecutorOutcome) -> None:
    """Check the WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID public result and effects."""
    assert isinstance(ctx.payload, WorkflowRunReadRequest)
    result = ctx.resolve(WorkflowRunReadProjection)
    assert isinstance(result, WorkflowRunReadProjection)
    assert result.profile_id == ctx.profile_id
    assert result.expected_period == ctx.payload.expected_period
    assert result.run.run_id == ctx.payload.run_id
    assert result.run.obligation is not None
    assert result.run.obligation.period == ctx.payload.expected_period


def assert_auth_read_outcome(ctx: ExecutorOutcome) -> None:
    """Check the AUTH_READ_OPERATION_DEFINITION_ID public result and effects."""
    assert isinstance(ctx.payload, AuthReadRequest)
    result = ctx.resolve(AuthReadProjection)
    assert isinstance(result, AuthReadProjection)
    assert result.profile_id == ctx.profile_id
    assert result.kind == ctx.payload.kind == "diagnostics_list"
    assert result.diagnostics_rows is not None


def assert_overview_read_outcome(ctx: ExecutorOutcome) -> None:
    """Check the overview read result and effects."""
    assert isinstance(ctx.payload, OverviewReadRequest)
    result = ctx.resolve(OverviewReadProjection)
    assert isinstance(result, OverviewReadProjection)
    assert result.profile_id == ctx.profile_id
    assert result.request == ctx.payload
    assert result.payload.kind == ctx.payload.kind.value
    match result.payload:
        case OverviewStatusRead() if ctx.payload.kind is OverviewReadKind.STATUS:
            if ctx.payload.period is None:
                assert result.payload.report is not None
                assert result.payload.period_report is None
                period_payload = OverviewReadRequest(
                    profile_id=ctx.profile_id,
                    kind=OverviewReadKind.STATUS,
                    output_language=OutputLanguage.ES,
                    period=PublicPeriod.from_period(Period.from_year_and_code(2025, "1T")),
                )
                _, period_observed = asyncio.run(
                    ctx.driver.run(
                        definition_id=ctx.case.definition_id,
                        subject_ref=profile_operation_subject(str(ctx.profile_id)),
                        payload=period_payload,
                    )
                )
                assert period_observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert period_observed.projection.effect is OperationEffect.NONE
                period_result = _resolve_result_projection(
                    ctx.driver,
                    ctx.registry,
                    definition_id=ctx.case.definition_id,
                    operation_id=period_observed.projection.operation_id,
                    terminal_revision=period_observed.projection.revision,
                    projection_type=OverviewReadProjection,
                )
                assert isinstance(period_result, OverviewReadProjection)
                assert period_result.request == period_payload
                assert isinstance(period_result.payload, OverviewStatusRead)
                assert period_result.payload.period_report is not None
                assert period_result.payload.period_report.period == period_payload.period
                assert period_result.payload.report is None
        case OverviewCalendarRead() if ctx.payload.kind is OverviewReadKind.CALENDAR:
            assert result.payload.calendar is not None
            assert result.payload.calendar.range.from_date == ctx.payload.from_date
            assert result.payload.calendar.range.to_date == ctx.payload.to_date
        case OverviewAgendaRead() if ctx.payload.kind is OverviewReadKind.AGENDA:
            assert result.payload.agenda.as_of == ctx.payload.as_of
            assert result.payload.agenda.horizon_days == ctx.payload.horizon_days
        case OverviewBacklogRead() if ctx.payload.kind is OverviewReadKind.BACKLOG:
            assert result.payload.backlog.range.from_date == ctx.payload.from_date
            assert result.payload.backlog.range.to_date == ctx.payload.to_date
        case OverviewExplainRead() if ctx.payload.kind is OverviewReadKind.EXPLAIN:
            assert result.payload.explanation.modelo == ctx.payload.modelo
            assert result.payload.explanation.year == ctx.payload.year
        case OverviewPrepareRead() if ctx.payload.kind is OverviewReadKind.PREPARE:
            assert ctx.payload.period is not None
            assert result.payload.preparation.modelo == ctx.payload.modelo
            assert result.payload.preparation.filing_year == ctx.payload.period.filing_year
            assert result.payload.preparation.period == ctx.payload.period.code
        case _:
            pytest.fail(f"unexpected overview result kind for {ctx.case.definition_id}")


def assert_workflow_run_list_outcome(ctx: ExecutorOutcome) -> None:
    """Check the WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID public result and effects."""
    assert isinstance(ctx.payload, WorkflowRunListRequest)
    result = ctx.resolve(WorkflowRunListProjection)
    assert isinstance(result, WorkflowRunListProjection)
    assert result.profile_id == ctx.profile_id
    assert tuple(run.run_id for run in result.runs) == ("b" * 16, "a" * 16)
    assert all(run.obligation is not None for run in result.runs)


def assert_overview_pipeline_outcome(ctx: ExecutorOutcome) -> None:
    """Check the overview.pipeline public result and effects."""
    assert isinstance(ctx.payload, OverviewPipelineRequest)
    assert ctx.overview_catalogues_before is not None
    result = ctx.resolve(OverviewPipelineProjection)
    assert isinstance(result, OverviewPipelineProjection)
    assert result.profile_id == ctx.profile_id
    assert result.period == ctx.payload.period
    assert result.output_language is ctx.payload.output_language
    assert isinstance(result.report, PipelineHealthSnapshot)
    assert result.report.profile_id == ctx.profile_id
    assert result.report.period == ctx.payload.period
    assert result.report.ledger.total_count == len(ctx.overview_catalogues_before[0].transactions)
    overview_bundle_after = build_verification_repository_bundle(str(ctx.profile_id), operation=ctx.operation)
    assert (
        overview_bundle_after.transaction.load(),
        overview_bundle_after.work_unit.load(),
        overview_bundle_after.calculation.load(operation=ctx.operation),
        overview_bundle_after.filing.load(),
        overview_bundle_after.verification.load(operation=ctx.operation),
    ) == ctx.overview_catalogues_before


def assert_workflow_resume_outcome(ctx: ExecutorOutcome) -> None:
    """Check the WORKFLOW_RESUME_OPERATION_DEFINITION_ID public result and effects."""
    assert isinstance(ctx.payload, WorkflowResumeRequest)
    assert ctx.resume_revision_catalogue_before is not None
    result = ctx.resolve(WorkflowResumeProjection)
    assert isinstance(result, WorkflowResumeProjection)
    assert result.profile_id == ctx.profile_id
    assert isinstance(result.outcome, WorkflowResumeSuccess)
    assert result.outcome.address.source == "calculation_revision_id"
    assert result.outcome.address.calculation_revision_id == ctx.payload.calculation_revision_id
    assert result.outcome.address.run_id == "c" * 16
    assert result.outcome.obligation.period == result.outcome.address.period
    assert result.outcome.aborted_reason is WorkflowAbortReason.SITE_UNAVAILABLE
    runs = WorkflowRunRepository().list()
    assert tuple(item.run_id for item in runs) == ("c" * 16,)
    assert CalculationRevisionCatalogueRepository().load(operation=ctx.operation) == (
        ctx.resume_revision_catalogue_before
    )


_STATEFUL_ASSERTIONS: tuple[tuple[str, Callable[[ExecutorOutcome], None]], ...] = (
    ("attachment_case", assert_attachment_effects),
    ("lifecycle_case", assert_lifecycle_effects),
    ("rule_case", assert_rule_effects),
    ("recipient_case", assert_recipient_effects),
    ("evidence_case", assert_evidence_effects),
    ("prorrata_case", assert_prorrata_effects),
    ("withholding_seed", assert_withholding_effects),
    ("asset_repository", assert_asset_effects),
    ("bienes_before", assert_bienes_effects),
    ("inventory_repository", assert_inventory_effects),
)

_DEFINITION_ASSERTIONS: dict[str, Callable[[ExecutorOutcome], None]] = {
    **LEDGER_OUTCOME_ASSERTIONS,
    **MODELO_OUTCOME_ASSERTIONS,
    "user-profile.recovery.status": assert_user_profile_recovery_status_outcome,
    "auth.credential.save": assert_auth_credential_save_outcome,
    WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID: assert_workflow_run_read_outcome,
    AUTH_READ_OPERATION_DEFINITION_ID: assert_auth_read_outcome,
    WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID: assert_workflow_run_list_outcome,
    "overview.pipeline": assert_overview_pipeline_outcome,
    WORKFLOW_RESUME_OPERATION_DEFINITION_ID: assert_workflow_resume_outcome,
    **dict.fromkeys(OVERVIEW_READ_DEFINITION_IDS.values(), assert_overview_read_outcome),
}


def _assert_registered_executor_conformance_outcome(
    asset_before: Any,
    asset_repository: Any,
    attachment_case: Any,
    bienes_before: Any,
    bulk_classify_before: Any,
    case: RegisteredExecutorConformanceCase,
    cleanup: OperationRuntimeCloseWitness,
    certificate_state_before: Any,
    definition_id: str,
    definition: OperationDefinition,
    driver: _ExecutionDriver,
    evidence_case: Any,
    family_preparation: Any,
    followup_case: Any,
    inventory_before: Any,
    inventory_repository: Any,
    invoice_catalogue_before: Any,
    iva_history_before: Any,
    lifecycle_case: Any,
    observed: OperationObservationSuccessV1,
    operation: PinnedAuthorityOperation,
    overview_catalogues_before: Any,
    payload: Any,
    profile_id: UUID,
    projection_history_case: Any,
    prorrata_before: Any,
    prorrata_case: Any,
    query_case: Any,
    ratios_before: Any,
    recipient_case: Any,
    registry: OperationRegistry,
    resume_revision_catalogue_before: Any,
    review_case: Any,
    rule_case: Any,
    submitted: OperationSubmission,
    tmp_path: Path,
    withholding_seed: Any,
) -> None:
    """Check the executed operation's public outcome and persisted effects."""
    phase_codes = tuple(
        event.phase_code for event in observed.event_page.events if isinstance(event, OperationPublicPhaseEventV1)
    )
    if case.expected_phase_codes is None:
        assert set(phase_codes) & set(definition.phase_codes)
    else:
        assert phase_codes == case.expected_phase_codes
    if case.definition_id == "user-profile.censo-review":
        assert observed.projection.lifecycle is OperationLifecycle.WAITING_FOR_INTERACTION
        assert isinstance(observed.projection.pending_interaction, OperationReviewAvailableInteractionV1)
        assert observed.projection.execution_deadline_at is not None
        assert cleanup.closed is True
        observed = asyncio.run(driver.apply_review(submitted, observed))
    assert observed.projection.lifecycle is OperationLifecycle.TERMINAL
    assert observed.projection.terminal_condition is case.expected_terminal, case.definition_id
    assert observed.projection.effect is case.expected_effect, case.definition_id
    assert observed.projection.refusal_ref == case.expected_refusal_ref, (
        case.definition_id,
        case.expected_refusal_ref,
        observed.projection.refusal_ref,
    )
    _judge_family_outcome(
        family_preparation,
        driver=driver,
        registry=registry,
        profile_id=profile_id,
        operation_id=submitted.receipt.operation_id,
        observed=observed,
    )
    ctx = ExecutorOutcome(
        asset_before=asset_before,
        asset_repository=asset_repository,
        attachment_case=attachment_case,
        bienes_before=bienes_before,
        bulk_classify_before=bulk_classify_before,
        case=case,
        cleanup=cleanup,
        certificate_state_before=certificate_state_before,
        definition_id=definition_id,
        definition=definition,
        driver=driver,
        evidence_case=evidence_case,
        family_preparation=family_preparation,
        followup_case=followup_case,
        inventory_before=inventory_before,
        inventory_repository=inventory_repository,
        invoice_catalogue_before=invoice_catalogue_before,
        iva_history_before=iva_history_before,
        lifecycle_case=lifecycle_case,
        observed=observed,
        operation=operation,
        overview_catalogues_before=overview_catalogues_before,
        payload=payload,
        profile_id=profile_id,
        projection_history_case=projection_history_case,
        prorrata_before=prorrata_before,
        prorrata_case=prorrata_case,
        query_case=query_case,
        ratios_before=ratios_before,
        recipient_case=recipient_case,
        registry=registry,
        resume_revision_catalogue_before=resume_revision_catalogue_before,
        review_case=review_case,
        rule_case=rule_case,
        submitted=submitted,
        tmp_path=tmp_path,
        withholding_seed=withholding_seed,
    )
    assert_expected_reads(ctx)
    for attribute, assertion in _STATEFUL_ASSERTIONS:
        if getattr(ctx, attribute) is not None:
            assertion(ctx)
    if case.expected_terminal is OperationTerminalCondition.FAILED:
        assert observed.projection.diagnostic_ref is not None
    if definition_id.startswith(("auth.certificate.", "ledger.ratios.")):
        assert_certificate_or_ratios_outcome(ctx)
    assertion = _DEFINITION_ASSERTIONS.get(definition_id)
    if assertion is not None:
        assertion(ctx)
    assert isinstance(observed.projection.pending_interaction, OperationNoPendingInteractionV1)
    asyncio.run(
        driver.review_not_pending(
            operation_id=submitted.receipt.operation_id,
            revision=observed.projection.revision,
            registry=registry,
        )
    )
