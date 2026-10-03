"""Strict versioned public projection of the complete workbench generation.

Only incompatible canonical nodes are mirrored; compatible children retain their
existing typed models. Projection and restoration validate the original models.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

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
    AeatSyncWorkspaceZoneStateV1,
)
from cadrumo.application.ledger.workspace import (
    LedgerInvoiceReconciliationRefV1,
    LedgerLinkInconsistencyRefV1,
    LedgerWorkspaceAreaStateV1,
    LedgerWorkspaceEntryRefV1,
)
from cadrumo.application.modelo.declaration_summary import DeclarationSummaryState
from cadrumo.application.modelo.declarations_calendar import (
    DeclarationsCalendarSourceStateV1,
)
from cadrumo.application.modelo.declarations_workspace_contracts import (
    DeclarationsLifecycleKind,
    DeclarationsWorkspaceZoneStateV1,
)
from cadrumo.application.modelo.work_form_models import ModeloFormResultDirection
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
from cadrumo.application.search.workbench import WorkbenchDestinationAdmission
from cadrumo.application.workbench_generation_contracts import (
    WorkbenchGenerationAvailability,
)
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.deadlines.festivos import DeadlineHolidayCoverage
from cadrumo.domain.deadlines.models import ObligationStatus
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecordStatus,
)
from cadrumo.domain.modelos.work_unit import WorkUnitState

from ..core.models import STRICT_FROZEN_CONFIG
from .operations.public_period import PublicPeriod
from .user_profile.censal_observation import CensalObservation
from .workbench_generation_modelo_contracts import (
    PublicActionArgumentBinding,
    PublicModeloGenerationStateV1,
    PublicModeloWorkConditionalRecargoPreview,
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
    census_observation: CensalObservation | None
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


class PublicSearchGenerationStateV1(BaseModel):
    """Search state only; private identity bases are rebuilt in the reader process."""

    model_config = STRICT_FROZEN_CONFIG

    availability: WorkbenchGenerationAvailability
    observed_at: datetime | None
    refusal: str | None


PublicWorkbenchGenerationV1.model_rebuild()
