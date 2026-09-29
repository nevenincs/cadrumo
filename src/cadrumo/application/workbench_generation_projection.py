"""Strict versioned public projection of the complete workbench generation.

Only incompatible canonical nodes are mirrored; compatible children retain their
existing typed models. Projection and restoration validate the original models.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from types import GenericAlias, UnionType
from typing import Annotated, Literal, Self, TypeAliasType, Union, cast, get_args, get_origin, get_type_hints
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
from cadrumo.application.modelo.edit_baseline_projection import ModeloEditApplyBaselineV1
from cadrumo.application.modelo.row_source_fingerprint import (
    ModeloRowSourceFingerprint,
)
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
    ModeloWorkspaceRefusalCode,
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
from cadrumo.core.revision_review import RevisionReviewStatus
from cadrumo.core.schema_family_disposition import (
    RegistrySchemaFamilyDisposition,
)
from cadrumo.domain.buckets.event import BucketEventObjectType, BucketEventType
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
from .operations.public_period import PublicPeriod
from .workbench_generation import (
    WorkbenchGenerationProjectionResultV1,
    WorkbenchGenerationV1,
    assemble_workbench_generation_search,
)


class PublicFactEntryV1(BaseModel):
    """One typed, ordered fact from a canonical immutable fact map."""

    model_config = STRICT_FROZEN_CONFIG

    key: str
    kind: Literal["string", "integer", "boolean", "decimal", "null"]
    text: str

    @model_validator(mode="after")
    def _validate_value(self) -> Self:
        if self.kind == "boolean" and self.text not in {"true", "false"}:
            raise ValueError("invalid boolean fact")
        if self.kind == "integer" and str(int(self.text)) != self.text:
            raise ValueError("invalid integer fact")
        if self.kind == "decimal":
            try:
                value = Decimal(self.text)
            except InvalidOperation:
                raise ValueError("invalid decimal fact") from None
            if not value.is_finite() or str(value) != self.text:
                raise ValueError("invalid decimal fact")
        if self.kind == "null" and self.text:
            raise ValueError("null fact must carry no text")
        return self


class PublicScalarValueV1(BaseModel):
    """Preserve scalar kind and decimal precision across the public schema."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["string", "integer", "boolean", "decimal", "date", "null"]
    text: str

    @model_validator(mode="after")
    def _validate_value(self) -> Self:
        if self.kind == "boolean" and self.text not in {"true", "false"}:
            raise ValueError("invalid boolean scalar")
        if self.kind == "integer" and str(int(self.text)) != self.text:
            raise ValueError("invalid integer scalar")
        if self.kind == "decimal":
            try:
                value = Decimal(self.text)
            except InvalidOperation:
                raise ValueError("invalid decimal scalar") from None
            if not value.is_finite() or str(value) != self.text:
                raise ValueError("invalid decimal scalar")
        if self.kind == "date":
            try:
                value_date = date.fromisoformat(self.text)
            except ValueError:
                raise ValueError("invalid date scalar") from None
            if value_date.isoformat() != self.text:
                raise ValueError("invalid date scalar")
        if self.kind == "null" and self.text:
            raise ValueError("null scalar must carry no text")
        return self


class PublicTextEntryV1(BaseModel):
    """One ordered string entry from a canonical lifecycle payload."""

    model_config = STRICT_FROZEN_CONFIG

    key: str
    value: str


class PublicModeloVisibleFilingTargetV1(BaseModel):
    """Closed public fields of the canonical visible filing address."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    filing_year: int
    period: PublicPeriod
    registry_revision_id: str | None
    bucket_id: str | None


class PublicModeloExactWorkUnitTargetV1(BaseModel):
    """Closed public fields of the canonical exact work-unit address."""

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: str
    bucket_id: str | None


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
    modelo_lifecycle: PublicModeloLifecycleGenerationResultV1
    modelo_graded_refusals: PublicModeloGradedRefusalsGenerationResultV1
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
    profile_precondition_verdict: PublicPreconditionVerdict | None
    registry_ready: bool
    registry_refusal: str
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
    data_type: str
    constraints: PublicCasillaConstraints | None
    declared_input_kind: InputKind
    concrete_bindings: tuple[ModeloWorkBindingOrigin, ...]
    concrete_formula: ModeloWorkFormulaOrigin | None
    relation_consumption: tuple[ModeloWorkRelationConsumption, ...]
    realised_kind: ModeloValueKind
    value: PublicScalarValueV1
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


class PublicModeloGradedRefusalsGenerationResultV1(BaseModel):
    """Typed local-human workbench view of ModeloGradedRefusalsGenerationResultV1."""

    model_config = STRICT_FROZEN_CONFIG

    availability: WorkbenchGenerationAvailability
    observed_at: datetime | None
    refusal: str | None
    projection: tuple[PublicGradedRefusalEntryV1, ...] | None

    @model_validator(mode="after")
    def _distinct_refusals(self) -> Self:
        if self.projection is not None and len({item.key for item in self.projection}) != len(self.projection):
            raise ValueError("duplicate graded-refusal key")
        return self


class PublicModeloWorkspaceDomainRefusalV1(BaseModel):
    """Typed local-human workbench view of ModeloWorkspaceDomainRefusalV1."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["domain"]
    contract_version: Literal[1]
    code: ModeloWorkspaceRefusalCode
    boundary: Literal["admission", "capability", "consistency", "locale", "schema"]
    capability: ModeloWorkspaceCapabilityName | None
    requested_target: PublicModeloWorkspaceVisibleFilingTargetV1 | PublicModeloWorkspaceExactWorkUnitTargetV1
    selected_target: PublicModeloWorkspaceResolvedTargetV1 | None
    facts: tuple[ModeloWorkspaceEvidenceFactV1, ...]
    evidence: tuple[ModeloWorkspaceLegalEvidenceReferenceV1 | ModeloWorkspaceSourceEvidenceReferenceV1, ...]
    responsible_owner: str
    reconsideration_condition: str
    source_disposition: RegistrySchemaFamilyDisposition | None
    recovery_action: ActionReference | None


class PublicGradedRefusalEntryV1(BaseModel):
    """One exact ordered graded-refusal key and its typed refusal."""

    model_config = STRICT_FROZEN_CONFIG

    key: str
    value: PublicModeloWorkspaceDomainRefusalV1


class PublicModeloWorkspaceVisibleFilingTargetV1(BaseModel):
    """Typed local-human workbench view of ModeloWorkspaceVisibleFilingTargetV1."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["visible_filing"]
    target: PublicModeloVisibleFilingTargetV1


class PublicModeloWorkspaceExactWorkUnitTargetV1(BaseModel):
    """Typed local-human workbench view of ModeloWorkspaceExactWorkUnitTargetV1."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["exact_work_unit"]
    target: PublicModeloExactWorkUnitTargetV1


class PublicModeloLifecycleGenerationResultV1(BaseModel):
    """Typed local-human workbench view of ModeloLifecycleGenerationResultV1."""

    model_config = STRICT_FROZEN_CONFIG

    availability: WorkbenchGenerationAvailability
    observed_at: datetime | None
    refusal: str | None
    projection: tuple[PublicModeloWorkspaceLifecycleProjectionV1, ...] | None


class PublicModeloWorkspaceLifecycleProjectionV1(BaseModel):
    """Typed local-human workbench view of ModeloWorkspaceLifecycleProjectionV1."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: Literal[1]
    target: PublicModeloWorkspaceResolvedTargetV1
    calculation_revision_id: str | None
    verification_report_id: str | None
    local_filing_record_id: str | None
    aeat_accepted: Literal[False]
    events: tuple[PublicBucketEvent, ...]
    edit_baseline: ModeloEditApplyBaselineV1 | None
    asks_modelo_390: bool


class PublicBucketEvent(BaseModel):
    """Typed local-human workbench view of BucketEvent."""

    model_config = STRICT_FROZEN_CONFIG

    event_id: str
    bucket_id: str
    event_type: BucketEventType
    occurred_at: datetime
    actor: str
    object_type: BucketEventObjectType
    object_id: str
    payload_version: int
    payload: tuple[PublicTextEntryV1, ...]

    @model_validator(mode="after")
    def _distinct_payload(self) -> Self:
        if len({item.key for item in self.payload}) != len(self.payload):
            raise ValueError("duplicate lifecycle payload key")
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


def _bare(annotation: object) -> object:
    if isinstance(annotation, TypeAliasType):
        return _bare(annotation.__value__)
    origin = get_origin(annotation)
    if origin is Annotated:
        return _bare(get_args(annotation)[0])
    if origin in (Union, UnionType):
        present = tuple(item for item in get_args(annotation) if item is not type(None))
        if len(present) == 1:
            return _bare(present[0])
    if isinstance(origin, TypeAliasType) and origin.__name__ == "_BoundedRefList":
        return GenericAlias(tuple, (get_args(annotation)[0], Ellipsis))
    if isinstance(origin, TypeAliasType):
        raise ValueError("unreviewed generic workbench type alias")
    return annotation


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
        (DeclarationsCalendarEntryRefV1, "recovery_action"),
    }
)


def _require_reviewed_exclusions() -> None:
    """Reject any new omitted canonical field before projecting owner data."""
    discovered: set[tuple[type[BaseModel], str]] = set()
    visited: set[type[BaseModel]] = set()

    def inspect(annotation: object) -> None:
        annotation = _bare(annotation)
        if annotation is InstalledWorkbenchSearchSnapshotV1:
            # Search documents and identity bases never enter the public result.
            return
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            if annotation in visited:
                return
            visited.add(annotation)
            for name, field in annotation.model_fields.items():
                if field.exclude not in (None, False):
                    discovered.add((annotation, name))
                inspect(field.annotation)
            return
        if isinstance(annotation, type) and is_dataclass(annotation):
            for field in fields(annotation):
                inspect(get_type_hints(annotation)[field.name])
            return
        for choice in get_args(annotation):
            inspect(choice)

    inspect(WorkbenchGenerationV1)
    if frozenset(discovered) != _REVIEWED_EXCLUDED_FIELDS:
        raise ValueError("workbench public excluded-field inventory changed")


_PROFILE_BOUND_PUBLIC_MODELS: frozenset[type[BaseModel]] = frozenset(
    {
        ModeloEditApplyBaselineV1,
        PublicModeloVisibleFilingTargetV1,
        PublicModeloExactWorkUnitTargetV1,
        PublicDeclarationsWorkspaceProjectionV1,
        PublicLedgerWorkspaceProjectionV1,
        PublicModeloWorkspaceResolvedTargetV1,
        PublicModeloWorkReview,
        PublicBucketEvent,
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


def _scalar(value: object) -> PublicScalarValueV1:
    if value is None:
        return PublicScalarValueV1(kind="null", text="")
    if isinstance(value, bool):
        return PublicScalarValueV1(kind="boolean", text="true" if value else "false")
    if isinstance(value, int):
        return PublicScalarValueV1(kind="integer", text=str(value))
    if isinstance(value, Decimal):
        return PublicScalarValueV1(kind="decimal", text=str(value))
    if isinstance(value, date):
        return PublicScalarValueV1(kind="date", text=value.isoformat())
    if isinstance(value, str):
        return PublicScalarValueV1(kind="string", text=value)
    raise TypeError("unsupported workbench scalar")


def _unscalar(value: PublicScalarValueV1) -> str | int | bool | Decimal | date | None:
    if value.kind == "null":
        return None
    if value.kind == "boolean":
        return value.text == "true"
    if value.kind == "integer":
        return int(value.text)
    if value.kind == "decimal":
        return Decimal(value.text)
    if value.kind == "date":
        return date.fromisoformat(value.text)
    return value.text


def _fact_entry(key: str, value: object) -> PublicFactEntryV1:
    scalar = _scalar(value)
    if scalar.kind == "date":
        raise TypeError("fact maps cannot contain dates")
    return PublicFactEntryV1(key=key, kind=scalar.kind, text=scalar.text)


def _mapping_key(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("workbench mapping key must be text")
    return value


def _mapping_text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("workbench mapping value must be text")
    return value


def _public_model_type(annotation: object, value: object) -> type[BaseModel] | None:
    annotation = _bare(annotation)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        for choice in get_args(annotation):
            candidate = _bare(choice)
            if not isinstance(candidate, type) or not issubclass(candidate, BaseModel):
                continue
            if value is None:
                continue
            # Distinct union arms retain their canonical class-name suffix.
            if candidate.__name__.removeprefix("Public") == type(value).__name__:
                return candidate
    return None


def _project(value: object, canonical: object, public: object) -> object:
    if value is None:
        return None
    canonical, public = _bare(canonical), _bare(public)
    if public is PublicScalarValueV1:
        return _scalar(value)
    if isinstance(value, Mapping):
        entries = cast(Mapping[object, object], value)
        if not isinstance(public, type) and get_origin(public) is tuple:
            item = get_args(public)[0]
            if item is PublicFactEntryV1:
                return tuple(_fact_entry(_mapping_key(key), fact) for key, fact in entries.items())
            if item is PublicTextEntryV1:
                return tuple(
                    PublicTextEntryV1(key=_mapping_key(key), value=_mapping_text(fact)) for key, fact in entries.items()
                )
            if item is PublicGradedRefusalEntryV1:
                return tuple(
                    PublicGradedRefusalEntryV1(
                        key=_mapping_key(key),
                        value=cast(
                            PublicModeloWorkspaceDomainRefusalV1,
                            _project(fact, type(fact), PublicModeloWorkspaceDomainRefusalV1),
                        ),
                    )
                    for key, fact in entries.items()
                )
        raise TypeError("unsupported workbench mapping")
    if isinstance(value, tuple):
        items = cast(tuple[object, ...], value)
        canonical_args = get_args(canonical)
        public_args = get_args(public)
        if get_origin(public) is not tuple or not public_args:
            raise TypeError("workbench tuple changed its public shape")
        if len(public_args) == 2 and public_args[1] is Ellipsis:
            canonical_item = canonical_args[0] if canonical_args else object
            return tuple(_project(item, canonical_item, public_args[0]) for item in items)
        if len(items) != len(public_args):
            raise ValueError("workbench fixed tuple changed arity")
        return tuple(_project(item, canonical_args[index], public_args[index]) for index, item in enumerate(items))
    if isinstance(value, BaseModel) or is_dataclass(value):
        target = _public_model_type(public, value)
        if target is None:
            raise TypeError("workbench public model arm is unavailable")
        if isinstance(value, BaseModel) and target is type(value):
            return target.model_validate_json(value.model_dump_json(), strict=True)
        target.model_rebuild()
        target_fields = target.model_fields
        if isinstance(value, BaseModel):
            source_fields = type(value).model_fields
            source_annotations = {name: field.annotation for name, field in source_fields.items()}
        else:
            source_fields = {field.name: field for field in fields(value)}
            source_annotations = get_type_hints(type(value))
        allowed_missing: set[str] = {"projection"} if target is PublicSearchGenerationStateV1 else set()
        if set(source_fields) - set(target_fields) != allowed_missing or set(target_fields) - set(source_fields):
            raise ValueError("workbench public model field inventory drifted")
        return target.model_validate(
            {
                name: _project(
                    getattr(value, name),
                    source_annotations[name],
                    field.annotation,
                )
                for name, field in target_fields.items()
            }
        )
    if isinstance(value, Decimal):
        return str(value)
    if public is str and isinstance(value, str):
        return str(value)
    return value


def _restore(value: object, canonical: object, public: object) -> object:
    if value is None:
        return None
    canonical, public = _bare(canonical), _bare(public)
    if isinstance(value, PublicScalarValueV1):
        return _unscalar(value)
    if isinstance(value, tuple):
        items = cast(tuple[object, ...], value)
        public_item = get_args(public)[0] if get_origin(public) is tuple else None
        if public_item is PublicFactEntryV1:
            return {
                entry.key: _unscalar(PublicScalarValueV1(kind=entry.kind, text=entry.text))
                for entry in cast(tuple[PublicFactEntryV1, ...], items)
            }
        if public_item is PublicTextEntryV1:
            return {entry.key: entry.value for entry in cast(tuple[PublicTextEntryV1, ...], items)}
        if public_item is PublicGradedRefusalEntryV1:
            canonical_value = get_args(canonical)[1]
            return {
                entry.key: _restore(entry.value, canonical_value, PublicModeloWorkspaceDomainRefusalV1)
                for entry in cast(tuple[PublicGradedRefusalEntryV1, ...], items)
            }
        if get_origin(canonical) not in (tuple, Mapping):
            raise TypeError("workbench tuple changed its canonical shape")
        canonical_args = get_args(canonical)
        public_args = get_args(public)
        if len(canonical_args) == 2 and canonical_args[1] is Ellipsis:
            return tuple(_restore(item, canonical_args[0], public_args[0]) for item in items)
        return tuple(_restore(item, canonical_args[index], public_args[index]) for index, item in enumerate(items))
    if isinstance(value, BaseModel):
        type(value).model_rebuild()
        if isinstance(canonical, type) and canonical is type(value):
            return type(value).model_validate_json(value.model_dump_json(), strict=True)
        if get_origin(canonical) in (Union, UnionType):
            options = [item for item in get_args(canonical) if isinstance(_bare(item), type)]
            matches = [
                item
                for item in options
                if isinstance(candidate := _bare(item), type)
                and value.__class__.__name__.removeprefix("Public") == candidate.__name__
            ]
            if len(matches) != 1:
                raise TypeError("workbench union arm changed")
            canonical = _bare(matches[0])
        if not isinstance(canonical, type):
            raise TypeError("workbench canonical model changed")
        source_fields = type(value).model_fields
        if issubclass(canonical, BaseModel):
            target_fields = canonical.model_fields
            target_annotations = {name: field.annotation for name, field in target_fields.items()}
        elif is_dataclass(canonical_class := cast(type[object], canonical)):
            target_fields = {field.name: field for field in fields(canonical_class)}
            target_annotations = get_type_hints(canonical_class)
        else:
            raise TypeError("workbench canonical model changed")
        if set(source_fields) - set(target_fields):
            raise ValueError("workbench canonical model field inventory drifted")
        restored = {
            name: _restore(getattr(value, name), target_annotations[name], source_fields[name].annotation)
            for name in target_fields
            if name in source_fields and not (canonical is WorkbenchGenerationV1 and name == "search")
        }
        if canonical is WorkbenchGenerationV1:
            # Public search carries state only. Rebuild its private identity
            # from the restored sibling projections before validating the
            # canonical result, which requires a value when AVAILABLE.
            search = assemble_workbench_generation_search(
                ledger=cast(WorkbenchGenerationProjectionResultV1[LedgerWorkspaceProjectionV1], restored["ledger"]),
                declarations=cast(
                    WorkbenchGenerationProjectionResultV1[DeclarationsWorkspaceProjectionV1],
                    restored["declarations"],
                ),
                aeat_sync=cast(
                    WorkbenchGenerationProjectionResultV1[AeatSyncWorkspaceProjectionV1], restored["aeat_sync"]
                ),
                modelo=cast(
                    WorkbenchGenerationProjectionResultV1[tuple[ModeloWorkspaceProjectionV1, ...]],
                    restored["modelo"],
                ),
                ledger_admission=cast(WorkbenchDestinationAdmission, restored["ledger_admission"]),
                declarations_admission=cast(WorkbenchDestinationAdmission, restored["declarations_admission"]),
                aeat_sync_admission=cast(WorkbenchDestinationAdmission, restored["aeat_sync_admission"]),
            )
            safe_search = cast(PublicWorkbenchGenerationV1, value).search
            if (
                search.availability != safe_search.availability
                or search.observed_at != safe_search.observed_at
                or search.refusal != safe_search.refusal
            ):
                raise ValueError("workbench search state changed")
            restored["search"] = search
        if issubclass(canonical, BaseModel):
            return canonical.model_validate(restored)
        return cast(Callable[..., object], canonical)(**restored)
    if canonical is Decimal and isinstance(value, str):
        try:
            decimal = Decimal(value)
        except InvalidOperation:
            raise ValueError("invalid workbench decimal") from None
        if not decimal.is_finite() or str(decimal) != value:
            raise ValueError("invalid workbench decimal")
        return decimal
    return value


def project_workbench_generation(
    profile_id: UUID, generation: WorkbenchGenerationV1
) -> WorkbenchGenerationOperationProjection:
    """Project the complete typed generation without retaining private search identity."""
    _require_reviewed_exclusions()
    public_generation = _project(generation, WorkbenchGenerationV1, PublicWorkbenchGenerationV1)
    if not isinstance(public_generation, PublicWorkbenchGenerationV1):
        raise TypeError("workbench public projection failed")
    projection = WorkbenchGenerationOperationProjection(profile_id=profile_id, generation=public_generation)
    restored = _restore(public_generation, WorkbenchGenerationV1, PublicWorkbenchGenerationV1)
    if not isinstance(restored, WorkbenchGenerationV1):
        raise TypeError("workbench canonical round-trip failed")
    if _project(restored, WorkbenchGenerationV1, PublicWorkbenchGenerationV1) != public_generation:
        raise ValueError("workbench public projection changed canonical meaning")
    return projection


def restore_workbench_generation(projection: WorkbenchGenerationOperationProjection) -> WorkbenchGenerationV1:
    """Rebuild the canonical generation and local process-keyed search identities."""
    _require_reviewed_exclusions()
    _require_profile_binding(projection.profile_id, projection.generation)
    restored = _restore(projection.generation, WorkbenchGenerationV1, PublicWorkbenchGenerationV1)
    if not isinstance(restored, WorkbenchGenerationV1):
        raise TypeError("workbench canonical restoration failed")
    if _project(restored, WorkbenchGenerationV1, PublicWorkbenchGenerationV1) != projection.generation:
        raise ValueError("workbench public projection changed canonical meaning")
    return restored
