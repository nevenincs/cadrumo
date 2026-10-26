"""Strict versioned public projection of the complete workbench generation.

Only incompatible canonical nodes are mirrored; compatible children retain their
existing typed models. Projection and restoration validate the original models.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, Self

from pydantic import BaseModel, field_validator, model_validator

from cadrumo.application.ledger.preflight import LedgerPreflightIssueReason
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
    ModeloWorkspaceProvenanceRecordV1,
    ModeloWorkspaceRevisionAssertionV1,
    ModeloWorkspaceSchemaIdentityV1,
    ModeloWorkspaceSchemaRecordV1,
    ModeloWorkspaceSourceEvidenceReferenceV1,
    ModeloWorkspaceStaticInspectionScopeV1,
)
from cadrumo.application.operator_actions.models import ActionReference
from cadrumo.application.state_projection import ModeloProfileRefusalCause, ModeloRegistryRefusalCause
from cadrumo.application.user_profile.commands import ProfilePreflightRequirement
from cadrumo.application.workbench_generation_contracts import (
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
from cadrumo.domain.calculations.registry.schema_base import CasillaSignConstraint
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.filing.schema import ModeloValueKind
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from cadrumo.domain.modelos.work_unit import WorkUnitState

from ..core.models import STRICT_FROZEN_CONFIG
from .operations.public_mirror import (
    PublicFactEntryV1,
    PublicScalarValueV1,
)
from .operations.public_period import PublicPeriod


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


class PublicActionArgumentBinding(BaseModel):
    """Typed local-human workbench view of ActionArgumentBinding."""

    model_config = STRICT_FROZEN_CONFIG

    argument_name: str
    status: ActionArgumentStatus
    value: PublicScalarValueV1
    source: ActionArgumentSource | None
    source_key: str | None
    source_evidence_id: str | None


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
