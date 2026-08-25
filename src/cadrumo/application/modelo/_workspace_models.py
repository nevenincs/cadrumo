"""Strict, frontend-neutral records for the read-only Modelo Workspace V1."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, field_validator, model_validator

from ...core import (
    STRICT_FROZEN_CONFIG,
    BindingSourceKind,
    CalculationSourceLineageRole,
    CasillaId,
    OutputLanguage,
    Period,
    RegistryAuthorityGrade,
    RegistrySchemaFamilyDisposition,
    RevisionReviewStatus,
)
from ...core.identity import BucketId, ContentDigest, WorkUnitId
from ...domain.calculations.registry import (
    BindingId,
    ExportFieldId,
    FormulaId,
    LegalRefId,
    ParameterId,
    RelationId,
    RevisionId,
    SourceRefId,
)
from ...domain.filing import ModeloScalar
from ...domain.modelos import ModeloCode, WorkUnitState
from ..operator_actions import ActionReference
from ._work_addressing import ModeloExactWorkUnitTarget, ModeloVisibleFilingTarget
from ._work_review import ModeloWorkReview

_MAX_FACET_PAGE_SIZE = 200
_MAX_SAFE_FACTS = 32
_MAX_SAFE_FACT_TEXT_LENGTH = 256

_BUCKET_ID_ADAPTER = TypeAdapter(BucketId)
_REVISION_ID_ADAPTER = TypeAdapter(RevisionId)
_WORK_UNIT_ID_ADAPTER = TypeAdapter(WorkUnitId)

type _BoundedText = Annotated[str, Field(min_length=1, max_length=256)]
type _BoundedCode = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")]
type _WorkspaceTarget = ModeloVisibleFilingTarget | ModeloExactWorkUnitTarget


class _WorkspaceModel(BaseModel):
    """The common fail-closed boundary posture for Workspace V1 records."""

    model_config = STRICT_FROZEN_CONFIG


class ModeloWorkspaceAdmissionKind(StrEnum):
    """The two explicitly different authority paths a workspace may request."""

    STATIC_INSPECTION = "static_inspection"
    GRADED_SNAPSHOT = "graded_snapshot"


class ModeloWorkspaceCapabilityName(StrEnum):
    """The complete read-only capability denominator for Workspace V1."""

    SCHEMA_INSPECTION = "schema_inspection"
    CALCULATION_MATERIALIZATION = "calculation_materialization"
    VERIFICATION_READINESS = "verification_readiness"
    FILING_DRAFT_READINESS = "filing_draft_readiness"
    FILING_EXPORT_READINESS = "filing_export_readiness"


class ModeloWorkspaceCapabilityDisposition(StrEnum):
    """A producer-declared capability posture; Workspace never infers this."""

    AVAILABLE = "available"
    NOT_APPLICABLE = "not_applicable"
    REFUSED = "refused"
    UNMEASURED = "unmeasured"


class ModeloWorkspaceFacetName(StrEnum):
    """Bounded facets exposed by one Workspace projection."""

    WORK_REVIEW = "work_review"
    SCHEMA = "schema"
    MATERIALIZATION = "materialization"
    PROVENANCE = "provenance"


class ModeloWorkspaceLocaleDisposition(StrEnum):
    """The one canonical locale-resolution outcome for a displayed record."""

    EXACT = "exact"
    SPANISH_FALLBACK = "spanish_fallback"
    SUPPRESSED = "suppressed"


class ModeloWorkspaceRevisionAssertionDisposition(StrEnum):
    """Whether the optional visible-target revision assertion matched law selection."""

    NOT_REQUESTED = "not_requested"
    MATCHED = "matched"
    MISMATCHED = "mismatched"


class ModeloWorkspaceRefusalCode(StrEnum):
    """Stable domain-boundary refusals for an otherwise supported Workspace V1."""

    TARGET_NOT_FOUND = "target_not_found"
    VISIBLE_TARGET_AMBIGUOUS = "visible_target_ambiguous"
    BUCKET_ASSERTION_MISMATCH = "bucket_assertion_mismatch"
    REVISION_ASSERTION_MISMATCH = "revision_assertion_mismatch"
    STATIC_INSPECTION_UNAVAILABLE = "static_inspection_unavailable"
    AUTHORITY_GRADE_UNAVAILABLE = "authority_grade_unavailable"
    SCHEMA_UNAVAILABLE = "schema_unavailable"
    LOCALE_UNAVAILABLE = "locale_unavailable"
    CONSISTENCY_UNAVAILABLE = "consistency_unavailable"
    WORKSPACE_CHANGED = "workspace_changed"


class ModeloWorkspaceSchemaClassification(StrEnum):
    """The exhaustive generated denominator classification for a registry field."""

    PROJECTED = "projected"
    DERIVED = "derived"
    BACKEND_ONLY = "backend_only"


class ModeloWorkspaceVersionHeader(_WorkspaceModel):
    """Minimal pre-dispatch shape read before target or secure-state resolution."""

    contract_version: Annotated[int, Field(ge=1)]


class ModeloWorkspaceStaticInspectionAdmissionV1(_WorkspaceModel):
    """Request static registry inspection without admitting a runtime snapshot."""

    kind: Literal[ModeloWorkspaceAdmissionKind.STATIC_INSPECTION] = ModeloWorkspaceAdmissionKind.STATIC_INSPECTION


class ModeloWorkspaceGradedSnapshotAdmissionV1(_WorkspaceModel):
    """Request a law-selected snapshot that satisfies one declared authority grade."""

    kind: Literal[ModeloWorkspaceAdmissionKind.GRADED_SNAPSHOT] = ModeloWorkspaceAdmissionKind.GRADED_SNAPSHOT
    required_grade: RegistryAuthorityGrade


type ModeloWorkspaceAdmissionV1 = Annotated[
    ModeloWorkspaceStaticInspectionAdmissionV1 | ModeloWorkspaceGradedSnapshotAdmissionV1,
    Field(discriminator="kind"),
]


def _target_from_mapping(value: Mapping[str, object]) -> _WorkspaceTarget:
    """Adapt an untyped wire mapping once into the existing canonical target family."""
    if "work_unit_id" in value:
        expected = {"work_unit_id", "bucket_id"}
        if set(value) - expected or "work_unit_id" not in value:
            raise ValueError("exact workspace targets accept only work_unit_id and optional bucket_id")
        work_unit_id = value["work_unit_id"]
        bucket_id = value.get("bucket_id")
        if not isinstance(work_unit_id, str) or (bucket_id is not None and not isinstance(bucket_id, str)):
            raise ValueError("exact workspace target identifiers must be strings")
        return ModeloExactWorkUnitTarget(
            work_unit_id=_WORK_UNIT_ID_ADAPTER.validate_python(work_unit_id),
            bucket_id=None if bucket_id is None else _BUCKET_ID_ADAPTER.validate_python(bucket_id),
        )

    expected = {"modelo", "filing_year", "period", "registry_revision_id", "bucket_id"}
    required = {"modelo", "filing_year", "period"}
    if set(value) - expected or not required.issubset(value):
        raise ValueError("visible workspace targets require modelo, filing_year, and period")
    modelo = value["modelo"]
    filing_year = value["filing_year"]
    period = value["period"]
    revision_id = value.get("registry_revision_id")
    bucket_id = value.get("bucket_id")
    if not isinstance(modelo, str) or type(filing_year) is not int:
        raise ValueError("visible workspace target modelo and filing_year must have canonical scalar types")
    if not isinstance(period, (str, Period, Mapping)):
        raise ValueError(
            "visible workspace target period must be a Period, registry token, or canonical period mapping"
        )
    if revision_id is not None and not isinstance(revision_id, str):
        raise ValueError("visible workspace target registry_revision_id must be a string")
    if bucket_id is not None and not isinstance(bucket_id, str):
        raise ValueError("visible workspace target bucket_id must be a string")
    resolved_period = (
        period
        if isinstance(period, Period)
        else Period.model_validate(period)
        if isinstance(period, Mapping)
        else Period.from_year_and_code(filing_year, period)
    )
    if resolved_period.filing_year != filing_year:
        raise ValueError("visible workspace target period must agree with filing_year")
    return ModeloVisibleFilingTarget(
        modelo=modelo,
        filing_year=filing_year,
        period=resolved_period,
        registry_revision_id=None if revision_id is None else _REVISION_ID_ADAPTER.validate_python(revision_id),
        bucket_id=None if bucket_id is None else _BUCKET_ID_ADAPTER.validate_python(bucket_id),
    )


class ModeloWorkspaceRequestV1(_WorkspaceModel):
    """One V1 read request over a canonical visible or advanced exact target."""

    contract_version: Literal[1] = 1
    target: _WorkspaceTarget
    admission: ModeloWorkspaceAdmissionV1
    output_language: OutputLanguage

    @field_validator("target", mode="before")
    @classmethod
    def _adapt_wire_target(cls, value: object) -> _WorkspaceTarget:
        if isinstance(value, (ModeloVisibleFilingTarget, ModeloExactWorkUnitTarget)):
            return value
        if not isinstance(value, Mapping):
            raise ValueError("workspace target must be a canonical target or an exact target mapping")
        return _target_from_mapping(value)


class ModeloWorkspaceRevisionAssertionV1(_WorkspaceModel):
    """The requested visible-target assertion and its law-selection outcome."""

    disposition: ModeloWorkspaceRevisionAssertionDisposition
    requested_revision_id: RevisionId | None = None

    @model_validator(mode="after")
    def _require_consistent_assertion_shape(self) -> ModeloWorkspaceRevisionAssertionV1:
        requested = self.requested_revision_id is not None
        if (self.disposition is ModeloWorkspaceRevisionAssertionDisposition.NOT_REQUESTED) != (not requested):
            raise ValueError("revision assertion disposition must agree with requested_revision_id")
        return self


class ModeloWorkspaceResolvedTargetV1(_WorkspaceModel):
    """Resolved natural coordinates and optional persisted work state, never a selector."""

    bucket_id: BucketId
    modelo: ModeloCode
    filing_year: Annotated[int, Field(ge=2000, le=2100)]
    period: Period
    law_selected_revision_id: RevisionId
    review_status: RevisionReviewStatus
    revision_assertion: ModeloWorkspaceRevisionAssertionV1
    work_unit_id: WorkUnitId | None = None
    work_state: WorkUnitState | None = None

    @model_validator(mode="after")
    def _require_work_identity_and_state_together(self) -> ModeloWorkspaceResolvedTargetV1:
        if (self.work_unit_id is None) != (self.work_state is None):
            raise ValueError("resolved workspace work_unit_id and work_state must be present together")
        return self


class ModeloWorkspaceLocaleSummaryV1(_WorkspaceModel):
    """Canonical locale coordinates, independent from semantic workspace identity."""

    requested_language: OutputLanguage
    resolved_language: OutputLanguage
    disposition: ModeloWorkspaceLocaleDisposition
    catalogue_digest: ContentDigest

    @model_validator(mode="after")
    def _validate_resolution(self) -> ModeloWorkspaceLocaleSummaryV1:
        if self.disposition is ModeloWorkspaceLocaleDisposition.EXACT:
            if self.requested_language is not self.resolved_language:
                raise ValueError("exact locale resolution requires the requested language")
        elif self.disposition is ModeloWorkspaceLocaleDisposition.SPANISH_FALLBACK:
            if self.requested_language is self.resolved_language or self.resolved_language is not OutputLanguage.ES:
                raise ValueError("locale fallback may resolve only a non-Spanish request to Spanish")
        elif self.resolved_language is not OutputLanguage.ES:
            raise ValueError("suppressed locale resolution retains Spanish as its canonical fallback")
        return self


class ModeloWorkspaceLocalizedTextV1(_WorkspaceModel):
    """One localized display string with its canonical resolution coordinates."""

    locale_key: _BoundedCode
    value: str
    locale: ModeloWorkspaceLocaleSummaryV1


class ModeloWorkspaceSchemaIdentityV1(_WorkspaceModel):
    """The selected public registry schema identity and its current field denominator."""

    schema_id: _BoundedCode
    schema_fingerprint: ContentDigest
    field_manifest_digest: ContentDigest


class ModeloWorkspaceCasillaReferenceV1(_WorkspaceModel):
    kind: Literal["casilla"] = "casilla"
    casilla_id: CasillaId


class ModeloWorkspaceBindingReferenceV1(_WorkspaceModel):
    kind: Literal["binding"] = "binding"
    binding_id: BindingId


class ModeloWorkspaceFormulaReferenceV1(_WorkspaceModel):
    kind: Literal["formula"] = "formula"
    formula_id: FormulaId


class ModeloWorkspaceRelationReferenceV1(_WorkspaceModel):
    kind: Literal["relation"] = "relation"
    relation_id: RelationId


class ModeloWorkspaceParameterReferenceV1(_WorkspaceModel):
    kind: Literal["parameter"] = "parameter"
    parameter_id: ParameterId


class ModeloWorkspaceExportFieldReferenceV1(_WorkspaceModel):
    kind: Literal["export_field"] = "export_field"
    export_field_id: ExportFieldId


type ModeloWorkspaceSchemaReferenceV1 = Annotated[
    ModeloWorkspaceCasillaReferenceV1
    | ModeloWorkspaceBindingReferenceV1
    | ModeloWorkspaceFormulaReferenceV1
    | ModeloWorkspaceRelationReferenceV1
    | ModeloWorkspaceParameterReferenceV1
    | ModeloWorkspaceExportFieldReferenceV1,
    Field(discriminator="kind"),
]


class ModeloWorkspaceSchemaRecordV1(_WorkspaceModel):
    """Explanatory schema row using canonical registry identities, never grammar objects."""

    reference: ModeloWorkspaceSchemaReferenceV1
    section_path: tuple[_BoundedText, ...]
    data_type: _BoundedCode
    label: ModeloWorkspaceLocalizedTextV1
    classification: ModeloWorkspaceSchemaClassification
    family_disposition: RegistrySchemaFamilyDisposition
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()


class ModeloWorkspaceFamilyDispositionV1(_WorkspaceModel):
    """One named registry schema-family disposition with its safe evidence references."""

    family: _BoundedCode
    disposition: RegistrySchemaFamilyDisposition
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()


class ModeloWorkspaceProvenanceRecordV1(_WorkspaceModel):
    """Safe causal lineage for one schema or materialization reference."""

    subject: ModeloWorkspaceSchemaReferenceV1
    lineage_role: CalculationSourceLineageRole
    resolved_source_kind: BindingSourceKind
    contributor_source_kind: BindingSourceKind | None = None
    source_ref: SourceRefId
    parent_source_ref: SourceRefId | None = None
    fingerprint: ContentDigest


class ModeloWorkspaceScalarMaterializationV1(_WorkspaceModel):
    """One scalar materialization keyed by the canonical casilla identity."""

    casilla_id: CasillaId
    value: ModeloScalar
    provenance: tuple[ModeloWorkspaceProvenanceRecordV1, ...] = ()


class ModeloWorkspaceRepeatedRowMaterializationV1(_WorkspaceModel):
    """One positive-index repeated binding row without flattening it into a casilla id."""

    binding_id: BindingId
    row_index: Annotated[int, Field(ge=1)]
    values: tuple[ModeloWorkspaceScalarMaterializationV1, ...]
    provenance: tuple[ModeloWorkspaceProvenanceRecordV1, ...] = ()


class ModeloWorkspaceMaterializationRecordV1(_WorkspaceModel):
    """A bounded scalar or repeated-row materialization record."""

    kind: Literal["scalar", "repeated_row"]
    scalar: ModeloWorkspaceScalarMaterializationV1 | None = None
    repeated_row: ModeloWorkspaceRepeatedRowMaterializationV1 | None = None

    @model_validator(mode="after")
    def _require_exactly_one_materialization_arm(self) -> ModeloWorkspaceMaterializationRecordV1:
        if self.kind == "scalar" and self.scalar is not None and self.repeated_row is None:
            return self
        if self.kind == "repeated_row" and self.repeated_row is not None and self.scalar is None:
            return self
        raise ValueError("workspace materialization kind must name exactly one matching arm")


class ModeloWorkspaceEvidenceFactV1(_WorkspaceModel):
    """A bounded non-financial fact for capability or refusal explanation."""

    name: _BoundedCode
    value: Annotated[str | int | bool, Field(max_length=_MAX_SAFE_FACT_TEXT_LENGTH)]


class ModeloWorkspaceLegalEvidenceReferenceV1(_WorkspaceModel):
    kind: Literal["legal"] = "legal"
    legal_ref_id: LegalRefId


class ModeloWorkspaceSourceEvidenceReferenceV1(_WorkspaceModel):
    kind: Literal["source"] = "source"
    source_ref_id: SourceRefId


type ModeloWorkspaceEvidenceReferenceV1 = Annotated[
    ModeloWorkspaceLegalEvidenceReferenceV1 | ModeloWorkspaceSourceEvidenceReferenceV1,
    Field(discriminator="kind"),
]


class ModeloWorkspaceCapabilityV1(_WorkspaceModel):
    """One non-inferred capability answer copied from its canonical producer."""

    capability: ModeloWorkspaceCapabilityName
    disposition: ModeloWorkspaceCapabilityDisposition
    producer_owner: _BoundedCode
    producer: _BoundedCode
    evidence: tuple[ModeloWorkspaceEvidenceReferenceV1, ...] = ()
    facts: tuple[ModeloWorkspaceEvidenceFactV1, ...] = ()
    source_disposition: RegistrySchemaFamilyDisposition | None = None
    recovery_action: ActionReference | None = None

    @field_validator("facts")
    @classmethod
    def _require_unique_bounded_facts(
        cls, value: tuple[ModeloWorkspaceEvidenceFactV1, ...]
    ) -> tuple[ModeloWorkspaceEvidenceFactV1, ...]:
        if len(value) > _MAX_SAFE_FACTS:
            raise ValueError(f"workspace capability facts cannot exceed {_MAX_SAFE_FACTS}")
        if len({fact.name for fact in value}) != len(value):
            raise ValueError("workspace capability fact names must be unique")
        return tuple(sorted(value, key=lambda fact: fact.name))


def _complete_capability_denominator(
    value: tuple[ModeloWorkspaceCapabilityV1, ...],
) -> tuple[ModeloWorkspaceCapabilityV1, ...]:
    """Keep both successful admission arms on the one closed capability inventory."""
    capability_set = {capability.capability for capability in value}
    if capability_set != set(ModeloWorkspaceCapabilityName) or len(value) != len(capability_set):
        raise ValueError("workspace capability rows must cover each V1 capability exactly once")
    return tuple(sorted(value, key=lambda capability: capability.capability.value))


class ModeloWorkspaceBoundedFacetV1[RecordT: BaseModel](_WorkspaceModel):
    """A baseline-pinned, finite page from one workspace facet."""

    facet: ModeloWorkspaceFacetName
    disposition: ModeloWorkspaceCapabilityDisposition
    records: tuple[RecordT, ...] = ()
    page_size: Annotated[int, Field(ge=1, le=_MAX_FACET_PAGE_SIZE)]
    next_cursor: str | None = None
    has_more: bool = False

    @model_validator(mode="after")
    def _validate_page(self) -> ModeloWorkspaceBoundedFacetV1[RecordT]:
        if len(self.records) > self.page_size:
            raise ValueError("workspace facet cannot contain more records than its page_size")
        if self.has_more != (self.next_cursor is not None):
            raise ValueError("workspace facet has_more must agree with next_cursor")
        if self.disposition is not ModeloWorkspaceCapabilityDisposition.AVAILABLE and (
            self.records or self.has_more or self.next_cursor is not None
        ):
            raise ValueError("unavailable workspace facets cannot carry records or cursors")
        return self


class ModeloWorkspaceWorkReviewFacetV1(_WorkspaceModel):
    """The exact canonical review facet or an explicit ineligible disposition."""

    disposition: ModeloWorkspaceCapabilityDisposition
    review: ModeloWorkReview | None = None

    @model_validator(mode="after")
    def _require_review_only_when_available(self) -> ModeloWorkspaceWorkReviewFacetV1:
        if (self.disposition is ModeloWorkspaceCapabilityDisposition.AVAILABLE) != (self.review is not None):
            raise ValueError("work review facet must contain its canonical review exactly when available")
        return self


class ModeloWorkspaceBaselineV1(_WorkspaceModel):
    """Opaque read consistency identity; this is not mutation authority or approval."""

    contract_version: Literal[1] = 1
    token: ContentDigest
    contributor_stamp_digest: ContentDigest
    target: ModeloWorkspaceResolvedTargetV1
    selected_revision_id: RevisionId
    schema_identity: ModeloWorkspaceSchemaIdentityV1
    locale_catalogue_digest: ContentDigest


class ModeloWorkspaceEvidenceHorizonV1(_WorkspaceModel):
    """The safe evidence coordinates on which the admitted projection rests."""

    source_refs: tuple[SourceRefId, ...]
    evidence_digest: ContentDigest


class ModeloWorkspaceSnapshotScopeV1(_WorkspaceModel):
    """The explicitly requested, declared, and effective grade for a snapshot admission."""

    required_grade: RegistryAuthorityGrade
    declared_grade: RegistryAuthorityGrade
    effective_grade: RegistryAuthorityGrade
    snapshot_scope_digest: ContentDigest


class ModeloWorkspaceStaticInspectionScopeV1(_WorkspaceModel):
    """The successful scope of inspection-only admission."""

    kind: Literal[ModeloWorkspaceAdmissionKind.STATIC_INSPECTION] = ModeloWorkspaceAdmissionKind.STATIC_INSPECTION
    snapshot_admitted: Literal[False] = False


class ModeloWorkspaceGradedSnapshotScopeV1(_WorkspaceModel):
    """The successful scope of one authority-grade-admitted snapshot."""

    kind: Literal[ModeloWorkspaceAdmissionKind.GRADED_SNAPSHOT] = ModeloWorkspaceAdmissionKind.GRADED_SNAPSHOT
    snapshot_admitted: Literal[True] = True
    scope: ModeloWorkspaceSnapshotScopeV1


type ModeloWorkspaceProjectionAdmissionV1 = Annotated[
    ModeloWorkspaceStaticInspectionScopeV1 | ModeloWorkspaceGradedSnapshotScopeV1,
    Field(discriminator="kind"),
]


class ModeloWorkspaceProjectionV1(_WorkspaceModel):
    """One assembled, baseline-pinned read projection with no mutation authority."""

    contract_version: Literal[1] = 1
    admission: ModeloWorkspaceProjectionAdmissionV1
    target: ModeloWorkspaceResolvedTargetV1
    schema_identity: ModeloWorkspaceSchemaIdentityV1
    locale: ModeloWorkspaceLocaleSummaryV1
    evidence_horizon: ModeloWorkspaceEvidenceHorizonV1
    family_dispositions: tuple[ModeloWorkspaceFamilyDispositionV1, ...]
    baseline: ModeloWorkspaceBaselineV1
    schema_facet: ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1]
    materialization_facet: ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceMaterializationRecordV1] | None = None
    provenance_facet: ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceProvenanceRecordV1] | None = None
    work_review: ModeloWorkspaceWorkReviewFacetV1
    capabilities: tuple[ModeloWorkspaceCapabilityV1, ...]

    @field_validator("capabilities")
    @classmethod
    def _require_complete_capability_denominator(
        cls, value: tuple[ModeloWorkspaceCapabilityV1, ...]
    ) -> tuple[ModeloWorkspaceCapabilityV1, ...]:
        return _complete_capability_denominator(value)

    @field_validator("family_dispositions")
    @classmethod
    def _require_unique_family_dispositions(
        cls, value: tuple[ModeloWorkspaceFamilyDispositionV1, ...]
    ) -> tuple[ModeloWorkspaceFamilyDispositionV1, ...]:
        if len({family.family for family in value}) != len(value):
            raise ValueError("workspace schema-family dispositions must be unique")
        return tuple(sorted(value, key=lambda family: family.family))

    @model_validator(mode="after")
    def _enforce_admission_scope(self) -> ModeloWorkspaceProjectionV1:
        if self.schema_facet.facet is not ModeloWorkspaceFacetName.SCHEMA:
            raise ValueError("workspace projection schema_facet must declare the schema facet")
        if self.baseline.target != self.target:
            raise ValueError("workspace baseline must pin the exact resolved target")
        if self.baseline.selected_revision_id != self.target.law_selected_revision_id:
            raise ValueError("workspace baseline must pin the exact law-selected revision")
        if self.baseline.schema_identity != self.schema_identity:
            raise ValueError("workspace baseline must pin the exact schema identity")
        if isinstance(self.admission, ModeloWorkspaceStaticInspectionScopeV1):
            if self.materialization_facet is not None or self.provenance_facet is not None:
                raise ValueError("static inspection cannot carry materialization or provenance facets")
            if self.work_review.disposition is ModeloWorkspaceCapabilityDisposition.AVAILABLE:
                raise ValueError("static inspection cannot carry a materialized work review")
            return self
        if self.materialization_facet is None or self.provenance_facet is None:
            raise ValueError("graded snapshot requires materialization and provenance facets")
        expected = (
            (self.materialization_facet, ModeloWorkspaceFacetName.MATERIALIZATION),
            (self.provenance_facet, ModeloWorkspaceFacetName.PROVENANCE),
        )
        if any(facet.facet is not expected_name for facet, expected_name in expected):
            raise ValueError("graded snapshot facets must retain their canonical names")
        return self


class ModeloWorkspaceStaticInspectionResultV1(_WorkspaceModel):
    """A successful static registry inspection with no runtime snapshot admission."""

    outcome: Literal["static_inspection"] = "static_inspection"
    contract_version: Literal[1] = 1
    projection: ModeloWorkspaceProjectionV1

    @model_validator(mode="after")
    def _require_static_projection(self) -> ModeloWorkspaceStaticInspectionResultV1:
        if self.projection.contract_version != self.contract_version or not isinstance(
            self.projection.admission, ModeloWorkspaceStaticInspectionScopeV1
        ):
            raise ValueError("static inspection result must carry one V1 static projection")
        return self


class ModeloWorkspaceGradedSnapshotResultV1(_WorkspaceModel):
    """A successful grade-admitted projection with bounded materialization facets."""

    outcome: Literal["graded_snapshot"] = "graded_snapshot"
    contract_version: Literal[1] = 1
    projection: ModeloWorkspaceProjectionV1

    @model_validator(mode="after")
    def _require_graded_projection(self) -> ModeloWorkspaceGradedSnapshotResultV1:
        if self.projection.contract_version != self.contract_version or not isinstance(
            self.projection.admission, ModeloWorkspaceGradedSnapshotScopeV1
        ):
            raise ValueError("graded snapshot result must carry one V1 graded projection")
        return self


class ModeloWorkspaceVersionRefusalV1(_WorkspaceModel):
    """Minimal refusal produced before a rejected request target is parsed."""

    kind: Literal["unsupported_version"] = "unsupported_version"
    requested_version: Annotated[int, Field(ge=1)] | None
    supported_version: Literal[1] = 1


class ModeloWorkspaceDomainRefusalV1(_WorkspaceModel):
    """Typed post-parse refusal without a partial projection or raw exception."""

    kind: Literal["domain"] = "domain"
    contract_version: Literal[1] = 1
    code: ModeloWorkspaceRefusalCode
    boundary: Literal["admission", "capability", "consistency", "locale", "schema"]
    capability: ModeloWorkspaceCapabilityName | None = None
    requested_target: _WorkspaceTarget
    selected_target: ModeloWorkspaceResolvedTargetV1 | None = None
    facts: tuple[ModeloWorkspaceEvidenceFactV1, ...] = ()
    evidence: tuple[ModeloWorkspaceEvidenceReferenceV1, ...] = ()
    responsible_owner: _BoundedCode
    source_disposition: RegistrySchemaFamilyDisposition | None = None
    reconsideration_condition: _BoundedText
    recovery_action: ActionReference | None = None

    @field_validator("requested_target", mode="before")
    @classmethod
    def _adapt_refusal_target(cls, value: object) -> _WorkspaceTarget:
        return ModeloWorkspaceRequestV1._adapt_wire_target(value)

    @field_validator("facts")
    @classmethod
    def _require_unique_refusal_facts(
        cls, value: tuple[ModeloWorkspaceEvidenceFactV1, ...]
    ) -> tuple[ModeloWorkspaceEvidenceFactV1, ...]:
        if len(value) > _MAX_SAFE_FACTS:
            raise ValueError(f"workspace refusal facts cannot exceed {_MAX_SAFE_FACTS}")
        if len({fact.name for fact in value}) != len(value):
            raise ValueError("workspace refusal fact names must be unique")
        return tuple(sorted(value, key=lambda fact: fact.name))


type ModeloWorkspaceRefusalV1 = Annotated[
    ModeloWorkspaceVersionRefusalV1 | ModeloWorkspaceDomainRefusalV1,
    Field(discriminator="kind"),
]


class ModeloWorkspaceRefusedResultV1(_WorkspaceModel):
    """The result arm that exposes a refusal without calling it a partial success."""

    outcome: Literal["refused"] = "refused"
    refusal: ModeloWorkspaceRefusalV1


type ModeloWorkspaceResultV1 = Annotated[
    ModeloWorkspaceStaticInspectionResultV1 | ModeloWorkspaceGradedSnapshotResultV1 | ModeloWorkspaceRefusedResultV1,
    Field(discriminator="outcome"),
]


__all__ = [
    "ModeloWorkspaceAdmissionKind",
    "ModeloWorkspaceAdmissionV1",
    "ModeloWorkspaceBaselineV1",
    "ModeloWorkspaceBoundedFacetV1",
    "ModeloWorkspaceCapabilityDisposition",
    "ModeloWorkspaceCapabilityName",
    "ModeloWorkspaceCapabilityV1",
    "ModeloWorkspaceDomainRefusalV1",
    "ModeloWorkspaceEvidenceFactV1",
    "ModeloWorkspaceEvidenceHorizonV1",
    "ModeloWorkspaceEvidenceReferenceV1",
    "ModeloWorkspaceExportFieldReferenceV1",
    "ModeloWorkspaceFacetName",
    "ModeloWorkspaceFamilyDispositionV1",
    "ModeloWorkspaceFormulaReferenceV1",
    "ModeloWorkspaceGradedSnapshotAdmissionV1",
    "ModeloWorkspaceGradedSnapshotResultV1",
    "ModeloWorkspaceGradedSnapshotScopeV1",
    "ModeloWorkspaceLocaleDisposition",
    "ModeloWorkspaceLocaleSummaryV1",
    "ModeloWorkspaceLocalizedTextV1",
    "ModeloWorkspaceMaterializationRecordV1",
    "ModeloWorkspaceParameterReferenceV1",
    "ModeloWorkspaceProjectionAdmissionV1",
    "ModeloWorkspaceProjectionV1",
    "ModeloWorkspaceProvenanceRecordV1",
    "ModeloWorkspaceRefusalCode",
    "ModeloWorkspaceRefusalV1",
    "ModeloWorkspaceRefusedResultV1",
    "ModeloWorkspaceRequestV1",
    "ModeloWorkspaceResolvedTargetV1",
    "ModeloWorkspaceResultV1",
    "ModeloWorkspaceRevisionAssertionDisposition",
    "ModeloWorkspaceRevisionAssertionV1",
    "ModeloWorkspaceSchemaClassification",
    "ModeloWorkspaceSchemaIdentityV1",
    "ModeloWorkspaceSchemaRecordV1",
    "ModeloWorkspaceSchemaReferenceV1",
    "ModeloWorkspaceSnapshotScopeV1",
    "ModeloWorkspaceStaticInspectionAdmissionV1",
    "ModeloWorkspaceStaticInspectionResultV1",
    "ModeloWorkspaceStaticInspectionScopeV1",
    "ModeloWorkspaceVersionHeader",
    "ModeloWorkspaceVersionRefusalV1",
    "ModeloWorkspaceWorkReviewFacetV1",
]
