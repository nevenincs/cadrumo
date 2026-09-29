"""Real-supervisor conformance matrix for every production executor."""

from __future__ import annotations

import asyncio
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
from pydantic import BaseModel

from cadrumo.adapters.outbound.aeat.browser.factory import default_browser_session_factory
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
from ...adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ...adapters.persistence.profile.tests.cross_period_seeding import (
    SEEDED_SOURCE_TAX_ID,
    seed_clean_cross_period_sources,
)
from ...adapters.persistence.profile.tests.justificante_metadata import persist_justificante_metadata
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ...application.auth.operation_definitions import build_auth_operation_definitions
from ...application.auth.read_operation import (
    AUTH_READ_OPERATION_DEFINITION_ID,
    AuthReadProjection,
    AuthReadRequest,
)
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
from ...application.ledger.actions_manual import create_manual_transaction
from ...application.ledger.check_operation import LedgerCheckProjection, LedgerCheckRequest
from ...application.ledger.history_operation import LedgerHistoryProjection, LedgerHistoryRequest
from ...application.ledger.id_resolution import resolve_lineage_transaction_id
from ...application.ledger.list_operation import LedgerListProjection, LedgerListRequest
from ...application.ledger.llm_classification import reject_llm_suggestion
from ...application.ledger.llm_classification_ports import LLMClassificationSuggestion
from ...application.ledger.models import ManualLedgerTransactionCommand
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
from ...application.ledger.review_operation import LedgerReviewProjection, LedgerReviewRequest
from ...application.ledger.status_operation import LedgerStatusProjection, LedgerStatusRequest
from ...application.ledger.track_operation import LedgerTrackProjection, LedgerTrackRequest
from ...application.ledger.tracking_projection import (
    LedgerParticipationProjection as LedgerParticipationEntryProjection,
)
from ...application.ledger.view_operation import LedgerViewProjection, LedgerViewRequest
from ...application.live.iva_wallet_history_operation import (
    IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID,
    IvaWalletHistoryProjection,
    IvaWalletHistoryRequest,
)
from ...application.local_reader_operation import LOCAL_READER_OPERATION_SUBJECT, LocalReaderProvisionAction
from ...application.modelo.amendment_action_ports import AmendmentActionPorts, AmendmentActionPortsFactory
from ...application.modelo.calculation_actions import calculate_modelo_revision
from ...application.modelo.dependency_operation import (
    MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,
    ModeloDependencyProjection,
    ModeloDependencyRequest,
)
from ...application.modelo.external_import_actions import import_external_filing_evidence
from ...application.modelo.history_operation import ModeloWorkHistoryProjection, ModeloWorkHistoryRequest
from ...application.modelo.m303_attestation_operation import (
    ModeloWorkM303AttestationPublicResultV2,
    ModeloWorkM303AttestationRequest,
)
from ...application.modelo.operation_definitions import (
    ModeloWorkCalculateRequest,
    resolve_active_workflow_profile,
)
from ...application.modelo.review_package_operation import (
    ModeloReviewPackageBuildPublicResultV1,
    ModeloReviewPackageBuildRequest,
)
from ...application.modelo.revision_inventory_operation import (
    ModeloWorkRevisionsProjection,
    ModeloWorkRevisionsRequest,
)
from ...application.modelo.revision_snapshot_operation import ModeloWorkRevisionSnapshotRequest
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
from ...application.review.filter import LedgerReviewStatus
from ...application.user_profile.automation_operations import build_automation_operation_definitions
from ...application.user_profile.bundle_export_contracts import ProfileBundleExportPurpose
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
from ...application.user_profile.registration import register_profile_with_credentials
from ...application.user_profile.section_rows import add_profile_repeatable_section_row
from ...application.user_profile.view_operation import ProfileViewPageKind
from ...application.workflow.abort import WorkflowAbortReason
from ...application.workflow.persistence import WorkflowRunRepository
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
from ...core.config import override_settings
from ...core.errors.hierarchy import InternalInvariantError
from ...core.external_constants import OutputLanguage
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
from ...domain.buckets.event import BucketEventType
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
from ...domain.calculations.registry.tests.cross_period_seeding import resolved_revision
from ...domain.deadlines.models import ObligationStatus
from ...domain.invoices.enums import IvaRate, PaymentStatus
from ...domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ...domain.invoices.service import LinkInconsistency
from ...domain.iva.classification import InvoiceKind
from ...domain.iva_compensation.carry_forward import IvaCompensationPeriodState
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue, CalculationRevisionState
from ...domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from ...domain.modelos.filing_record import ExternalEvidenceKind, ModeloRecordCatalogue
from ...domain.modelos.verification_report import VerificationCompletenessStatus
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.user_profile.plantilla_media import PlantillaMediaState
from ...domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ...domain.user_profile.values import UserProfileFact
from ...tests.aeat_literal_fixtures import aeat_url
from ..adapter_composition import (
    build_amendment_action_ports,
    build_calculation_action_ports,
    build_censal_fetch_port,
    build_filing_action_ports,
    build_verification_repository_bundle,
)
from ..censal_review import review_censal_with_services
from ..ledger_action_composition import compose_ledger_action_ports
from ..operation_composition import build_auth_operation_ports, build_production_operation_registry
from . import modelo_operation_test_support
from .profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
)

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
            OperationEffect.UNKNOWN,
            # No certificate is configured in the isolated root, so the
            # provider's local readiness refuses before any session attempt.
            expected_refusal_ref="REFUSED_AUTH_LOGIN_PRECONDITION",
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


def _payload(
    definition: OperationDefinition, *, profile_id: UUID, tmp_path: Path, operation: PinnedAuthorityOperation
) -> tuple[str, BaseModel, bytes | None]:
    """Use only the exact request type exported by the registered definition."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    values: dict[str, object]
    secret: bytes | None = None
    subject_ref = f"profile:{profile_id}"
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
        case "modelo.export":
            # A DRAFT revision is not exportable. `_require_exportable_revision_state`
            # admits only SEALED states (VERIFICADO_COMPLETO, PRESENTADO,
            # PRESENTADO_SUPERSEDIDO), because a fichero is a filing-grade
            # artefact and a return still being edited has no business becoming
            # one. So this seeds through verification rather than calculation.
            revision_id, _report_id = modelo_operation_test_support.seeded_modelo_verification_report(
                profile_id, operation=operation
            )
            subject_ref = revision_id
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
    cleanup = _CloseWitness()
    with (
        _closed_model_runtime() if definition_id == "local-reader.provision" else nullcontext(),
        _runtime(tmp_path / case.definition_id, cleanup=cleanup) as (driver, registry, profile_id),
    ):
        definitions = {definition.definition_id: definition for definition in registry.definitions}
        definition = definitions[case.definition_id]
        subject_ref, payload, secret = _payload(
            definition, profile_id=profile_id, tmp_path=tmp_path / case.definition_id, operation=operation
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
        if case.definition_id == "ledger.track":
            assert isinstance(payload, LedgerTrackRequest)
            track = _resolve_result_projection(
                driver,
                registry,
                definition_id=case.definition_id,
                operation_id=submitted.receipt.operation_id,
                terminal_revision=observed.projection.revision,
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
                CalculationRevisionCatalogueRepository()
                .load(operation=operation)
                .get(participation.calculation_revision_id)
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
        if case.definition_id == "ledger.participation":
            assert isinstance(payload, LedgerParticipationRequest)
            participation_result = _resolve_result_projection(
                driver,
                registry,
                definition_id=case.definition_id,
                operation_id=submitted.receipt.operation_id,
                terminal_revision=observed.projection.revision,
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
        if case.definition_id == "ledger.participation.rebuild":
            assert isinstance(payload, LedgerParticipationRebuildRequest)
            rebuild_result = _resolve_result_projection(
                driver,
                registry,
                definition_id=case.definition_id,
                operation_id=submitted.receipt.operation_id,
                terminal_revision=observed.projection.revision,
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
            index = TransactionParticipationIndexRepository(bucket_id=str(profile_id)).load(
                transactions[0].transaction_id
            )
            assert len(index.participations) == 1
            assert index.participations[0].revision_state == CalculationRevisionState.VERIFICADO_COMPLETO.value
        if case.definition_id == "ledger.review":
            assert isinstance(payload, LedgerReviewRequest)
            review = _resolve_result_projection(
                driver,
                registry,
                definition_id=case.definition_id,
                operation_id=submitted.receipt.operation_id,
                terminal_revision=observed.projection.revision,
                projection_type=LedgerReviewProjection,
            )
            assert isinstance(review, LedgerReviewProjection)
            assert review.profile_id == profile_id
            assert review.transaction_prefix == payload.transaction_prefix
            assert len(review.rows) == 1
            row = review.rows[0]
            assert row.description == "conformance review seed"
            assert row.status is LedgerReviewStatus.PENDING
            assert row.transaction is not None
            assert row.transaction.description == row.description
            assert row.transaction.transaction_id.startswith(cast(str, payload.transaction_prefix))
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
