"""Assert public settlement, result projections, and operation-specific effects."""

from __future__ import annotations

import asyncio
import csv
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID
from zipfile import ZipFile

import pytest

from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
from ...adapters.persistence.profile.counterparty_establishment import build_counterparty_establishment_repository
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.own_accounts import OwnAccountRepository
from ...adapters.persistence.profile.tests.cross_period_seeding import SEEDED_SOURCE_TAX_ID
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...application.actividad_asset.activity_asset_projections import (
    ActivityAssetClaimProjection,
    ActivityAssetCorrectProjection,
    ActivityAssetCreateProjection,
    ActivityAssetFilingHandoffProjection,
    ActivityAssetForecastProjection,
    ActivityAssetInspectProjection,
)
from ...application.aggregation.service import aggregate_per_modelo
from ...application.auth.auth_read_contracts import (
    AUTH_READ_OPERATION_DEFINITION_ID,
    AuthReadProjection,
    AuthReadRequest,
)
from ...application.auth.certificate_source_operations import list_operator_certificate_sources
from ...application.bienes_inversion.registered_result_contracts import (
    BienesInversionDeclareProjection,
    BienesInversionListProjection,
    BienInversionRecordProjection,
)
from ...application.bucket_event_repository import bucket_event_history_repository
from ...application.inventory.registered_projections import (
    InventoryClosingAuthorityOperationProjection,
    InventoryCreateProjection,
    InventoryLedgerProjection,
    InventoryListProjection,
    InventoryMovementAddProjection,
    InventoryValuationOperationProjection,
)
from ...application.invoices.catalogue_add_contracts import InvoiceAddResult
from ...application.invoices.catalogue_read_operation import (
    INVOICE_LIST_OPERATION_DEFINITION_ID,
    INVOICE_VIEW_OPERATION_DEFINITION_ID,
    InvoiceListProjection,
    InvoiceListRequest,
    InvoiceViewProjection,
    InvoiceViewRequest,
    InvoiceViewSuccess,
)
from ...application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from ...application.invoices.catalogue_remove_operation import (
    INVOICE_REMOVE_OPERATION_DEFINITION_ID,
    InvoiceRemoveRequest,
    InvoiceRemoveResult,
)
from ...application.invoices.catalogue_update_operation import (
    INVOICE_UPDATE_OPERATION_DEFINITION_ID,
    InvoiceUpdateRequest,
    InvoiceUpdateResult,
)
from ...application.ledger.allocate_operation import LedgerAllocateOperationResult, LedgerAllocateRequest
from ...application.ledger.attachment_mutation_operation import LedgerAttachmentOperationResult
from ...application.ledger.bulk_classify_operation import (
    LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
    LedgerBulkClassifyProjection,
    LedgerBulkClassifyRequest,
)
from ...application.ledger.check_operation import LedgerCheckProjection, LedgerCheckRequest
from ...application.ledger.classify_requests import LedgerClassifyRequest
from ...application.ledger.classify_result_contracts import LedgerClassifyOperationResult
from ...application.ledger.counterparty_operation import LedgerCounterpartyRequest, LedgerCounterpartyResult
from ...application.ledger.evidence_add_operation import LedgerEvidenceAddProjection, LedgerEvidenceAddRequest
from ...application.ledger.evidence_mutation_operation import (
    LedgerEvidenceRemoveProjection,
    LedgerEvidenceRemoveRequest,
    LedgerEvidenceUpdateProjection,
    LedgerEvidenceUpdateRequest,
)
from ...application.ledger.evidence_read_operation import (
    LedgerEvidenceListProjection,
    LedgerEvidenceListRequest,
    LedgerEvidenceViewProjection,
    LedgerEvidenceViewRequest,
    LedgerEvidenceViewSuccess,
)
from ...application.ledger.history_operation import LedgerHistoryProjection, LedgerHistoryRequest
from ...application.ledger.import_operation import LedgerImportRequest, LedgerImportResultProjection
from ...application.ledger.invoice_evidence_confirm_operation import LedgerEvidenceConfirmProjection
from ...application.ledger.ledger_add_contracts import LedgerAddOperationResult, LedgerAddRequest
from ...application.ledger.lifecycle_contracts import LedgerLifecycleOperationResult
from ...application.ledger.list_operation import LedgerListProjection, LedgerListRequest
from ...application.ledger.merge_operation import LedgerMergeOperationResult, LedgerMergeRequest
from ...application.ledger.models import ManualLedgerTransactionPatch
from ...application.ledger.own_account_operation import LedgerOwnAccountRequest, LedgerOwnAccountResult
from ...application.ledger.participation_operation import LedgerParticipationRequest
from ...application.ledger.participation_rebuild_operation import LedgerParticipationRebuildRequest
from ...application.ledger.preflight import LedgerPreflightIssueReason
from ...application.ledger.preflight_operation import LedgerPreflightProjection, LedgerPreflightRequest
from ...application.ledger.remove_operation import LedgerRemoveOperationResult, LedgerRemoveRequest
from ...application.ledger.reset_operation import LedgerResetOperationResult, LedgerResetRequest
from ...application.ledger.review_operation import LedgerReviewProjection
from ...application.ledger.rule_contracts import LedgerRuleAddProjection
from ...application.ledger.split_operation import LedgerSplitOperationResult, LedgerSplitRequest
from ...application.ledger.status_operation import LedgerStatusProjection, LedgerStatusRequest
from ...application.ledger.update_contracts import LedgerUpdateOperationResult, LedgerUpdateRequest
from ...application.ledger.usage_ratio_repository import load_usage_ratio_profile
from ...application.ledger.view_operation import LedgerViewProjection, LedgerViewRequest
from ...application.live.iva_wallet_history_operation import (
    IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID,
    IvaWalletHistoryProjection,
    IvaWalletHistoryRequest,
)
from ...application.modelo.aggregate_projection import ModeloAggregateProjection
from ...application.modelo.calculation_report_verification_operation import (
    MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID,
    ModeloCalculationReportVerificationProjection,
)
from ...application.modelo.dependency_operation import (
    MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,
    ModeloDependencyProjection,
    ModeloDependencyRequest,
)
from ...application.modelo.history_operation import ModeloWorkHistoryProjection, ModeloWorkHistoryRequest
from ...application.modelo.invoice_withholding_capture_contracts import ModeloInvoiceWithholdingCaptureProjection
from ...application.modelo.iva_wallet_balance_operation import ModeloIvaWalletBalanceProjection
from ...application.modelo.iva_wallet_correction_operation import (
    MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
    ModeloIvaWalletCorrectionProjection,
)
from ...application.modelo.iva_wallet_override_operation import ModeloIvaWalletOverrideProjection
from ...application.modelo.iva_wallet_seed_operation import ModeloIvaWalletSeedProjection
from ...application.modelo.m303_attestation_operation import (
    ModeloWorkM303AttestationPublicResultV2,
    ModeloWorkM303AttestationRequest,
)
from ...application.modelo.mcp_query_contracts import (
    ModeloBindingsResolveTypedProjection,
    ModeloReadinessSummaryProjection,
)
from ...application.modelo.query_read_contracts import (
    ModeloBindingsListProjection,
    ModeloBindingsResolveProjection,
    ModeloReadinessProjection,
    ModeloRequiresProjection,
)
from ...application.modelo.review_package_operation import (
    ModeloReviewPackageBuildPublicResultV1,
    ModeloReviewPackageBuildRequest,
)
from ...application.modelo.review_package_recipient_operations import ReviewPackageRecipientAddProjection
from ...application.modelo.revision_inventory_operation import ModeloWorkRevisionsProjection, ModeloWorkRevisionsRequest
from ...application.modelo.revision_snapshot_operation import ModeloWorkRevisionSnapshotRequest
from ...application.modelo.taxation_comparison_operation import (
    MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
    ModeloTaxationComparisonRequest,
)
from ...application.modelo.wizard_attempt_operation import (
    ModeloWorkWizardAttemptCalculated,
    ModeloWorkWizardAttemptProjection,
    ModeloWorkWizardAttemptRequest,
)
from ...application.modelo.wizard_context_operation import (
    ModeloWorkWizardContextProjection,
    ModeloWorkWizardContextRequest,
)
from ...application.modelo.work_create_operation import (
    ModeloWorkCreateProjection,
    ModeloWorkCreateRefusal,
    ModeloWorkCreateRequest,
)
from ...application.modelo.work_inventory_operation import ModeloWorkListProjection, ModeloWorkListRequest
from ...application.modelo.work_review_contracts import ModeloWorkReviewProjection, ModeloWorkReviewRequest
from ...application.operations.capabilities import OperationRequestStoragePolicy
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
from ...application.review.filter import LedgerReviewStatus
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
from ...core.invoice_link import LinkInconsistencyDirection
from ...core.iva_compensation_provenance import IvaCompensationStateProvenance
from ...core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.period import Period
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_location
from ...domain.attachments.m303_filing_evidence import (
    M303Exonerado390ApplicabilityAssertion,
    parse_m303_exonerado_390_applicability_attestation,
)
from ...domain.buckets.event import BucketEventType
from ...domain.categories.spending_category_catalogue import require_spending_category
from ...domain.invoices.models import InvoiceCatalogue
from ...domain.invoices.service import LinkInconsistency
from ...domain.iva.schema import IvaCategory
from ...domain.modelos.work_unit import WorkUnitState
from ...domain.transactions.enums import BusinessClassification
from ...domain.transactions.models import TransactionCatalogue
from ..adapter_composition import (
    build_bienes_inversion_repository,
    build_ledger_evidence_ports,
    build_prorrata_register_repository,
    build_verification_repository_bundle,
)
from . import modelo_operation_test_support
from .activity_asset_operation_test_support import assert_activity_asset_conformance_result
from .aggregate_operation_test_support import aggregate_conformance_command
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
    _CloseWitness,
    _ExecutionDriver,
    _judge_family_outcome,
    _resolve_result_projection,
)
from .registered_executor_result_assertions import (
    _assert_calculation_report_verification_projection,
    _assert_canonical_bulk_classification_update,
    _assert_ledger_participation_lookup_result,
    _assert_ledger_participation_rebuild_result,
    _assert_ledger_review_projection,
    _assert_ledger_track_result,
)
from .registered_executor_scenario_constants import (
    _CREDENTIAL_INPUT,
    _LEDGER_LIST_PRIVATE_FILTER_SENTINEL,
    _OWN_ACCOUNT_SYNTHETIC_IBAN,
)


def _assert_registered_executor_conformance_outcome(
    asset_before: Any,
    asset_repository: Any,
    attachment_case: Any,
    bienes_before: Any,
    bulk_classify_before: Any,
    case: RegisteredExecutorConformanceCase,
    cleanup: _CloseWitness,
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
    assert observed.projection.refusal_ref == case.expected_refusal_ref, case.definition_id
    _judge_family_outcome(
        family_preparation,
        driver=driver,
        registry=registry,
        profile_id=profile_id,
        operation_id=submitted.receipt.operation_id,
        observed=observed,
    )
    for expected_read in (
        projection_history_case.expected_projection if projection_history_case is not None else None,
        query_case.expected_projection if query_case is not None else None,
        review_case.expected_read if review_case is not None else None,
        followup_case.expected_read if followup_case is not None else None,
    ):
        if expected_read is not None:
            actual_read = _resolve_result_projection(
                driver,
                registry,
                definition_id=case.definition_id,
                operation_id=submitted.receipt.operation_id,
                terminal_revision=observed.projection.revision,
                projection_type=type(expected_read),
            )
            if query_case is not None:
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
                assert actual_read.authority_generation == operation.generation.logical_generation
            actual_fields = actual_read.model_dump(mode="json")
            expected_fields = expected_read.model_dump(mode="json")
            assert actual_read == expected_read, {
                key: (actual_fields[key], expected_fields[key])
                for key in actual_fields
                if actual_fields[key] != expected_fields[key]
            }
    if attachment_case is not None:
        attachment_result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerAttachmentOperationResult,
        )
        assert isinstance(attachment_result, LedgerAttachmentOperationResult)
        assert attachment_result.outcome == "updated"
        assert attachment_result.result is not None
        assert_ledger_attachment_operation_conformance_result(
            attachment_case, attachment_result.result, operation_run_id=submitted.receipt.operation_id
        )
    if lifecycle_case is not None:
        lifecycle_result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerLifecycleOperationResult,
        )
        assert isinstance(lifecycle_result, LedgerLifecycleOperationResult)
        assert lifecycle_result.outcome == "updated"
        assert lifecycle_result.result is not None
        assert_ledger_lifecycle_operation_conformance_result(
            lifecycle_case, lifecycle_result.result, operation_run_id=submitted.receipt.operation_id
        )
    if rule_case is not None:
        rule_result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=(
                type(rule_case.expected_projection)
                if rule_case.expected_projection is not None
                else LedgerRuleAddProjection
            ),
        )
        assert_ledger_rule_operation_conformance_result(
            rule_case, rule_result, operation_run_id=submitted.receipt.operation_id
        )
    if recipient_case is not None:
        recipient_result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=(
                type(recipient_case.expected_projection)
                if recipient_case.expected_projection is not None
                else ReviewPackageRecipientAddProjection
            ),
        )
        assert_recipient_operation_conformance_result(
            recipient_case, recipient_result, profile_id=profile_id, operation_id=submitted.receipt.operation_id
        )
    if evidence_case is not None:
        result_type = (
            type(evidence_case.expected_read)
            if evidence_case.expected_read is not None
            else LedgerEvidenceConfirmProjection
        )
        evidence_result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=result_type,
        )
        if evidence_case.expected_read is not None:
            assert evidence_result == evidence_case.expected_read
            assert InvoiceCatalogueRepository(bucket_id=str(profile_id)).load().invoices == {}
        else:
            assert isinstance(evidence_result, LedgerEvidenceConfirmProjection)
            assert evidence_result.profile_id == profile_id
            assert_invoice_evidence_confirmation_persisted(
                evidence_case, evidence_result, operation_id=submitted.receipt.operation_id
            )
    if prorrata_case is not None:
        assert prorrata_before is not None
        prorrata_after = read_prorrata_operation_conformance_register(
            profile_id, repository_factory=build_prorrata_register_repository, operation=operation
        )
        assert prorrata_after == prorrata_case.expected_register
        prorrata_result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=type(prorrata_case.expected_projection),
        )
        assert prorrata_result == prorrata_case.expected_projection
        assert isinstance(prorrata_result, (ProrrataListProjection, ProrrataMutationProjection))
        assert prorrata_result.profile_id == profile_id
        assert prorrata_result.count == prorrata_case.expected_count
        assert observed.projection.effect is prorrata_case.expected_effect
        if prorrata_case.operation_id == "list":
            assert prorrata_after == prorrata_before
            assert prorrata_result.count == len(prorrata_after.entries)
        else:
            assert prorrata_after != prorrata_before
            assert prorrata_result.count == (
                len(prorrata_after.sector_definitions)
                if prorrata_case.operation_id == "declare_sector"
                else len(prorrata_after.entries)
            )
    if withholding_seed is not None:
        withholding_result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloInvoiceWithholdingCaptureProjection,
        )
        assert isinstance(withholding_result, ModeloInvoiceWithholdingCaptureProjection)
        assert withholding_result.profile_id == profile_id
        assert withholding_result.outcome == "captured"
        assert withholding_result.modelo == withholding_seed.request.command.modelo
        assert withholding_result.period.to_period() == withholding_seed.period
        withholding_after = read_invoice_withholding_conformance_case(profile_id, withholding_seed)
        assert_invoice_withholding_conformance_write(
            withholding_after, withholding_seed, profile_id=profile_id, operation=operation
        )
        assert withholding_result.observation_count == len(withholding_after.observations)
        assert withholding_result.withholding_window is not None
        assert withholding_result.withholding_window.generation == withholding_after.generation
    if asset_repository is not None:
        assert asset_before is not None
        asset_projection_type = {
            "ledger.actividad-asset.create": ActivityAssetCreateProjection,
            "ledger.actividad-asset.inspect": ActivityAssetInspectProjection,
            "ledger.actividad-asset.correct": ActivityAssetCorrectProjection,
            "ledger.actividad-asset.forecast": ActivityAssetForecastProjection,
            "ledger.actividad-asset.claim": ActivityAssetClaimProjection,
            "ledger.actividad-asset.filing-handoff": ActivityAssetFilingHandoffProjection,
        }[case.definition_id]
        asset_projection = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=asset_projection_type,
        )
        assert_activity_asset_conformance_result(
            definition_id=case.definition_id,
            payload=payload,
            projection=asset_projection,
            before=asset_before,
            after=asset_repository.load(),
            operation=operation,
        )
    if case.definition_id == "modelo.aggregate":
        aggregate_result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloAggregateProjection,
        )
        assert isinstance(aggregate_result, ModeloAggregateProjection)
        canonical_aggregate = aggregate_per_modelo(
            aggregate_conformance_command(operation=operation), operation=operation
        )
        assert canonical_aggregate.log_fields.observation_count == 2
        assert canonical_aggregate.log_fields.result_row_count == 1
        assert aggregate_result == ModeloAggregateProjection(
            outcome="aggregated",
            profile_id=profile_id,
            modelo=str(canonical_aggregate.modelo),
            period=PublicPeriod.from_period(canonical_aggregate.period),
            provider=canonical_aggregate.provider,
            observation_count=canonical_aggregate.log_fields.observation_count,
            source_kinds=canonical_aggregate.source_kinds,
            result_row_count=canonical_aggregate.log_fields.result_row_count,
            clave_breakdown=(),
            absent_source_families=(),
            withholding_window=None,
            refusal_reason=None,
        )
    if bienes_before is not None:
        bienes_after = read_bienes_inversion_operation_conformance_register(
            profile_id, repository_factory=build_bienes_inversion_repository
        )
        expected_record = bienes_inversion_conformance_record(case.definition_id, operation=operation)
        assert bienes_after.records == (expected_record,)
        bienes_projection_type = (
            BienesInversionListProjection if case.definition_id.endswith(".list") else BienesInversionDeclareProjection
        )
        bienes_result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=bienes_projection_type,
        )
        assert isinstance(bienes_result, BienesInversionListProjection | BienesInversionDeclareProjection)
        assert bienes_result.profile_id == profile_id
        expected_projection = BienInversionRecordProjection.from_record(expected_record)
        if isinstance(bienes_result, BienesInversionListProjection):
            assert bienes_after == bienes_before
            assert bienes_result.rows == (expected_projection,)
        else:
            assert bienes_before.records == ()
            assert bienes_result.outcome == "declared"
            assert bienes_result.refusal is None
            assert bienes_result.count == 1
            assert bienes_result.record == expected_projection
    if inventory_repository is not None:
        projection_type = {
            "ledger.inventory.list": InventoryListProjection,
            "ledger.inventory.create": InventoryCreateProjection,
            "ledger.inventory.movement.add": InventoryMovementAddProjection,
            "ledger.inventory.valuation.preview": InventoryValuationOperationProjection,
            "ledger.inventory.closing-authority.record": InventoryClosingAuthorityOperationProjection,
        }[case.definition_id]
        inventory_result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=projection_type,
        )
        inventory_after = inventory_repository.load()
        assert len(inventory_after.ledgers) == 1
        ledger = inventory_after.ledgers[0]
        if isinstance(inventory_result, InventoryListProjection):
            assert inventory_result.profile_id == profile_id
            assert len(inventory_result.rows) == 1
            assert inventory_result.rows[0].actividad_id == ledger.actividad_id
            assert inventory_after == inventory_before
        elif isinstance(inventory_result, InventoryCreateProjection | InventoryMovementAddProjection):
            assert inventory_result.profile_id == profile_id and inventory_result.ledger is not None
            assert inventory_result.ledger == InventoryLedgerProjection.from_ledger(
                ledger, bucket_event_ids=inventory_result.bucket_event_ids
            )
            expected_movements = 1 if isinstance(inventory_result, InventoryMovementAddProjection) else 0
            assert len(ledger.period_movements) == expected_movements
            events = bucket_event_history_repository(bucket_id=str(profile_id)).load().events
            assert all(event_id in events for event_id in inventory_result.bucket_event_ids)
        elif isinstance(inventory_result, InventoryValuationOperationProjection):
            assert inventory_result.preview is not None and inventory_result.preview.profile_id == profile_id
            assert Decimal(inventory_result.preview.derived_closing_value.decimal) == Decimal("100.00")
            assert inventory_after == inventory_before
            events = bucket_event_history_repository(bucket_id=str(profile_id)).load().events
            assert all(event_id in events for event_id in inventory_result.preview.bucket_event_ids)
        else:
            assert isinstance(inventory_result, InventoryClosingAuthorityOperationProjection)
            assert inventory_result.record is not None and inventory_result.record.profile_id == profile_id
            assert ledger.closing_authority_record is not None
            assert inventory_result.record.authority_record_fingerprint == ledger.closing_authority_record.fingerprint
            assert inventory_result.record.changed is True
    if case.definition_id == "user-profile.recovery.status":
        recovery = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=RecoveryStatusProjection,
        )
        assert isinstance(recovery, RecoveryStatusProjection)
        assert recovery.profile_id == profile_id
        assert recovery.enrolled is True
        assert recovery.enrolled == profile_recovery_status(profile_id=profile_id).enrolled
    if case.definition_id.startswith(("auth.certificate.", "ledger.ratios.")):
        contract = registry.lookup_public_contract(case.definition_id)
        assert contract.result_schema is not None
        result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=registry.lookup_public_schema_binding(contract.result_schema).model_type,
        )
        document = result.model_dump(mode="json")
        assert document["profile_id"] == str(profile_id)
        assert _CREDENTIAL_INPUT not in result.model_dump_json()
        if case.definition_id.startswith("auth.certificate.source."):
            sources = list_operator_certificate_sources()
            if case.definition_id == "auth.certificate.source.remove":
                assert sources.sources == ()
                assert document["result"]["removed"] is True
            elif case.definition_id == "auth.certificate.source.list":
                assert document["result"] == sources.model_dump(mode="json")
            elif case.definition_id == "auth.certificate.source.check":
                assert document["result"]["entries"][0]["result"] == "file_missing"
                assert document["result"]["has_warnings"] is False
            else:
                assert len(sources.sources) == 1
                assert sources.sources[0].name == "supervisor-certificate"
                assert sources.sources[0].certificate_path == str(
                    tmp_path / case.definition_id / "absent-certificate.p12"
                )
                if case.definition_id == "auth.certificate.source.select":
                    assert sources.active_source == "supervisor-certificate"
            if certificate_state_before is not None:
                assert workflow_state_repository().load() == certificate_state_before
        elif case.definition_id.startswith("auth.certificate.secret."):
            stored = build_certificate_secret_backend(bucket_id=str(profile_id), settings=load_settings()).get(
                "supervisor-certificate"
            )
            if case.definition_id == "auth.certificate.secret.set":
                assert stored is not None and stored.get_secret_value() == _CREDENTIAL_INPUT
            else:
                assert stored is None
                assert document["result"]["removed"] is True
        else:
            ratios_after = load_usage_ratio_profile(bucket_id=str(profile_id), operation=operation)
            events_after = bucket_event_history_repository(bucket_id=str(profile_id)).load()
            category = require_spending_category("vehiculo_combustible", authority=operation)
            if case.definition_id == "ledger.ratios.set":
                assert ratios_after.ratios[category] == Decimal("0.5")
                assert any(
                    event.event_type is BucketEventType.LEDGER_RATIOS_SET for event in events_after.events.values()
                )
            elif case.definition_id == "ledger.ratios.unset":
                assert category not in ratios_after.ratios
                assert any(
                    event.event_type is BucketEventType.LEDGER_RATIOS_UNSET for event in events_after.events.values()
                )
            else:
                assert (ratios_after, events_after) == ratios_before
    if case.expected_terminal is OperationTerminalCondition.FAILED:
        assert observed.projection.diagnostic_ref is not None
    if case.definition_id == "modelo.work.create":
        assert isinstance(payload, ModeloWorkCreateRequest)
        assert observed.projection.result_ref is None
        result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloWorkCreateProjection,
        )
        assert isinstance(result, ModeloWorkCreateProjection)
        assert result.profile_id == profile_id
        assert result.period == payload.period
        assert isinstance(result.outcome, ModeloWorkCreateRefusal)
        assert result.outcome.modelo == payload.modelo == "202"
        assert result.outcome.reason
        assert WorkUnitCatalogueRepository().load().work_units == {}
    if case.definition_id == WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID:
        assert isinstance(payload, WorkflowRunReadRequest)
        result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=WorkflowRunReadProjection,
        )
        assert isinstance(result, WorkflowRunReadProjection)
        assert result.profile_id == profile_id
        assert result.expected_period == payload.expected_period
        assert result.run.run_id == payload.run_id
        assert result.run.obligation is not None
        assert result.run.obligation.period == payload.expected_period
    if case.definition_id == AUTH_READ_OPERATION_DEFINITION_ID:
        assert isinstance(payload, AuthReadRequest)
        result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=AuthReadProjection,
        )
        assert isinstance(result, AuthReadProjection)
        assert result.profile_id == profile_id
        assert result.kind == payload.kind == "diagnostics_list"
        assert result.diagnostics_rows is not None
    if case.definition_id in OVERVIEW_READ_DEFINITION_IDS.values():
        assert isinstance(payload, OverviewReadRequest)
        result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=OverviewReadProjection,
        )
        assert isinstance(result, OverviewReadProjection)
        assert result.profile_id == profile_id
        assert result.request == payload
        assert result.payload.kind == payload.kind.value
        match result.payload:
            case OverviewStatusRead() if payload.kind is OverviewReadKind.STATUS:
                if payload.period is None:
                    assert result.payload.report is not None
                    assert result.payload.period_report is None
                    period_payload = OverviewReadRequest(
                        profile_id=profile_id,
                        kind=OverviewReadKind.STATUS,
                        output_language=OutputLanguage.ES,
                        period=PublicPeriod.from_period(Period.from_year_and_code(2025, "1T")),
                    )
                    _, period_observed = asyncio.run(
                        driver.run(
                            definition_id=case.definition_id,
                            subject_ref=profile_operation_subject(str(profile_id)),
                            payload=period_payload,
                        )
                    )
                    assert period_observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    assert period_observed.projection.effect is OperationEffect.NONE
                    period_result = _resolve_result_projection(
                        driver,
                        registry,
                        definition_id=case.definition_id,
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
            case OverviewCalendarRead() if payload.kind is OverviewReadKind.CALENDAR:
                assert result.payload.calendar is not None
                assert result.payload.calendar.range.from_date == payload.from_date
                assert result.payload.calendar.range.to_date == payload.to_date
            case OverviewAgendaRead() if payload.kind is OverviewReadKind.AGENDA:
                assert result.payload.agenda.as_of == payload.as_of
                assert result.payload.agenda.horizon_days == payload.horizon_days
            case OverviewBacklogRead() if payload.kind is OverviewReadKind.BACKLOG:
                assert result.payload.backlog.range.from_date == payload.from_date
                assert result.payload.backlog.range.to_date == payload.to_date
            case OverviewExplainRead() if payload.kind is OverviewReadKind.EXPLAIN:
                assert result.payload.explanation.modelo == payload.modelo
                assert result.payload.explanation.year == payload.year
            case OverviewPrepareRead() if payload.kind is OverviewReadKind.PREPARE:
                assert payload.period is not None
                assert result.payload.preparation.modelo == payload.modelo
                assert result.payload.preparation.filing_year == payload.period.filing_year
                assert result.payload.preparation.period == payload.period.code
            case _:
                pytest.fail(f"unexpected overview result kind for {case.definition_id}")
    if case.definition_id == WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID:
        assert isinstance(payload, WorkflowRunListRequest)
        result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=WorkflowRunListProjection,
        )
        assert isinstance(result, WorkflowRunListProjection)
        assert result.profile_id == profile_id
        assert tuple(run.run_id for run in result.runs) == ("b" * 16, "a" * 16)
        assert all(run.obligation is not None for run in result.runs)
    if case.definition_id == "overview.pipeline":
        assert isinstance(payload, OverviewPipelineRequest)
        assert overview_catalogues_before is not None
        result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=OverviewPipelineProjection,
        )
        assert isinstance(result, OverviewPipelineProjection)
        assert result.profile_id == profile_id
        assert result.period == payload.period
        assert result.output_language is payload.output_language
        assert isinstance(result.report, PipelineHealthSnapshot)
        assert result.report.profile_id == profile_id
        assert result.report.period == payload.period
        assert result.report.ledger.total_count == len(overview_catalogues_before[0].transactions)
        overview_bundle_after = build_verification_repository_bundle(str(profile_id), operation=operation)
        assert (
            overview_bundle_after.transaction.load(),
            overview_bundle_after.work_unit.load(),
            overview_bundle_after.calculation.load(operation=operation),
            overview_bundle_after.filing.load(),
            overview_bundle_after.verification.load(operation=operation),
        ) == overview_catalogues_before
    if case.definition_id == WORKFLOW_RESUME_OPERATION_DEFINITION_ID:
        assert isinstance(payload, WorkflowResumeRequest)
        assert resume_revision_catalogue_before is not None
        result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=WorkflowResumeProjection,
        )
        assert isinstance(result, WorkflowResumeProjection)
        assert result.profile_id == profile_id
        assert isinstance(result.outcome, WorkflowResumeSuccess)
        assert result.outcome.address.source == "calculation_revision_id"
        assert result.outcome.address.calculation_revision_id == payload.calculation_revision_id
        assert result.outcome.address.run_id == "c" * 16
        assert result.outcome.obligation.period == result.outcome.address.period
        assert result.outcome.aborted_reason is WorkflowAbortReason.SITE_UNAVAILABLE
        runs = WorkflowRunRepository().list()
        assert tuple(item.run_id for item in runs) == ("c" * 16,)
        assert CalculationRevisionCatalogueRepository().load(operation=operation) == (resume_revision_catalogue_before)
    if case.definition_id == MODELO_DEPENDENCY_OPERATION_DEFINITION_ID:
        assert isinstance(payload, ModeloDependencyRequest)
        result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloDependencyProjection,
        )
        assert isinstance(result, ModeloDependencyProjection)
        assert result.profile_id == profile_id
        assert result.snapshot.filing_year == payload.filing_year
        assert result.snapshot.modelo_filter == payload.modelo
        assert result.snapshot.period_filter == payload.period
        assert result.snapshot.clean_state is not None
        assert result.snapshot.clean_state.target_modelo == payload.modelo
        assert result.snapshot.clean_state.target_period == payload.period
        assert all(item.target_filing_year == payload.filing_year for item in result.snapshot.items)
    if case.definition_id == "modelo.work.revision_snapshot":
        assert isinstance(payload, ModeloWorkRevisionSnapshotRequest)
        assert observed.projection.result_ref is not None
        assert observed.projection.result_ref != payload.calculation_revision_id
    if case.definition_id == MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID:
        assert isinstance(payload, ModeloTaxationComparisonRequest)
        assert observed.projection.result_ref is None
        assert WorkUnitCatalogueRepository().load().get(payload.work_unit_id) is not None
    if case.definition_id == "modelo.work.list":
        assert isinstance(payload, ModeloWorkListRequest)
        inventory = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloWorkListProjection,
        )
        assert isinstance(inventory, ModeloWorkListProjection)
        assert inventory.profile_id == profile_id
        assert inventory.include_discarded is False
        assert len(inventory.units) == 1
        row = inventory.units[0]
        assert row.bucket_id == str(profile_id)
        assert row.modelo == "130"
        assert row.filing_year == 2025
        assert row.state is WorkUnitState.BORRADOR
    if case.definition_id == "modelo.work.history":
        assert isinstance(payload, ModeloWorkHistoryRequest)
        history = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloWorkHistoryProjection,
        )
        assert isinstance(history, ModeloWorkHistoryProjection)
        assert history.profile_id == profile_id
        assert history.history.bucket_id == str(profile_id)
        assert history.history.work_unit_id == payload.work_unit_id
        assert history.history.events
        assert all(event.bucket_id == profile_id for event in history.history.events)
    if case.definition_id == "modelo.work.review":
        assert isinstance(payload, ModeloWorkReviewRequest)
        review = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloWorkReviewProjection,
        )
        assert isinstance(review, ModeloWorkReviewProjection)
        assert review.profile_id == profile_id
        assert review.review.bucket_id == str(profile_id)
        assert review.review.work_unit_id == payload.work_unit_id
        assert review.review.modelo == modelo_operation_test_support.MODELO
        assert review.review.filing_year == modelo_operation_test_support.MODELO_FILING_YEAR
        assert review.review.period == PublicPeriod.from_period(
            Period.from_year_and_code(
                modelo_operation_test_support.MODELO_FILING_YEAR, modelo_operation_test_support.MODELO_PERIOD
            )
        )
        assert review.review.calculation_revision_id is None
        assert review.review.lifecycle_state is None
        assert review.review.verification_outcome is None
    if case.definition_id == "modelo.work.wizard_context":
        assert isinstance(payload, ModeloWorkWizardContextRequest)
        context = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloWorkWizardContextProjection,
        )
        assert isinstance(context, ModeloWorkWizardContextProjection)
        assert context.profile_id == profile_id
        assert context.unit.work_unit_id == payload.work_unit_id
        assert context.unit.bucket_id == str(profile_id)
        assert context.output_language is OutputLanguage.ES
        assert context.steps
        assert all(step.legal_refs and step.source_refs for step in context.steps)
    if case.definition_id == "modelo.work.wizard_attempt":
        assert isinstance(payload, ModeloWorkWizardAttemptRequest)
        attempt = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloWorkWizardAttemptProjection,
        )
        assert isinstance(attempt, ModeloWorkWizardAttemptProjection)
        assert attempt.profile_id == profile_id
        assert attempt.output_language is OutputLanguage.ES
        assert isinstance(attempt.outcome, ModeloWorkWizardAttemptCalculated)
        calculation_result = attempt.outcome.result
        assert calculation_result.revision_published is True
        assert calculation_result.work_unit_id == payload.calculation.work_unit_id
        assert calculation_result.unit.current_calculation_revision_id == calculation_result.calculation_revision_id
        calculation_catalogue = CalculationRevisionCatalogueRepository().load(operation=operation)
        revision = calculation_catalogue.get(calculation_result.calculation_revision_id)
        assert revision is not None
        assert revision.work_unit_id == payload.calculation.work_unit_id
        assert revision.calculation_revision_id == calculation_result.calculation_revision_id
        unit = WorkUnitCatalogueRepository().load().get(payload.calculation.work_unit_id)
        assert unit is not None
        assert unit.current_calculation_revision_id == revision.calculation_revision_id
    if case.definition_id == "modelo.work.revisions":
        assert isinstance(payload, ModeloWorkRevisionsRequest)
        inventory = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloWorkRevisionsProjection,
        )
        assert isinstance(inventory, ModeloWorkRevisionsProjection)
        stored_revisions = CalculationRevisionCatalogueRepository().load().revisions
        assert inventory.profile_id == profile_id
        assert inventory.work_unit_id_filter is None
        assert {row.calculation_revision_id for row in inventory.revisions} == set(stored_revisions)
        assert len(inventory.revisions) == len(stored_revisions)
    if case.definition_id == MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID:
        verification = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloCalculationReportVerificationProjection,
        )
        _assert_calculation_report_verification_projection(payload, verification, profile_id=profile_id)
    if case.definition_id == "modelo.review_package.build":
        assert isinstance(payload, ModeloReviewPackageBuildRequest)
        result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloReviewPackageBuildPublicResultV1,
        )
        assert isinstance(result, ModeloReviewPackageBuildPublicResultV1)
        package_path = Path(result.output_path)
        assert package_path == Path(payload.output_path)
        assert package_path.is_file()
        expected_revision = CalculationRevisionCatalogueRepository().load().get(payload.calculation_revision_id)
        assert expected_revision is not None
        assert result.manifest.bucket_id == str(profile_id)
        assert result.manifest.work_unit_id == expected_revision.work_unit_id
        assert result.manifest.calculation_revision_id == payload.calculation_revision_id
        assert result.member_count >= 1
        assert result.handoff_required is True
        with ZipFile(package_path) as package:
            assert package.testzip() is None
    if case.definition_id == "modelo.work.m303_attestation":
        assert isinstance(payload, ModeloWorkM303AttestationRequest)
        result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloWorkM303AttestationPublicResultV2,
        )
        assert isinstance(result, ModeloWorkM303AttestationPublicResultV2)
        assert result.profile_id == profile_id
        assert result.work_unit_id is None
        assert result.period == PublicPeriod.from_period(Period.from_year_and_code(2025, "4T"))
        evidence = parse_m303_exonerado_390_applicability_attestation(
            AttachmentStore().read_bytes(result.attachment_id)
        )
        assert evidence.period == Period.from_year_and_code(2025, "4T")
        assert evidence.asserted_value is M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE
        assert not WorkUnitCatalogueRepository().load().work_units
    if case.definition_id == "ledger.counterparty":
        assert isinstance(payload, LedgerCounterpartyRequest)
        result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerCounterpartyResult,
        )
        assert isinstance(result, LedgerCounterpartyResult)
        assert result.profile_id == profile_id
        assert result.action == payload.action == "confirm"
        assert result.changed is True
        assert result.recorded is True
        assert result.facts is not None
        assert result.facts.territorial_scope == "es_canarias"
        assert result.facts.asserted_by == payload.asserted_by
        persisted = build_counterparty_establishment_repository(bucket_id=str(profile_id)).load(
            result.facts.counterparty_key
        )
        assert persisted is not None
        assert persisted.counterparty_key == result.facts.counterparty_key
        assert persisted.canonical_tax_identifier == result.facts.canonical_tax_identifier
        assert persisted.territorial_scope is not None
        assert persisted.territorial_scope.value == result.facts.territorial_scope
        assert persisted.asserted_by == payload.asserted_by
    if case.definition_id == "ledger.own_account":
        assert isinstance(payload, LedgerOwnAccountRequest)
        result = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerOwnAccountResult,
        )
        assert isinstance(result, LedgerOwnAccountResult)
        assert result.profile_id == profile_id
        assert result.action == "add"
        assert result.changed is True
        assert result.own_account_id == "acc-01"
        assert [account.masked_iban for account in result.accounts] == ["ES \u00b7\u00b7\u00b7\u00b7 1332"]
        assert _OWN_ACCOUNT_SYNTHETIC_IBAN[4:-4] not in result.model_dump_json()
        persisted = OwnAccountRepository(bucket_id=str(profile_id)).load()
        assert [account.iban for account in persisted.accounts] == [_OWN_ACCOUNT_SYNTHETIC_IBAN]
    if case.definition_id == "ledger.remove":
        assert isinstance(payload, LedgerRemoveRequest)
        removal = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerRemoveOperationResult,
        )
        assert isinstance(removal, LedgerRemoveOperationResult)
        assert removal.profile_id == profile_id
        assert removal.report.transaction_id == payload.transaction_id
        assert removal.report.removed is False
        assert removal.report.dry_run is True
        assert any(
            transaction.transaction_id == payload.transaction_id
            for transaction in TransactionCatalogueRepository(bucket_id=str(profile_id)).load()
        )
    if case.definition_id == "ledger.allocate":
        assert isinstance(payload, LedgerAllocateRequest)
        allocated = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerAllocateOperationResult,
        )
        assert isinstance(allocated, LedgerAllocateOperationResult)
        assert allocated.profile_id == profile_id
        assert allocated.transaction.transaction_id == payload.transaction_id
        assert allocated.transaction.business_classification == "MIXED"
        assert allocated.transaction.business_pct == "0.5"
        persisted_allocation = (
            TransactionCatalogueRepository(bucket_id=str(profile_id)).load().get(payload.transaction_id)
        )
        assert persisted_allocation is not None
        assert persisted_allocation.business_classification is BusinessClassification.MIXED
        assert persisted_allocation.business_pct == Decimal("0.5")
    if case.definition_id == "ledger.classify.single":
        assert isinstance(payload, LedgerClassifyRequest)
        classified = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerClassifyOperationResult,
        )
        assert isinstance(classified, LedgerClassifyOperationResult)
        assert classified.profile_id == profile_id
        assert classified.outcome == "classified"
        assert classified.transaction is not None
        assert classified.transaction.transaction_id == payload.transaction_id
        assert classified.transaction.business_classification == "BUSINESS"
        assert classified.bucket_event_ids
        persisted_classification = (
            TransactionCatalogueRepository(bucket_id=str(profile_id)).load().get(payload.transaction_id)
        )
        assert persisted_classification is not None
        assert persisted_classification.business_classification is BusinessClassification.BUSINESS
    if case.definition_id == LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID:
        assert isinstance(payload, LedgerBulkClassifyRequest)
        bulk_projection = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerBulkClassifyProjection,
        )
        assert isinstance(bulk_projection, LedgerBulkClassifyProjection)
        assert bulk_projection.profile_id == profile_id
        assert bulk_projection.outcome == "classified"
        assert bulk_projection.result is not None
        result = bulk_projection.result
        assert result.total == 2
        assert result.applied == 1
        assert result.skipped == 0
        assert len(result.failures) == 1

        csv_rows = tuple(csv.DictReader(payload.csv_text.splitlines()))
        assert len(csv_rows) == 2
        valid_row, invalid_row = csv_rows
        valid_transaction_id = valid_row["transaction_id"]
        invalid_transaction_id = invalid_row["transaction_id"]
        assert valid_transaction_id is not None
        assert invalid_transaction_id is not None
        assert valid_row["iva_category"] == "domestic_general"
        assert invalid_row["iva_category"] == "not-a-declared-category"
        assert result.failures[0].row_index == 1
        assert result.failures[0].transaction_id == invalid_transaction_id
        assert "not declared by the facts registry" in result.failures[0].reason

        assert bulk_classify_before is not None
        transactions_before, history_before = bulk_classify_before
        transactions_after = TransactionCatalogueRepository(bucket_id=str(profile_id)).load()
        history_after = bucket_event_history_repository(bucket_id=str(profile_id)).load()
        assert transactions_after.transactions.keys() == transactions_before.transactions.keys()
        assert transactions_after.get(invalid_transaction_id) == transactions_before.get(invalid_transaction_id)
        assert all(history_after.events.get(event_id) == event for event_id, event in history_before.events.items())
        new_events = tuple(
            event for event_id, event in history_after.events.items() if event_id not in history_before.events
        )
        assert len(new_events) == 1
        event = new_events[0]
        assert result.bucket_event_ids == (event.event_id,)

        before_transaction = transactions_before.get(valid_transaction_id)
        after_transaction = transactions_after.get(valid_transaction_id)
        assert before_transaction is not None
        assert after_transaction is not None
        _assert_canonical_bulk_classification_update(
            profile_id=profile_id,
            operation=operation,
            before=before_transaction,
            after=after_transaction,
            patch=ManualLedgerTransactionPatch(
                business_classification=BusinessClassification.BUSINESS,
                iva_category=IvaCategory("domestic_general"),
            ),
            actor=payload.actor or str(profile_id),
            event=event,
        )

        expected_transactions = dict(transactions_before.transactions)
        expected_transactions[valid_transaction_id] = after_transaction
        assert transactions_after == TransactionCatalogue.from_transactions(expected_transactions.values())
    if case.definition_id == "ledger.evidence.add":
        assert isinstance(payload, LedgerEvidenceAddRequest)
        added_evidence = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerEvidenceAddProjection,
        )
        assert isinstance(added_evidence, LedgerEvidenceAddProjection)
        assert added_evidence.profile_id == profile_id
        assert added_evidence.record.bucket_id == str(profile_id)
        assert added_evidence.record.source_path == payload.source_path
        assert added_evidence.bucket_event_ids
        persisted_evidence = build_ledger_evidence_ports(bucket_id=str(profile_id)).evidence_repository.load(
            bucket_id=str(profile_id)
        )
        assert len(persisted_evidence) == 1
        assert persisted_evidence[0].evidence_id == added_evidence.record.evidence_id
    if case.definition_id == "ledger.evidence.list":
        assert isinstance(payload, LedgerEvidenceListRequest)
        listed = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerEvidenceListProjection,
        )
        assert isinstance(listed, LedgerEvidenceListProjection)
        assert listed.profile_id == profile_id
        assert listed.count == len(listed.rows) == 1
        assert listed.rows[0].bucket_id == str(profile_id)
    if case.definition_id == "ledger.evidence.view":
        assert isinstance(payload, LedgerEvidenceViewRequest)
        viewed = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerEvidenceViewProjection,
        )
        assert isinstance(viewed, LedgerEvidenceViewProjection)
        assert viewed.profile_id == profile_id
        assert isinstance(viewed.outcome, LedgerEvidenceViewSuccess)
        assert viewed.outcome.record.bucket_id == str(profile_id)
        assert viewed.outcome.record.evidence_id == payload.evidence_id
    if case.definition_id == "ledger.evidence.update":
        assert isinstance(payload, LedgerEvidenceUpdateRequest)
        updated_evidence = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerEvidenceUpdateProjection,
        )
        assert isinstance(updated_evidence, LedgerEvidenceUpdateProjection)
        assert updated_evidence.profile_id == profile_id
        assert updated_evidence.record.evidence_id == payload.evidence_id
        assert updated_evidence.record.supplier == "Conformance Supplier"
        assert updated_evidence.bucket_event_ids
        persisted_evidence = build_ledger_evidence_ports(bucket_id=str(profile_id)).evidence_repository.load(
            bucket_id=str(profile_id)
        )
        assert len(persisted_evidence) == 1
        assert persisted_evidence[0].supplier == "Conformance Supplier"
    if case.definition_id == "ledger.evidence.remove":
        assert isinstance(payload, LedgerEvidenceRemoveRequest)
        removed_evidence = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerEvidenceRemoveProjection,
        )
        assert isinstance(removed_evidence, LedgerEvidenceRemoveProjection)
        assert removed_evidence.profile_id == profile_id
        assert removed_evidence.record.evidence_id == payload.evidence_id
        assert removed_evidence.bucket_event_ids
        persisted_evidence = build_ledger_evidence_ports(bucket_id=str(profile_id)).evidence_repository.load(
            bucket_id=str(profile_id)
        )
        assert persisted_evidence == ()
    if case.definition_id == "ledger.split.manual":
        assert isinstance(payload, LedgerSplitRequest)
        split = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerSplitOperationResult,
        )
        assert isinstance(split, LedgerSplitOperationResult)
        assert split.profile_id == profile_id
        assert split.parent_transaction_id == payload.transaction_id
        assert len(split.child_transaction_ids) == 2
        persisted_split = TransactionCatalogueRepository(bucket_id=str(profile_id)).load()
        assert all(child_id in persisted_split.transactions for child_id in split.child_transaction_ids)
        # The parent stays stored and split; the result names what recombines the cohort.
        split_parent = persisted_split.transactions[split.parent_transaction_id]
        assert split_parent.lifecycle_state.value == "SPLIT"
        assert split.parent_business_classification is split_parent.business_classification
        assert split.child_business_classification is BusinessClassification.NOT_YET_PROCESSED
        assert split.remerged_by == ("ledger.merge",)
    if case.definition_id == "ledger.merge":
        assert isinstance(payload, LedgerMergeRequest)
        merged = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerMergeOperationResult,
        )
        assert isinstance(merged, LedgerMergeOperationResult)
        assert merged.profile_id == profile_id
        assert merged.source_child_ids == tuple(sorted(payload.child_ids))
        persisted_merge = TransactionCatalogueRepository(bucket_id=str(profile_id)).load()
        assert merged.merged_transaction_id in persisted_merge.transactions
        assert all(child_id in persisted_merge.transactions for child_id in merged.source_child_ids)
    if case.definition_id == "ledger.update":
        assert isinstance(payload, LedgerUpdateRequest)
        updated = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerUpdateOperationResult,
        )
        assert isinstance(updated, LedgerUpdateOperationResult)
        assert updated.profile_id == profile_id
        assert updated.outcome == "updated"
        assert updated.transaction is not None
        assert updated.transaction.description == "updated through registered operation"
        assert updated.bucket_event_ids
        persisted_update = (
            TransactionCatalogueRepository(bucket_id=str(profile_id)).load().get(updated.transaction.transaction_id)
        )
        assert persisted_update is not None
        assert persisted_update.raw.description == "updated through registered operation"
    if case.definition_id == "ledger.reset":
        assert isinstance(payload, LedgerResetRequest)
        reset = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerResetOperationResult,
        )
        assert isinstance(reset, LedgerResetOperationResult)
        assert reset.profile_id == profile_id
        assert reset.report.reset is True
        assert reset.report.dry_run is False
        assert reset.report.reason == payload.reason
        assert len(reset.report.removed_transaction_ids) == 1
        assert reset.report.bucket_event_ids
        assert tuple(TransactionCatalogueRepository(bucket_id=str(profile_id)).load()) == ()
    if case.definition_id == "ledger.import":
        assert isinstance(payload, LedgerImportRequest)
        imported = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerImportResultProjection,
        )
        assert isinstance(imported, LedgerImportResultProjection)
        assert imported.profile_id == profile_id
        assert imported.bucket_id == str(profile_id)
        assert imported.dry_run is True
        assert imported.rows == imported.imported == imported.skipped == imported.likely_duplicates == 0
        assert len(imported.refused_files) == 1
        assert imported.refused_files[0].file_name == "missing.csv"
        assert imported.refused_files[0].reason_code == "transaction_validation"
        assert tuple(TransactionCatalogueRepository(bucket_id=str(profile_id)).load()) == ()
    if case.definition_id == "ledger.add":
        assert isinstance(payload, LedgerAddRequest)
        added = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerAddOperationResult,
        )
        assert isinstance(added, LedgerAddOperationResult)
        assert added.profile_id == profile_id
        assert added.outcome == "created"
        assert added.transaction is not None
        assert added.transaction.description == payload.description
        assert added.bucket_event_ids
        persisted_add = (
            TransactionCatalogueRepository(bucket_id=str(profile_id)).load().get(added.transaction.transaction_id)
        )
        assert persisted_add is not None
        assert persisted_add.raw.description == payload.description
    if case.definition_id == "ledger.status":
        assert isinstance(payload, LedgerStatusRequest)
        status = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerStatusProjection,
        )
        assert isinstance(status, LedgerStatusProjection)
        assert status.profile_id == profile_id
        assert status.period is None
        assert Decimal(status.business_income_total) == Decimal("0")
        assert Decimal(status.business_expense_total) == Decimal("0")
        assert Decimal(status.business_net_total) == Decimal("0")
        assert status.total_count == 0
        assert status.active_count == status.archived_count == status.stashed_count == 0
        assert status.readiness_issues == ()
        assert status.stale_filings == ()
    if case.definition_id == "ledger.check":
        assert isinstance(payload, LedgerCheckRequest)
        check = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerCheckProjection,
        )
        assert isinstance(check, LedgerCheckProjection)
        assert payload.period is not None
        assert check.profile_id == profile_id
        assert check.period == payload.period
        assert check.periods == (str(payload.period.to_period()),)
        assert check.checked_transaction_count == 0
        assert check.issues == ()
        assert not check.ready
        invoices = InvoiceCatalogueRepository(bucket_id=str(profile_id)).load().invoices
        assert len(invoices) == 1
        invoice = next(iter(invoices.values()))
        assert check.link_inconsistencies == (
            LinkInconsistency(
                invoice_id=invoice.invoice_id,
                transaction_id="f" * 64,
                direction=LinkInconsistencyDirection.INVOICE_ONLY,
            ),
        )
        assert len(TransactionCatalogueRepository(bucket_id=str(profile_id)).load()) == 0
        assert definition.capabilities.permitted_effects == frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    if case.definition_id == "ledger.invoice.add":
        created = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=InvoiceAddResult,
        )
        assert isinstance(created, InvoiceAddResult)
        assert created.profile_id == profile_id
        assert created.outcome == "created"
        catalogue = InvoiceCatalogueRepository(bucket_id=str(profile_id)).load()
        assert len(catalogue.invoices) == 1
        assert created.invoice is not None
        invoice = catalogue.invoices[created.invoice.invoice_id]
        assert invoice.invoice_number == "CONFORMANCE-INVOICE-2025-ADD"
        assert invoice.grand_total == Decimal("121.00")
        assert created.invoice == CatalogueInvoiceSnapshot.from_invoice(invoice)
    if case.definition_id == INVOICE_LIST_OPERATION_DEFINITION_ID:
        assert isinstance(payload, InvoiceListRequest)
        inventory = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=InvoiceListProjection,
        )
        assert isinstance(inventory, InvoiceListProjection)
        assert inventory.profile_id == profile_id
        assert inventory.kind is None
        assert invoice_catalogue_before is not None
        assert tuple(inventory.invoices) == tuple(
            CatalogueInvoiceSnapshot.from_invoice(invoice) for invoice in invoice_catalogue_before.values()
        )
        assert len(inventory.invoices) == 1
    if case.definition_id == INVOICE_VIEW_OPERATION_DEFINITION_ID:
        assert isinstance(payload, InvoiceViewRequest)
        selection = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=InvoiceViewProjection,
        )
        assert isinstance(selection, InvoiceViewProjection)
        assert selection.profile_id == profile_id
        assert selection.invoice_id == payload.invoice_id
        assert isinstance(selection.outcome, InvoiceViewSuccess)
        assert invoice_catalogue_before is not None
        assert selection.outcome.invoice == CatalogueInvoiceSnapshot.from_invoice(
            invoice_catalogue_before.invoices[payload.invoice_id]
        )
    if case.definition_id == INVOICE_REMOVE_OPERATION_DEFINITION_ID:
        assert isinstance(payload, InvoiceRemoveRequest)
        removal = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=InvoiceRemoveResult,
        )
        assert isinstance(removal, InvoiceRemoveResult)
        assert removal.profile_id == profile_id
        assert removal.invoice_id == payload.invoice_id
        assert invoice_catalogue_before is not None
        removed_invoice = invoice_catalogue_before.invoices[payload.invoice_id]
        assert removal.invoice == CatalogueInvoiceSnapshot.from_invoice(removed_invoice)
        expected_catalogue = InvoiceCatalogue(
            invoices={
                invoice_id: invoice
                for invoice_id, invoice in invoice_catalogue_before.invoices.items()
                if invoice_id != payload.invoice_id
            }
        )
        assert InvoiceCatalogueRepository(bucket_id=str(profile_id)).load() == expected_catalogue
    if case.definition_id == INVOICE_UPDATE_OPERATION_DEFINITION_ID:
        assert isinstance(payload, InvoiceUpdateRequest)
        update = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=InvoiceUpdateResult,
        )
        assert isinstance(update, InvoiceUpdateResult)
        assert update.profile_id == profile_id
        assert update.invoice_id == payload.invoice_id
        assert update.invoice.invoice_id == payload.invoice_id
        assert update.invoice.counterparty_name == "Updated conformance supplier"
        assert update.invoice.retention_amount is not None
        assert Decimal(update.invoice.retention_amount.decimal) == Decimal("0.00")
        assert update.bucket_event_ids
        assert invoice_catalogue_before is not None
        original = invoice_catalogue_before.invoices[payload.invoice_id]
        persisted = InvoiceCatalogueRepository(bucket_id=str(profile_id)).load()
        assert set(persisted.invoices) == set(invoice_catalogue_before.invoices)
        corrected = persisted.invoices[payload.invoice_id]
        assert corrected.invoice_id == original.invoice_id
        assert corrected.counterparty_name == "Updated conformance supplier"
        assert corrected.retention_amount == Decimal("0.00")
        assert corrected.notes == original.notes
        assert corrected.linked_transaction_ids == original.linked_transaction_ids
        assert (
            corrected.model_copy(
                update={
                    "counterparty_name": original.counterparty_name,
                    "retention_amount": original.retention_amount,
                    "updated_at": original.updated_at,
                }
            )
            == original
        )
        for invoice_id, invoice in invoice_catalogue_before.invoices.items():
            if invoice_id != payload.invoice_id:
                assert persisted.invoices[invoice_id] == invoice
        event_catalogue = BucketEventHistoryRepository().load()
        assert all(event_id in event_catalogue.events for event_id in update.bucket_event_ids)
        assert any(
            event_catalogue.events[event_id].object_id == payload.invoice_id
            and event_catalogue.events[event_id].event_type is BucketEventType.PAYABLE_INVOICE_UPDATED
            for event_id in update.bucket_event_ids
        )
    if case.definition_id == IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID:
        assert isinstance(payload, IvaWalletHistoryRequest)
        history = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=IvaWalletHistoryProjection,
        )
        assert isinstance(history, IvaWalletHistoryProjection)
        assert history.profile_id == profile_id
        assert history.as_of_year == payload.as_of_year
        assert history.row_count == 1
        row = history.rows[0]
        assert row.year == 2025
        assert row.period.to_period() == Period.from_year_and_code(2025, "1T")
        assert row.provenance is IvaCompensationStateProvenance.APP_FILING
        assert row.generated_amount == "40.00"
        assert history.carry_forward_lot_count == 1
        assert history.carry_forward_lots[0].source_period == row.period
        assert history.carry_forward_lots[0].remaining_amount == "40.00"
        assert history.authority_decision_count == 0
        assert iva_history_before is not None
        assert IvaCompensationHistoryRepository().list_periods() == iva_history_before
    if case.definition_id == MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID:
        correction = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloIvaWalletCorrectionProjection,
        )
        assert isinstance(correction, ModeloIvaWalletCorrectionProjection)
        assert correction.profile_id == profile_id
        assert correction.period.to_period() == Period.from_year_and_code(2024, "4T")
        assert correction.previous_amount == "500.00"
        assert correction.amount == "1200.50"
        assert correction.provenance is IvaCompensationStateProvenance.OPERATOR_CORRECTION
        assert correction.register_status is None
        assert correction.reason == "corrected opening balance"
        persisted = IvaCompensationHistoryRepository(bucket_id=str(profile_id)).load_period(
            correction.period.to_period()
        )
        assert persisted is not None
        assert persisted.available_end_amount == Decimal("1200.50")
    if case.definition_id == "modelo.iva-wallet.balance":
        balance = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloIvaWalletBalanceProjection,
        )
        assert isinstance(balance, ModeloIvaWalletBalanceProjection)
        assert balance.profile_id == profile_id
        assert balance.as_of_year == 2024
        assert Decimal(balance.total_balance) == Decimal("500.00")
        assert Decimal(balance.active_balance) == Decimal("500.00")
        assert Decimal(balance.expired_balance) == Decimal("0.00")
        assert Decimal(balance.unallocated_applied_amount) == Decimal("0.00")
        assert balance.lot_count == 1
        assert balance.next_expiry_year == 2028
    if case.definition_id == "modelo.iva-wallet.seed":
        seeded = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloIvaWalletSeedProjection,
        )
        assert isinstance(seeded, ModeloIvaWalletSeedProjection)
        assert seeded.profile_id == profile_id
        assert seeded.period.to_period() == Period.from_year_and_code(2024, "4T")
        assert seeded.amount == "500.00"
        assert seeded.provenance is IvaCompensationStateProvenance.OPERATOR_SEED
        persisted_seed = IvaCompensationHistoryRepository(bucket_id=str(profile_id)).load_period(
            seeded.period.to_period()
        )
        assert persisted_seed is not None
        assert persisted_seed.available_end_amount == Decimal("500.00")
    if case.definition_id == "modelo.iva-wallet.override":
        overridden = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloIvaWalletOverrideProjection,
        )
        assert isinstance(overridden, ModeloIvaWalletOverrideProjection)
        assert overridden.profile_id == profile_id
        assert overridden.period.to_period() == Period.from_year_and_code(2025, "1T")
        assert overridden.amount == "450.00"
        assert overridden.reason == "operator asserted prior compensation"
        assert overridden.evidence_locator == "synthetic:conformance:prior-compensation"
        assert str(overridden.selected_authority) == "taxpayer_override"
        assert str(overridden.divergence) == "override"
        persisted_override = IvaWalletDecisionRepository().load_decision(
            SEEDED_SOURCE_TAX_ID, overridden.period.to_period()
        )
        assert persisted_override is not None
        assert str(persisted_override.selected_authority) == "taxpayer_override"
    if case.definition_id in {INVOICE_LIST_OPERATION_DEFINITION_ID, INVOICE_VIEW_OPERATION_DEFINITION_ID}:
        assert invoice_catalogue_before is not None
        assert InvoiceCatalogueRepository(bucket_id=str(profile_id)).load() == invoice_catalogue_before
    if case.definition_id == "ledger.preflight":
        assert isinstance(payload, LedgerPreflightRequest)
        preflight = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerPreflightProjection,
        )
        assert isinstance(preflight, LedgerPreflightProjection)
        assert preflight.profile_id == profile_id
        assert preflight.period == payload.period
        assert preflight.checked_transaction_count == 1
        assert not preflight.ready
        transactions = TransactionCatalogueRepository(bucket_id=str(profile_id)).load()
        assert len(transactions) == 2
        transaction_ids_by_description = {
            transaction.raw.description: transaction.transaction_id for transaction in transactions.values()
        }
        selected_transaction_id = transaction_ids_by_description["conformance preflight selected-period issue"]
        outside_transaction_id = transaction_ids_by_description["conformance preflight outside-period issue"]
        assert len(preflight.issues) == 1
        assert preflight.issues[0].transaction_id == selected_transaction_id
        assert preflight.issues[0].reason is LedgerPreflightIssueReason.MISSING_CATEGORY
        assert outside_transaction_id not in {issue.transaction_id for issue in preflight.issues}
        assert definition.capabilities.permitted_effects == frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    if case.definition_id == "ledger.list":
        assert isinstance(payload, LedgerListRequest)
        selection = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerListProjection,
        )
        assert isinstance(selection, LedgerListProjection)
        assert selection.profile_id == profile_id
        assert selection.total == 3
        assert selection.truncated is True
        assert selection.offset == payload.offset == 1
        assert selection.limit == payload.limit == 2
        assert selection.by_group is False
        assert [row.transaction.description for row in selection.rows] == [
            "ledger list page B",
            "ledger list page C",
        ]
        assert all(row.group_label == _LEDGER_LIST_PRIVATE_FILTER_SENTINEL for row in selection.rows)
        materialization = asyncio.run(
            driver.services.observation.reader.read_observation(
                submitted.receipt.operation_id,
                0,
                limit=256,
            )
        )
        assert materialization.snapshot.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
        assert materialization.snapshot.credential_free_request_json is None
        journal_file = (
            tmp_path
            / case.definition_id
            / "cadrumo-storage"
            / "operations"
            / storage_location(StorageCategory.OPERATION_JOURNAL).relative_path()
            / f"{submitted.receipt.operation_id}.json"
        )
        assert journal_file.is_file()
        assert _LEDGER_LIST_PRIVATE_FILTER_SENTINEL.encode() not in journal_file.read_bytes()
    if case.definition_id == "ledger.history":
        assert isinstance(payload, LedgerHistoryRequest)
        history = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerHistoryProjection,
        )
        assert isinstance(history, LedgerHistoryProjection)
        assert history.profile_id == profile_id
        assert history.transaction_prefix == payload.transaction_prefix
        assert history.include_split_siblings is False
        assert history.event_count == 1
        assert len(history.events) == 1
        assert history.transaction_id in history.object_ids
    if case.definition_id == "ledger.view":
        assert isinstance(payload, LedgerViewRequest)
        view = _resolve_result_projection(
            driver,
            registry,
            definition_id=case.definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerViewProjection,
        )
        assert isinstance(view, LedgerViewProjection)
        assert view.profile_id == profile_id
        assert view.transaction_prefix == payload.transaction_prefix
        assert view.transaction.transaction_id.startswith(payload.transaction_prefix)
        assert view.transaction.description == "conformance view seed"
        assert view.review_status is LedgerReviewStatus.PENDING
        assert view.latest_llm_rejection is not None
        assert view.latest_llm_rejection.operator_reason == "operator rejected the conformance suggestion"
    if definition_id == "ledger.track":
        _assert_ledger_track_result(
            driver,
            registry,
            profile_id=profile_id,
            operation=operation,
            payload=payload,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
        )
    if definition_id == "ledger.participation":
        assert isinstance(payload, LedgerParticipationRequest)
        _assert_ledger_participation_lookup_result(
            driver,
            registry,
            profile_id=profile_id,
            payload=payload,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
        )
    if definition_id == "ledger.participation.rebuild":
        assert isinstance(payload, LedgerParticipationRebuildRequest)
        _assert_ledger_participation_rebuild_result(
            driver,
            registry,
            profile_id=profile_id,
            operation=operation,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
        )
    if definition_id == "ledger.review":
        review = _resolve_result_projection(
            driver,
            registry,
            definition_id=definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerReviewProjection,
        )
        _assert_ledger_review_projection(payload, review, profile_id=profile_id)
    assert isinstance(observed.projection.pending_interaction, OperationNoPendingInteractionV1)
    asyncio.run(
        driver.review_not_pending(
            operation_id=submitted.receipt.operation_id,
            revision=observed.projection.revision,
            registry=registry,
        )
    )
