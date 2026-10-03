"""Strict versioned public projection of the complete workbench generation.

Only incompatible canonical nodes are mirrored; compatible children retain their
existing typed models. Projection and restoration validate the original models.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, Self, cast
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

from cadrumo.application.aeat_sync.workspace import (
    AeatSyncAeatObservationState,
    AeatSyncDiscrepancyKind,
    AeatSyncJustificanteState,
    AeatSyncLocalFilingState,
    AeatSyncReconciliationState,
    AeatSyncSourceState,
    AeatSyncWorkspaceCensusRowV1,
    AeatSyncWorkspaceNotificationRowV1,
    AeatSyncWorkspaceOverviewRowV1,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceZoneStateV1,
)
from cadrumo.application.ledger.preflight import LedgerPreflightIssueReason
from cadrumo.application.ledger.workspace import (
    LedgerInvoiceReconciliationRefV1,
    LedgerLinkInconsistencyRefV1,
    LedgerWorkspaceAreaStateV1,
    LedgerWorkspaceEntryRefV1,
    LedgerWorkspaceProjectionV1,
)
from cadrumo.application.modelo.declaration_summary import DeclarationSummary, DeclarationSummaryState
from cadrumo.application.modelo.declarations_calendar import (
    DeclarationsCalendarEntryRefV1,
    DeclarationsCalendarSourceStateV1,
)
from cadrumo.application.modelo.declarations_workspace import (
    DeclarationsLifecycleKind,
    DeclarationsWorkspaceCalculationRevisionRefV1,
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceFilingRefV1,
    DeclarationsWorkspaceLifecycleRefV1,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceZoneStateV1,
)
from cadrumo.application.modelo.row_source_fingerprint import (
    ModeloRowSourceFingerprint,
)
from cadrumo.application.modelo.work_form_models import ModeloFormResultDirection
from cadrumo.application.modelo.work_review import (
    ModeloWorkBindingOrigin,
    ModeloWorkFormulaOrigin,
    ModeloWorkOriginAnomaly,
    ModeloWorkProgress,
    ModeloWorkRelationConsumption,
)
from cadrumo.application.modelo.workspace_models import (
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceContributorIdentityV1,
    ModeloWorkspaceEvidenceFactV1,
    ModeloWorkspaceEvidenceHorizonV1,
    ModeloWorkspaceFacetName,
    ModeloWorkspaceFamilyDispositionV1,
    ModeloWorkspaceGradedSnapshotScopeV1,
    ModeloWorkspaceLegalEvidenceReferenceV1,
    ModeloWorkspaceLocaleSummaryV1,
    ModeloWorkspaceProjectionV1,
    ModeloWorkspaceProvenanceRecordV1,
    ModeloWorkspaceRevisionAssertionV1,
    ModeloWorkspaceSchemaIdentityV1,
    ModeloWorkspaceSchemaRecordV1,
    ModeloWorkspaceSourceEvidenceReferenceV1,
    ModeloWorkspaceStaticInspectionScopeV1,
)
from cadrumo.application.operator_actions.models import ActionReference
from cadrumo.application.overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendarEntrySource,
    OverviewCalendarRange,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from cadrumo.application.overview.coverage import ObligationCoverageReport
from cadrumo.application.overview.home import (
    HomeAccountSession,
    HomeDeclarationState,
    HomeLedgerReadiness,
    HomeZoneState,
)
from cadrumo.application.search.installed_workbench import (
    InstalledWorkbenchSearchSnapshotV1,
)
from cadrumo.application.search.workbench import WorkbenchDestinationAdmission
from cadrumo.application.state_projection import ModeloProfileRefusalCause, ModeloRegistryRefusalCause
from cadrumo.application.user_profile.commands import ProfilePreflightRequirement
from cadrumo.application.workbench_generation import (
    WorkbenchGenerationAvailability,
)
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.estado_casilla_oficial import EstadoCasillaOficial
from cadrumo.core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
    OperatorActionAxis,
)
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.core.revision_review import RevisionReviewStatus
from cadrumo.core.schema_family_disposition import (
    RegistrySchemaFamilyDisposition,
)
from cadrumo.domain.calculations.registry.schema_base import CasillaSignConstraint
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.deadlines.festivos import DeadlineHolidayCoverage
from cadrumo.domain.deadlines.models import ObligationStatus
from cadrumo.domain.filing.schema import ModeloValueKind
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecordStatus,
)
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from cadrumo.domain.modelos.work_unit import WorkUnitState

from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.time.utc import validate_utc_aware
from .operations.public_mirror import (
    PublicFactEntryV1,
    PublicScalarValueV1,
    excluded_canonical_fields,
    project_public_mirror,
    restore_public_mirror,
)
from .operations.public_period import PublicPeriod
from .workbench_generation import (
    WorkbenchGenerationProjectionResultV1,
    WorkbenchGenerationV1,
    assemble_workbench_generation_search,
)


class PublicWorkbenchGenerationV1(BaseModel):
    """Typed local-human workbench view of WorkbenchGenerationV1."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: Literal[1]
    assembled_at: datetime
    home: PublicHomeGenerationStateV1
    ledger: PublicLedgerGenerationStateV1
    declarations: PublicDeclarationsGenerationStateV1
    declarations_calendar: PublicDeclarationsCalendarGenerationResultV1
    aeat_sync: PublicAeatSyncGenerationResultV1
    modelo: PublicModeloGenerationStateV1
    search: PublicSearchGenerationStateV1
    ledger_admission: WorkbenchDestinationAdmission
    declarations_admission: WorkbenchDestinationAdmission
    aeat_sync_admission: WorkbenchDestinationAdmission


class PublicAeatSyncGenerationResultV1(BaseModel):
    """Typed local-human workbench view of AeatSyncGenerationResultV1."""

    model_config = STRICT_FROZEN_CONFIG

    availability: WorkbenchGenerationAvailability
    observed_at: datetime | None
    refusal: str | None
    projection: PublicAeatSyncWorkspaceProjectionV1 | None


class PublicAeatSyncWorkspaceProjectionV1(BaseModel):
    """Typed local-human workbench view of AeatSyncWorkspaceProjectionV1."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: int
    zones: tuple[AeatSyncWorkspaceZoneStateV1, ...]
    overview: tuple[AeatSyncWorkspaceOverviewRowV1, ...]
    census: tuple[AeatSyncWorkspaceCensusRowV1, ...]
    filed_declarations: tuple[PublicAeatSyncWorkspaceFiledDeclarationRowV1, ...]
    notifications: tuple[AeatSyncWorkspaceNotificationRowV1, ...]
    evidence_comparison: tuple[PublicAeatSyncWorkspaceEvidenceComparisonRowV1, ...]
    reconciliation: tuple[PublicAeatSyncWorkspaceReconciliationRowV1, ...]


class PublicAeatSyncWorkspaceEvidenceComparisonRowV1(BaseModel):
    """Typed local-human workbench view of AeatSyncWorkspaceEvidenceComparisonRowV1."""

    model_config = STRICT_FROZEN_CONFIG

    supported_actions: tuple[ActionReference, ...]
    supported_operations: tuple[str, ...]
    modelo: str
    filing_year: int
    period: PublicPeriod
    local_state: AeatSyncSourceState
    aeat_state: AeatSyncSourceState
    local_observed_at: datetime | None
    aeat_observed_at: datetime | None
    discrepancy_kind: AeatSyncDiscrepancyKind
    local_value: str | None
    aeat_value: str | None


class PublicAeatSyncWorkspaceFiledDeclarationRowV1(BaseModel):
    """Typed local-human workbench view of AeatSyncWorkspaceFiledDeclarationRowV1."""

    model_config = STRICT_FROZEN_CONFIG

    supported_actions: tuple[ActionReference, ...]
    supported_operations: tuple[str, ...]
    modelo: str
    filing_year: int
    period: PublicPeriod
    local_filing_state: AeatSyncLocalFilingState
    local_filed_at: datetime | None
    aeat_observation_state: AeatSyncAeatObservationState
    aeat_observed_at: datetime | None
    justificante_state: AeatSyncJustificanteState
    justificante_observed_at: datetime | None


class PublicAeatSyncWorkspaceReconciliationRowV1(BaseModel):
    """Typed local-human workbench view of AeatSyncWorkspaceReconciliationRowV1."""

    model_config = STRICT_FROZEN_CONFIG

    supported_actions: tuple[ActionReference, ...]
    supported_operations: tuple[str, ...]
    modelo: str
    filing_year: int
    period: PublicPeriod
    local_state: AeatSyncSourceState
    aeat_state: AeatSyncSourceState
    local_observed_at: datetime | None
    aeat_observed_at: datetime | None
    discrepancy_kind: AeatSyncDiscrepancyKind
    local_value: str | None
    aeat_value: str | None
    reconciliation_state: AeatSyncReconciliationState


class PublicDeclarationsGenerationStateV1(BaseModel):
    """Typed local-human workbench view of DeclarationsGenerationStateV1."""

    model_config = STRICT_FROZEN_CONFIG

    availability: WorkbenchGenerationAvailability
    observed_at: datetime | None
    refusal: str | None
    projection: PublicDeclarationsWorkspaceProjectionV1 | None


class PublicDeclarationsWorkspaceProjectionV1(BaseModel):
    """Typed local-human workbench view of DeclarationsWorkspaceProjectionV1."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: int
    bucket_id: str
    zones: tuple[DeclarationsWorkspaceZoneStateV1, ...]
    declarations: tuple[PublicDeclarationsWorkspaceDeclarationRefV1, ...]
    calculation_revisions: tuple[PublicDeclarationsWorkspaceCalculationRevisionRefV1, ...]
    filings: tuple[PublicDeclarationsWorkspaceFilingRefV1, ...]
    lifecycle: tuple[PublicDeclarationsWorkspaceLifecycleRefV1, ...]
    creation_targets: tuple[PublicDeclarationTarget, ...]


class PublicDeclarationTarget(BaseModel):
    """Typed local-human workbench view of DeclarationTarget."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    period: PublicPeriod


class PublicDeclarationsWorkspaceCalculationRevisionRefV1(BaseModel):
    """Typed local-human workbench view of DeclarationsWorkspaceCalculationRevisionRefV1."""

    model_config = STRICT_FROZEN_CONFIG

    calculation_revision_id: str
    work_unit_id: str
    modelo: str
    filing_year: int
    period: PublicPeriod
    state: CalculationRevisionState
    created_at: datetime
    updated_at: datetime
    is_current: bool
    is_filed: bool


class PublicDeclarationsWorkspaceDeclarationRefV1(BaseModel):
    """Typed local-human workbench view of DeclarationsWorkspaceDeclarationRefV1."""

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: str
    modelo: str
    filing_year: int
    period: PublicPeriod
    state: WorkUnitState
    has_current_calculation: bool
    has_current_filing: bool
    settled_result: str | None
    summary: PublicDeclarationSummary | None


class PublicDeclarationSummary(BaseModel):
    """Typed local-human workbench view of DeclarationSummary."""

    model_config = STRICT_FROZEN_CONFIG

    state: DeclarationSummaryState
    blocking_count: int | None
    checked: bool
    result: PublicModeloFormResult | None
    is_correction: bool
    technical_reason: str | None


class PublicModeloFormResult(BaseModel):
    """Typed local-human workbench view of ModeloFormResult."""

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: str
    box: str | None
    value: str | None
    direction: ModeloFormResultDirection
    disposition: ResultDisposition | None
    election_may_change: bool


class PublicDeclarationsWorkspaceFilingRefV1(BaseModel):
    """Typed local-human workbench view of DeclarationsWorkspaceFilingRefV1."""

    model_config = STRICT_FROZEN_CONFIG

    filing_record_id: str
    work_unit_id: str
    calculation_revision_id: str
    modelo: str
    filing_year: int
    period: PublicPeriod
    filed_at: datetime
    local_status: ModeloRecordStatus
    origin: FilingOrigin
    confirmation: AeatConfirmationState
    declaration_kind: FilingDeclarationKind
    amends_filing_record_id: str | None
    evidence_kind: ExternalEvidenceKind | None


class PublicDeclarationsWorkspaceLifecycleRefV1(BaseModel):
    """Typed local-human workbench view of DeclarationsWorkspaceLifecycleRefV1."""

    model_config = STRICT_FROZEN_CONFIG

    fact_id: str
    work_unit_id: str
    modelo: str
    filing_year: int
    period: PublicPeriod
    occurred_at: datetime
    kind: DeclarationsLifecycleKind


class PublicDeclarationsCalendarGenerationResultV1(BaseModel):
    """Typed local-human workbench view of DeclarationsCalendarGenerationResultV1."""

    model_config = STRICT_FROZEN_CONFIG

    availability: WorkbenchGenerationAvailability
    observed_at: datetime | None
    refusal: str | None
    projection: PublicDeclarationsCalendarProjectionV1 | None


class PublicDeclarationsCalendarProjectionV1(BaseModel):
    """Typed local-human workbench view of DeclarationsCalendarProjectionV1."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: int
    as_of: date
    generated_at: datetime
    query_range: OverviewCalendarRange
    sources: tuple[DeclarationsCalendarSourceStateV1, ...]
    entries: tuple[PublicDeclarationsCalendarEntryRefV1, ...]
    coverage: ObligationCoverageReport


class PublicDeclarationsCalendarEntryRefV1(BaseModel):
    """Typed local-human workbench view of DeclarationsCalendarEntryRefV1."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    filing_year: int
    period: PublicPeriod
    opens_on: date
    closes_on: date
    adjusted_closes_on: date
    shift_reason: str
    holiday_coverage: DeadlineHolidayCoverage
    holiday_territory: str | None
    payment_cutoff_on: date | None
    evaluated_on: date
    days_overdue: int | None
    legal_status: ObligationStatus
    user_state: OverviewPeriodState
    local_filing_state: OverviewLocalFilingState | None
    aeat_submission_state: OverviewAeatSubmissionState | None
    justificante_verified: bool | None
    evidence_conflicted: bool
    aeat_submitted_at: datetime | None
    aeat_reference_id: str | None
    aeat_needs_check: bool
    source: OverviewCalendarEntrySource
    conditional_recargo_preview: PublicModeloWorkConditionalRecargoPreview | None
    recovery_action: PublicDeclaredNextAction | None


class PublicModeloWorkConditionalRecargoPreview(BaseModel):
    """Typed local-human workbench view of ModeloWorkConditionalRecargoPreview."""

    model_config = STRICT_FROZEN_CONFIG

    band_id: str
    surcharge_pct: str
    interest_applies: bool
    legal_ref: str
    rate_reference_on: date
    assessment_status: Literal["unassessed"]

    @field_validator("surcharge_pct")
    @classmethod
    def _valid_decimal_rate(cls, value: str) -> str:
        try:
            decimal = Decimal(value)
        except InvalidOperation:
            raise ValueError("invalid surcharge percentage") from None
        if not decimal.is_finite() or decimal < 0 or str(decimal) != value:
            raise ValueError("invalid surcharge percentage")
        return value


class PublicHomeGenerationStateV1(BaseModel):
    """Typed local-human workbench view of HomeGenerationStateV1."""

    model_config = STRICT_FROZEN_CONFIG

    availability: WorkbenchGenerationAvailability
    observed_at: datetime | None
    refusal: str | None
    projection: PublicHomeProjectionV1 | None


class PublicHomeProjectionV1(BaseModel):
    """Typed local-human workbench view of HomeProjectionV1."""

    model_config = STRICT_FROZEN_CONFIG

    generated_at: datetime
    account: HomeAccountSession
    actions_state: HomeZoneState
    actions: tuple[PublicHomeNextAction, ...]
    declarations_state: HomeZoneState
    declarations: tuple[PublicHomeDeclarationResume, ...]
    ledger_state: HomeZoneState
    ledger: HomeLedgerReadiness | None
    agenda_state: HomeZoneState
    agenda_evidence_state: HomeZoneState
    agenda: tuple[PublicHomeAgendaEntry, ...]
    messages_state: HomeZoneState
    messages_requiring_attention: int | None


class PublicHomeNextAction(BaseModel):
    """Typed local-human workbench view of HomeNextAction."""

    model_config = STRICT_FROZEN_CONFIG

    rank: int
    action: PublicDeclaredNextAction
    reason_code: str
    modelo: str | None
    filing_year: int | None
    period: PublicPeriod | None


class PublicDeclaredNextAction(BaseModel):
    """Typed local-human workbench view of DeclaredNextAction."""

    model_config = STRICT_FROZEN_CONFIG

    action: ActionReference
    argument_bindings: tuple[PublicActionArgumentBinding, ...]


class PublicActionArgumentBinding(BaseModel):
    """Typed local-human workbench view of ActionArgumentBinding."""

    model_config = STRICT_FROZEN_CONFIG

    argument_name: str
    status: ActionArgumentStatus
    value: PublicScalarValueV1
    source: ActionArgumentSource | None
    source_key: str | None
    source_evidence_id: str | None


class PublicHomeAgendaEntry(BaseModel):
    """Typed local-human workbench view of HomeAgendaEntry."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    filing_year: int
    period: PublicPeriod
    due_on: date
    period_state: OverviewPeriodState
    local_filing_state: OverviewLocalFilingState
    aeat_submission_state: OverviewAeatSubmissionState


class PublicHomeDeclarationResume(BaseModel):
    """Typed local-human workbench view of HomeDeclarationResume."""

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: str
    modelo: str
    filing_year: int
    period: PublicPeriod
    name: str
    state: HomeDeclarationState
    revision_id: str | None


class PublicLedgerGenerationStateV1(BaseModel):
    """Typed local-human workbench view of LedgerGenerationStateV1."""

    model_config = STRICT_FROZEN_CONFIG

    availability: WorkbenchGenerationAvailability
    observed_at: datetime | None
    refusal: str | None
    projection: PublicLedgerWorkspaceProjectionV1 | None


class PublicLedgerWorkspaceProjectionV1(BaseModel):
    """Typed local-human workbench view of LedgerWorkspaceProjectionV1."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: int
    bucket_id: str
    areas: tuple[LedgerWorkspaceAreaStateV1, ...]
    entries: tuple[LedgerWorkspaceEntryRefV1, ...]
    review_transaction_ids: tuple[str, ...]
    invoice_reconciliations: tuple[LedgerInvoiceReconciliationRefV1, ...]
    link_inconsistencies: tuple[LedgerLinkInconsistencyRefV1, ...]
    affected_declarations: tuple[PublicLedgerAffectedDeclarationRefV1, ...]


class PublicLedgerAffectedDeclarationRefV1(BaseModel):
    """Typed local-human workbench view of LedgerAffectedDeclarationRefV1."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    filing_year: int
    period: PublicPeriod
    calculation_revision_id: str
    changed_count: int
    removed_count: int


class PublicModeloGenerationStateV1(BaseModel):
    """Typed local-human workbench view of ModeloGenerationStateV1."""

    model_config = STRICT_FROZEN_CONFIG

    availability: WorkbenchGenerationAvailability
    observed_at: datetime | None
    refusal: str | None
    projection: tuple[PublicModeloWorkspaceProjectionV1, ...] | None


class PublicModeloWorkspaceProjectionV1(BaseModel):
    """Typed local-human workbench view of ModeloWorkspaceProjectionV1."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: Literal[1]
    admission: ModeloWorkspaceStaticInspectionScopeV1 | ModeloWorkspaceGradedSnapshotScopeV1
    target: PublicModeloWorkspaceResolvedTargetV1
    schema_identity: ModeloWorkspaceSchemaIdentityV1
    locale: ModeloWorkspaceLocaleSummaryV1
    evidence_horizon: ModeloWorkspaceEvidenceHorizonV1
    family_dispositions: tuple[ModeloWorkspaceFamilyDispositionV1, ...]
    contributors: tuple[ModeloWorkspaceContributorIdentityV1, ...]
    baseline: PublicModeloWorkspaceBaselineV1
    schema_facet: PublicModeloSchemaFacetV1
    materialization_facet: PublicModeloMaterializationFacetV1 | None
    provenance_facet: PublicModeloProvenanceFacetV1 | None
    work_review: PublicModeloWorkspaceWorkReviewFacetV1
    readiness: PublicProjectionModeloReadiness | None
    capabilities: tuple[PublicModeloWorkspaceCapabilityV1, ...]


class PublicModeloWorkspaceBaselineV1(BaseModel):
    """Typed local-human workbench view of ModeloWorkspaceBaselineV1."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: Literal[1]
    token: str
    contributor_stamp_digest: str
    contributor_epoch_digest: str
    target: PublicModeloWorkspaceResolvedTargetV1
    selected_revision_id: str
    schema_identity: ModeloWorkspaceSchemaIdentityV1
    locale_catalogue_digest: str


class PublicModeloWorkspaceCapabilityV1(BaseModel):
    """Typed local-human workbench view of ModeloWorkspaceCapabilityV1."""

    model_config = STRICT_FROZEN_CONFIG

    capability: ModeloWorkspaceCapabilityName
    disposition: ModeloWorkspaceCapabilityDisposition
    target: PublicModeloWorkspaceResolvedTargetV1
    selected_revision_id: str
    producer_owner: str
    producer: str
    evidence: tuple[ModeloWorkspaceLegalEvidenceReferenceV1 | ModeloWorkspaceSourceEvidenceReferenceV1, ...]
    facts: tuple[ModeloWorkspaceEvidenceFactV1, ...]
    source_disposition: RegistrySchemaFamilyDisposition | None
    recovery_action: ActionReference | None


class PublicModeloMaterializationFacetV1(BaseModel):
    """Typed local-human workbench view of ModeloMaterializationFacetV1."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: Literal[1]
    selected_revision_id: str
    schema_identity: ModeloWorkspaceSchemaIdentityV1
    baseline: PublicModeloWorkspaceBaselineV1
    contributor_epoch_digest: str
    contributors: tuple[ModeloWorkspaceContributorIdentityV1, ...]
    facet: ModeloWorkspaceFacetName
    disposition: ModeloWorkspaceCapabilityDisposition
    records: tuple[
        PublicModeloWorkspaceScalarMaterializationRecordV1 | PublicModeloWorkspaceRepeatedRowMaterializationRecordV1,
        ...,
    ]
    page_size: int
    next_cursor: PublicModeloWorkspaceCursorV1 | None
    has_more: bool


class PublicModeloWorkspaceScalarMaterializationRecordV1(BaseModel):
    """Typed local-human workbench view of ModeloWorkspaceScalarMaterializationRecordV1."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["scalar"]
    scalar: PublicModeloWorkspaceScalarMaterializationV1


class PublicModeloWorkspaceRepeatedRowMaterializationRecordV1(BaseModel):
    """Typed local-human workbench view of ModeloWorkspaceRepeatedRowMaterializationRecordV1."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["repeated_row"]
    repeated_row: PublicModeloWorkspaceRepeatedRowMaterializationV1


class PublicModeloWorkspaceRepeatedRowMaterializationV1(BaseModel):
    """Typed local-human workbench view of ModeloWorkspaceRepeatedRowMaterializationV1."""

    model_config = STRICT_FROZEN_CONFIG

    binding_id: str
    row_index: int
    values: tuple[PublicModeloWorkspaceScalarMaterializationV1, ...]


class PublicModeloWorkspaceScalarMaterializationV1(BaseModel):
    """Typed local-human workbench view of ModeloWorkspaceScalarMaterializationV1."""

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: str
    value: PublicScalarValueV1


class PublicModeloProvenanceFacetV1(BaseModel):
    """Typed local-human workbench view of ModeloProvenanceFacetV1."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: Literal[1]
    selected_revision_id: str
    schema_identity: ModeloWorkspaceSchemaIdentityV1
    baseline: PublicModeloWorkspaceBaselineV1
    contributor_epoch_digest: str
    contributors: tuple[ModeloWorkspaceContributorIdentityV1, ...]
    facet: ModeloWorkspaceFacetName
    disposition: ModeloWorkspaceCapabilityDisposition
    records: tuple[ModeloWorkspaceProvenanceRecordV1, ...]
    page_size: int
    next_cursor: PublicModeloWorkspaceCursorV1 | None
    has_more: bool


class PublicProjectionModeloReadiness(BaseModel):
    """Typed local-human workbench view of ProjectionModeloReadiness."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: str
    modelo: str
    revision_id: str
    filing_year: int
    period: PublicPeriod
    missing: tuple[ProfilePreflightRequirement, ...]
    profile_ready: bool
    per_operation_requirements_assessed: bool
    profile_refusal: str
    profile_refusal_cause: ModeloProfileRefusalCause | None
    profile_precondition_verdict: PublicPreconditionVerdict | None
    registry_ready: bool
    registry_refusal: str
    registry_refusal_cause: ModeloRegistryRefusalCause | None
    binding_ready: bool
    missing_bindings: tuple[PublicProjectionModeloBindingRequirement, ...]
    ledger_preflight_required: bool
    ledger_ready: bool | None
    ledger_period: PublicPeriod | None
    ledger_checked_transaction_count: int
    ledger_issues: tuple[PublicLedgerPreflightIssue, ...]
    ready: bool


class PublicLedgerPreflightIssue(BaseModel):
    """Typed local-human workbench view of LedgerPreflightIssue."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: str | Literal["__period__"]
    reason: LedgerPreflightIssueReason
    detail: str


class PublicProjectionModeloBindingRequirement(BaseModel):
    """Typed local-human workbench view of ProjectionModeloBindingRequirement."""

    model_config = STRICT_FROZEN_CONFIG

    binding_id: str
    source: BindingSourceKind
    input_channel: str


class PublicPreconditionVerdict(BaseModel):
    """Typed local-human workbench view of PreconditionVerdict."""

    model_config = STRICT_FROZEN_CONFIG

    failed_condition_id: str
    evidence: tuple[PublicConditionEvidence, ...]
    action: ActionReference | None
    argument_bindings: tuple[PublicActionArgumentBinding, ...]
    missing_argument_names: tuple[str, ...]
    conditionality: ActionConditionality
    no_recovery_outcome: NoRecoveryOutcome | None


class PublicConditionEvidence(BaseModel):
    """Typed local-human workbench view of ConditionEvidence."""

    model_config = STRICT_FROZEN_CONFIG

    condition_id: str
    evidence_id: str
    provenance: ActionEvidenceProvenance
    values: tuple[PublicFactEntryV1, ...]

    @model_validator(mode="after")
    def _distinct_values(self) -> Self:
        if len({item.key for item in self.values}) != len(self.values):
            raise ValueError("duplicate condition evidence key")
        return self


class PublicModeloSchemaFacetV1(BaseModel):
    """Typed local-human workbench view of ModeloSchemaFacetV1."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: Literal[1]
    selected_revision_id: str
    schema_identity: ModeloWorkspaceSchemaIdentityV1
    baseline: PublicModeloWorkspaceBaselineV1
    contributor_epoch_digest: str
    contributors: tuple[ModeloWorkspaceContributorIdentityV1, ...]
    facet: ModeloWorkspaceFacetName
    disposition: ModeloWorkspaceCapabilityDisposition
    records: tuple[ModeloWorkspaceSchemaRecordV1, ...]
    page_size: int
    next_cursor: PublicModeloWorkspaceCursorV1 | None
    has_more: bool


class PublicModeloWorkspaceCursorV1(BaseModel):
    """Typed local-human workbench view of ModeloWorkspaceCursorV1."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: Literal[1]
    baseline: PublicModeloWorkspaceBaselineV1
    selected_revision_id: str
    schema_identity: ModeloWorkspaceSchemaIdentityV1
    facet: ModeloWorkspaceFacetName
    contributor_epoch_digest: str
    continuation: str


class PublicModeloWorkspaceResolvedTargetV1(BaseModel):
    """Typed local-human workbench view of ModeloWorkspaceResolvedTargetV1."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: str
    modelo: str
    filing_year: int
    period: PublicPeriod
    law_selected_revision_id: str
    review_status: RevisionReviewStatus
    requested_revision_assertion: ModeloWorkspaceRevisionAssertionV1
    stored_revision_assertion: ModeloWorkspaceRevisionAssertionV1
    work_unit_id: str | None
    work_state: WorkUnitState | None


class PublicModeloWorkspaceWorkReviewFacetV1(BaseModel):
    """Typed local-human workbench view of ModeloWorkspaceWorkReviewFacetV1."""

    model_config = STRICT_FROZEN_CONFIG

    disposition: ModeloWorkspaceCapabilityDisposition
    review: PublicModeloWorkReview | None


class PublicModeloWorkReview(BaseModel):
    """Typed local-human workbench view of ModeloWorkReview."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: str
    modelo: str
    filing_year: int
    period: PublicPeriod
    registry_revision_id: str
    work_unit_id: str
    calculation_revision_id: str | None
    lifecycle_state: CalculationRevisionState | None
    verification_outcome: VerificationCompletenessStatus | None
    progress: ModeloWorkProgress
    casillas: tuple[PublicModeloWorkReviewCasilla, ...]
    findings: tuple[PublicModeloVerificationFinding, ...]
    blockers: tuple[PublicBlockerRef, ...]
    row_source_fingerprints: tuple[ModeloRowSourceFingerprint, ...]


class PublicModeloWorkReviewCasilla(BaseModel):
    """Typed local-human workbench view of ModeloWorkReviewCasilla."""

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: str
    number: str
    segmento: str | None
    official_reference: str | None
    section_path: tuple[str, ...]
    label: str
    semantic_role: str | None
    data_type: str
    constraints: PublicCasillaConstraints | None
    declared_input_kind: InputKind
    concrete_bindings: tuple[ModeloWorkBindingOrigin, ...]
    concrete_formula: ModeloWorkFormulaOrigin | None
    relation_consumption: tuple[ModeloWorkRelationConsumption, ...]
    realised_kind: ModeloValueKind
    value: PublicScalarValueV1
    absent_by_design: bool
    origin_anomaly: ModeloWorkOriginAnomaly | None
    estado_casilla_oficial: EstadoCasillaOficial
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    formula_id: str | None
    blocked_by: tuple[PublicBlockerRef, ...]


class PublicBlockerRef(BaseModel):
    """Typed local-human workbench view of BlockerRef."""

    model_config = STRICT_FROZEN_CONFIG

    axis: OperatorActionAxis
    native_code: str
    facts: tuple[PublicFactEntryV1, ...]

    @model_validator(mode="after")
    def _distinct_facts(self) -> Self:
        if len({item.key for item in self.facts}) != len(self.facts):
            raise ValueError("duplicate blocker fact key")
        return self


class PublicCasillaConstraints(BaseModel):
    """Typed local-human workbench view of CasillaConstraints."""

    model_config = STRICT_FROZEN_CONFIG

    sign: CasillaSignConstraint
    min_value: str | None
    max_value: str | None
    pattern: str | None
    min_length: int | None
    max_length: int | None
    enum: tuple[str, ...] | None
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


class PublicModeloVerificationFinding(BaseModel):
    """Typed local-human workbench view of ModeloVerificationFinding."""

    model_config = STRICT_FROZEN_CONFIG

    kind: ModeloVerificationFindingKind
    severity: ModeloVerificationFindingSeverity
    casilla_id: str | None
    expectation_id: str | None
    message_locale_key: str
    message_facts: tuple[PublicFactEntryV1, ...]
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]

    @model_validator(mode="after")
    def _distinct_message_facts(self) -> Self:
        if len({item.key for item in self.message_facts}) != len(self.message_facts):
            raise ValueError("duplicate finding fact key")
        return self


class PublicSearchGenerationStateV1(BaseModel):
    """Search state only; private identity bases are rebuilt in the reader process."""

    model_config = STRICT_FROZEN_CONFIG

    availability: WorkbenchGenerationAvailability
    observed_at: datetime | None
    refusal: str | None


class WorkbenchGenerationOperationProjection(BaseModel):
    """Public exact-profile envelope around one complete generation version."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    generation: PublicWorkbenchGenerationV1

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_utc_instants(self) -> Self:
        """Retain the canonical UTC-only boundary after primitive projection."""

        def inspect(value: object) -> None:
            if isinstance(value, datetime):
                validate_utc_aware(value)
            elif isinstance(value, BaseModel):
                for field_name in type(value).model_fields:
                    inspect(getattr(value, field_name))
            elif isinstance(value, tuple):
                for item in cast(tuple[object, ...], value):
                    inspect(item)

        inspect(self.generation)
        _require_profile_binding(self.profile_id, self.generation)
        return self


PublicWorkbenchGenerationV1.model_rebuild()
WorkbenchGenerationOperationProjection.model_rebuild()


_REVIEWED_EXCLUDED_FIELDS: frozenset[tuple[type[BaseModel], str]] = frozenset(
    {
        (DeclarationsWorkspaceProjectionV1, "bucket_id"),
        (DeclarationsWorkspaceDeclarationRefV1, "work_unit_id"),
        (DeclarationsWorkspaceCalculationRevisionRefV1, "calculation_revision_id"),
        (DeclarationsWorkspaceCalculationRevisionRefV1, "work_unit_id"),
        (DeclarationsWorkspaceFilingRefV1, "filing_record_id"),
        (DeclarationsWorkspaceFilingRefV1, "work_unit_id"),
        (DeclarationsWorkspaceFilingRefV1, "calculation_revision_id"),
        (DeclarationsWorkspaceFilingRefV1, "amends_filing_record_id"),
        (DeclarationsWorkspaceLifecycleRefV1, "fact_id"),
        (DeclarationsWorkspaceLifecycleRefV1, "work_unit_id"),
        (DeclarationSummary, "technical_reason"),
        (DeclarationsCalendarEntryRefV1, "aeat_reference_id"),
        (DeclarationsCalendarEntryRefV1, "recovery_action"),
    }
)


def _require_reviewed_exclusions() -> None:
    """Reject any new omitted canonical field before projecting owner data."""
    # Search documents and identity bases never enter the public result.
    discovered = excluded_canonical_fields(
        WorkbenchGenerationV1, opaque=frozenset({InstalledWorkbenchSearchSnapshotV1})
    )
    if discovered != _REVIEWED_EXCLUDED_FIELDS:
        raise ValueError("workbench public excluded-field inventory changed")


_PROFILE_BOUND_PUBLIC_MODELS: frozenset[type[BaseModel]] = frozenset(
    {
        PublicDeclarationsWorkspaceProjectionV1,
        PublicLedgerWorkspaceProjectionV1,
        PublicModeloWorkspaceResolvedTargetV1,
        PublicModeloWorkReview,
    }
)


def _require_profile_binding(profile_id: UUID, generation: PublicWorkbenchGenerationV1) -> None:
    """Check each explicit bucket coordinate against the admitted envelope."""
    expected = str(profile_id)

    def inspect(value: object) -> None:
        if isinstance(value, BaseModel):
            model = type(value)
            if "bucket_id" in model.model_fields:
                if model not in _PROFILE_BOUND_PUBLIC_MODELS:
                    raise ValueError("workbench bucket-bearing model needs review")
                bucket_id = cast(str | None, value.__dict__["bucket_id"])
                if bucket_id is not None and bucket_id != expected:
                    raise ValueError("workbench projection profile mismatch")
            for field_name in model.model_fields:
                inspect(getattr(value, field_name))
        elif isinstance(value, Mapping):
            for item in cast(Mapping[object, object], value).values():
                inspect(item)
        elif isinstance(value, tuple):
            for item in cast(tuple[object, ...], value):
                inspect(item)
        elif is_dataclass(value):
            for field in fields(value):
                inspect(getattr(value, field.name))

    inspect(generation)


_OMITTED: dict[type[BaseModel], frozenset[str]] = {PublicSearchGenerationStateV1: frozenset({"projection"})}
"""Public search carries state only; its private identity is rebuilt in the reader process."""
_WITHHELD: frozenset[tuple[type[object], str]] = frozenset({(WorkbenchGenerationV1, "search")})


def _rebuild_search(canonical: type[object], restored: dict[str, object], public: BaseModel) -> None:
    """Rebuild search identity from the restored sibling projections, then check its public state."""
    if canonical is not WorkbenchGenerationV1:
        return
    search = assemble_workbench_generation_search(
        ledger=cast(WorkbenchGenerationProjectionResultV1[LedgerWorkspaceProjectionV1], restored["ledger"]),
        declarations=cast(
            WorkbenchGenerationProjectionResultV1[DeclarationsWorkspaceProjectionV1],
            restored["declarations"],
        ),
        aeat_sync=cast(WorkbenchGenerationProjectionResultV1[AeatSyncWorkspaceProjectionV1], restored["aeat_sync"]),
        modelo=cast(
            WorkbenchGenerationProjectionResultV1[tuple[ModeloWorkspaceProjectionV1, ...]],
            restored["modelo"],
        ),
        ledger_admission=cast(WorkbenchDestinationAdmission, restored["ledger_admission"]),
        declarations_admission=cast(WorkbenchDestinationAdmission, restored["declarations_admission"]),
        aeat_sync_admission=cast(WorkbenchDestinationAdmission, restored["aeat_sync_admission"]),
    )
    safe_search = cast(PublicWorkbenchGenerationV1, public).search
    if (
        search.availability != safe_search.availability
        or search.observed_at != safe_search.observed_at
        or search.refusal != safe_search.refusal
    ):
        raise ValueError("workbench search state changed")
    restored["search"] = search


def _project(generation: WorkbenchGenerationV1) -> object:
    return project_public_mirror(generation, WorkbenchGenerationV1, PublicWorkbenchGenerationV1, omitted=_OMITTED)


def _restore(public: PublicWorkbenchGenerationV1) -> object:
    return restore_public_mirror(
        public, WorkbenchGenerationV1, PublicWorkbenchGenerationV1, withheld=_WITHHELD, complete=_rebuild_search
    )


def project_workbench_generation(
    profile_id: UUID, generation: WorkbenchGenerationV1
) -> WorkbenchGenerationOperationProjection:
    """Project the complete typed generation without retaining private search identity."""
    _require_reviewed_exclusions()
    public_generation = _project(generation)
    if not isinstance(public_generation, PublicWorkbenchGenerationV1):
        raise TypeError("workbench public projection failed")
    projection = WorkbenchGenerationOperationProjection(profile_id=profile_id, generation=public_generation)
    restored = _restore(public_generation)
    if not isinstance(restored, WorkbenchGenerationV1):
        raise TypeError("workbench canonical round-trip failed")
    if _project(restored) != public_generation:
        raise ValueError("workbench public projection changed canonical meaning")
    return projection


def restore_workbench_generation(projection: WorkbenchGenerationOperationProjection) -> WorkbenchGenerationV1:
    """Rebuild the canonical generation and local process-keyed search identities."""
    _require_reviewed_exclusions()
    _require_profile_binding(projection.profile_id, projection.generation)
    restored = _restore(projection.generation)
    if not isinstance(restored, WorkbenchGenerationV1):
        raise TypeError("workbench canonical restoration failed")
    if _project(restored) != projection.generation:
        raise ValueError("workbench public projection changed canonical meaning")
    return restored
