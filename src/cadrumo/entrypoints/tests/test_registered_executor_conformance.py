"""Real-supervisor conformance matrix for every production executor."""

from __future__ import annotations

import asyncio
import csv
import hashlib
from collections.abc import Awaitable, Callable, Generator, Mapping
from contextlib import AbstractContextManager, contextmanager, nullcontext
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast, override
from uuid import UUID
from zipfile import ZipFile

import pytest
from pydantic import BaseModel, SecretStr

from cadrumo.adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope, default_browser_session_factory
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    seed_modelo_ready_profile_record,
    upsert_test_profile_facts,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ...adapters.persistence.operations.financial_operand_custody import (
    OperationFinancialOperandCustodyFilesystemRepository,
)
from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
)
from ...adapters.persistence.profile.counterparty_establishment import build_counterparty_establishment_repository
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.notification_documents import notification_document_repository
from ...adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ...adapters.persistence.profile.tests.cross_period_seeding import (
    SEEDED_SOURCE_TAX_ID,
    seed_clean_cross_period_sources,
)
from ...adapters.persistence.profile.tests.justificante_metadata import persist_justificante_metadata
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...adapters.persistence.profile.verify_observations import VerifyObservationRepository
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ...application.actividad_asset.operation_dtos import (
    ActivityAssetRevisionSnapshot,
    ScheduledAmortizationChargeSnapshot,
)
from ...application.actividad_asset.registered_operations import (
    ActivityAssetClaimProjection,
    ActivityAssetCorrectProjection,
    ActivityAssetCreateProjection,
    ActivityAssetFilingHandoffProjection,
    ActivityAssetForecastProjection,
    ActivityAssetInspectProjection,
)
from ...application.aggregation.service import aggregate_per_modelo
from ...application.auth.certificate_source_operations import (
    list_operator_certificate_sources,
    register_operator_certificate_source,
    set_operator_certificate_source_secret,
)
from ...application.auth.operation_definitions import build_auth_operation_definitions
from ...application.auth.read_operation import (
    AUTH_READ_OPERATION_DEFINITION_ID,
    AuthReadProjection,
    AuthReadRequest,
)
from ...application.bienes_inversion.registered_operation import (
    BienesInversionDeclareProjection,
    BienesInversionListProjection,
    BienInversionRecordProjection,
)
from ...application.bucket_event_repository import bucket_event_history_repository
from ...application.calculations.iva_compensation_history import seed_iva_compensation_period
from ...application.inventory.registered_operation import (
    InventoryClosingAuthorityOperationProjection,
    InventoryCreateProjection,
    InventoryLedgerProjection,
    InventoryListProjection,
    InventoryMovementAddProjection,
    InventoryValuationOperationProjection,
)
from ...application.inventory.tests.registered_operation_conformance_support import (
    prepare_inventory_operation_conformance_case,
)
from ...application.invoices.catalogue_add_operation import InvoiceAddResult
from ...application.invoices.catalogue_lifecycle import CatalogueInvoicePatch
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
    InvoiceUpdatePatch,
    InvoiceUpdateRequest,
    InvoiceUpdateResult,
)
from ...application.ledger.actions_import import LedgerProviderID
from ...application.ledger.actions_manual import (
    command_from_patch,
    create_manual_transaction,
    prepare_manual_transaction_update,
)
from ...application.ledger.actions_split_merge import split_transaction
from ...application.ledger.add_operation import LedgerAddOperationResult, LedgerAddRequest
from ...application.ledger.allocate_operation import LedgerAllocateOperationResult, LedgerAllocateRequest
from ...application.ledger.attachment_mutation_operation import (
    LedgerAttachmentOperationResult,
)
from ...application.ledger.bulk_classify_operation import (
    LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
    LedgerBulkClassifyProjection,
    LedgerBulkClassifyRequest,
)
from ...application.ledger.check_operation import LedgerCheckProjection, LedgerCheckRequest
from ...application.ledger.classify_operation import (
    LedgerClassifyOperationResult,
    LedgerClassifyPatch,
    LedgerClassifyRequest,
)
from ...application.ledger.counterparty_operation import LedgerCounterpartyRequest, LedgerCounterpartyResult
from ...application.ledger.evidence import PurchaseInvoiceEvidenceService
from ...application.ledger.evidence_add_operation import LedgerEvidenceAddProjection, LedgerEvidenceAddRequest
from ...application.ledger.evidence_mutation_operation import (
    LedgerEvidenceRemoveProjection,
    LedgerEvidenceRemoveRequest,
    LedgerEvidenceUpdatePatch,
    LedgerEvidenceUpdateProjection,
    LedgerEvidenceUpdateRequest,
)
from ...application.ledger.evidence_read_operation import (
    LedgerEvidenceListProjection,
    LedgerEvidenceListRequest,
    LedgerEvidenceViewProjection,
    LedgerEvidenceViewRequest,
)
from ...application.ledger.history_operation import LedgerHistoryProjection, LedgerHistoryRequest
from ...application.ledger.id_resolution import resolve_lineage_transaction_id
from ...application.ledger.import_operation import LedgerImportRequest, LedgerImportResultProjection
from ...application.ledger.invoice_evidence_operation import LedgerEvidenceConfirmProjection
from ...application.ledger.lifecycle_mutation_operation import (
    LedgerLifecycleOperationId,
    LedgerLifecycleOperationResult,
)
from ...application.ledger.list_operation import LedgerListProjection, LedgerListRequest
from ...application.ledger.llm_classification import reject_llm_suggestion
from ...application.ledger.llm_classification_ports import LLMClassificationSuggestion
from ...application.ledger.merge_operation import LedgerMergeOperationResult, LedgerMergeRequest
from ...application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch, SplitChildCommand
from ...application.ledger.participation_operation import (
    LedgerParticipationProjection as LedgerParticipationLookupProjection,
)
from ...application.ledger.participation_operation import (
    LedgerParticipationRequest,
)
from ...application.ledger.participation_rebuild_operation import (
    LedgerParticipationRebuildProjection,
    LedgerParticipationRebuildRequest,
)
from ...application.ledger.preflight import LedgerPreflightIssueReason
from ...application.ledger.preflight_operation import LedgerPreflightProjection, LedgerPreflightRequest
from ...application.ledger.remove_operation import LedgerRemoveOperationResult, LedgerRemoveRequest
from ...application.ledger.reset_operation import LedgerResetOperationResult, LedgerResetRequest
from ...application.ledger.review_operation import LedgerReviewProjection, LedgerReviewRequest
from ...application.ledger.rule_operation import LedgerRuleAddProjection
from ...application.ledger.split_operation import (
    LedgerSplitOperationResult,
    LedgerSplitRequest,
)
from ...application.ledger.status_operation import LedgerStatusProjection, LedgerStatusRequest
from ...application.ledger.track_operation import LedgerTrackProjection, LedgerTrackRequest
from ...application.ledger.tracking_projection import (
    LedgerParticipationProjection as LedgerParticipationEntryProjection,
)
from ...application.ledger.update_operation import (
    LedgerUpdateOperationResult,
    LedgerUpdatePatch,
    LedgerUpdateRequest,
)
from ...application.ledger.usage_ratio_repository import load_usage_ratio_profile, save_usage_ratio_profile
from ...application.ledger.view_operation import LedgerViewProjection, LedgerViewRequest
from ...application.live.expedientes import ExpedientesCapture, ExpedientesService
from ...application.live.expedientes_ports import ExpedientesDeclaration
from ...application.live.iva_wallet_history_operation import (
    IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID,
    IvaWalletHistoryProjection,
    IvaWalletHistoryRequest,
)
from ...application.live.notification_documents import NotificationDocumentRecord
from ...application.live.notification_ports import NotificationsSnapshot, NotificationType, RemoteNotification
from ...application.live.notifications import NotificationsService
from ...application.live.verify import VerifyService, VerifySurface
from ...application.live.verify_capture_operation import VerifyLiveObservation, build_verify_capture_definition
from ...application.local_reader_operation import LOCAL_READER_OPERATION_SUBJECT, LocalReaderProvisionAction
from ...application.modelo.aggregate_operation import ModeloAggregateOperationRequest, ModeloAggregateProjection
from ...application.modelo.amendment_action_ports import AmendmentActionPorts, AmendmentActionPortsFactory
from ...application.modelo.calculation_actions import calculate_modelo_revision
from ...application.modelo.calculation_report_verification import (
    CalculationSummaryCheckName,
    CalculationSummaryVerificationLayer,
    CalculationSummaryVerificationOutcome,
    CalculationSummaryVerificationReason,
)
from ...application.modelo.calculation_report_verification_operation import (
    MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID,
    ModeloCalculationReportVerificationProjection,
    ModeloCalculationReportVerificationRequest,
)
from ...application.modelo.dependency_operation import (
    MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,
    ModeloDependencyProjection,
    ModeloDependencyRequest,
)
from ...application.modelo.external_import_actions import import_external_filing_evidence
from ...application.modelo.history_operation import ModeloWorkHistoryProjection, ModeloWorkHistoryRequest
from ...application.modelo.invoice_withholding_capture_operation import (
    MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
    ModeloInvoiceWithholdingCaptureProjection,
    ModeloInvoiceWithholdingCaptureRequest,
)
from ...application.modelo.iva_wallet_balance_operation import ModeloIvaWalletBalanceProjection
from ...application.modelo.iva_wallet_correction_operation import (
    MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
    ModeloIvaWalletCorrectionProjection,
)
from ...application.modelo.iva_wallet_override_operation import ModeloIvaWalletOverrideProjection
from ...application.modelo.iva_wallet_seed_operation import ModeloIvaWalletSeedProjection
from ...application.modelo.local_observation_operation import ModeloLocalObservationCasillaValue
from ...application.modelo.m303_attestation_operation import (
    ModeloWorkM303AttestationPublicResultV2,
    ModeloWorkM303AttestationRequest,
)
from ...application.modelo.mcp_query_operation import (
    ModeloBindingsResolveTypedProjection,
    ModeloReadinessSummaryProjection,
)
from ...application.modelo.operation_definitions import (
    ModeloWorkCalculateRequest,
    resolve_active_workflow_profile,
)
from ...application.modelo.query_read_operation import (
    ModeloBindingsListProjection,
    ModeloBindingsResolveProjection,
    ModeloReadinessProjection,
    ModeloRequiresProjection,
)
from ...application.modelo.reconciliation_records import ModeloReconciliationEvidenceKind
from ...application.modelo.review_package_operation import (
    ModeloReviewPackageBuildPublicResultV1,
    ModeloReviewPackageBuildRequest,
)
from ...application.modelo.review_package_recipient_operations import ReviewPackageRecipientAddProjection
from ...application.modelo.revision_inventory_operation import (
    ModeloWorkRevisionsProjection,
    ModeloWorkRevisionsRequest,
)
from ...application.modelo.revision_snapshot_operation import ModeloWorkRevisionSnapshotRequest
from ...application.modelo.taxation_comparison_operation import (
    MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
    ModeloTaxationComparisonRequest,
)
from ...application.modelo.verification_actions import verify_modelo_revision
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
    MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE,
    ModeloWorkCreateProjection,
    ModeloWorkCreateRefusal,
    ModeloWorkCreateRequest,
)
from ...application.modelo.work_inventory_operation import ModeloWorkListProjection, ModeloWorkListRequest
from ...application.modelo.work_review_operation import ModeloWorkReviewProjection, ModeloWorkReviewRequest
from ...application.operations.capabilities import OperationRequestStoragePolicy
from ...application.operations.composition import (
    OperationComposedServices,
    OperationSubmission,
    compose_operation_services,
)
from ...application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionReferenceV1,
)
from ...application.operations.frontend_requests import (
    OperationCancellationRefusalV1,
    OperationCancellationRequestV1,
    OperationCancellationSuccessV1,
    OperationObservationRequestV1,
    OperationObservationResultV1,
    OperationObservationSuccessV1,
    OperationObservationVersionHeader,
    OperationPublicPhaseEventV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseMutationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationReviewProjectionRefusalCode,
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionRequestV1,
)
from ...application.operations.models import OperationRequest
from ...application.operations.observation import OperationObservationService
from ...application.operations.public_period import PublicPeriod
from ...application.operations.registry import (
    OperationDefinition,
    OperationRegistry,
)
from ...application.operator_actions.models import ConditionEvidence, PreconditionVerdict
from ...application.overview.pipeline_operation import OverviewPipelineProjection, OverviewPipelineRequest
from ...application.overview.pipeline_projection import PipelineHealthSnapshot
from ...application.overview.read_operation import (
    OVERVIEW_READ_DEFINITION_IDS,
    OverviewAgendaRead,
    OverviewBacklogRead,
    OverviewCalendarRead,
    OverviewExplainRead,
    OverviewPrepareRead,
    OverviewReadKind,
    OverviewReadProjection,
    OverviewReadRequest,
    OverviewStatusRead,
)
from ...application.prorrata_register.registered_operations import ProrrataListProjection, ProrrataMutationProjection
from ...application.review.filter import LedgerReviewStatus
from ...application.user_profile.automation_operations import build_automation_operation_definitions
from ...application.user_profile.bundle_export_contracts import ProfileBundleExportPurpose
from ...application.user_profile.censal_file_import_operation import CensalFileImportProvenance
from ...application.user_profile.censal_observation import (
    CensalObservation,
    CensalObservationAddress,
    CensalObservationIdentity,
)
from ...application.user_profile.censal_operation import (
    CensalFieldIntent,
    CensalOperationAcquisition,
    CensalProfileBaseline,
    CensalReviewedFieldIntent,
    CensalReviewProjectionV1,
    build_censal_operation_definition,
)
from ...application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS
from ...application.user_profile.custody_ports import profile_custody_secure_object_repository
from ...application.user_profile.login_session import login_profile, logout_active_profile
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.recovery_custody import enroll_profile_recovery, profile_recovery_status
from ...application.user_profile.recovery_status_operation import RecoveryStatusProjection
from ...application.user_profile.registration import register_profile_with_credentials
from ...application.user_profile.section_rows import add_profile_repeatable_section_row
from ...application.user_profile.view_operation import ProfileViewPageKind
from ...application.workflow.abort import WorkflowAbortReason
from ...application.workflow.persistence import WorkflowRunRepository, workflow_state_repository
from ...application.workflow.resume_operation import (
    WORKFLOW_RESUME_OPERATION_DEFINITION_ID,
    WorkflowResumeProjection,
    WorkflowResumeRequest,
    WorkflowResumeSuccess,
)
from ...application.workflow.run_models import (
    WorkflowObligationFacts,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
)
from ...application.workflow.run_read_operation import (
    WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID,
    WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,
    WorkflowRunListProjection,
    WorkflowRunListRequest,
    WorkflowRunReadProjection,
    WorkflowRunReadRequest,
)
from ...core.auth_provider import AuthProviderKind
from ...core.config import load_settings, override_settings
from ...core.errors.hierarchy import InternalInvariantError
from ...core.external_constants import OutputLanguage
from ...core.identity_check_verdict import IdentityCheckVerdict
from ...core.invoice_link import LinkInconsistencyDirection
from ...core.iva_compensation_provenance import IvaCompensationStateProvenance
from ...core.ledger_sort import LedgerSortField
from ...core.model_catalogue import ModelRole
from ...core.modelo import Modelo
from ...core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.period import Period
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_location
from ...core.time.clock import now
from ...domain.attachments.m303_filing_evidence import (
    M303Exonerado390ApplicabilityAssertion,
    parse_m303_exonerado_390_applicability_attestation,
)
from ...domain.buckets.event import BucketEvent, BucketEventType
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
from ...domain.calculations.registry.tests.cross_period_seeding import resolved_revision
from ...domain.categories.spending_category_catalogue import require_spending_category
from ...domain.deadlines.models import ObligationStatus
from ...domain.invoices.enums import IvaRate, PaymentStatus
from ...domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ...domain.invoices.service import LinkInconsistency
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.schema import IvaCategory
from ...domain.iva_compensation.carry_forward import IvaCompensationPeriodState
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue, CalculationRevisionState
from ...domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from ...domain.modelos.filing_record import ExternalEvidenceKind, ModeloRecordCatalogue
from ...domain.modelos.verification_report import VerificationCompletenessStatus
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState
from ...domain.notifications.sancion import SancionLiquidacion
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.usage_ratios.model import UsageRatioProfile
from ...domain.user_profile.plantilla_media import PlantillaMediaState
from ...domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ...domain.user_profile.values import UserProfileFact
from ...tests.aeat_literal_fixtures import aeat_url
from ..actividad_asset_composition import build_activity_asset_operation_ports
from ..adapter_composition import (
    build_amendment_action_ports,
    build_bienes_inversion_repository,
    build_calculation_action_ports,
    build_censal_fetch_port,
    build_expedientes_ports,
    build_filing_action_ports,
    build_inventory_service_ports,
    build_ledger_evidence_ports,
    build_prorrata_register_repository,
    build_verification_repository_bundle,
)
from ..justificante_composition import build_justificante_capture_service
from ..ledger_action_composition import compose_ledger_action_ports
from ..live_state_composition import compose_notifications_ports
from ..operation_composition import build_auth_operation_ports, build_production_operation_registry
from . import modelo_operation_test_support
from .activity_asset_operation_test_support import (
    activity_asset_revision,
    assert_activity_asset_conformance_result,
    seed_activity_asset,
)
from .aggregate_operation_test_support import aggregate_conformance_command
from .censal_review_test_support import review_censal_with_services
from .evidence_followup_operation_test_support import prepare_evidence_followup_conformance_case
from .invoice_evidence_operation_test_support import (
    assert_invoice_evidence_confirmation_persisted,
    prepare_invoice_evidence_conformance_case,
)
from .invoice_withholding_operation_test_support import (
    InvoiceWithholdingConformanceSeed,
    assert_invoice_withholding_conformance_write,
    read_invoice_withholding_conformance_case,
    seed_invoice_withholding_conformance_case,
)
from .ledger_attachment_operation_test_support import (
    assert_ledger_attachment_operation_conformance_result,
    prepare_ledger_attachment_operation_conformance_case,
)
from .ledger_lifecycle_operation_test_support import (
    LedgerLifecycleOperationConformanceCase,
    assert_ledger_lifecycle_operation_conformance_result,
    prepare_ledger_lifecycle_operation_conformance_case,
)
from .ledger_rule_operation_test_support import (
    assert_ledger_rule_operation_conformance_result,
    prepare_ledger_rule_operation_conformance_case,
)
from .modelo_projection_history_conformance_support import prepare_modelo_projection_history_conformance_case
from .modelo_query_operation_test_support import prepare_modelo_query_conformance_case
from .profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
)
from .prorrata_bienes_operation_test_support import (
    bienes_inversion_conformance_record,
    prepare_bienes_inversion_operation_conformance_case,
    read_bienes_inversion_operation_conformance_register,
)
from .prorrata_operation_test_support import (
    ProrrataOperationConformanceCase,
    prepare_prorrata_operation_conformance_case,
    read_prorrata_operation_conformance_register,
)
from .recipient_operation_test_support import (
    assert_recipient_operation_conformance_result,
    prepare_recipient_operation_case,
)
from .review_read_operation_test_support import prepare_review_read_conformance_case

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CREDENTIAL_INPUT = "s45-registered-executor-passphrase"
_ROTATED_CREDENTIAL_INPUT = "s45-registered-executor-rotated-passphrase"
_LEDGER_LIST_PRIVATE_FILTER_SENTINEL = "private-ledger-list-filter-sentinel-6d7c"


@dataclass(frozen=True, slots=True)
class _RegisteredExecutorConformanceCase:
    definition_id: str
    expected_terminal: OperationTerminalCondition
    expected_effect: OperationEffect
    expected_phase_codes: tuple[str, ...] | None = None
    expected_refusal_ref: str | None = None


def _closed_model_runtime() -> AbstractContextManager[object]:
    """Point the local model runtime at a closed port so no live runtime is ever reached."""
    return override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat")


def _registered_definition_ids() -> tuple[str, ...]:
    """Every definition the production registry actually composes.

    The matrix is parametrised from this rather than from a hand-listed
    tuple. A hardcoded item list encodes the registry as it stood on the
    day it was written and then detects nothing: this test's own name
    claims it covers EVERY production registered executor, and while the
    list was hand-maintained it silently covered none of the modelo
    family. Deriving the subjects means a newly composed operation joins
    the matrix by existing, and reports a missing scenario rather than
    reconciling quietly.
    """
    return tuple(sorted(definition.definition_id for definition in build_production_operation_registry().definitions))


_EXPECTATIONS: Mapping[str, _RegisteredExecutorConformanceCase] = {
    case.definition_id: case
    for case in (
        *(
            _RegisteredExecutorConformanceCase(
                f"ledger.rule.{action}",
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.NONE if action == "list" else OperationEffect.UPDATED,
                (f"ledger.rule.{action}",),
            )
            for action in ("add", "list", "apply")
        ),
        *(
            _RegisteredExecutorConformanceCase(
                definition_id, OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, phase_codes
            )
            for definition_id, phase_codes in (
                ("modelo.history", ("modelo.history",)),
                ("modelo.history.timeline", ("modelo.history.timeline",)),
                ("modelo.project", ("modelo.project.prepare", "modelo.project.result")),
                ("modelo.compare", ("modelo.compare.prepare", "modelo.compare.result")),
            )
        ),
        *(
            _RegisteredExecutorConformanceCase(
                f"ledger.{action}", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, (f"ledger.{action}",)
            )
            for action in ("archive", "stash", "restore", "exclude")
        ),
        *(
            _RegisteredExecutorConformanceCase(
                definition_id,
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.NONE,
                (definition_id,),
            )
            for definition_id in (
                "app.review.queue",
                "app.review.view",
                "modelo.bindings.list",
                "modelo.bindings.resolve",
                "modelo.bindings.resolve.typed",
                "modelo.requires",
                "modelo.readiness",
                "modelo.readiness.summary",
                "ledger.evidence.attachment_queue",
                "ledger.evidence.attachment_view",
                "ledger.evidence.consent.list",
                "ledger.evidence.review.list",
                "ledger.evidence.review.view",
            )
        ),
        *(
            _RegisteredExecutorConformanceCase(
                f"config.collab.recipient.{action}",
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.NONE if action == "list" else OperationEffect.UPDATED,
                (f"config.collab.recipient.{action}",),
            )
            for action in ("add", "list", "remove")
        ),
        *(
            _RegisteredExecutorConformanceCase(
                definition.definition_id,
                OperationTerminalCondition.REFUSED,
                OperationEffect.NONE,
                expected_phase_codes=(definition.definition_id + ".execute",),
                expected_refusal_ref="REFUSED_AUTOMATION_ADMINISTRATION",
            )
            for definition in build_automation_operation_definitions()
        ),
        _RegisteredExecutorConformanceCase(
            "auth.profile.login", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "auth.profile.passphrase-rotate", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "auth.provider.configure", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "auth.session.acquire",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            # No certificate is configured in the isolated root, so the
            # provider's local readiness refuses before any session attempt.
            expected_refusal_ref="REFUSED_AUTH_LOGIN_PRECONDITION",
        ),
        *(
            _RegisteredExecutorConformanceCase(definition_id, OperationTerminalCondition.SUCCEEDED, effect)
            for definition_id, effect in (
                ("auth.certificate.source.register", OperationEffect.UPDATED),
                ("auth.certificate.source.list", OperationEffect.NONE),
                ("auth.certificate.source.select", OperationEffect.UPDATED),
                ("auth.certificate.source.remove", OperationEffect.UPDATED),
                ("auth.certificate.source.check", OperationEffect.NONE),
                ("auth.certificate.secret.set", OperationEffect.UPDATED),
                ("auth.certificate.secret.remove", OperationEffect.UPDATED),
                ("ledger.ratios.list", OperationEffect.NONE),
                ("ledger.ratios.eligible", OperationEffect.NONE),
                ("ledger.ratios.validate", OperationEffect.NONE),
                ("ledger.ratios.set", OperationEffect.UPDATED),
                ("ledger.ratios.unset", OperationEffect.UPDATED),
            )
        ),
        _RegisteredExecutorConformanceCase(
            "auth.session.logout", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "auth.session.reset", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            AUTH_READ_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("auth.local-read.execute",),
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.field-mutation", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.repeatable-row-mutation", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.repeatable-row-update", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.repeatable-row-remove", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.patch", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.plantilla-media", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.descendants", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.complete-setup",
            OperationTerminalCondition.REFUSED,
            OperationEffect.UNKNOWN,
            expected_refusal_ref="REFUSED_PROFILE_SCHEMA_VALIDATION",
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.view", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "workbench.generation",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.bundle-export", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.logout", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            # Discovery needs an authenticated session and the isolated root
            # holds no certificate, so the pull fails before any remote read.
            "live.filed-history.pull",
            OperationTerminalCondition.FAILED,
            OperationEffect.NONE,
        ),
        _RegisteredExecutorConformanceCase(
            "live.expedientes.capture.bulk",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("expedientes-capture.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        _RegisteredExecutorConformanceCase(
            "live.expedientes.capture.single",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("expedientes-capture.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        _RegisteredExecutorConformanceCase(
            "live.filed-capture.bulk",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("filed-bulk.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        _RegisteredExecutorConformanceCase(
            "live.filed-capture.single",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("filed-capture.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        _RegisteredExecutorConformanceCase(
            "live.filed-capture.source",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("filed-source.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        _RegisteredExecutorConformanceCase(
            "live.filed-discover",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("filed-discover.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        _RegisteredExecutorConformanceCase(
            "live.filed-list",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("filed-list.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        _RegisteredExecutorConformanceCase(
            "live.iva-wallet.capture",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("iva-wallet.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        _RegisteredExecutorConformanceCase(
            "live.iva-wallet.evidence-capture",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("iva-evidence.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        _RegisteredExecutorConformanceCase(
            "live.iva-wallet.history-capture",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("iva-history.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        _RegisteredExecutorConformanceCase(
            "live.justificante.capture",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("justificante-capture.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        _RegisteredExecutorConformanceCase(
            "live.notifications.capture",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("notifications-capture.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        _RegisteredExecutorConformanceCase(
            "live.notifications.document.capture",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("notification-document-capture.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        _RegisteredExecutorConformanceCase(
            "live.verify.nif-iva", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "live.verify.tgvi", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "live.verify.list", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "live.verify.view", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "live.verify.latest", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "live.justificante.list",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("justificante-list.read", "justificante-list.result"),
        ),
        _RegisteredExecutorConformanceCase(
            "live.justificante.show",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("justificante-show.read", "justificante-show.result"),
        ),
        _RegisteredExecutorConformanceCase(
            "live.expedientes.list",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("expedientes-list.read", "expedientes-list.result"),
        ),
        _RegisteredExecutorConformanceCase(
            "live.expedientes.show",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("expedientes-show.read", "expedientes-show.result"),
        ),
        _RegisteredExecutorConformanceCase(
            "live.expedientes.latest",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("expedientes-latest.read", "expedientes-latest.result"),
        ),
        _RegisteredExecutorConformanceCase(
            "live.notifications.list",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("notifications-list.read", "notifications-list.result"),
        ),
        _RegisteredExecutorConformanceCase(
            "live.notifications.show",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("notifications-show.read", "notifications-show.result"),
        ),
        _RegisteredExecutorConformanceCase(
            "live.notifications.latest",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("notifications-latest.read", "notifications-latest.result"),
        ),
        _RegisteredExecutorConformanceCase(
            "live.notifications.document.view",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("notification-document-view.read", "notification-document-view.result"),
        ),
        _RegisteredExecutorConformanceCase(
            "live.notifications.document.history",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("notification-document-history.read", "notification-document-history.result"),
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.reconcile.list",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("modelo.reconcile.list",),
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.filing_record.view", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.filing_record.list", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.verification_report.list", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.verification_report.view", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.observation.local", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.filing_record.import", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            # The isolated settings name no Drive root folder, so the production
            # transport refuses while planning, before any remote call.
            "export.google-sheets",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (
                "export.google-sheets.preflight",
                "export.google-sheets.plan",
            ),
            expected_refusal_ref="REFUSED_GOOGLE_SHEETS_EXPORT_ROOT_FOLDER_REQUIRED",
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.censo-review", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.censo-prepare", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.censo-file-import", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.censo-preview",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.reconcile.import",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            expected_refusal_ref="REFUSED_RECONCILIATION_EVIDENCE_INVALID",
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.reconcile.pull",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("modelo-reconcile-pull.prepare",),
            expected_refusal_ref="REFUSED_LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NOT_FOUND",
        ),
        # Verify against a closed runtime endpoint: the executor settles its
        # typed not-ready outcome and changes nothing on the host.
        _RegisteredExecutorConformanceCase(
            "local-reader.provision", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.rename", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.metadata", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.create",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("modelo.work.create",),
            expected_refusal_ref=MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE,
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.list", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("modelo.work.list",)
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.history",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("modelo.work.history",),
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.filing_record", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.review",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("modelo.work.review",),
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.amendment_context", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,),
        ),
        _RegisteredExecutorConformanceCase(
            WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID,),
        ),
        _RegisteredExecutorConformanceCase(
            WORKFLOW_RESUME_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (WORKFLOW_RESUME_OPERATION_DEFINITION_ID,),
        ),
        _RegisteredExecutorConformanceCase(
            MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,),
        ),
        _RegisteredExecutorConformanceCase(
            "overview.pipeline", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("overview.pipeline",)
        ),
        *(
            _RegisteredExecutorConformanceCase(
                definition_id,
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.NONE,
                (definition_id,),
            )
            for definition_id in OVERVIEW_READ_DEFINITION_IDS.values()
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.wizard_context",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("modelo.work.wizard_context",),
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.revision", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.revision_snapshot", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.revisions", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        _RegisteredExecutorConformanceCase(
            MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,),
            expected_refusal_ref="REFUSED_TAXATION_COMPARISON",
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.review_package.build",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("modelo.review_package.build.preconditions",),
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.m303_attestation",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("modelo.work.m303_attestation.preconditions",),
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.counterparty",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.counterparty",),
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.remove", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.remove",)
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.import", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.import",)
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.add", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, ("ledger.add",)
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.allocate", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, ("ledger.allocate",)
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.classify.single",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.classify.single",),
        ),
        _RegisteredExecutorConformanceCase(
            LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,),
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.evidence.add",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.evidence.add",),
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.evidence.list",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("ledger.evidence.list",),
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.evidence.view",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("ledger.evidence.view",),
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.evidence.update",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.evidence.update",),
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.evidence.remove",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.evidence.remove",),
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.evidence.reader-readiness",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("ledger.evidence.reader-readiness",),
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.evidence.extract",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("ledger.evidence.extract",),
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.evidence.confirm",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.evidence.confirm",),
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.split.manual",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.split.manual",),
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.merge",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.merge",),
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.update", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, ("ledger.update",)
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.attach", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, ("ledger.attach",)
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.detach", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, ("ledger.detach",)
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.reset", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, ("ledger.reset",)
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.status", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.status",)
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.check", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.check",)
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.preflight", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.preflight",)
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.history", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.history",)
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.view", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.view",)
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.track", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.track",)
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.list", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.list",)
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.invoice.add", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, ("ledger.invoice.add",)
        ),
        _RegisteredExecutorConformanceCase(
            MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.aggregate", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        *(
            _RegisteredExecutorConformanceCase(
                f"ledger.bienes_inversion.{action}",
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.NONE if action == "list" else OperationEffect.UPDATED,
                (f"ledger.bienes_inversion.{action}",),
            )
            for action in ("list", "declare")
        ),
        *(
            _RegisteredExecutorConformanceCase(
                f"ledger.prorrata.{action}",
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.NONE if action == "list" else OperationEffect.UPDATED,
            )
            for action in (
                "list",
                "declare_sector",
                "elect_especial",
                "elect_general",
                "revoke_especial",
                "seed",
                "seed_sector",
                "settle_sector",
            )
        ),
        *(
            _RegisteredExecutorConformanceCase(
                definition_id,
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.NONE if definition_id == "ledger.inventory.list" else OperationEffect.UPDATED,
                (definition_id,),
            )
            for definition_id in (
                "ledger.inventory.list",
                "ledger.inventory.create",
                "ledger.inventory.movement.add",
                "ledger.inventory.valuation.preview",
                "ledger.inventory.closing-authority.record",
            )
        ),
        *(
            _RegisteredExecutorConformanceCase(
                f"ledger.actividad-asset.{action}",
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.UPDATED if action in {"create", "correct", "claim"} else OperationEffect.NONE,
                (f"ledger.actividad-asset.{action}",),
            )
            for action in ("create", "inspect", "correct", "forecast", "claim", "filing-handoff")
        ),
        _RegisteredExecutorConformanceCase(
            "user-profile.recovery.status",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("user-profile.recovery.status",),
        ),
        _RegisteredExecutorConformanceCase(
            INVOICE_LIST_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (INVOICE_LIST_OPERATION_DEFINITION_ID,),
        ),
        _RegisteredExecutorConformanceCase(
            INVOICE_VIEW_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (INVOICE_VIEW_OPERATION_DEFINITION_ID,),
        ),
        _RegisteredExecutorConformanceCase(
            INVOICE_REMOVE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (INVOICE_REMOVE_OPERATION_DEFINITION_ID,),
        ),
        _RegisteredExecutorConformanceCase(
            INVOICE_UPDATE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (INVOICE_UPDATE_OPERATION_DEFINITION_ID,),
        ),
        _RegisteredExecutorConformanceCase(
            IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID,),
        ),
        _RegisteredExecutorConformanceCase(
            MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (
                "modelo.iva-wallet.correct.commit",
                "modelo.iva-wallet.correct.result",
            ),
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.iva-wallet.balance",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("modelo.iva-wallet.balance.read",),
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.iva-wallet.seed",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("modelo.iva-wallet.seed.commit", "modelo.iva-wallet.seed.result"),
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.iva-wallet.override",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("modelo.iva-wallet.override.commit", "modelo.iva-wallet.override.result"),
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.participation",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("ledger.participation",),
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.participation.rebuild",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.participation.rebuild",),
        ),
        _RegisteredExecutorConformanceCase(
            "ledger.review", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.review",)
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.discard", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            # Calculated from the unit's (empty) ledger aggregation: the M130
            # revision marks no casilla required, so one revision is persisted.
            "modelo.work.calculate",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("modelo.work.calculate.ledger",),
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.wizard_attempt",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("modelo.work.wizard_attempt",),
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.verify", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.file", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.edit.apply", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.export", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        _RegisteredExecutorConformanceCase(
            MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
        ),
        _RegisteredExecutorConformanceCase(
            "modelo.work.amend", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
    )
}
"""The settlement each registered executor is expected to reach.

Keyed by definition id, never ordered or counted. Coverage is asserted
against the live registry below, so an operation that gains a definition
without gaining a scenario fails by name instead of by tally."""


@dataclass(slots=True)
class _CloseWitness:
    """Observe cleanup owned by the actual CENSO executor."""

    closed: bool = False

    async def close(self) -> None:
        self.closed = True


class _HeldClock:
    """A supervisor clock that stands still until released, then reads real time.

    The supervisor measures its execution deadline on this clock, so while it
    is held no amount of host slowness can expire the deadline before the
    executor has suspended at its review.
    """

    def __init__(self) -> None:
        self._held_at: datetime | None = now()

    def __call__(self) -> datetime:
        return now() if self._held_at is None else self._held_at

    def release(self) -> None:
        self._held_at = None


@dataclass(slots=True)
class _ExecutionDriver:
    """Single registered execution driver over the canonical composed supervisor."""

    services: OperationComposedServices

    async def prepare(self, *, definition_id: str, subject_ref: str, payload: BaseModel, secret: bytes | None = None):
        submitted = await self.services.submission.submit(
            OperationRequest(definition_id=definition_id, subject_ref=subject_ref, payload=payload),
            actor_ref=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        )
        requirement = submitted.receipt.secret_requirement
        if requirement is not None:
            assert secret is not None
            buffer = bytearray(secret)
            await self.services.submission.submit_secret(requirement, buffer)
            assert buffer == bytearray(len(secret))
        else:
            assert secret is None
        return submitted

    async def run(self, *, definition_id: str, subject_ref: str, payload: BaseModel, secret: bytes | None = None):
        submitted = await self.prepare(
            definition_id=definition_id,
            subject_ref=subject_ref,
            payload=payload,
            secret=secret,
        )
        before_start = await self.observe(submitted.receipt.operation_id)
        cancellation = await self.services.cancellation.request(
            OperationCancellationRequestV1(
                operation_id=submitted.receipt.operation_id, expected_revision=before_start.projection.revision
            )
        )
        assert isinstance(cancellation, OperationCancellationRefusalV1)
        await self.services.submission.start(submitted.receipt.operation_id)
        await self.services.submission.settled(submitted.receipt.operation_id)
        return submitted, await self.observe(submitted.receipt.operation_id)

    async def observe(self, operation_id: str) -> OperationObservationSuccessV1:
        observed = await self.services.observation.observe(
            OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=256)
        )
        assert isinstance(observed, OperationObservationSuccessV1)
        return observed

    async def respond_apply(self, submitted: OperationSubmission, observed: OperationObservationSuccessV1) -> str:
        pending = observed.projection.pending_interaction
        assert isinstance(pending, OperationReviewAvailableInteractionV1)
        response = await self.services.response(
            OperationResponseControlRequestV1(
                operation_id=pending.operation_id,
                interaction_id=pending.interaction_id,
                revision=pending.revision,
                actor_ref=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            ),
            submitted.response_capability,
        )
        accepted = await response.apply(
            OperationResponseApplyRequestV1(
                operation_id=pending.operation_id,
                interaction_id=pending.interaction_id,
                revision=pending.revision,
                actor_ref=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                responded_at=now(),
            )
        )
        assert isinstance(accepted, OperationResponseMutationSuccessV1)
        return pending.operation_id

    async def apply_review(
        self, submitted: OperationSubmission, observed: OperationObservationSuccessV1
    ) -> OperationObservationSuccessV1:
        operation_id = await self.respond_apply(submitted, observed)
        return await self.await_terminal(operation_id)

    async def await_terminal(self, operation_id: str) -> OperationObservationSuccessV1:
        """Observe a public terminal projection after real executor work completes."""
        for _ in range(100):
            observed = await self.observe(operation_id)
            if observed.projection.lifecycle is OperationLifecycle.TERMINAL:
                return observed
            await asyncio.sleep(0)
        raise AssertionError("review continuation did not settle")

    async def review_not_pending(self, *, operation_id: str, revision: int, registry: OperationRegistry) -> None:
        """Prove the public REVIEW control truthfully refuses an operation without a pending review."""
        review_contract = registry.lookup_public_contract("user-profile.censo-review")
        assert review_contract.review_projection_schema is not None
        result = await self.services.review.resolve(
            OperationReviewProjectionRequestV1(
                reference=OperationReviewProjectionReferenceV1(
                    operation_id=operation_id,
                    interaction_id="0" * 64,
                    revision=revision,
                    review_projection_schema=review_contract.review_projection_schema,
                    definition_contract_digest=review_contract.definition_contract_digest,
                    expires_at=None,
                )
            ),
            CensalReviewProjectionV1,
        )
        assert isinstance(result, OperationReviewProjectionRefusalV1)
        assert result.code is OperationReviewProjectionRefusalCode.REVIEW_NOT_PENDING


def _resolve_result_projection(
    driver: _ExecutionDriver,
    registry: OperationRegistry,
    *,
    definition_id: str,
    operation_id: str,
    terminal_revision: int,
    projection_type: type[BaseModel],
) -> BaseModel:
    """Resolve one typed public result through encrypted operand custody."""
    contract = registry.lookup_public_contract(definition_id)
    assert contract.result_schema is not None
    result = asyncio.run(
        driver.services.result.resolve(
            OperationResultProjectionRequestV1(
                operation_id=operation_id,
                terminal_revision=terminal_revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=contract.result_schema,
            ),
            projection_type,
        )
    )
    assert isinstance(result, OperationResultProjectionSuccessV1)
    assert isinstance(result.projection, projection_type)
    return result.projection


def _observation() -> CensalObservation:
    return CensalObservation(
        identity=CensalObservationIdentity(nif="12345678Z"),
        domicilio_fiscal=CensalObservationAddress(
            tipo_via="CALLE",
            nombre_via="Mayor",
            numero_casa="7",
            codigo_postal="28013",
            referencia_catastral="1234567VK4713C0001AB",
        ),
        domicilio_notificacion=CensalObservationAddress(),
        captured_at=datetime(2026, 8, 24, 18, tzinfo=UTC),
        source_url=aeat_url("sede", "/censo/consulta"),
    )


def _seeded_modelo_filing_record(profile_id: UUID, *, operation: PinnedAuthorityOperation) -> tuple[str, str]:
    """File one real revision and return its filing-record and casilla ids.

    Amendment corrects something already FILED, so its fixture cannot stop at a
    verified revision: it needs the filing record that amendment is addressed
    to. Reached through the same filing authority the `file` operation uses, so
    the record amendment corrects is one the product actually produces.

    The casilla is taken from the revision's own declared inputs rather than
    named, for the reason the edit fixture gives: the M130 casilla mapping is
    revision-scoped, and a literal here would be silently wrong the moment the
    governing revision changes.
    """
    unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
    revision = resolved_revision(
        modelo=modelo_operation_test_support.MODELO,
        filing_year=modelo_operation_test_support.MODELO_FILING_YEAR,
        period=modelo_operation_test_support.MODELO_PERIOD,
    )
    casilla_id = sorted(casilla.id for casilla in revision.casillas)[0]
    evidence_reference_id = f"CSV{modelo_operation_test_support.MODELO}{modelo_operation_test_support.MODELO_FILING_YEAR}{modelo_operation_test_support.MODELO_PERIOD}".upper()
    # The unit is created at the live clock, so the evidence cannot be stamped
    # with the profile's fixed seeding clock: the catalogue refuses a work unit
    # whose updated_at precedes its created_at, and rightly so.
    evidence_clock = now()

    # Amendment refuses a baseline with no external evidence
    # (`AmendmentEvidenceMissingError`), and that refusal is correct: an
    # amendment corrects a return the authority already holds, so the baseline
    # has to be one AEAT evidenced rather than one this process filed locally.
    # The record therefore comes through the external-import door, exactly as
    # the cross-period seeder produces its own sources.
    persist_justificante_metadata(
        evidence_reference_id,
        modelo=modelo_operation_test_support.MODELO,
        filing_year=modelo_operation_test_support.MODELO_FILING_YEAR,
        period=modelo_operation_test_support.MODELO_PERIOD,
        captured_at=evidence_clock,
        tax_id=SEEDED_SOURCE_TAX_ID,
    )
    record = import_external_filing_evidence(
        work_unit_id=unit.work_unit_id,
        casilla_values={casilla_id: Decimal("100")},
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id=evidence_reference_id,
        actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        filing_repository=ModeloRecordCatalogueRepository(),
        bucket_event_repository=BucketEventHistoryRepository(),
        observation_repository=CalculationObservationRepository(),
        expected_tax_id=SEEDED_SOURCE_TAX_ID,
        clock=evidence_clock,
    ).filing_record
    return str(record.filing_record_id), str(casilla_id)


def _seeded_ledger_track_with_finalized_participation(profile_id: UUID, *, operation: PinnedAuthorityOperation) -> str:
    """Create one ledger transaction consumed by a real, verified calculation."""
    unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
    seed_clean_cross_period_sources(
        unit,
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        filing_repository=ModeloRecordCatalogueRepository(),
        bucket_event_repository=BucketEventHistoryRepository(),
        operation=operation,
    )
    ledger_ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=str(profile_id),
            booked_date=date(2025, 1, 15),
            amount=Decimal("12.00"),
            direction=TransactionDirection.INCOMING,
            description="conformance track participation seed",
            business_classification=BusinessClassification.BUSINESS,
            taxable_base=Decimal("12.00"),
            iva_rate=Decimal("0"),
            iva_amount=Decimal("0"),
            actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        ),
        ports=ledger_ports,
        occurred_at=now(),
    )
    transaction_id = created.ref.transaction_id
    calculation = calculate_modelo_revision(
        unit.work_unit_id,
        ports=build_calculation_action_ports(bucket_id=unit.bucket_id, operation=operation),
        actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        casilla_inputs={},
        binding_values=modelo_operation_test_support.FIRST_QUARTER_PRIOR_PERIOD_BINDINGS,
        source_transaction_ids=(transaction_id,),
    )
    report = verify_modelo_revision(
        calculation.calculation_revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        verification_repositories=build_verification_repository_bundle(unit.bucket_id, operation=operation),
        actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        workflow_profile=resolve_active_workflow_profile(operation),
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        operation=operation,
    )
    if report.completeness_status is not VerificationCompletenessStatus.COMPLETE:
        findings = "; ".join(finding.kind.value for finding in report.findings) or "no findings reported"
        raise AssertionError(f"track participation seed did not verify completely: {findings}")
    persisted = (
        CalculationRevisionCatalogueRepository().load(operation=operation).get(calculation.calculation_revision_id)
    )
    assert persisted is not None
    assert persisted.source_transaction_ids == (transaction_id,)
    assert persisted.state is CalculationRevisionState.VERIFICADO_COMPLETO
    index = TransactionParticipationIndexRepository(bucket_id=str(profile_id)).load(transaction_id)
    assert len(index.participations) == 1
    assert index.participations[0].calculation_revision_id == persisted.calculation_revision_id
    return transaction_id


def _seeded_modelo_edit_submission(profile_id: UUID, *, operation: PinnedAuthorityOperation) -> tuple[str, object]:
    """Build one canonical edit DTO over the revision this fixture just persisted."""
    from ...adapters.persistence.profile.modelos_calculation import (
        CalculationRevisionCatalogueRepository,
    )
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
    from ...application.modelo.edit_contract import ModeloEditCompatibilityTupleV1, ModeloEditMutationFamily
    from ...application.modelo.edit_models import (
        ModeloEditBaselineV1,
        ModeloEditScalarAddressV1,
        ModeloEditScalarIntentKind,
        ModeloEditSchemaIdentityV1,
        ModeloEditSubmissionV1,
        ModeloEditWritableScalarSurfaceEntryV1,
        ModeloScalarEditIntentV1,
    )
    from ...application.modelo.operation_definitions import ModeloEditApplySubmissionV1
    from ...application.operations.registry import OperationSchemaIdentityV1
    from ...core.casilla_id import validated_casilla_id
    from ...core.hashing import content_hash_hex
    from ...domain.calculations.registry.schema_base import CasillaDataType

    unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
    seeded_casilla_id = validated_casilla_id("06")
    with bundled_indexed_authority().operation() as operation:
        revision = calculate_modelo_revision(
            unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=unit.bucket_id, operation=operation),
            actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            casilla_inputs={seeded_casilla_id: Decimal("0")},
            binding_values=modelo_operation_test_support.FIRST_QUARTER_PRIOR_PERIOD_BINDINGS,
        )
    objects = secure_object_repository_for_active_bucket()
    work_catalogue = WorkUnitCatalogueRepository(objects=objects).load()
    calculation_catalogue = CalculationRevisionCatalogueRepository(objects=objects).load()
    current_unit = work_catalogue.get(unit.work_unit_id)
    if current_unit is None:
        raise AssertionError("the edit conformance fixture lost its seeded work unit")
    casilla_id = next(iter(revision.input_values_by_casilla_id))
    identity = OperationSchemaIdentityV1(
        schema_id="modelo.edit.contract", schema_version=1, schema_fingerprint="a" * 64
    )
    compatibility = ModeloEditCompatibilityTupleV1(
        contract_set_digest="a" * 64,
        operation_definition_id="modelo.calculate",
        definition_contract_digest="a" * 64,
        request_schema=identity,
        result_schema=identity,
        review_projection_contract_version=None,
        review_schema=None,
        workspace_refresh_target_schema=identity,
        financial_operand_schema=identity,
    )
    permitted_surface = (
        ModeloEditWritableScalarSurfaceEntryV1(
            casilla_id=casilla_id,
            data_type=CasillaDataType.MONEY,
            allowed_intents=(
                ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE,
            ),
        ),
    )
    issued_at = datetime.now(UTC)
    baseline = ModeloEditBaselineV1(
        compatibility=compatibility,
        bucket_id=current_unit.bucket_id,
        modelo=current_unit.modelo,
        filing_year=current_unit.filing_year,
        period=current_unit.period,
        work_unit_id=current_unit.work_unit_id,
        work_catalogue_revision=content_hash_hex(work_catalogue.model_dump(mode="json")),
        calculation_catalogue_revision=content_hash_hex(calculation_catalogue.model_dump(mode="json")),
        current_calculation_revision_id=revision.calculation_revision_id,
        law_selected_revision_id=current_unit.revision_id,
        schema_identity=ModeloEditSchemaIdentityV1(
            schema_id="modelo-edit-conformance",
            schema_fingerprint=content_hash_hex(revision.registry_snapshot_ref.model_dump(mode="json")),
            completeness_manifest_digest=content_hash_hex({"fixture": "calculated-revision"}),
        ),
        schema_version=1,
        permitted_surface=permitted_surface,
        permitted_surface_digest=content_hash_hex([entry.model_dump(mode="json") for entry in permitted_surface]),
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        issued_at=issued_at,
        expires_at=issued_at + timedelta(minutes=15),
        baseline_id=content_hash_hex(
            {"work_unit_id": current_unit.work_unit_id, "revision_id": revision.calculation_revision_id}
        ),
    )
    submission = ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        scalar_intents=(
            ModeloScalarEditIntentV1(
                address=ModeloEditScalarAddressV1(casilla_id=casilla_id),
                kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                value="100.00",
            ),
        ),
    )
    return unit.work_unit_id, ModeloEditApplySubmissionV1.from_submission(submission)


def _profile_baseline(profile_id: UUID, *, decode_context: ProfileDecodeContext) -> dict[str, object]:
    """Use the actual encrypted record's CAS coordinates for a manager write."""
    record = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=decode_context).load(
        profile_id
    )
    return {"expected_revision": record.record_revision, "expected_content_digest": record.content_digest}


def _seeded_repeatable_row(
    profile_id: UUID, *, operation: PinnedAuthorityOperation, decode_context: ProfileDecodeContext
) -> tuple[str, dict[str, object]]:
    """Create a real schema row so update/remove target a stored identity."""
    baseline = _profile_baseline(profile_id, decode_context=decode_context)
    mutation = add_profile_repeatable_section_row(
        profile_id=str(profile_id),
        section_key="activities",
        values={"description": "Consultoria"},
        expected_revision=cast(int, baseline["expected_revision"]),
        expected_content_digest=cast(str, baseline["expected_content_digest"]),
        schema=operation.profile_schema(),
        profile_decode_context=decode_context,
    )
    return str(mutation.row_index), {
        "expected_revision": mutation.record.record_revision,
        "expected_content_digest": mutation.record.content_digest,
    }


def _workflow_obligation(modelo: str, period: Period) -> WorkflowObligationFacts:
    """Build a locale-neutral, period-consistent run obligation for encrypted fixtures."""
    return WorkflowObligationFacts(
        modelo=Modelo(modelo),
        period=period,
        opens_on=date(period.filing_year, 1, 1),
        closes_on=date(period.filing_year, 12, 31),
        status=ObligationStatus.UPCOMING,
    )


def _workflow_result(
    run_id: str,
    *,
    modelo: str,
    period: Period,
    started_at: datetime,
    aborted_reason: WorkflowAbortReason | None = None,
) -> WorkflowResult:
    """Create one valid persisted terminal record without private prose."""
    obligation = _workflow_obligation(modelo, period)
    if aborted_reason is None:
        return WorkflowResult(
            run_id=run_id,
            started_at=started_at,
            ended_at=started_at,
            final_stage=WorkflowStage.DONE,
            obligation=obligation,
            steps=(),
            summary_locale_key="application.workflow.results.completed",
        )

    condition_id = "workflow.execution.completed"
    verdict = PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(
            ConditionEvidence(
                condition_id=condition_id,
                evidence_id="workflow.execution.error_code",
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                values={"completed": False, "error_code": "workflow.execution.site_unavailable"},
            ),
        ),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )
    step = WorkflowStep(
        stage=WorkflowStage.BUILDING_DRAFT,
        started_at=started_at,
        ended_at=started_at,
        success=False,
        summary_locale_key="application.workflow.steps.workflow_failure",
        precondition_verdict=verdict,
    )
    return WorkflowResult(
        run_id=run_id,
        started_at=started_at,
        ended_at=started_at,
        final_stage=WorkflowStage.ABORTED,
        aborted_reason=aborted_reason,
        obligation=obligation,
        steps=(step,),
        summary_locale_key="application.workflow.results.aborted",
    )


def _seeded_justificante_snapshot(profile_id: UUID):
    """Persist one synthetic receipt for local list/show executor scenarios."""
    pdf_bytes = b"%PDF-1.4\nregistered executor conformance\n%%EOF"
    return build_justificante_capture_service(str(profile_id)).capture(
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        expediente_id="202613000010001A",
        csv="ABCD1234EFGH5678",
        pdf_bytes=pdf_bytes,
        pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        captured_at=now(),
    )


def _seeded_expedientes_snapshot(profile_id: UUID):
    """Persist one synthetic declaration-register snapshot without opening AEAT."""
    bucket_id = str(profile_id)
    captured_at = now()
    capture = ExpedientesCapture(
        declarations=(
            ExpedientesDeclaration(
                modelo="303",
                ejercicio=2025,
                period=Period.from_year_and_code(2025, "1T"),
                expediente_id="12345678901234567890",
                estado="ALTA",
                tipo_solicitud="Presentación",
                observaciones="Conformance snapshot",
                presented_at=captured_at,
                justificante_link_text="Justificante",
                archive_link_text="Archivo",
                declaration_copy_link_text="Copia",
            ),
        ),
        captured_at=captured_at,
        source_url=str(aeat_url("sede", "/declaraciones")),
        authenticated_identity="12345678Z",
    )
    return ExpedientesService(ports=build_expedientes_ports(bucket_id=bucket_id)).capture(
        bucket_id=bucket_id,
        capture=capture,
    )


def _seeded_notifications_snapshot(profile_id: UUID):
    """Persist one synthetic local notification snapshot; its query port is never called."""
    captured_at = now()
    return NotificationsService(ports=compose_notifications_ports(settings=load_settings())).capture(
        bucket_id=str(profile_id),
        snapshot=NotificationsSnapshot(
            rows=(
                RemoteNotification(
                    certificado_id="1234567890",
                    tipo=NotificationType.NOTIFICACION,
                    concepto="Conformance notification",
                    titular_nif="12345678Z",
                    titular_nombre="Synthetic taxpayer",
                    destinatario_nif="12345678Z",
                    destinatario_nombre="Synthetic taxpayer",
                    fecha_emision=captured_at.date(),
                    fecha_notificacion=None,
                    modo_notificacion=None,
                    leida=False,
                    source_url="https://sede.example/notification/1234567890",
                ),
            ),
            captured_at=captured_at,
            source_url="https://sede.example/notifications",
        ),
        authenticated_identity="12345678Z",
    )


def _seeded_notification_document(profile_id: UUID) -> NotificationDocumentRecord:
    """Persist one synthetic document custody index row for local read scenarios."""
    certificado_id = "2699101808461"
    digest = "c" * 64
    record = NotificationDocumentRecord(
        certificado_id=certificado_id,
        bucket_id=str(profile_id),
        attachment_id=digest,
        document_sha256=digest,
        byte_size=4096,
        source_url=f"https://sede.example/notification/{certificado_id}",
        fetched_at=now(),
        sancion=SancionLiquidacion(
            certificado_id=certificado_id,
            clave_liquidacion="A2860024500012345",
            referencia="2024/0001234",
            nif="12345678Z",
            objeto_tributario="sancion",
            base_sancion=Decimal("3687.120"),
            porcentaje_minimo=Decimal("50.00"),
            sancion_resultante=Decimal("1843.560"),
            reduccion_conformidad=Decimal("553.070"),
            reduccion_pronto_pago=Decimal("516.20"),
            diferencia=Decimal("774.290"),
            importe_a_ingresar=Decimal("774.290"),
            document_sha256=digest,
        ),
    )
    notification_document_repository(str(profile_id), load_settings()).save(record)
    return record


def _ledger_lifecycle_case(
    definition_id: str, *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> LedgerLifecycleOperationConformanceCase:
    operation_ids: tuple[LedgerLifecycleOperationId, ...] = (
        "ledger.archive",
        "ledger.stash",
        "ledger.restore",
        "ledger.exclude",
    )
    for operation_id in operation_ids:
        if definition_id == operation_id:
            return prepare_ledger_lifecycle_operation_conformance_case(operation_id, profile_id, operation=operation)
    raise ValueError(f"unsupported ledger lifecycle conformance case: {definition_id}")


def _prorrata_case(
    definition_id: str, *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> ProrrataOperationConformanceCase:
    return prepare_prorrata_operation_conformance_case(
        definition_id,
        profile_id,
        repository_factory=build_prorrata_register_repository,
        operation=operation,
        observation_repository=(
            build_calculation_action_ports(bucket_id=str(profile_id), operation=operation).observation_repository
            if definition_id == "ledger.prorrata.seed"
            else None
        ),
    )


def _payload(
    definition: OperationDefinition, *, profile_id: UUID, tmp_path: Path, operation: PinnedAuthorityOperation
) -> tuple[str, BaseModel, bytes | None]:
    """Use only the exact request type exported by the registered definition."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    values: dict[str, object]
    secret: bytes | None = None
    subject_ref = f"profile:{profile_id}"
    if definition.definition_id in {
        "ledger.evidence.reader-readiness",
        "ledger.evidence.extract",
        "ledger.evidence.confirm",
    }:
        evidence_case = prepare_invoice_evidence_conformance_case(
            definition.definition_id, profile_id=profile_id, operation=operation
        )
        return profile_operation_subject(str(profile_id)), evidence_case.request, None
    if definition.definition_id.startswith("ledger.prorrata."):
        prorrata_case = _prorrata_case(definition.definition_id, profile_id=profile_id, operation=operation)
        return profile_operation_subject(str(profile_id)), prorrata_case.request, None
    if definition.definition_id == "modelo.aggregate":
        return (
            profile_operation_subject(str(profile_id)),
            ModeloAggregateOperationRequest.from_inputs(
                profile_id=profile_id, command=aggregate_conformance_command(operation=operation)
            ),
            None,
        )
    if definition.definition_id == MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID:
        withholding_seed = seed_invoice_withholding_conformance_case(profile_id, operation=operation)
        return profile_operation_subject(str(profile_id)), withholding_seed.request, None
    if definition.definition_id in {item.definition_id for item in build_automation_operation_definitions()}:
        # The default production graph has no trusted runtime owner. The
        # dedicated administration integration suite proves positive execution
        # of every member with real custody and an explicitly bound owner.
        return (
            subject_ref,
            definition.request_type.model_validate({"profile_id": profile_id, "request_id": UUID(int=1)}),
            b"synthetic" if definition.ephemeral_secret is not None else None,
        )
    match definition.definition_id:
        case "auth.local-read":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "kind": "diagnostics_list"}
        case "auth.profile.login":
            values = {"profile_id": profile_id}
            secret = _CREDENTIAL_INPUT.encode()
        case "auth.profile.passphrase-rotate":
            values = {"profile_id": profile_id}
            secret = (
                '{"current_passphrase":"'
                + _CREDENTIAL_INPUT
                + '","new_passphrase":"'
                + _ROTATED_CREDENTIAL_INPUT
                + '","new_passphrase_confirmation":"'
                + _ROTATED_CREDENTIAL_INPUT
                + '"}'
            ).encode()
        case "auth.provider.configure":
            values = {"provider": AuthProviderKind.CERTIFICATE}
        case "auth.session.acquire":
            values = {}
        case (
            "auth.certificate.source.register"
            | "auth.certificate.source.list"
            | "auth.certificate.source.select"
            | "auth.certificate.source.remove"
            | "auth.certificate.source.check"
            | "auth.certificate.secret.set"
            | "auth.certificate.secret.remove"
        ):
            source_name = "supervisor-certificate"
            source_path = tmp_path / "absent-certificate.p12"
            if definition.definition_id != "auth.certificate.source.register":
                register_operator_certificate_source(
                    name=source_name,
                    certificate_path=source_path,
                    operation=operation,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                )
            values = {"profile_id": profile_id}
            if definition.definition_id not in {"auth.certificate.source.list", "auth.certificate.source.check"}:
                values["name"] = source_name
            if definition.definition_id == "auth.certificate.source.register":
                values["certificate_path"] = source_path
            if definition.definition_id == "auth.certificate.secret.set":
                secret = _CREDENTIAL_INPUT.encode()
            elif definition.definition_id == "auth.certificate.secret.remove":
                set_operator_certificate_source_secret(
                    name=source_name,
                    secret=SecretStr(_CREDENTIAL_INPUT),
                    certificate_secret_backend_factory=build_certificate_secret_backend,
                    operation=operation,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                )
        case "ledger.ratios.list" | "ledger.ratios.eligible":
            values = {"profile_id": profile_id, "year": 2025}
        case "ledger.ratios.validate":
            values = {"profile_id": profile_id}
        case "ledger.ratios.set":
            values = {"profile_id": profile_id, "year": 2025, "category": "vehiculo_combustible", "ratio": "0.5"}
        case "ledger.ratios.unset":
            category = require_spending_category("vehiculo_combustible", authority=operation)
            save_usage_ratio_profile(
                UsageRatioProfile(ratios={category: Decimal("0.50")}),
                bucket_id=str(profile_id),
            )
            values = {"profile_id": profile_id, "category": "vehiculo_combustible"}
        case "auth.session.logout" | "auth.session.reset":
            values = {"all_providers": True}
        case "user-profile.field-mutation":
            values = {
                "profile_id": profile_id,
                **_profile_baseline(profile_id, decode_context=_profile_decode_context_for_test),
                "path": PROFILE_OUTPUT_LANGUAGE_PATH,
                "value": "es",
            }
        case "user-profile.patch":
            values = {
                "profile_id": profile_id,
                **_profile_baseline(profile_id, decode_context=_profile_decode_context_for_test),
                "colegio_concertado": True,
            }
        case "user-profile.plantilla-media":
            values = {
                "profile_id": profile_id,
                **_profile_baseline(profile_id, decode_context=_profile_decode_context_for_test),
                "year": 2025,
                "change": {"kind": "set", "average_workforce": "2.50", "state": PlantillaMediaState.OBSERVED},
            }
        case "user-profile.descendants":
            values = {
                "profile_id": profile_id,
                **_profile_baseline(profile_id, decode_context=_profile_decode_context_for_test),
                "descendants": (),
            }
        case "user-profile.complete-setup":
            values = {
                "profile_id": profile_id,
                **_profile_baseline(profile_id, decode_context=_profile_decode_context_for_test),
            }
        case "user-profile.view":
            values = {"profile_id": profile_id, "page_kind": ProfileViewPageKind.FACTS}
        case "workbench.generation":
            values = {"profile_id": profile_id, "output_language": OutputLanguage.ES}
        case "user-profile.repeatable-row-mutation":
            values = {
                "profile_id": profile_id,
                **_profile_baseline(profile_id, decode_context=_profile_decode_context_for_test),
                "section_key": "activities",
                "values": ({"field_key": "description", "value": "Consultoria"},),
            }
        case "user-profile.repeatable-row-update" | "user-profile.repeatable-row-remove":
            row_key, baseline = _seeded_repeatable_row(
                profile_id, operation=operation, decode_context=_profile_decode_context_for_test
            )
            values = {
                "profile_id": profile_id,
                **baseline,
                "section_key": "activities",
                "row_key": row_key,
            }
            if definition.definition_id == "user-profile.repeatable-row-update":
                values["values"] = ({"field_key": "description", "value": "Assessoria"},)
        case "user-profile.bundle-export":
            values = {
                "profile_id": profile_id,
                "destination": tmp_path / "profile.bundle",
                "purpose": ProfileBundleExportPurpose.PORTABLE_TRANSFER,
            }
            secret = _CREDENTIAL_INPUT.encode()
        case "user-profile.logout":
            values = {"profile_id": profile_id}
        case "local-reader.provision":
            subject_ref = LOCAL_READER_OPERATION_SUBJECT
            values = {"action": LocalReaderProvisionAction.VERIFY, "role": ModelRole.TEXT_EXTRACTION}
        case "live.expedientes.capture.single":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "modelo": "303", "year": 2025}
        case "live.expedientes.capture.bulk":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "modelos": ("303",), "year_from": 2025, "year_to": 2025}
        case "live.filed-capture.single":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "output_root": tmp_path / "filed-single",
                "modelo": "303",
                "year": 2025,
                "period": "1T",
            }
        case "live.filed-capture.bulk":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "output_root": tmp_path / "filed-bulk",
                "year_from": 2025,
                "year_to": 2025,
                "modelos": ("303",),
            }
        case "live.filed-capture.source":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "output_root": tmp_path / "filed-source",
                "modelo": "303",
                "year": 2025,
                "period": "1T",
            }
        case "live.filed-list":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "modelo": "303", "year_from": 2025, "year_to": 2025}
        case "live.filed-discover":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "live.justificante.list":
            _seeded_justificante_snapshot(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "live.justificante.capture":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "modelo": "130", "year": 2025, "period": "1T"}
        case "live.justificante.show":
            snapshot = _seeded_justificante_snapshot(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "snapshot_id": snapshot.snapshot_id}
        case "live.expedientes.list":
            _seeded_expedientes_snapshot(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "live.expedientes.show":
            snapshot = _seeded_expedientes_snapshot(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "snapshot_id": snapshot.snapshot_id}
        case "live.expedientes.latest":
            _seeded_expedientes_snapshot(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "live.notifications.list" | "live.notifications.latest":
            _seeded_notifications_snapshot(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "live.notifications.show":
            snapshot = _seeded_notifications_snapshot(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "snapshot_id": snapshot.snapshot_id}
        case "live.notifications.document.view":
            record = _seeded_notification_document(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "certificado_id": record.certificado_id}
        case "live.notifications.document.history":
            _seeded_notification_document(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "live.notifications.capture":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "live.notifications.document.capture":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "certificado_id": "2699101808461"}
        case "live.verify.nif-iva" | "live.verify.tgvi":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "nif": "12345678Z"}
        case "live.verify.list" | "live.verify.view" | "live.verify.latest":
            subject_ref = profile_operation_subject(str(profile_id))
            observation = VerifyService(persistence=VerifyObservationRepository(bucket_id=str(profile_id))).record(
                bucket_id=str(profile_id),
                surface=VerifySurface.NIF_IVA,
                nif="12345678Z",
                verdict=IdentityCheckVerdict.VALID,
                checked_at=now(),
            )
            values = {"profile_id": profile_id}
            if definition.definition_id == "live.verify.view":
                values["observation_id"] = observation.observation_id
            elif definition.definition_id == "live.verify.latest":
                values.update(surface=VerifySurface.NIF_IVA, nif="12345678Z")
        case "live.filed-history.pull":
            subject_ref = str(profile_id)
            values = {"output_root": tmp_path / "filed-history", "dry_run": True}
        case "live.iva-wallet.history":
            period = Period.from_year_and_code(2025, "1T")
            history_state = IvaCompensationPeriodState(
                provenance=IvaCompensationStateProvenance.APP_FILING,
                taxpayer_nif="12345678Z",
                filing_year=2025,
                period=period,
                registry_snapshot_ref=operation.snapshot(
                    "303", filing_year=2025, period=period.registry_token
                ).snapshot_ref,
                presented_at=now(),
                prior_pending_amount=Decimal("0"),
                applied_amount=Decimal("0"),
                pending_for_later_amount=Decimal("40.00"),
                period_result_amount=Decimal("-40.00"),
                final_result_amount=Decimal("-40.00"),
                generated_amount=Decimal("40.00"),
                available_end_amount=Decimal("40.00"),
                source_observation_key="conformance:iva-history:2025:1T",
            )
            IvaCompensationHistoryRepository().save_period(history_state)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "as_of_year": 2025}
        case "modelo.iva-wallet.correct":
            period = Period.from_year_and_code(2024, "4T")
            seed_modelo_ready_profile_record(str(profile_id), clock=now(), tax_id=SEEDED_SOURCE_TAX_ID)
            seed_iva_compensation_period(
                taxpayer_nif=SEEDED_SOURCE_TAX_ID,
                period=period,
                amount=Decimal("500.00"),
                repository=IvaCompensationHistoryRepository(bucket_id=str(profile_id)),
                operation=operation,
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "period": PublicPeriod.from_period(period),
                "amount": "1200.50",
                "reason": "corrected opening balance",
            }
        case "modelo.iva-wallet.balance":
            period = Period.from_year_and_code(2024, "4T")
            seed_modelo_ready_profile_record(str(profile_id), clock=now(), tax_id=SEEDED_SOURCE_TAX_ID)
            seed_iva_compensation_period(
                taxpayer_nif=SEEDED_SOURCE_TAX_ID,
                period=period,
                amount=Decimal("500.00"),
                repository=IvaCompensationHistoryRepository(bucket_id=str(profile_id)),
                operation=operation,
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "as_of_year": 2024}
        case "modelo.iva-wallet.seed":
            seed_modelo_ready_profile_record(str(profile_id), clock=now(), tax_id=SEEDED_SOURCE_TAX_ID)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "period": PublicPeriod.from_period(Period.from_year_and_code(2024, "4T")),
                "amount": "500.00",
            }
        case "modelo.iva-wallet.override":
            seed_modelo_ready_profile_record(str(profile_id), clock=now(), tax_id=SEEDED_SOURCE_TAX_ID)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "period": PublicPeriod.from_period(Period.from_year_and_code(2025, "1T")),
                "amount": "450.00",
                "reason": "operator asserted prior compensation",
                "evidence_locator": "synthetic:conformance:prior-compensation",
            }
        case "live.iva-wallet.capture":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "target_year": 2025, "target_period": "1T"}
        case "live.iva-wallet.evidence-capture":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "output_root": tmp_path / "iva-evidence",
                "year_from": 2025,
                "year_to": 2025,
                "target_year": 2025,
                "target_period": "1T",
            }
        case "live.iva-wallet.history-capture":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "output_root": tmp_path / "iva-history-capture",
                "year_from": 2025,
                "year_to": 2025,
            }
        case "export.google-sheets":
            values = {"profile_id": profile_id, "modelo": "130", "filing_year": 2025, "period": "1T", "dry_run": False}
        case "user-profile.censo-review":
            subject_ref = str(profile_id)
            record = ProfileRecordRepository.for_current_session(
                profile_id, profile_decode_context=_profile_decode_context_for_test
            ).load(profile_id)
            values = {
                "baseline": CensalProfileBaseline.from_record(record),
                "field_intents": tuple(
                    CensalReviewedFieldIntent(path=path, intent=CensalFieldIntent.ADOPT)
                    for path in CENSAL_ADOPTABLE_PATHS
                ),
            }
        case "user-profile.censo-prepare":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "user-profile.censo-file-import":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "facts": (
                    {
                        "path": "contact.fiscal_address",
                        "value": "Calle Mayor 1",
                        "source": CensalFileImportProvenance.ARTEFACT,
                    },
                ),
            }
        case "user-profile.censo-preview":
            subject_ref = profile_operation_subject(str(profile_id))
            record = ProfileRecordRepository.for_current_session(
                profile_id, profile_decode_context=_profile_decode_context_for_test
            ).load(profile_id)
            values = {"baseline": CensalProfileBaseline.from_record(record)}
        case "modelo.reconcile.import":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "work_unit_id": unit.work_unit_id,
                "source_kind": ModeloReconciliationEvidenceKind.JUSTIFICANTE,
                "source_path": str(tmp_path / "missing-evidence.pdf"),
            }
        case "modelo.reconcile.pull":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "work_unit_id": unit.work_unit_id, "snapshot_id": "a" * 64}
        case "modelo.reconcile.list":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "work_unit_id": None}
        case "modelo.work.rename":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = unit.work_unit_id
            values = {
                "work_unit_id": unit.work_unit_id,
                "new_name": "Conformance renamed unit",
                "observed_name": unit.name,
                "observed_updated_at": unit.updated_at,
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "modelo.work.metadata":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            values = {"profile_id": profile_id, "work_unit_id": unit.work_unit_id}
        case "modelo.work.create":
            upsert_test_profile_facts(
                profile_id,
                (
                    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                    UserProfileFact(path="identity.name", value="Conformance"),
                    UserProfileFact(path="identity.surnames", value="Natural Person"),
                    UserProfileFact(path="activities.description", value="professional services"),
                    UserProfileFact(path="censo.activity_start_date", value="2025-01-01"),
                    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                    UserProfileFact(path="iva.regime", value="GENERAL"),
                    UserProfileFact(path="iva.m303_regime_composition", value="general"),
                    UserProfileFact(path="iva.redeme_enrolled", value=False),
                    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                ),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "modelo": "202",
                "period": PublicPeriod.from_period(Period.from_year_and_code(2025, "1P")),
                "revision_id": "2025-y-siguientes",
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "modelo.work.list":
            modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "include_discarded": False}
        case "modelo.work.history":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = unit.work_unit_id
            values = {"profile_id": profile_id, "work_unit_id": unit.work_unit_id}
        case "modelo.work.review":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = unit.work_unit_id
            values = {"profile_id": profile_id, "work_unit_id": unit.work_unit_id}
        case "modelo.work.filing_record":
            filing_record_id, _casilla_id = _seeded_modelo_filing_record(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "filing_record_id": filing_record_id}
        case "modelo.filing_record.view":
            filing_record_id, _casilla_id = _seeded_modelo_filing_record(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "filing_record_id": filing_record_id}
        case "modelo.filing_record.list":
            _seeded_modelo_filing_record(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "modelo.verification_report.list":
            modelo_operation_test_support.seeded_modelo_verification_report(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "modelo.verification_report.view":
            _revision_id, report_id = modelo_operation_test_support.seeded_modelo_verification_report(
                profile_id, operation=operation
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "verification_report_id": report_id}
        case "modelo.observation.local":
            modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            revision = resolved_revision(
                modelo=modelo_operation_test_support.MODELO,
                filing_year=modelo_operation_test_support.MODELO_FILING_YEAR,
                period=modelo_operation_test_support.MODELO_PERIOD,
            )
            casilla_id = sorted(casilla.id for casilla in revision.casillas)[0]
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "action": "record",
                "modelo": modelo_operation_test_support.MODELO,
                "period": PublicPeriod.from_period(
                    Period.from_year_and_code(
                        modelo_operation_test_support.MODELO_FILING_YEAR,
                        modelo_operation_test_support.MODELO_PERIOD,
                    )
                ),
                "casilla_values": (ModeloLocalObservationCasillaValue(casilla_id=casilla_id, value="100"),),
                "actor": None,
                "reason": "conformance observation",
            }
        case "modelo.filing_record.import":
            seed_modelo_ready_profile_record(str(profile_id), clock=now(), tax_id=SEEDED_SOURCE_TAX_ID)
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            revision = resolved_revision(
                modelo=modelo_operation_test_support.MODELO,
                filing_year=modelo_operation_test_support.MODELO_FILING_YEAR,
                period=modelo_operation_test_support.MODELO_PERIOD,
            )
            casilla_id = sorted(casilla.id for casilla in revision.casillas)[0]
            evidence_reference_id = f"CSV{modelo_operation_test_support.MODELO}{modelo_operation_test_support.MODELO_FILING_YEAR}{modelo_operation_test_support.MODELO_PERIOD}".upper()
            persist_justificante_metadata(
                evidence_reference_id,
                modelo=modelo_operation_test_support.MODELO,
                filing_year=modelo_operation_test_support.MODELO_FILING_YEAR,
                period=modelo_operation_test_support.MODELO_PERIOD,
                captured_at=now(),
                tax_id=SEEDED_SOURCE_TAX_ID,
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "work_unit_id": unit.work_unit_id,
                "evidence_kind": ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                "evidence_reference_id": evidence_reference_id,
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                "casilla_values": ((casilla_id, "100"),),
            }
        case "modelo.work.amendment_context":
            filing_record_id, _casilla_id = _seeded_modelo_filing_record(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "filing_record_id": filing_record_id}
        case "modelo.work.dependencies":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "filing_year": unit.filing_year,
                "modelo": unit.modelo,
                "period": PublicPeriod.from_period(unit.period),
            }
        case "workflow.run.read":
            run_id = "a" * 16
            period = Period.from_year_and_code(2025, "1T")
            WorkflowRunRepository().save(
                _workflow_result(
                    run_id,
                    modelo="303",
                    period=period,
                    started_at=datetime(2025, 5, 1, tzinfo=UTC),
                )
            )
            subject_ref = run_id
            values = {
                "profile_id": profile_id,
                "run_id": run_id,
                "expected_period": PublicPeriod.from_period(period),
            }
        case overview_definition_id if overview_definition_id in OVERVIEW_READ_DEFINITION_IDS.values():
            kind = OverviewReadKind(overview_definition_id.removeprefix("overview."))
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "kind": kind, "output_language": OutputLanguage.ES}
            if kind is OverviewReadKind.CALENDAR:
                values.update({"from_date": date(2025, 1, 1), "to_date": date(2025, 12, 31)})
            elif kind is OverviewReadKind.AGENDA:
                values.update({"as_of": date(2025, 1, 1), "horizon_days": 30})
            elif kind is OverviewReadKind.BACKLOG:
                values.update({"from_date": date(2025, 1, 1), "to_date": date(2025, 12, 31)})
            elif kind is OverviewReadKind.EXPLAIN:
                values.update({"modelo": "303", "year": 2025})
            elif kind is OverviewReadKind.PREPARE:
                values.update(
                    {"modelo": "303", "period": PublicPeriod.from_period(Period.from_year_and_code(2025, "1T"))}
                )
        case "overview.pipeline":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            for booked_date, description in (
                (date(2025, 1, 15), "conformance overview selected-period seed"),
                (date(2025, 4, 15), "conformance overview other-period seed"),
            ):
                create_manual_transaction(
                    ManualLedgerTransactionCommand(
                        bucket_id=str(profile_id),
                        booked_date=booked_date,
                        amount=Decimal("12.00"),
                        direction=TransactionDirection.INCOMING,
                        description=description,
                        business_classification=BusinessClassification.NOT_YET_PROCESSED,
                        actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                    ),
                    ports=ports,
                    occurred_at=now(),
                )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "period": PublicPeriod.from_period(Period.from_year_and_code(2025, "1T")),
                "output_language": OutputLanguage.ES,
            }
        case "workflow.run.list":
            first_period = Period.from_year_and_code(2025, "1T")
            second_period = Period.from_year_and_code(2025, "2T")
            WorkflowRunRepository().save(
                _workflow_result(
                    "a" * 16,
                    modelo="303",
                    period=first_period,
                    started_at=datetime(2025, 5, 1, tzinfo=UTC),
                )
            )
            WorkflowRunRepository().save(
                _workflow_result(
                    "b" * 16,
                    modelo="130",
                    period=second_period,
                    started_at=datetime(2025, 8, 1, tzinfo=UTC),
                )
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "workflow.resume.context":
            revision_id = modelo_operation_test_support.seeded_modelo_calculation_revision(
                profile_id, operation=operation
            )
            revision = CalculationRevisionCatalogueRepository().load(operation=operation).get(revision_id)
            assert revision is not None
            unit = WorkUnitCatalogueRepository().load().get(revision.work_unit_id)
            assert unit is not None
            run_id = "c" * 16
            WorkflowRunRepository().save(
                _workflow_result(
                    run_id,
                    modelo=unit.modelo,
                    period=unit.period,
                    started_at=datetime(2026, 1, 1, tzinfo=UTC),
                    aborted_reason=WorkflowAbortReason.SITE_UNAVAILABLE,
                )
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "calculation_revision_id": revision_id}
        case "modelo.work.wizard_context":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = unit.work_unit_id
            values = {
                "profile_id": profile_id,
                "work_unit_id": unit.work_unit_id,
                "output_language": OutputLanguage.ES,
            }
        case "modelo.work.revision":
            revision_id = modelo_operation_test_support.seeded_modelo_calculation_revision(
                profile_id, operation=operation
            )
            values = {"profile_id": profile_id, "calculation_revision_id": revision_id}
        case "modelo.work.revision_snapshot":
            revision_id = modelo_operation_test_support.seeded_modelo_calculation_revision(
                profile_id, operation=operation
            )
            revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
            assert revision is not None
            subject_ref = revision.work_unit_id
            values = {"profile_id": profile_id, "calculation_revision_id": revision_id}
        case "modelo.work.revisions":
            modelo_operation_test_support.seeded_modelo_calculation_revision(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "work_unit_id": None}
        case "modelo.work.compare_taxation":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "work_unit_id": unit.work_unit_id}
        case "modelo.review_package.build":
            revision_id, _report_id = modelo_operation_test_support.seeded_modelo_verification_report(
                profile_id, operation=operation
            )
            revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
            assert revision is not None
            subject_ref = revision.work_unit_id
            output_path = (tmp_path / "review-package.zip").resolve()
            values = {
                "profile_id": profile_id,
                "calculation_revision_id": revision_id,
                "output_path": str(output_path),
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "modelo.work.m303_attestation":
            seed_modelo_ready_profile_record(str(profile_id), clock=now(), tax_id=SEEDED_SOURCE_TAX_ID)
            upsert_test_profile_facts(
                str(profile_id),
                (UserProfileFact(path="censo.activity_start_date", value="2025-01-01"),),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "work_unit_id": None,
                "period": PublicPeriod.from_period(Period.from_year_and_code(2025, "4T")),
                "observed_at": now(),
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "ledger.counterparty":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "action": "confirm",
                "tax_identifier": "B12345674",
                "territorial_scope": "es_canarias",
                "asserted_by": "operator:registered-executor-conformance",
                "note": "synthetic supervisor conformance assertion",
            }
        case "ledger.remove":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 15),
                    amount=Decimal("12.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance removal dry run seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "transaction_id": created.ref.transaction_id,
                "reason": "synthetic conformance dry run",
                "dry_run": True,
            }
        case "ledger.allocate":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 17),
                    amount=Decimal("20.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance business-share allocation seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "transaction_id": created.ref.transaction_id,
                "business_pct": "0.5",
            }
        case "ledger.classify.single":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 19),
                    amount=Decimal("22.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance single classification seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "transaction_id": created.ref.transaction_id,
                "patch": LedgerClassifyPatch(business_classification="BUSINESS"),
                "patch_fields": ("business_classification",),
            }
        case "ledger.classify.bulk":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created_valid = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 20),
                    amount=Decimal("23.00"),
                    direction=TransactionDirection.OUTGOING,
                    description=f"conformance bulk classification valid {profile_id.hex}",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            created_invalid = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 20),
                    amount=Decimal("24.00"),
                    direction=TransactionDirection.OUTGOING,
                    description=f"conformance bulk classification invalid {profile_id.hex}",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "csv_text": (
                    "transaction_id,classification,iva_category\n"
                    f"{created_valid.ref.transaction_id},BUSINESS,domestic_general\n"
                    f"{created_invalid.ref.transaction_id},BUSINESS,not-a-declared-category\n"
                ),
                "actor": None,
            }
        case "ledger.evidence.add":
            evidence_file = tmp_path / "conformance-purchase-invoice-add.pdf"
            evidence_file.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "source_path": str(evidence_file)}
        case "ledger.evidence.list" | "ledger.evidence.view" | "ledger.evidence.update" | "ledger.evidence.remove":
            evidence_file = tmp_path / "conformance-purchase-invoice.pdf"
            evidence_file.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
            evidence = PurchaseInvoiceEvidenceService(
                ports=build_ledger_evidence_ports(bucket_id=str(profile_id)),
            ).add(bucket_id=str(profile_id), source_path=evidence_file)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
            if definition.definition_id == "ledger.evidence.view":
                values["evidence_id"] = evidence.record.evidence_id
            if definition.definition_id == "ledger.evidence.update":
                values.update(
                    evidence_id=evidence.record.evidence_id,
                    patch=LedgerEvidenceUpdatePatch(supplier="Conformance Supplier"),
                    patch_fields=("supplier",),
                )
            if definition.definition_id == "ledger.evidence.remove":
                values["evidence_id"] = evidence.record.evidence_id
        case "ledger.split.manual":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 21),
                    amount=Decimal("20.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance manual split seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "transaction_id": created.ref.transaction_id,
                "children": (
                    {"amount": "8", "description": "first split child"},
                    {"amount": "12", "description": "second split child"},
                ),
                "reason": "synthetic conformance split",
            }
        case "ledger.merge":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 22),
                    amount=Decimal("20.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance manual merge seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            split = split_transaction(
                bucket_id=str(profile_id),
                transaction_id=created.ref.transaction_id,
                children=(
                    SplitChildCommand(amount=Decimal("8"), description="first merge child"),
                    SplitChildCommand(amount=Decimal("12"), description="second merge child"),
                ),
                actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                reason="synthetic conformance merge seed",
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "child_ids": split.child_transaction_ids,
                "reason": "synthetic conformance merge",
            }
        case "ledger.update":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 18),
                    amount=Decimal("21.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance ledger update seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "transaction_id": created.ref.transaction_id,
                "patch": LedgerUpdatePatch(description="updated through registered operation"),
                "patch_fields": ("description",),
            }
        case "ledger.reset":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 16),
                    amount=Decimal("13.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance catalogue reset seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "reason": "synthetic conformance reset",
                "dry_run": False,
            }
        case "ledger.import":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "files": (tmp_path / "missing.csv",),
                "provider": LedgerProviderID.CSV,
                "dry_run": True,
                "verify": False,
                "verify_source": None,
                "period": None,
            }
        case "ledger.add":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "booked_date": "2025-01-20",
                "amount": "23.00",
                "direction": TransactionDirection.OUTGOING,
                "description": "conformance manual add",
            }
        case "ledger.status":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "period": None}
        case "ledger.check":
            absent_transaction_id = "f" * 64
            invoice = Invoice.model_validate(
                {
                    "kind": InvoiceKind.RECEIVED,
                    "bucket_id": str(profile_id),
                    "invoice_number": "CHECK-2025-001",
                    "issued_at": date(2025, 5, 1),
                    "counterparty_name": "Conformance Supplier",
                    "counterparty_tax_id": "B12345674",
                    "counterparty_country": "ES",
                    "base_total": Decimal("100.00"),
                    "iva_total": Decimal("21.00"),
                    "grand_total": Decimal("121.00"),
                    "currency": "EUR",
                    "payment_status": PaymentStatus.PAID,
                    "linked_transaction_ids": (absent_transaction_id,),
                    "lines": (
                        InvoiceLine(
                            description="Conformance invoice link",
                            quantity=Decimal("1"),
                            unit_price=Decimal("100.00"),
                            subtotal=Decimal("100.00"),
                            iva_rate=IvaRate.from_registry("RATE_21"),
                            iva_amount=Decimal("21.00"),
                        ),
                    ),
                }
            )
            InvoiceCatalogueRepository(bucket_id=str(profile_id)).save(
                InvoiceCatalogue(invoices={invoice.invoice_id: invoice})
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "period": PublicPeriod.from_period(Period.from_year_and_code(2026, "1T")),
            }
        case "ledger.preflight":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2026, 1, 15),
                    amount=Decimal("121.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance preflight selected-period issue",
                    business_classification=BusinessClassification.BUSINESS,
                    category_id=None,
                    taxable_base=Decimal("100.00"),
                    iva_rate=Decimal("0.21"),
                    iva_amount=Decimal("21.00"),
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2026, 4, 15),
                    amount=Decimal("242.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance preflight outside-period issue",
                    business_classification=BusinessClassification.BUSINESS,
                    category_id=None,
                    taxable_base=Decimal("200.00"),
                    iva_rate=Decimal("0.21"),
                    iva_amount=Decimal("42.00"),
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now() + timedelta(seconds=1),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "period": PublicPeriod.from_period(Period.from_year_and_code(2026, "1T")),
            }
        case "ledger.history":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 15),
                    amount=Decimal("12.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance history seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "transaction_prefix": created.ref.transaction_id[:12],
                "include_split_siblings": False,
            }
        case "ledger.view":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 15),
                    amount=Decimal("12.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance view seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            reject_llm_suggestion(
                LLMClassificationSuggestion(
                    transaction_id=created.ref.transaction_id,
                    provenance="llm:conformance:test-model",
                    classification=BusinessClassification.BUSINESS,
                    confidence=Decimal("0.9"),
                    reason="conformance suggestion",
                ),
                bucket_id=str(profile_id),
                reason="operator rejected the conformance suggestion",
                actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                source_command="conformance ledger view seed",
                transaction_repository=ports.transaction_repository,
                bucket_event_repository=ports.bucket_event_repository,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "transaction_prefix": created.ref.transaction_id[:12],
            }
        case "ledger.track":
            transaction_id = _seeded_ledger_track_with_finalized_participation(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "transaction_prefix": transaction_id[:12],
            }
        case "ledger.list":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            for index, (booked_date, description) in enumerate(
                (
                    (date(2025, 1, 15), "ledger list page A"),
                    (date(2025, 2, 15), "ledger list page B"),
                    (date(2025, 3, 15), "ledger list page C"),
                    (date(2025, 4, 15), "ledger list outside period"),
                )
            ):
                create_manual_transaction(
                    ManualLedgerTransactionCommand(
                        bucket_id=str(profile_id),
                        booked_date=booked_date,
                        amount=Decimal(10 + index),
                        direction=TransactionDirection.OUTGOING,
                        description=description,
                        business_classification=BusinessClassification.NOT_YET_PROCESSED,
                        group_label=_LEDGER_LIST_PRIVATE_FILTER_SENTINEL,
                        actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                    ),
                    ports=ports,
                    occurred_at=now() + timedelta(seconds=index),
                )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "filters": ("period=1T", "year=2025", "classification=not_yet_processed"),
                "group": _LEDGER_LIST_PRIVATE_FILTER_SENTINEL,
                "limit": 2,
                "offset": 1,
                "sort_by": LedgerSortField.DESCRIPTION,
            }
        case (
            "ledger.inventory.list"
            | "ledger.inventory.create"
            | "ledger.inventory.movement.add"
            | "ledger.inventory.valuation.preview"
            | "ledger.inventory.closing-authority.record"
        ):
            inventory_case = prepare_inventory_operation_conformance_case(
                definition.definition_id, profile_id, ports_factory=build_inventory_service_ports
            )
            subject_ref = profile_operation_subject(str(profile_id))
            inventory_payload = inventory_case.request
            assert isinstance(inventory_payload, BaseModel)
            assert isinstance(inventory_payload, definition.request_type)
            return subject_ref, inventory_payload, None
        case "ledger.bienes_inversion.list" | "ledger.bienes_inversion.declare":
            bienes_case = prepare_bienes_inversion_operation_conformance_case(
                definition.definition_id,
                profile_id,
                repository_factory=build_bienes_inversion_repository,
                operation=operation,
            )
            assert isinstance(bienes_case.request, definition.request_type)
            return profile_operation_subject(str(profile_id)), bienes_case.request, None
        case "ledger.actividad-asset.create":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "revision": ActivityAssetRevisionSnapshot.from_domain(activity_asset_revision("conformance-create")),
            }
        case (
            "ledger.actividad-asset.inspect"
            | "ledger.actividad-asset.correct"
            | "ledger.actividad-asset.forecast"
            | "ledger.actividad-asset.claim"
            | "ledger.actividad-asset.filing-handoff"
        ):
            action = definition.definition_id.rsplit(".", 1)[1]
            asset_seed = seed_activity_asset(
                profile_id,
                operation=operation,
                asset_id=f"conformance-{action}",
                include_claim=action == "filing-handoff",
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
            if action == "inspect":
                values["asset_id"] = asset_seed.revision.asset_id
            elif action == "correct":
                values["revision"] = ActivityAssetRevisionSnapshot.from_domain(
                    activity_asset_revision(
                        asset_seed.revision.asset_id,
                        revision_number=2,
                        supersedes_revision_id=asset_seed.revision.revision_id,
                    )
                )
            elif action == "forecast":
                values.update(
                    asset_id=asset_seed.revision.asset_id, covered_from=date(2025, 1, 1), covered_until=date(2026, 1, 1)
                )
            elif action == "claim":
                values.update(
                    forecast=ScheduledAmortizationChargeSnapshot.from_domain(asset_seed.forecast),
                    creating_operation="activity-asset-conformance.claim",
                )
            else:
                values.update(tax_year=2025, m130_period="4T")
        case "ledger.invoice.add":
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "kind": InvoiceKind.RECEIVED,
                "counterparty_name": "Conformance Supplier",
                "counterparty_tax_id": "B12345674",
                "counterparty_country": "ES",
                "invoice_number": "CONFORMANCE-INVOICE-2025-ADD",
                "issued_at": date(2025, 5, 1),
                "taxable_base": {"decimal": "100.00"},
                "iva_rate": {"decimal": "21"},
                "currency": "EUR",
            }
        case "user-profile.recovery.status":
            enroll_profile_recovery(
                profile_id=profile_id,
                current_passphrase=_CREDENTIAL_INPUT,
                recovery_handover=lambda enrollment: enrollment.recovery_key.code,
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "ledger.invoice.list" | "ledger.invoice.view" | "ledger.invoice.remove" | "ledger.invoice.update":
            invoice = _seed_conformance_invoice(profile_id)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
            if definition.definition_id == INVOICE_LIST_OPERATION_DEFINITION_ID:
                values["kind"] = None
            elif definition.definition_id in {
                INVOICE_REMOVE_OPERATION_DEFINITION_ID,
                INVOICE_UPDATE_OPERATION_DEFINITION_ID,
            }:
                values["invoice_id"] = invoice.invoice_id
                if definition.definition_id == INVOICE_UPDATE_OPERATION_DEFINITION_ID:
                    values["patch"] = InvoiceUpdatePatch.from_patch(
                        CatalogueInvoicePatch.model_validate(
                            {"counterparty_name": "Updated conformance supplier", "retention_amount": Decimal("0.00")}
                        )
                    )
            else:
                values["invoice_id"] = invoice.invoice_id
        case "ledger.participation":
            transaction_id = _seeded_ledger_track_with_finalized_participation(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "transaction_prefix": transaction_id[:12]}
        case "ledger.participation.rebuild":
            _seeded_ledger_track_with_finalized_participation(profile_id, operation=operation)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id}
        case "ledger.review":
            ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=str(profile_id),
                    booked_date=date(2025, 1, 15),
                    amount=Decimal("21.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="conformance review seed",
                    business_classification=BusinessClassification.NOT_YET_PROCESSED,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
                ports=ports,
                occurred_at=now(),
            )
            subject_ref = profile_operation_subject(str(profile_id))
            values = {"profile_id": profile_id, "transaction_prefix": created.ref.transaction_id[:12]}
        case "modelo.work.report_verify":
            tmp_path.mkdir(parents=True, exist_ok=True)
            source = (tmp_path / "malformed-calculation-summary.pdf").resolve()
            source_bytes = b"synthetic malformed calculation summary PDF"
            source.write_bytes(source_bytes)
            subject_ref = profile_operation_subject(str(profile_id))
            values = {
                "profile_id": profile_id,
                "source_path": str(source),
                "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            }
        case "modelo.export":
            # A DRAFT revision is not exportable. `_require_exportable_revision_state`
            # admits only SEALED states (VERIFICADO_COMPLETO, PRESENTADO,
            # PRESENTADO_SUPERSEDIDO), because a fichero is a filing-grade
            # artefact and a return still being edited has no business becoming
            # one. So this seeds through verification rather than calculation.
            revision_id, _report_id = modelo_operation_test_support.seeded_modelo_verification_report(
                profile_id, operation=operation
            )
            export_revision = CalculationRevisionCatalogueRepository().load(operation=operation).get(revision_id)
            assert export_revision is not None
            subject_ref = export_revision.work_unit_id
            values = {
                "calculation_revision_id": revision_id,
                "output_path": str(tmp_path / "modelo-130-2025-1T.txt"),
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "modelo.edit.apply":
            work_unit_id, wire_submission = _seeded_modelo_edit_submission(profile_id, operation=operation)
            subject_ref = work_unit_id
            values = {"submission": wire_submission}
        case "modelo.work.file":
            revision_id, report_id = modelo_operation_test_support.seeded_modelo_verification_report(
                profile_id, operation=operation
            )
            revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
            assert revision is not None
            subject_ref = revision.work_unit_id
            values = {
                "approval": {
                    "calculation_revision_id": revision_id,
                    "verification_report_id": report_id,
                },
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "modelo.work.amend":
            filing_record_id, casilla_id = _seeded_modelo_filing_record(profile_id, operation=operation)
            # The subject is the FILED RECORD, not the work unit: two amendments
            # of one filed return describe competing corrections to the same
            # declaration and must serialise against each other.
            subject_ref = filing_record_id
            values = {
                "baseline": {"from_filing_record_id": filing_record_id},
                # The request model is strict: the enum instance and a tuple,
                # not their loose equivalents. A `.value` string and a list both
                # round-trip through JSON but are refused at the boundary, which
                # is the point of declaring the schema strict.
                "amendment_kind": CalculationRevisionAmendmentKind.COMPLEMENTARIA,
                "overrides": ({"casilla_id": casilla_id, "value": "150.00"},),
                "reason": "corrected the declared base for the conformance matrix",
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "modelo.work.calculate":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = unit.work_unit_id
            values = {
                "work_unit_id": unit.work_unit_id,
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "modelo.work.wizard_attempt":
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = unit.work_unit_id
            values = {
                "profile_id": profile_id,
                "output_language": OutputLanguage.ES,
                "calculation": ModeloWorkCalculateRequest(
                    work_unit_id=unit.work_unit_id,
                    actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                ),
            }
        case "modelo.work.verify":
            revision_id = modelo_operation_test_support.seeded_modelo_calculation_revision(
                profile_id, operation=operation
            )
            revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
            assert revision is not None
            subject_ref = revision.work_unit_id
            values = {
                "calculation_revision_id": revision_id,
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case "modelo.work.discard":
            # The baseline is the operator's EXACT APPROVAL, so it carries the
            # unit's state as observed rather than as re-read: name and
            # updated_at come off the seeded unit itself. A baseline resolved
            # inside the executor would match by construction and the
            # compare-and-swap this operation declares would never refuse.
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            subject_ref = unit.work_unit_id
            values = {
                "baseline": {
                    "work_unit_id": unit.work_unit_id,
                    "name": unit.name,
                    "observed_updated_at": unit.updated_at,
                },
                "reason": "discarded by the registered-executor conformance matrix",
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            }
        case _:  # pragma: no cover - the coverage census names any definition missing a scenario.
            raise AssertionError(f"no conformance scenario for {definition.definition_id}")
    return subject_ref, definition.request_type.model_validate(values, strict=True), secret


def _seed_conformance_invoice(profile_id: UUID) -> Invoice:
    """Persist one domain-valid invoice for registered catalogue read scenarios."""
    invoice = Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "bucket_id": str(profile_id),
            "invoice_number": "CONFORMANCE-INVOICE-2025-001",
            "issued_at": date(2025, 5, 1),
            "counterparty_name": "Conformance Supplier",
            "notes": "Conformance note preserved by partial update",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "payment_status": PaymentStatus.PAID,
            "lines": (
                InvoiceLine(
                    description="Conformance catalogue invoice",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    subtotal=Decimal("100.00"),
                    iva_rate=IvaRate.from_registry("RATE_21"),
                    iva_amount=Decimal("21.00"),
                ),
            ),
        }
    )
    InvoiceCatalogueRepository(bucket_id=str(profile_id)).save(InvoiceCatalogue(invoices={invoice.invoice_id: invoice}))
    return invoice


@contextmanager
def _runtime(
    tmp_path: Path,
    *,
    cleanup: _CloseWitness,
    before_irreversible_section: Callable[[], Awaitable[None]] | None = None,
    execution_timeout: timedelta = timedelta(hours=1),
    amendment_action_ports_factory: AmendmentActionPortsFactory | None = None,
    clock: Callable[[], datetime] = now,
) -> Generator[tuple[_ExecutionDriver, OperationRegistry, UUID]]:
    """Fresh production profile, inventory, journal, lease, and operand custody per case."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()

    async def acquire_censo() -> CensalOperationAcquisition:
        return CensalOperationAcquisition(observation=_observation(), resource=cleanup)

    async def acquire_verify(surface, nif, expected, operation) -> VerifyLiveObservation:
        del surface, expected, operation
        return VerifyLiveObservation(nif=nif, verdict=IdentityCheckVerdict.VALID)

    def verify_definition(surface: VerifySurface) -> OperationDefinition:
        return build_verify_capture_definition(
            surface,
            persistence_factory=lambda bucket_id: VerifyObservationRepository(bucket_id=bucket_id),
            acquire=acquire_verify,
            browser_resources_factory=BrowserRuntimeResourceScope,
            provider_preflight=lambda _profile_id, _operation: None,
        )

    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        enrolled = register_profile_with_credentials(
            label="S45 registered executor subject",
            passphrase=_CREDENTIAL_INPUT,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            profile_create_context=_profile_create_context_for_test,
            profile_decode_context=_profile_decode_context_for_test,
        )
        profile_id = UUID(enrolled.profile_id)
        initial_login = login_profile(
            name=enrolled.profile_id,
            passphrase_callback=lambda: _CREDENTIAL_INPUT,
            profile_decode_context=_profile_decode_context_for_test,
        )
        registry = build_production_operation_registry(
            auth_definitions=build_auth_operation_definitions(
                ports=build_auth_operation_ports(), profile_login=lambda **_kwargs: initial_login
            ),
            censal_definition=build_censal_operation_definition(
                certificate_secret_backend_factory=build_certificate_secret_backend,
                browser_session_factory=default_browser_session_factory,
                acquire=acquire_censo,
                before_irreversible_section=before_irreversible_section,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                censal_fetch_port=build_censal_fetch_port(),
            ),
            verify_nif_iva_definition=verify_definition(VerifySurface.NIF_IVA),
            verify_tgvi_definition=verify_definition(VerifySurface.TGVI),
            amendment_action_ports_factory=amendment_action_ports_factory or build_amendment_action_ports,
        )
        journal = OperationJournalRepository(storage_root=root / "operations")
        with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as objects:
            authority_scope = bundled_indexed_authority().operation()
            authority_operation = authority_scope.__enter__()
            services = compose_operation_services(
                registry=registry,
                authority_operation=authority_operation,
                journal=journal,
                reader=journal,
                event_stream=journal,
                leases=OperationLeaseFilesystemRepository(storage_root=root / "operations"),
                operands=operation_secure_reference_repository(objects=cast(SecureObjectRepository, objects)),
                owner_id="1" * 64,
                lease_token_factory=lambda: "2" * 64,
                clock=clock,
                lease_duration=timedelta(minutes=10),
                execution_timeout=execution_timeout,
                cleanup_timeout=timedelta(minutes=2),
                financial_operand_custody=OperationFinancialOperandCustodyFilesystemRepository(
                    root=root / "operations" / "financial_operand_custody",
                ),
            )
            try:
                yield _ExecutionDriver(services=services), registry, profile_id
            finally:
                asyncio.run(services.shutdown())
                authority_scope.__exit__(None, None, None)
                # The login above binds this process's live session; a runtime
                # that leaves it open hands every later test in the worker a
                # logged-in profile it never created.
                logout_active_profile()


@pytest.mark.parametrize("apply", [True, False], ids=["apply", "reject"])
def test_censal_frontend_driver_reviews_one_acquisition_and_rolls_back_rejection(
    tmp_path: Path,
    apply: bool,
    operation: PinnedAuthorityOperation,
) -> None:
    """The public frontend driver answers the encrypted exact proposal once."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    cleanup = _CloseWitness()
    with _runtime(tmp_path / f"frontend-{apply}", cleanup=cleanup) as (_driver, _registry, profile_id):
        repository = ProfileRecordRepository.for_current_session(
            profile_id, profile_decode_context=_profile_decode_context_for_test
        )
        before = repository.load(profile_id)
        decisions: list[tuple[str | None, ...]] = []

        def decide(projection) -> bool:
            decisions.append(tuple(field.observed_value for field in projection.fields))
            return apply

        result = asyncio.run(
            review_censal_with_services(
                _driver.services,
                operation=operation,
                actor_ref="operator:frontend-test",
                decide=decide,
            )
        )

        assert result.applied is apply
        assert len(decisions) == 1
        assert len(decisions[0]) == len(CENSAL_ADOPTABLE_PATHS)
        assert decisions[0][0]
        assert decisions[0][1] == "28013"
        assert cleanup.closed is True
        after = repository.load(profile_id)
        if apply:
            assert after.record_revision == before.record_revision + 1
            assert after.content_digest != before.content_digest
        else:
            assert after == before


def test_censal_frontend_driver_never_reports_a_failed_terminal_as_applied(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """An accepted response followed by a failed continuation stays a failure."""
    cleanup = _CloseWitness()
    with _runtime(tmp_path / "frontend-failed", cleanup=cleanup) as (driver, _registry, _profile_id):
        delegate = driver.services.observation

        class _FailedTerminalObservation(OperationObservationService):
            @override
            async def observe(
                self, request: OperationObservationVersionHeader | OperationObservationRequestV1
            ) -> OperationObservationResultV1:
                observed = await super().observe(request)
                if (
                    isinstance(observed, OperationObservationSuccessV1)
                    and observed.projection.lifecycle is OperationLifecycle.TERMINAL
                ):
                    return observed.model_copy(
                        update={
                            "projection": observed.projection.model_copy(
                                update={
                                    "terminal_condition": OperationTerminalCondition.FAILED,
                                    "effect": OperationEffect.UNKNOWN,
                                    "result_ref": None,
                                    "diagnostic_ref": "diagnostic:censo-stale",
                                }
                            )
                        }
                    )
                return observed

        failing_services = replace(
            driver.services,
            observation=_FailedTerminalObservation(reader=delegate.reader, registry=delegate.registry),
        )
        with pytest.raises(InternalInvariantError, match="did not succeed"):
            asyncio.run(
                review_censal_with_services(
                    failing_services,
                    operation=operation,
                    actor_ref="operator:frontend-failed-test",
                    decide=lambda _projection: True,
                )
            )


def test_every_registered_definition_has_a_conformance_scenario() -> None:
    """The matrix's subjects are the registry's, in both directions.

    This is the census the hardcoded item list used to stand in for. It
    asserts membership, never a count: a tally would have to be edited
    every time an operation is composed, which trains everyone to update
    the constant and then detects nothing.
    """
    registered = set(_registered_definition_ids())
    declared = set(_EXPECTATIONS)

    assert not registered - declared, (
        "registered operations run through the supervisor with no conformance scenario, so this "
        f"matrix does not cover what its name claims: {sorted(registered - declared)}"
    )
    assert not declared - registered, (
        f"conformance scenarios name operations the production registry does not compose: {sorted(declared - registered)}"
    )


def _assert_ledger_track_result(
    driver: _ExecutionDriver,
    registry: OperationRegistry,
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    payload: BaseModel,
    operation_id: str,
    terminal_revision: int,
) -> None:
    assert isinstance(payload, LedgerTrackRequest)
    track = _resolve_result_projection(
        driver,
        registry,
        definition_id="ledger.track",
        operation_id=operation_id,
        terminal_revision=terminal_revision,
        projection_type=LedgerTrackProjection,
    )
    assert isinstance(track, LedgerTrackProjection)
    transaction_id = resolve_lineage_transaction_id(
        payload.transaction_prefix,
        TransactionCatalogueRepository(bucket_id=str(profile_id)).load(),
    )
    assert track.profile_id == profile_id
    assert track.transaction_prefix == payload.transaction_prefix
    assert track.transaction.transaction_id == transaction_id
    assert track.tracking.transaction_id == transaction_id
    assert track.participated_in is not None
    index = TransactionParticipationIndexRepository(bucket_id=str(profile_id)).load(transaction_id)
    assert len(index.participations) == 1
    participation = index.participations[0]
    assert track.participated_in == (LedgerParticipationEntryProjection.from_participation(participation),)
    assert participation.filing_record_id is None
    assert participation.justificante_reference is None
    assert participation.revision_state == CalculationRevisionState.VERIFICADO_COMPLETO.value
    revision = (
        CalculationRevisionCatalogueRepository().load(operation=operation).get(participation.calculation_revision_id)
    )
    assert revision is not None
    assert revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert transaction_id in revision.source_transaction_ids
    assert revision.work_unit_id == participation.work_unit_id
    unit = WorkUnitCatalogueRepository().load().get(participation.work_unit_id)
    assert unit is not None
    assert participation.modelo == str(unit.modelo)
    assert participation.filing_year == unit.filing_year
    assert participation.period == unit.period


def _assert_ledger_participation_lookup_result(
    driver: _ExecutionDriver,
    registry: OperationRegistry,
    *,
    profile_id: UUID,
    payload: LedgerParticipationRequest,
    operation_id: str,
    terminal_revision: int,
) -> None:
    participation_result = _resolve_result_projection(
        driver,
        registry,
        definition_id="ledger.participation",
        operation_id=operation_id,
        terminal_revision=terminal_revision,
        projection_type=LedgerParticipationLookupProjection,
    )
    assert isinstance(participation_result, LedgerParticipationLookupProjection)
    transaction_id = resolve_lineage_transaction_id(
        payload.transaction_prefix,
        TransactionCatalogueRepository(bucket_id=str(profile_id)).load(),
    )
    assert participation_result.profile_id == profile_id
    assert participation_result.transaction_prefix == payload.transaction_prefix
    assert participation_result.transaction_id == transaction_id
    index = TransactionParticipationIndexRepository(bucket_id=str(profile_id)).load(transaction_id)
    assert len(index.participations) == 1
    assert participation_result.participations == (
        LedgerParticipationEntryProjection.from_participation(index.participations[0]),
    )
    assert index.participations[0].revision_state == CalculationRevisionState.VERIFICADO_COMPLETO.value


def _assert_ledger_participation_rebuild_result(
    driver: _ExecutionDriver,
    registry: OperationRegistry,
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    operation_id: str,
    terminal_revision: int,
) -> None:
    rebuild_result = _resolve_result_projection(
        driver,
        registry,
        definition_id="ledger.participation.rebuild",
        operation_id=operation_id,
        terminal_revision=terminal_revision,
        projection_type=LedgerParticipationRebuildProjection,
    )
    assert isinstance(rebuild_result, LedgerParticipationRebuildProjection)
    assert rebuild_result.profile_id == profile_id
    assert rebuild_result.transaction_count == 1
    assert rebuild_result.participation_count == 1
    persisted_revisions = CalculationRevisionCatalogueRepository().load(operation=operation).revisions
    assert rebuild_result.revision_count == len(persisted_revisions) > 0
    assert rebuild_result.stale_removed_count == 0
    transactions = tuple(TransactionCatalogueRepository(bucket_id=str(profile_id)).load())
    assert len(transactions) == 1
    index = TransactionParticipationIndexRepository(bucket_id=str(profile_id)).load(transactions[0].transaction_id)
    assert len(index.participations) == 1
    assert index.participations[0].revision_state == CalculationRevisionState.VERIFICADO_COMPLETO.value


def _assert_canonical_bulk_classification_update(
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    before: Transaction,
    after: Transaction,
    patch: ManualLedgerTransactionPatch,
    actor: str,
    event: BucketEvent,
) -> None:
    """Compare a persisted batch row and event to canonical manual-update meaning."""
    bucket_id = str(profile_id)
    ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=operation)
    command = command_from_patch(
        bucket_id=bucket_id,
        current=before,
        patch=patch,
        actor=actor,
        source_command="aeat app ledger classify --file",
    )
    prepared = prepare_manual_transaction_update(
        current=before,
        command=command,
        previous_transaction_id=before.transaction_id,
        now=event.occurred_at,
        ports=ports,
    )
    assert prepared is not None
    expected_transaction, expected_events = prepared
    assert after == expected_transaction
    assert expected_events == (event,)


def _assert_ledger_review_projection(payload: BaseModel, review: BaseModel, *, profile_id: UUID) -> None:
    assert isinstance(payload, LedgerReviewRequest)
    assert isinstance(review, LedgerReviewProjection)
    assert review.profile_id == profile_id
    assert review.transaction_prefix == payload.transaction_prefix
    assert len(review.rows) == 1
    row = review.rows[0]
    assert row.description == "conformance review seed"
    assert row.status is LedgerReviewStatus.PENDING
    assert row.transaction is not None
    assert row.transaction.description == row.description
    assert payload.transaction_prefix is not None
    assert row.transaction.transaction_id.startswith(payload.transaction_prefix)


def _assert_calculation_report_verification_projection(
    payload: BaseModel, projection: BaseModel, *, profile_id: UUID
) -> None:
    assert isinstance(payload, ModeloCalculationReportVerificationRequest)
    assert isinstance(projection, ModeloCalculationReportVerificationProjection)
    assert projection.profile_id == profile_id == payload.profile_id
    assert projection.source_sha256 == payload.source_sha256
    assert projection.source_sha256 == hashlib.sha256(Path(payload.source_path).read_bytes()).hexdigest()
    assert payload.trusted_public_key_hex is None
    verdict = projection.verification
    assert verdict.outcome is CalculationSummaryVerificationOutcome.REFUSED
    assert verdict.store_checked is False
    assert verdict.signing_key_fingerprint is None
    assert len(verdict.checks) == 1
    check = verdict.checks[0]
    assert check.check is CalculationSummaryCheckName.PDF
    assert check.layer is CalculationSummaryVerificationLayer.DOCUMENT
    assert check.reason is CalculationSummaryVerificationReason.PDF_UNREADABLE


@pytest.mark.parametrize("definition_id", _registered_definition_ids())
@pytest.mark.timeout(90)
def test_every_production_registered_executor_runs_through_the_shared_supervisor_matrix(
    tmp_path: Path, definition_id: str, *, operation: PinnedAuthorityOperation
) -> None:
    """Actual execution, effects, settlement, review, cleanup, and truthful control refusal."""
    case = _EXPECTATIONS.get(definition_id)
    if case is None:
        pytest.fail(
            f"{definition_id} is composed into the production registry but declares no conformance "
            "scenario, so nothing proves its executor settles, cleans up, or refuses truthfully"
        )
    assert case is not None
    cleanup = _CloseWitness()
    with (
        _closed_model_runtime()
        if definition_id
        in {
            "local-reader.provision",
            "ledger.evidence.reader-readiness",
            "ledger.evidence.extract",
            "ledger.evidence.confirm",
        }
        else nullcontext(),
        _runtime(tmp_path / case.definition_id, cleanup=cleanup) as (driver, registry, profile_id),
    ):
        definitions = {definition.definition_id: definition for definition in registry.definitions}
        definition = definitions[case.definition_id]
        projection_history_case = (
            prepare_modelo_projection_history_conformance_case(
                case.definition_id, profile_id=profile_id, operation=operation
            )
            if case.definition_id in {"modelo.history", "modelo.history.timeline", "modelo.project", "modelo.compare"}
            else None
        )
        query_case = (
            prepare_modelo_query_conformance_case(case.definition_id, profile_id=profile_id, operation=operation)
            if case.definition_id
            in {
                "modelo.bindings.list",
                "modelo.bindings.resolve",
                "modelo.bindings.resolve.typed",
                "modelo.requires",
                "modelo.readiness",
                "modelo.readiness.summary",
            }
            else None
        )
        review_case = (
            prepare_review_read_conformance_case(case.definition_id, profile_id=profile_id, operation=operation)
            if case.definition_id in {"app.review.queue", "app.review.view"}
            else None
        )
        followup_case = (
            prepare_evidence_followup_conformance_case(case.definition_id, profile_id=profile_id, operation=operation)
            if case.definition_id
            in {
                "ledger.evidence.attachment_queue",
                "ledger.evidence.attachment_view",
                "ledger.evidence.consent.list",
                "ledger.evidence.review.list",
                "ledger.evidence.review.view",
            }
            else None
        )
        recipient_case = (
            prepare_recipient_operation_case(case.definition_id, profile_id)
            if case.definition_id.startswith("config.collab.recipient.")
            else None
        )
        attachment_case = (
            prepare_ledger_attachment_operation_conformance_case(case.definition_id, profile_id, operation=operation)
            if case.definition_id in {"ledger.attach", "ledger.detach"}
            else None
        )
        lifecycle_case = (
            _ledger_lifecycle_case(case.definition_id, profile_id=profile_id, operation=operation)
            if case.definition_id in {"ledger.archive", "ledger.stash", "ledger.restore", "ledger.exclude"}
            else None
        )
        rule_case = (
            prepare_ledger_rule_operation_conformance_case(case.definition_id, profile_id, operation=operation)
            if case.definition_id in {"ledger.rule.add", "ledger.rule.list", "ledger.rule.apply"}
            else None
        )
        prorrata_case = (
            _prorrata_case(case.definition_id, profile_id=profile_id, operation=operation)
            if case.definition_id.startswith("ledger.prorrata.")
            else None
        )
        evidence_case = (
            prepare_invoice_evidence_conformance_case(case.definition_id, profile_id=profile_id, operation=operation)
            if case.definition_id
            in {"ledger.evidence.reader-readiness", "ledger.evidence.extract", "ledger.evidence.confirm"}
            else None
        )
        if query_case is not None:
            subject_ref, payload, secret = profile_operation_subject(str(profile_id)), query_case.request, None
        elif projection_history_case is not None:
            subject_ref, payload, secret = (
                profile_operation_subject(str(profile_id)),
                projection_history_case.request,
                None,
            )
        elif review_case is not None:
            subject_ref, payload, secret = profile_operation_subject(str(profile_id)), review_case.request, None
        elif followup_case is not None:
            subject_ref, payload, secret = profile_operation_subject(str(profile_id)), followup_case.request, None
        elif recipient_case is not None:
            subject_ref, payload, secret = profile_operation_subject(str(profile_id)), recipient_case.request, None
        elif attachment_case is not None:
            subject_ref, payload, secret = profile_operation_subject(str(profile_id)), attachment_case.request, None
        elif lifecycle_case is not None:
            subject_ref, payload, secret = profile_operation_subject(str(profile_id)), lifecycle_case.request, None
        elif rule_case is not None:
            subject_ref, payload, secret = profile_operation_subject(str(profile_id)), rule_case.request, None
        elif evidence_case is not None:
            subject_ref, payload, secret = profile_operation_subject(str(profile_id)), evidence_case.request, None
        elif prorrata_case is None:
            subject_ref, payload, secret = _payload(
                definition, profile_id=profile_id, tmp_path=tmp_path / case.definition_id, operation=operation
            )
        else:
            subject_ref, payload, secret = profile_operation_subject(str(profile_id)), prorrata_case.request, None
        bulk_classify_before = (
            (
                TransactionCatalogueRepository(bucket_id=str(profile_id)).load(),
                bucket_event_history_repository(bucket_id=str(profile_id)).load(),
            )
            if case.definition_id == LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID
            else None
        )
        prorrata_before = (
            read_prorrata_operation_conformance_register(
                profile_id, repository_factory=build_prorrata_register_repository, operation=operation
            )
            if prorrata_case is not None
            else None
        )
        withholding_seed = (
            InvoiceWithholdingConformanceSeed(
                request=payload,
                invoice_id=payload.evidence.invoice_id,
                period=payload.command.period.to_period(),
            )
            if isinstance(payload, ModeloInvoiceWithholdingCaptureRequest)
            else None
        )
        if withholding_seed is not None:
            withholding_before = read_invoice_withholding_conformance_case(profile_id, withholding_seed)
            assert withholding_before.generation == 0
            assert withholding_before.observations == ()
        certificate_state_before = (
            workflow_state_repository().load()
            if case.definition_id in {"auth.certificate.source.list", "auth.certificate.source.check"}
            else None
        )
        ratios_before = (
            (
                load_usage_ratio_profile(bucket_id=str(profile_id), operation=operation),
                bucket_event_history_repository(bucket_id=str(profile_id)).load(),
            )
            if case.definition_id.startswith("ledger.ratios.")
            else None
        )
        invoice_catalogue_before = (
            InvoiceCatalogueRepository(bucket_id=str(profile_id)).load()
            if case.definition_id
            in {
                INVOICE_LIST_OPERATION_DEFINITION_ID,
                INVOICE_VIEW_OPERATION_DEFINITION_ID,
                INVOICE_REMOVE_OPERATION_DEFINITION_ID,
                INVOICE_UPDATE_OPERATION_DEFINITION_ID,
            }
            else None
        )
        asset_repository = (
            build_activity_asset_operation_ports(bucket_id=str(profile_id), operation=operation).history_repository
            if case.definition_id.startswith("ledger.actividad-asset.")
            else None
        )
        asset_before = asset_repository.load() if asset_repository is not None else None
        inventory_repository = (
            build_inventory_service_ports(bucket_id=str(profile_id)).inventory_repository_factory(str(profile_id))
            if case.definition_id.startswith("ledger.inventory.")
            else None
        )
        inventory_before = inventory_repository.load() if inventory_repository is not None else None
        bienes_before = (
            read_bienes_inversion_operation_conformance_register(
                profile_id, repository_factory=build_bienes_inversion_repository
            )
            if case.definition_id.startswith("ledger.bienes_inversion.")
            else None
        )
        iva_history_before = (
            IvaCompensationHistoryRepository().list_periods()
            if case.definition_id == IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID
            else None
        )
        resume_revision_catalogue_before = (
            CalculationRevisionCatalogueRepository().load(operation=operation)
            if case.definition_id == WORKFLOW_RESUME_OPERATION_DEFINITION_ID
            else None
        )
        overview_catalogues_before = None
        if case.definition_id == "overview.pipeline":
            overview_bundle = build_verification_repository_bundle(str(profile_id), operation=operation)
            overview_catalogues_before = (
                overview_bundle.transaction.load(),
                overview_bundle.work_unit.load(),
                overview_bundle.calculation.load(operation=operation),
                overview_bundle.filing.load(),
                overview_bundle.verification.load(operation=operation),
            )
        submitted, observed = asyncio.run(
            driver.run(definition_id=definition.definition_id, subject_ref=subject_ref, payload=payload, secret=secret)
        )
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
                BienesInversionListProjection
                if case.definition_id.endswith(".list")
                else BienesInversionDeclareProjection
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
                assert (
                    inventory_result.record.authority_record_fingerprint == ledger.closing_authority_record.fingerprint
                )
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
                        event.event_type is BucketEventType.LEDGER_RATIOS_UNSET
                        for event in events_after.events.values()
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
            assert CalculationRevisionCatalogueRepository().load(operation=operation) == (
                resume_revision_catalogue_before
            )
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
            assert viewed.record.bucket_id == str(profile_id)
            assert viewed.record.evidence_id == payload.evidence_id
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
            assert definition.capabilities.permitted_effects == frozenset(
                {OperationEffect.NONE, OperationEffect.UNKNOWN}
            )
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
            assert definition.capabilities.permitted_effects == frozenset(
                {OperationEffect.NONE, OperationEffect.UNKNOWN}
            )
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


@pytest.mark.timeout(90)
def test_ledger_track_uses_null_when_no_finalized_revision_participates(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """An empty encrypted index stays JSON null for a real ledger transaction."""
    with _runtime(tmp_path / "ledger-track-empty", cleanup=_CloseWitness()) as (driver, registry, profile_id):
        ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=str(profile_id),
                booked_date=date(2025, 1, 15),
                amount=Decimal("12.00"),
                direction=TransactionDirection.INCOMING,
                description="conformance track empty-index seed",
                business_classification=BusinessClassification.BUSINESS,
                taxable_base=Decimal("12.00"),
                iva_rate=Decimal("0"),
                iva_amount=Decimal("0"),
                actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            ),
            ports=ports,
            occurred_at=now(),
        )
        request = LedgerTrackRequest(profile_id=profile_id, transaction_prefix=created.ref.transaction_id[:12])
        submitted, observed = asyncio.run(
            driver.run(
                definition_id="ledger.track",
                subject_ref=profile_operation_subject(str(profile_id)),
                payload=request,
                secret=None,
            )
        )
        assert observed.projection.lifecycle is OperationLifecycle.TERMINAL
        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert observed.projection.effect is OperationEffect.NONE
        track = _resolve_result_projection(
            driver,
            registry,
            definition_id="ledger.track",
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerTrackProjection,
        )
        assert isinstance(track, LedgerTrackProjection)
        assert track.transaction.transaction_id == created.ref.transaction_id
        assert track.participated_in is None
        index = TransactionParticipationIndexRepository(bucket_id=str(profile_id)).load(created.ref.transaction_id)
        assert index.transaction_id == created.ref.transaction_id
        assert index.participations == ()
        assert isinstance(observed.projection.pending_interaction, OperationNoPendingInteractionV1)
        asyncio.run(
            driver.review_not_pending(
                operation_id=submitted.receipt.operation_id,
                revision=observed.projection.revision,
                registry=registry,
            )
        )


@pytest.mark.parametrize("raced_catalogue", ["filing", "work_unit", "calculation"])
@pytest.mark.timeout(90)
def test_amendment_co_commit_refuses_each_stale_catalogue_without_partial_writes(
    tmp_path: Path,
    raced_catalogue: str,
    monkeypatch: pytest.MonkeyPatch,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The real amendment writer preserves a valid concurrent write on every CAS axis."""
    filing_record_id: str | None = None
    work_unit_id: str | None = None
    calculation_revision_id: str | None = None
    raced: list[str] = []
    raced_calculation_instants: list[datetime] = []
    concurrent_filing_note = "concurrent filing catalogue update"
    concurrent_work_unit_name = "Concurrent work-unit update"

    def amendment_ports_factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> AmendmentActionPorts:
        ports = build_amendment_action_ports(bucket_id=bucket_id, operation=operation)
        if raced_catalogue == "filing":
            filing_repository = cast(ModeloRecordCatalogueRepository, ports.filing_repository)
            original_filing_load = filing_repository.load_revisioned

            def load_revisioned() -> tuple[ModeloRecordCatalogue, str]:
                catalogue, revision_id = original_filing_load()
                if not raced:
                    assert filing_record_id is not None
                    record = catalogue.get(filing_record_id)
                    assert record is not None
                    concurrent_record = record.model_copy(update={"notes": concurrent_filing_note})
                    filing_repository.save(
                        ModeloRecordCatalogue(records={**catalogue.records, filing_record_id: concurrent_record})
                    )
                    raced.append(raced_catalogue)
                return catalogue, revision_id

            monkeypatch.setattr(filing_repository, "load_revisioned", load_revisioned)
        elif raced_catalogue == "work_unit":
            work_unit_repository = cast(WorkUnitCatalogueRepository, ports.work_unit_repository)
            original_work_unit_load = work_unit_repository.load_revisioned

            def load_revisioned() -> tuple[WorkUnitCatalogue, str]:
                catalogue, revision_id = original_work_unit_load()
                if not raced:
                    assert work_unit_id is not None
                    original_unit = catalogue.get(work_unit_id)
                    assert original_unit is not None
                    updated_at = max(now(), original_unit.updated_at) + timedelta(seconds=1)
                    concurrent_unit = WorkUnit.model_validate(
                        {
                            **original_unit.model_dump(mode="python"),
                            "name": concurrent_work_unit_name,
                            "updated_at": updated_at,
                        },
                        strict=True,
                    )
                    work_unit_repository.save(
                        WorkUnitCatalogue(work_units={**catalogue.work_units, work_unit_id: concurrent_unit})
                    )
                    raced.append(raced_catalogue)
                return catalogue, revision_id

            monkeypatch.setattr(work_unit_repository, "load_revisioned", load_revisioned)
        elif raced_catalogue == "calculation":
            calculation_repository = cast(CalculationRevisionCatalogueRepository, ports.calculation_repository)
            original_calculation_load = calculation_repository.load_revisioned

            def load_revisioned(
                *, operation: PinnedAuthorityOperation | None = None
            ) -> tuple[CalculationRevisionCatalogue, str]:
                catalogue, revision_id = original_calculation_load(operation=operation)
                if not raced:
                    assert calculation_revision_id is not None
                    revision = catalogue.get(calculation_revision_id)
                    assert revision is not None
                    lifecycle_instants = (
                        revision.created_at,
                        revision.updated_at,
                        revision.verified_at,
                        revision.filed_at,
                        revision.superseded_at,
                        revision.discarded_at,
                    )
                    updated_at = max(instant for instant in lifecycle_instants if instant is not None) + timedelta(
                        seconds=1
                    )
                    concurrent_revision = revision.model_copy(update={"updated_at": updated_at})
                    calculation_repository.save(
                        CalculationRevisionCatalogue(
                            revisions={
                                **catalogue.revisions,
                                calculation_revision_id: concurrent_revision,
                            }
                        )
                    )
                    raced_calculation_instants.append(updated_at)
                    raced.append(raced_catalogue)
                return catalogue, revision_id

            monkeypatch.setattr(calculation_repository, "load_revisioned", load_revisioned)
        else:  # pragma: no cover - parametrization is deliberately closed.
            raise AssertionError(f"unknown amendment CAS catalogue: {raced_catalogue}")
        return ports

    with _runtime(
        tmp_path / f"amendment-cas-{raced_catalogue}",
        cleanup=_CloseWitness(),
        amendment_action_ports_factory=amendment_ports_factory,
    ) as (driver, registry, profile_id):
        definition = registry.lookup("modelo.work.amend")
        subject_ref, payload, secret = _payload(
            definition,
            profile_id=profile_id,
            tmp_path=tmp_path / f"amendment-cas-{raced_catalogue}",
            operation=operation,
        )
        assert secret is None
        filing_record_id = subject_ref

        records_before = ModeloRecordCatalogueRepository().load()
        baseline = records_before.get(filing_record_id)
        assert baseline is not None
        work_unit_id = baseline.work_unit_id
        calculation_revision_id = baseline.calculation_revision_id
        work_units_before = WorkUnitCatalogueRepository().load()
        calculations_before = CalculationRevisionCatalogueRepository().load()
        events_before = BucketEventHistoryRepository().load()
        original_work_unit = work_units_before.get(work_unit_id)
        assert original_work_unit is not None
        assert calculations_before.get(calculation_revision_id) is not None

        submitted, observed = asyncio.run(
            driver.run(definition_id=definition.definition_id, subject_ref=subject_ref, payload=payload)
        )
        assert observed.projection.lifecycle is OperationLifecycle.TERMINAL
        assert observed.projection.terminal_condition is OperationTerminalCondition.FAILED
        assert observed.projection.effect is OperationEffect.UNKNOWN
        assert observed.projection.result_ref is None
        assert observed.projection.diagnostic_ref is not None
        assert raced == [raced_catalogue]

        records_after = ModeloRecordCatalogueRepository().load()
        work_units_after = WorkUnitCatalogueRepository().load()
        calculations_after = CalculationRevisionCatalogueRepository().load()
        events_after = BucketEventHistoryRepository().load()
        if raced_catalogue == "filing":
            concurrent_record = records_after.get(filing_record_id)
            assert concurrent_record is not None
            assert concurrent_record.notes == concurrent_filing_note
            expected_records = dict(records_before.records)
            expected_records[filing_record_id] = concurrent_record
            assert records_after.records == expected_records
        else:
            assert records_after.records == records_before.records
        if raced_catalogue == "work_unit":
            concurrent_unit = work_units_after.get(work_unit_id)
            assert concurrent_unit is not None
            assert concurrent_unit.name == concurrent_work_unit_name
            assert concurrent_unit.updated_at > original_work_unit.updated_at
            expected_work_units = dict(work_units_before.work_units)
            expected_work_units[work_unit_id] = concurrent_unit
            assert work_units_after.work_units == expected_work_units
        else:
            assert work_units_after.work_units == work_units_before.work_units
        if raced_catalogue == "calculation":
            concurrent_revision = calculations_after.get(calculation_revision_id)
            assert concurrent_revision is not None
            assert len(raced_calculation_instants) == 1
            assert concurrent_revision.updated_at == raced_calculation_instants[0]
            expected_revisions = dict(calculations_before.revisions)
            expected_revisions[calculation_revision_id] = concurrent_revision
            assert calculations_after.revisions == expected_revisions
        else:
            assert calculations_after.revisions == calculations_before.revisions
        assert events_after.events == events_before.events
        assert not any(record.amends_filing_record_id is not None for record in records_after.records.values())
        assert submitted.receipt.operation_id == observed.projection.operation_id


@pytest.mark.timeout(90)
def test_calculate_refused_before_persisting_reports_no_effect(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A precondition refusal settles REFUSED with NONE, never the open UNKNOWN.

    Modelo 303 filing evidence addressed to a Modelo 130 unit is refused while
    the executor is still only reading, so nothing can have been written and
    the truthful effect is NONE.
    """
    with _runtime(tmp_path / "calculate-refusal", cleanup=_CloseWitness()) as (driver, registry, profile_id):
        definition = registry.lookup("modelo.work.calculate")
        unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
        payload = definition.request_type.model_validate(
            {
                "work_unit_id": unit.work_unit_id,
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                "ordinary_m303_filing_evidence": {"joint_return_elected": False},
            },
            strict=True,
        )

        _submitted, observed = asyncio.run(
            driver.run(definition_id=definition.definition_id, subject_ref=unit.work_unit_id, payload=payload)
        )

        assert observed.projection.lifecycle is OperationLifecycle.TERMINAL
        assert observed.projection.terminal_condition is OperationTerminalCondition.REFUSED
        assert observed.projection.refusal_ref == "REFUSED_MODELO_M303_FILING_EVIDENCE"
        assert observed.projection.effect is OperationEffect.NONE


def test_censo_cooperative_cancellation_settles_after_its_irreversible_section(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Drive manual cancellation through the public control service to its exact terminal receipt."""
    reached_boundary = asyncio.Event()
    release_boundary = asyncio.Event()

    async def before_irreversible_section() -> None:
        reached_boundary.set()
        await release_boundary.wait()

    cleanup = _CloseWitness()
    with _runtime(
        tmp_path / "censo-cancellation",
        cleanup=cleanup,
        before_irreversible_section=before_irreversible_section,
    ) as (driver, registry, profile_id):
        definition = registry.lookup("user-profile.censo-review")
        subject_ref, payload, secret = _payload(
            definition, profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )

        async def run() -> None:
            submitted = await driver.prepare(
                definition_id=definition.definition_id,
                subject_ref=subject_ref,
                payload=payload,
                secret=secret,
            )
            await driver.services.submission.start(submitted.receipt.operation_id)
            await driver.services.submission.settled(submitted.receipt.operation_id)
            waiting = await driver.observe(submitted.receipt.operation_id)
            operation_id = await driver.respond_apply(submitted, waiting)
            await reached_boundary.wait()
            running = await driver.observe(operation_id)
            requested = await driver.services.cancellation.request(
                OperationCancellationRequestV1(operation_id=operation_id, expected_revision=running.projection.revision)
            )
            assert isinstance(requested, OperationCancellationSuccessV1)
            assert requested.cancellation_acknowledged is False
            release_boundary.set()
            terminal = await driver.await_terminal(operation_id)
            assert terminal.projection.terminal_condition is OperationTerminalCondition.CANCELLED
            assert terminal.projection.effect is OperationEffect.NONE
            assert terminal.projection.cancellation_acknowledged is True
            assert terminal.projection.cleanup_deadline_at is not None
            assert cleanup.closed is True

        asyncio.run(run())


def test_censo_execution_deadline_settles_its_actual_cooperative_safe_stop(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Let the supervisor-owned deadline drive the production CENSO continuation to timed out.

    The deadline must pass while the review waits, not while the executor is
    still working up to it: a deadline that expires first stops the executor
    before any review exists. Holding the supervisor clock until the review is
    on offer fixes that order on any host instead of racing a 50 ms budget.
    """
    cleanup = _CloseWitness()
    clock = _HeldClock()
    with _runtime(
        tmp_path / "censo-deadline",
        cleanup=cleanup,
        execution_timeout=timedelta(milliseconds=50),
        clock=clock,
    ) as (driver, registry, profile_id):
        definition = registry.lookup("user-profile.censo-review")
        subject_ref, payload, secret = _payload(
            definition, profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )

        async def run() -> None:
            submitted, waiting = await driver.run(
                definition_id=definition.definition_id,
                subject_ref=subject_ref,
                payload=payload,
                secret=secret,
            )
            assert waiting.projection.execution_deadline_at is not None
            await asyncio.sleep(max((waiting.projection.execution_deadline_at - now()).total_seconds(), 0) + 0.01)
            clock.release()
            operation_id = await driver.respond_apply(submitted, waiting)
            terminal = await driver.await_terminal(operation_id)
            assert terminal.projection.terminal_condition is OperationTerminalCondition.TIMED_OUT
            assert terminal.projection.effect is OperationEffect.NONE
            assert terminal.projection.cancellation_requested is True
            assert terminal.projection.cancellation_acknowledged is True
            assert terminal.projection.cleanup_deadline_at is not None
            assert cleanup.closed is True

        asyncio.run(run())


def test_the_filing_authority_accepts_the_registered_operation_fixture(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The direct filing door accepts the same genuine grant as the executor.

    This control uses the same seeded and verified revision, actor and workflow
    profile as the registered operation. It separates fixture/domain validity
    from any future operation-wrapper regression without fabricating a report.
    """
    from ...application.modelo.filing_actions import file_modelo_revision

    with _runtime(tmp_path / "authority-control", cleanup=_CloseWitness()) as (_driver, _registry, profile_id):
        revision_id, report_id = modelo_operation_test_support.seeded_modelo_verification_report(
            profile_id, operation=operation
        )

        with bundled_indexed_authority().operation() as operation:
            record = file_modelo_revision(
                revision_id,
                approved_verification_report_id=report_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                ports=build_filing_action_ports(bucket_id=str(profile_id)),
                actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                workflow_profile=resolve_active_workflow_profile(operation),
                operation=operation,
                notes=None,
            ).record

        assert record is not None, "the filing authority produced no record for a verified-complete revision"
