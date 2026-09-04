"""Strict, frontend-neutral records for the read-only Modelo Workspace V1."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, NonNegativeInt, field_validator, model_validator

from ...core.aggregation import BindingSourceKind
from ...core.authority_grade import RegistryAuthorityGrade
from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.identity import BucketId, ContentDigest, ContinuidadId, ProfileId, TransactionId, WorkUnitId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.revision_review import RevisionReviewStatus
from ...core.schema_family_disposition import RegistrySchemaFamilyDisposition
from ...domain.calculations.registry.ids import (
    ApplicabilityRuleId,
    BindingId,
    ExportFieldId,
    FormulaId,
    LegalRefId,
    ParameterId,
    RelationId,
    RevisionId,
    SourceRefId,
)
from ...domain.filing.schema import ModeloScalar
from ...domain.modelos.calculation_revision import CalculationSourceRef
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.work_unit import WorkUnitState
from ..ledger.preflight import LedgerPreflightIssueReason
from ..operator_actions.models import ActionReference
from ..registry.closure import RegistryClosureLimb
from .work_addressing import ModeloExactWorkUnitTarget, ModeloVisibleFilingTarget
from .work_review import ModeloWorkReview

_MAX_FACET_PAGE_SIZE = 200
_MAX_CONTRIBUTORS = 32
_MAX_SCHEMA_RECORD_FAMILY_DEPTH = 16
_MAX_SCHEMA_RELATIONSHIPS = 128
_MAX_SCHEMA_EVIDENCE_REFERENCES = 64
_MAX_REPEATED_ROW_VALUES = 200
_MAX_CLOSURE_LIMBS = 16
_MAX_SAFE_FACTS = 32
_MAX_SAFE_FACT_TEXT_LENGTH = 256

type _BoundedText = Annotated[str, Field(min_length=1, max_length=256)]
type _BoundedCode = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")]
type _BoundedLocaleKey = Annotated[str, Field(min_length=1, max_length=256, pattern=r"^[a-z][A-Za-z0-9_.-]*$")]
"""Locale keys embed a base32hex-encoded arbitrary identity segment
(:func:`~cadrumo.domain.calculations.registry.modelo_localization.encode_modelo_locale_segment`)
for any casilla/binding/relation/etc id containing characters outside the
plain-segment pattern, so a real key can exceed ``_BoundedCode``'s 128-char
bound; 256 covers the longest real casilla id observed in the bundled
registry (143 chars) with headroom.

An interior segment may be UPPERCASE, and that is not a laxity: the encoder's
plain-segment pattern is ``[A-Za-z0-9_-]``, so an id like the Modelo 100
casilla ``A`` is passed through as itself rather than encoded, and the packaged
catalogues carry it in that spelling. A lowercase-only bound here disagreed
with both the producer and the shipped data, and the disagreement was not
cosmetic -- it made every Workspace destination unopenable for any modelo
declaring an uppercase casilla id, which includes Modelo 100. The leading
character stays lowercase because the first segment is always a namespace
(``modelo.``, ``flows.``, ``wizard.``) and no producer emits any other shape."""
type _BoundedLocalizedText = Annotated[str, Field(min_length=1, max_length=512)]
type _BoundedRefList[T] = Annotated[tuple[T, ...], Field(max_length=_MAX_SCHEMA_EVIDENCE_REFERENCES)]


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


class ModeloWorkspaceRevisionAssertionSource(StrEnum):
    """The fixed coordinate that supplied one independently checked assertion."""

    REQUESTED = "requested"
    STORED = "stored"


class ModeloWorkspaceRevisionAssertionDisposition(StrEnum):
    """The closed outcome of one independently checked revision assertion."""

    NOT_PRESENT = "not_present"
    MATCHED = "matched"
    MISMATCHED = "mismatched"


class ModeloWorkspaceRefusalCode(StrEnum):
    """Stable domain-boundary refusals for an otherwise supported Workspace V1."""

    TARGET_NOT_FOUND = "target_not_found"
    """The natural (modelo, filing_year, period) coordinate the target names
    resolves cleanly, but no :class:`WorkUnit` exists there yet -- the WORK
    selector's own ``ABSENT`` state (``resolution.work_unit is None``).
    Distinct from ``CALCULATION_UNAVAILABLE``, whose work unit DOES exist and
    merely carries no calculation revision: an absent work unit cannot be
    "calculated"; it must be created first, a different operator remedy the
    two codes must not share."""
    VISIBLE_TARGET_AMBIGUOUS = "visible_target_ambiguous"
    BUCKET_ASSERTION_MISMATCH = "bucket_assertion_mismatch"
    REVISION_ASSERTION_MISMATCH = "revision_assertion_mismatch"
    STATIC_INSPECTION_UNAVAILABLE = "static_inspection_unavailable"
    AUTHORITY_GRADE_UNAVAILABLE = "authority_grade_unavailable"
    CALCULATION_UNAVAILABLE = "calculation_unavailable"
    """The WORK axis resolved an EXISTING work unit for this target, but it
    carries no calculation revision yet (``current_calculation_revision_id is
    None``), so a GRADED_SNAPSHOT admission cannot produce the required
    materialization/provenance facets. Distinct from
    ``AUTHORITY_GRADE_UNAVAILABLE`` (a REGISTRY-axis fact): folding a missing
    calculation into the grade code would send an operator to the wrong
    remedy -- the registry, not "calculate this work unit first". Also
    distinct from ``TARGET_NOT_FOUND`` (no work unit exists at all): this
    code's own reconsideration text ("calculate this work unit") presumes a
    work unit the operator can act on. Never raised for a STATIC_INSPECTION
    admission, which has no calculation dependency."""
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


class ModeloWorkspaceVisibleFilingTargetV1(_WorkspaceModel):
    """Serialized visible-target arm that retains the canonical target operand."""

    kind: Literal["visible_filing"] = "visible_filing"
    target: ModeloVisibleFilingTarget


class ModeloWorkspaceExactWorkUnitTargetV1(_WorkspaceModel):
    """Serialized exact-work-unit arm that retains the canonical target operand."""

    kind: Literal["exact_work_unit"] = "exact_work_unit"
    target: ModeloExactWorkUnitTarget


type ModeloWorkspaceTargetV1 = Annotated[
    ModeloWorkspaceVisibleFilingTargetV1 | ModeloWorkspaceExactWorkUnitTargetV1,
    Field(discriminator="kind"),
]


class ModeloWorkspaceRefreshTargetV1(_WorkspaceModel):
    """The exact workspace read one settled Modelo operation invalidates.

    Names the resolved work-unit coordinates rather than wrapping a request
    selector, so a frontend re-reads the affected unit without interpreting a
    settled receipt it should not have to understand.

    The coordinates are spelled as closed typed fields rather than reusing
    :data:`ModeloWorkspaceTargetV1`: that union embeds a plain dataclass,
    whose generated schema carries no closed-object marker, and a target
    published through the operations public-schema registry must be closed
    end to end.
    """

    contract_version: Literal[1] = 1
    work_unit_id: WorkUnitId


class ModeloWorkspaceRequestV1(_WorkspaceModel):
    """One V1 read request over a canonical visible or advanced exact target."""

    contract_version: Literal[1] = 1
    target: ModeloWorkspaceTargetV1
    admission: ModeloWorkspaceAdmissionV1
    output_language: OutputLanguage


class ModeloWorkspaceRevisionAssertionV1(_WorkspaceModel):
    """One source-fixed optional assertion and its independently supplied outcome."""

    source: ModeloWorkspaceRevisionAssertionSource
    disposition: ModeloWorkspaceRevisionAssertionDisposition
    asserted_revision_id: RevisionId | None

    @model_validator(mode="after")
    def _require_consistent_assertion_shape(self) -> ModeloWorkspaceRevisionAssertionV1:
        asserted = self.asserted_revision_id is not None
        if (self.disposition is ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT) != (not asserted):
            raise ValueError("revision assertion disposition must agree with asserted_revision_id")
        return self


class ModeloWorkspaceResolvedTargetV1(_WorkspaceModel):
    """Resolved natural coordinates and optional persisted work state, never a selector."""

    bucket_id: BucketId
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    law_selected_revision_id: RevisionId
    review_status: RevisionReviewStatus
    requested_revision_assertion: ModeloWorkspaceRevisionAssertionV1
    stored_revision_assertion: ModeloWorkspaceRevisionAssertionV1
    work_unit_id: WorkUnitId | None = None
    work_state: WorkUnitState | None = None

    @model_validator(mode="after")
    def _require_work_identity_and_state_together(self) -> ModeloWorkspaceResolvedTargetV1:
        if (self.work_unit_id is None) != (self.work_state is None):
            raise ValueError("resolved workspace work_unit_id and work_state must be present together")
        if self.requested_revision_assertion.source is not ModeloWorkspaceRevisionAssertionSource.REQUESTED:
            raise ValueError("requested workspace revision assertion must retain the requested source")
        if self.stored_revision_assertion.source is not ModeloWorkspaceRevisionAssertionSource.STORED:
            raise ValueError("stored workspace revision assertion must retain the stored source")
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

    kind: Literal["localized"] = "localized"
    locale_key: _BoundedLocaleKey
    value: _BoundedLocalizedText
    locale: ModeloWorkspaceLocaleSummaryV1


class ModeloWorkspaceTechnicalLabelV1(_WorkspaceModel):
    """A row's canonical registry identifier, presented honestly as never-translated.

    Formula, binding, relation, and parameter identities have no
    locale-catalogue entry anywhere in the tree and are never surfaced to a
    taxpayer as operator-facing prose -- they are registry names, always
    shown as themselves in every diagnostic and review surface that already
    displays them. Wrapping a bare identifier in
    :class:`ModeloWorkspaceLocalizedTextV1` would misrepresent it as a
    translation that happened; this type says plainly that none did.
    """

    kind: Literal["technical"] = "technical"
    identifier: _BoundedCode


type ModeloWorkspaceRecordLabelV1 = Annotated[
    ModeloWorkspaceLocalizedTextV1 | ModeloWorkspaceTechnicalLabelV1,
    Field(discriminator="kind"),
]


class ModeloWorkspaceSchemaIdentityV1(_WorkspaceModel):
    """The selected public registry schema identity and its current field denominator."""

    schema_id: _BoundedCode
    schema_fingerprint: ContentDigest
    field_manifest_digest: ContentDigest


class ModeloWorkspaceCasillaReferenceV1(_WorkspaceModel):
    """A canonical casilla identity exposed in one schema reference."""

    kind: Literal["casilla"] = "casilla"
    casilla_id: CasillaId


class ModeloWorkspaceBindingReferenceV1(_WorkspaceModel):
    """A canonical binding identity exposed in one schema reference."""

    kind: Literal["binding"] = "binding"
    binding_id: BindingId


class ModeloWorkspaceFormulaReferenceV1(_WorkspaceModel):
    """A canonical formula identity exposed in one schema reference."""

    kind: Literal["formula"] = "formula"
    formula_id: FormulaId


class ModeloWorkspaceRelationReferenceV1(_WorkspaceModel):
    """A canonical relation identity exposed in one schema reference."""

    kind: Literal["relation"] = "relation"
    relation_id: RelationId


class ModeloWorkspaceParameterReferenceV1(_WorkspaceModel):
    """A canonical parameter identity exposed in one schema reference."""

    kind: Literal["parameter"] = "parameter"
    parameter_id: ParameterId


class ModeloWorkspaceExportFieldReferenceV1(_WorkspaceModel):
    """A canonical export-field identity exposed in one schema reference."""

    kind: Literal["export_field"] = "export_field"
    export_field_id: ExportFieldId


class ModeloWorkspaceContinuityReferenceV1(_WorkspaceModel):
    """A canonical cross-revision casilla continuity identity."""

    kind: Literal["continuity"] = "continuity"
    continuidad_id: ContinuidadId


class ModeloWorkspaceFormulaCasillaOperandReferenceV1(_WorkspaceModel):
    """A formula operand that addresses a canonical casilla."""

    kind: Literal["formula_operand_casilla"] = "formula_operand_casilla"
    formula_id: FormulaId
    casilla_id: CasillaId


class ModeloWorkspaceFormulaBindingOperandReferenceV1(_WorkspaceModel):
    """A formula operand that reads a canonical decimal binding."""

    kind: Literal["formula_operand_binding"] = "formula_operand_binding"
    formula_id: FormulaId
    binding_id: BindingId


class ModeloWorkspaceFormulaDateBindingOperandReferenceV1(_WorkspaceModel):
    """A formula operand that reads a canonical date binding."""

    kind: Literal["formula_operand_date_binding"] = "formula_operand_date_binding"
    formula_id: FormulaId
    binding_id: BindingId


class ModeloWorkspaceFormulaParameterOperandReferenceV1(_WorkspaceModel):
    """A formula operand that addresses a canonical parameter."""

    kind: Literal["formula_operand_parameter"] = "formula_operand_parameter"
    formula_id: FormulaId
    parameter_id: ParameterId


class ModeloWorkspaceFormulaRelationOperandReferenceV1(_WorkspaceModel):
    """A formula operand that addresses a canonical relation."""

    kind: Literal["formula_operand_relation"] = "formula_operand_relation"
    formula_id: FormulaId
    relation_id: RelationId


class ModeloWorkspaceFormulaLiteralOperandReferenceV1(_WorkspaceModel):
    """A formula literal arm without exporting its formula compiler node."""

    kind: Literal["formula_operand_literal"] = "formula_operand_literal"
    formula_id: FormulaId


class ModeloWorkspaceFormulaDispatchOperandReferenceV1(_WorkspaceModel):
    """A dispatch-table formula operand retaining its parameter identities."""

    kind: Literal["formula_operand_dispatch"] = "formula_operand_dispatch"
    formula_id: FormulaId
    parameter_ids: Annotated[tuple[ParameterId, ...], Field(min_length=1, max_length=_MAX_SCHEMA_RELATIONSHIPS)]

    @field_validator("parameter_ids")
    @classmethod
    def _require_unique_formula_dispatch_parameters(cls, value: tuple[ParameterId, ...]) -> tuple[ParameterId, ...]:
        if not value or len(set(value)) != len(value):
            raise ValueError("workspace formula dispatch parameters must be non-empty and unique")
        return tuple(sorted(value))


type ModeloWorkspaceFormulaOperandReferenceV1 = Annotated[
    ModeloWorkspaceFormulaCasillaOperandReferenceV1
    | ModeloWorkspaceFormulaBindingOperandReferenceV1
    | ModeloWorkspaceFormulaDateBindingOperandReferenceV1
    | ModeloWorkspaceFormulaParameterOperandReferenceV1
    | ModeloWorkspaceFormulaRelationOperandReferenceV1
    | ModeloWorkspaceFormulaLiteralOperandReferenceV1
    | ModeloWorkspaceFormulaDispatchOperandReferenceV1,
    Field(discriminator="kind"),
]


class ModeloWorkspaceRelationSourceEndpointReferenceV1(_WorkspaceModel):
    """The canonical source-casilla endpoint of one registry relation."""

    kind: Literal["relation_source_casilla"] = "relation_source_casilla"
    relation_id: RelationId
    casilla_id: CasillaId


class ModeloWorkspaceRelationTargetEndpointReferenceV1(_WorkspaceModel):
    """The canonical target-binding endpoint of one registry relation."""

    kind: Literal["relation_target_binding"] = "relation_target_binding"
    relation_id: RelationId
    binding_id: BindingId


type ModeloWorkspaceRelationEndpointReferenceV1 = Annotated[
    ModeloWorkspaceRelationSourceEndpointReferenceV1 | ModeloWorkspaceRelationTargetEndpointReferenceV1,
    Field(discriminator="kind"),
]


class ModeloWorkspaceApplicabilityReferenceV1(_WorkspaceModel):
    """A canonical registry applicability-rule identity."""

    kind: Literal["applicability"] = "applicability"
    applicability_rule_id: ApplicabilityRuleId


class ModeloWorkspaceConstraintReferenceV1(_WorkspaceModel):
    """The casilla identity to which its canonical registry constraints apply."""

    kind: Literal["constraint"] = "constraint"
    casilla_id: CasillaId


class ModeloWorkspaceExportExposureReferenceV1(_WorkspaceModel):
    """One canonical casilla-to-export-field exposure without layout internals."""

    kind: Literal["export_exposure"] = "export_exposure"
    casilla_id: CasillaId
    export_field_id: ExportFieldId


type ModeloWorkspaceSchemaReferenceV1 = Annotated[
    ModeloWorkspaceCasillaReferenceV1
    | ModeloWorkspaceBindingReferenceV1
    | ModeloWorkspaceFormulaReferenceV1
    | ModeloWorkspaceRelationReferenceV1
    | ModeloWorkspaceParameterReferenceV1
    | ModeloWorkspaceExportFieldReferenceV1
    | ModeloWorkspaceContinuityReferenceV1
    | ModeloWorkspaceFormulaCasillaOperandReferenceV1
    | ModeloWorkspaceFormulaBindingOperandReferenceV1
    | ModeloWorkspaceFormulaDateBindingOperandReferenceV1
    | ModeloWorkspaceFormulaParameterOperandReferenceV1
    | ModeloWorkspaceFormulaRelationOperandReferenceV1
    | ModeloWorkspaceFormulaLiteralOperandReferenceV1
    | ModeloWorkspaceFormulaDispatchOperandReferenceV1
    | ModeloWorkspaceRelationSourceEndpointReferenceV1
    | ModeloWorkspaceRelationTargetEndpointReferenceV1
    | ModeloWorkspaceApplicabilityReferenceV1
    | ModeloWorkspaceConstraintReferenceV1
    | ModeloWorkspaceExportExposureReferenceV1,
    Field(discriminator="kind"),
]


class ModeloWorkspaceSchemaRecordV1(_WorkspaceModel):
    """Explanatory schema row using canonical registry identities, never grammar objects."""

    reference: ModeloWorkspaceSchemaReferenceV1
    record_family: Annotated[tuple[_BoundedText, ...], Field(max_length=_MAX_SCHEMA_RECORD_FAMILY_DEPTH)]
    section_path: Annotated[tuple[_BoundedText, ...], Field(max_length=_MAX_SCHEMA_RECORD_FAMILY_DEPTH)] = ()
    """The modelo's OWN declared section path for this record, when it has one.

    Distinct from ``record_family``, which labels which registry family the
    record belongs to. Only casillas carry a declared section: a binding,
    formula, relation or parameter is not placed anywhere in the modelo's
    printed structure, so an empty tuple there means "this kind of record has
    no section", not "the section was dropped".
    """
    data_type: _BoundedCode
    label: ModeloWorkspaceRecordLabelV1
    classification: ModeloWorkspaceSchemaClassification
    family_disposition: RegistrySchemaFamilyDisposition
    legal_refs: _BoundedRefList[LegalRefId] | None = ()
    """``None`` means this admission's producer never carries legal grounding
    for this reference kind; an empty tuple means it does, and none is
    declared. The two must never collapse into one "nothing here" shape --
    a bare empty tuple over legal grounding reads as "the law requires
    nothing," while ``None`` honestly reads as "not measured"."""
    source_refs: _BoundedRefList[SourceRefId] = ()
    continuity: Annotated[
        tuple[ModeloWorkspaceContinuityReferenceV1, ...], Field(max_length=_MAX_SCHEMA_RELATIONSHIPS)
    ] = ()
    applicability: Annotated[
        tuple[ModeloWorkspaceApplicabilityReferenceV1, ...], Field(max_length=_MAX_SCHEMA_RELATIONSHIPS)
    ] = ()
    constraints: (
        Annotated[tuple[ModeloWorkspaceConstraintReferenceV1, ...], Field(max_length=_MAX_SCHEMA_RELATIONSHIPS)] | None
    ) = ()
    """``None`` means this admission's producer never carries constraint
    declarations for this reference kind (the same distinction as
    ``legal_refs``): a static inspection has no ``CasillaDefinition`` to
    check, so it cannot honestly claim "no constraints declared" the way an
    empty tuple would."""
    formula_operands: Annotated[
        tuple[ModeloWorkspaceFormulaOperandReferenceV1, ...], Field(max_length=_MAX_SCHEMA_RELATIONSHIPS)
    ] = ()
    relation_endpoints: Annotated[
        tuple[ModeloWorkspaceRelationEndpointReferenceV1, ...], Field(max_length=_MAX_SCHEMA_RELATIONSHIPS)
    ] = ()
    export_exposure: Annotated[
        tuple[ModeloWorkspaceExportExposureReferenceV1, ...], Field(max_length=_MAX_SCHEMA_RELATIONSHIPS)
    ] = ()


class ModeloWorkspaceFamilyDispositionV1(_WorkspaceModel):
    """One named registry schema-family disposition with its safe evidence references."""

    family: _BoundedCode
    disposition: RegistrySchemaFamilyDisposition
    legal_refs: _BoundedRefList[LegalRefId] = ()
    source_refs: _BoundedRefList[SourceRefId] = ()


class ModeloWorkspaceProvenanceRecordV1(_WorkspaceModel):
    """One selected canonical resolver lineage row, optionally for a workspace subject.

    ``subject`` is ``None`` when the underlying ``calculation_source``
    (``CalculationSourceRef``) carries no linked casilla identity --
    ``source_casilla_ids`` empty, which is the common case today since most
    resolver call sites do not yet populate it. This is the same
    None-vs-()-shaped distinction drawn by a schema record's optional
    grounding fields: ``None`` means "this producer never carries this data
    for this row", never a silently dropped record. An unlinked ref still
    produces exactly one record (never zero), so an audit reader sees every
    contributing source and can distinguish "unattributed" from "record
    never surfaced".
    """

    subject: ModeloWorkspaceSchemaReferenceV1 | None
    calculation_source: CalculationSourceRef


class ModeloWorkspaceScalarMaterializationV1(_WorkspaceModel):
    """One scalar materialization keyed by the canonical casilla identity."""

    casilla_id: CasillaId
    value: ModeloScalar


class ModeloWorkspaceRepeatedRowMaterializationV1(_WorkspaceModel):
    """One positive-index repeated binding row without flattening it into a casilla id."""

    binding_id: BindingId
    row_index: Annotated[int, Field(ge=1)]
    values: Annotated[
        tuple[ModeloWorkspaceScalarMaterializationV1, ...], Field(min_length=1, max_length=_MAX_REPEATED_ROW_VALUES)
    ]


class ModeloWorkspaceScalarMaterializationRecordV1(_WorkspaceModel):
    """One scalar materialization arm with no nullable sibling payload."""

    kind: Literal["scalar"] = "scalar"
    scalar: ModeloWorkspaceScalarMaterializationV1


class ModeloWorkspaceRepeatedRowMaterializationRecordV1(_WorkspaceModel):
    """One repeated-row materialization arm with no nullable sibling payload."""

    kind: Literal["repeated_row"] = "repeated_row"
    repeated_row: ModeloWorkspaceRepeatedRowMaterializationV1


type ModeloWorkspaceMaterializationRecordV1 = Annotated[
    ModeloWorkspaceScalarMaterializationRecordV1 | ModeloWorkspaceRepeatedRowMaterializationRecordV1,
    Field(discriminator="kind"),
]


class ModeloWorkspaceTextFactValueV1(_WorkspaceModel):
    """A bounded safe text fact, never a raw exception or localized command."""

    kind: Literal["text"] = "text"
    value: Annotated[str, Field(min_length=1, max_length=_MAX_SAFE_FACT_TEXT_LENGTH)]


class ModeloWorkspaceCountFactValueV1(_WorkspaceModel):
    """A non-negative count fact with no text-length constraint."""

    kind: Literal["count"] = "count"
    value: NonNegativeInt


class ModeloWorkspaceFlagFactValueV1(_WorkspaceModel):
    """A closed Boolean fact with no string validation applied."""

    kind: Literal["flag"] = "flag"
    value: bool


type ModeloWorkspaceEvidenceFactValueV1 = Annotated[
    ModeloWorkspaceTextFactValueV1 | ModeloWorkspaceCountFactValueV1 | ModeloWorkspaceFlagFactValueV1,
    Field(discriminator="kind"),
]


class ModeloWorkspaceEvidenceFactV1(_WorkspaceModel):
    """A bounded non-financial fact for capability or refusal explanation."""

    name: _BoundedCode
    value: ModeloWorkspaceEvidenceFactValueV1


class ModeloWorkspaceLegalEvidenceReferenceV1(_WorkspaceModel):
    """A canonical legal-reference identity used as safe evidence."""

    kind: Literal["legal"] = "legal"
    legal_ref_id: LegalRefId


class ModeloWorkspaceSourceEvidenceReferenceV1(_WorkspaceModel):
    """A canonical source-reference identity used as safe evidence."""

    kind: Literal["source"] = "source"
    source_ref_id: SourceRefId


type ModeloWorkspaceEvidenceReferenceV1 = Annotated[
    ModeloWorkspaceLegalEvidenceReferenceV1 | ModeloWorkspaceSourceEvidenceReferenceV1,
    Field(discriminator="kind"),
]


class ModeloWorkspaceBaselineV1(_WorkspaceModel):
    """Opaque read consistency identity; this is not mutation authority or approval.

    COMPARABLE BY EQUALITY, deliberately. Every field is a content digest or a
    resolved coordinate: there is no timestamp and no minted id, so two
    baselines computed over the same state ARE equal, and the codebase relies
    on that to keep a cursor, a facet and a projection pinned to one read.

    Do not carry this property to :class:`ModeloEditBaselineV1`. That one is a
    time-bounded admission authority carrying ``issued_at``, ``expires_at`` and
    ``baseline_id``, so two admissions of an unchanged tree are never equal and
    record equality there can only ever report "different". The two are
    compared in OPPOSITE ways and share a name; an editor session once answered
    staleness by comparing edit baselines as if they were these, and its stale
    signal was permanently on.
    """

    contract_version: Literal[1] = 1
    token: ContentDigest
    contributor_stamp_digest: ContentDigest
    contributor_epoch_digest: ContentDigest
    target: ModeloWorkspaceResolvedTargetV1
    selected_revision_id: RevisionId
    schema_identity: ModeloWorkspaceSchemaIdentityV1
    locale_catalogue_digest: ContentDigest

    @model_validator(mode="after")
    def _require_exact_baseline_coordinate(self) -> ModeloWorkspaceBaselineV1:
        if self.selected_revision_id != self.target.law_selected_revision_id:
            raise ValueError("workspace baseline selected_revision_id must equal the target law-selected revision")
        return self


class ModeloWorkspaceContributorIdentityV1(_WorkspaceModel):
    """One producer identity captured in a baseline-pinned Workspace read."""

    owner: _BoundedCode
    producer: _BoundedCode


def _require_unique_contributor_identities(
    value: tuple[ModeloWorkspaceContributorIdentityV1, ...],
) -> tuple[ModeloWorkspaceContributorIdentityV1, ...]:
    """Keep each pinned contributor tuple deterministic without declaring its port contract."""
    identities = tuple((contributor.owner, contributor.producer) for contributor in value)
    if not identities or len(set(identities)) != len(identities):
        raise ValueError("workspace contributors must be non-empty and unique")
    return tuple(sorted(value, key=lambda contributor: (contributor.owner, contributor.producer)))


class ModeloWorkspaceCursorV1(_WorkspaceModel):
    """One opaque continuation bound to the complete Workspace read coordinate."""

    contract_version: Literal[1] = 1
    baseline: ModeloWorkspaceBaselineV1
    selected_revision_id: RevisionId
    schema_identity: ModeloWorkspaceSchemaIdentityV1
    facet: ModeloWorkspaceFacetName
    contributor_epoch_digest: ContentDigest
    continuation: _BoundedText

    @model_validator(mode="after")
    def _require_exact_cursor_coordinate(self) -> ModeloWorkspaceCursorV1:
        if self.baseline.contract_version != self.contract_version:
            raise ValueError("workspace cursor baseline must retain the V1 contract version")
        if self.baseline.selected_revision_id != self.selected_revision_id:
            raise ValueError("workspace cursor baseline must retain the selected revision")
        if self.baseline.schema_identity != self.schema_identity:
            raise ValueError("workspace cursor baseline must retain the schema identity and fingerprint")
        if self.baseline.contributor_epoch_digest != self.contributor_epoch_digest:
            raise ValueError("workspace cursor baseline must retain the contributor epoch digest")
        return self


class ModeloWorkspaceCapabilityV1(_WorkspaceModel):
    """One non-inferred capability answer copied from its canonical producer."""

    capability: ModeloWorkspaceCapabilityName
    disposition: ModeloWorkspaceCapabilityDisposition
    target: ModeloWorkspaceResolvedTargetV1
    selected_revision_id: RevisionId
    producer_owner: _BoundedCode
    producer: _BoundedCode
    evidence: Annotated[
        tuple[ModeloWorkspaceEvidenceReferenceV1, ...], Field(max_length=_MAX_SCHEMA_EVIDENCE_REFERENCES)
    ] = ()
    facts: Annotated[tuple[ModeloWorkspaceEvidenceFactV1, ...], Field(max_length=_MAX_SAFE_FACTS)] = ()
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

    @model_validator(mode="after")
    def _require_exact_capability_coordinate(self) -> ModeloWorkspaceCapabilityV1:
        if self.selected_revision_id != self.target.law_selected_revision_id:
            raise ValueError("workspace capability selected_revision_id must equal the target law-selected revision")
        return self


def _complete_capability_denominator(
    value: tuple[ModeloWorkspaceCapabilityV1, ...],
) -> tuple[ModeloWorkspaceCapabilityV1, ...]:
    """Keep both successful admission arms on the one closed capability inventory."""
    capability_set = {capability.capability for capability in value}
    if capability_set != set(ModeloWorkspaceCapabilityName) or len(value) != len(capability_set):
        raise ValueError("workspace capability rows must cover each V1 capability exactly once")
    return tuple(sorted(value, key=lambda capability: capability.capability.value))


class ModeloWorkspaceBoundedFacetV1[RecordT](_WorkspaceModel):
    """A baseline-pinned, finite page from one workspace facet."""

    contract_version: Literal[1] = 1
    selected_revision_id: RevisionId
    schema_identity: ModeloWorkspaceSchemaIdentityV1
    baseline: ModeloWorkspaceBaselineV1
    contributor_epoch_digest: ContentDigest
    contributors: Annotated[
        tuple[ModeloWorkspaceContributorIdentityV1, ...], Field(min_length=1, max_length=_MAX_CONTRIBUTORS)
    ]
    facet: ModeloWorkspaceFacetName
    disposition: ModeloWorkspaceCapabilityDisposition
    records: Annotated[tuple[RecordT, ...], Field(max_length=_MAX_FACET_PAGE_SIZE)] = ()
    page_size: Annotated[int, Field(ge=1, le=_MAX_FACET_PAGE_SIZE)]
    next_cursor: ModeloWorkspaceCursorV1 | None = None
    has_more: bool = False

    @field_validator("contributors")
    @classmethod
    def _require_unique_facet_contributors(
        cls, value: tuple[ModeloWorkspaceContributorIdentityV1, ...]
    ) -> tuple[ModeloWorkspaceContributorIdentityV1, ...]:
        return _require_unique_contributor_identities(value)

    @model_validator(mode="after")
    def _validate_page(self) -> ModeloWorkspaceBoundedFacetV1[RecordT]:
        if self.baseline.contract_version != self.contract_version:
            raise ValueError("workspace facet baseline must retain the V1 contract version")
        if self.baseline.selected_revision_id != self.selected_revision_id:
            raise ValueError("workspace facet baseline must retain the selected revision")
        if self.baseline.schema_identity != self.schema_identity:
            raise ValueError("workspace facet baseline must retain the schema identity and fingerprint")
        if self.baseline.contributor_epoch_digest != self.contributor_epoch_digest:
            raise ValueError("workspace facet baseline must retain the contributor epoch digest")
        if len(self.records) > self.page_size:
            raise ValueError("workspace facet cannot contain more records than its page_size")
        if self.has_more != (self.next_cursor is not None):
            raise ValueError("workspace facet has_more must agree with next_cursor")
        if self.next_cursor is not None and (
            self.next_cursor.contract_version != self.contract_version
            or self.next_cursor.baseline != self.baseline
            or self.next_cursor.selected_revision_id != self.selected_revision_id
            or self.next_cursor.schema_identity != self.schema_identity
            or self.next_cursor.facet is not self.facet
            or self.next_cursor.contributor_epoch_digest != self.contributor_epoch_digest
        ):
            raise ValueError("workspace cursor must retain the complete facet consistency coordinate")
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


class ModeloWorkspaceEvidenceHorizonV1(_WorkspaceModel):
    """The safe evidence coordinates on which the admitted projection rests."""

    source_refs: _BoundedRefList[SourceRefId]
    evidence_digest: ContentDigest


class ModeloWorkspaceProfileRequirementV1(_WorkspaceModel):
    """One bounded profile requirement from the canonical readiness axis."""

    selector: Annotated[str, Field(min_length=1, max_length=128)]
    section_key: Annotated[str, Field(min_length=1, max_length=64)]
    field_key: Annotated[str, Field(min_length=1, max_length=128)]
    label: _BoundedLocalizedText
    legal_refs: Annotated[tuple[LegalRefId, ...], Field(max_length=_MAX_SCHEMA_EVIDENCE_REFERENCES)] = ()
    modelos: Annotated[tuple[ModeloCode, ...], Field(max_length=_MAX_SCHEMA_EVIDENCE_REFERENCES)] = ()


class ModeloWorkspaceBindingRequirementV1(_WorkspaceModel):
    """One missing canonical calculation-binding requirement from readiness."""

    binding_id: BindingId
    source: BindingSourceKind
    input_channel: Annotated[str, Field(min_length=1, max_length=16)]


class ModeloWorkspaceLedgerTransactionSubjectV1(_WorkspaceModel):
    """A ledger-preflight issue attached to one identified transaction."""

    kind: Literal["transaction"] = "transaction"
    transaction_id: TransactionId


class ModeloWorkspaceLedgerPeriodSubjectV1(_WorkspaceModel):
    """A ledger-preflight issue that is not tied to any one transaction.

    :class:`~cadrumo.application.ledger.preflight.LedgerPreflightIssue`
    carries ``transaction_id: TransactionId | Literal["__period__"]`` for a
    condition scoped to the whole period rather than one row (an unsupported
    period with no date span, per ``_unsupported_period_issue``). Collapsing
    that case into a required ``TransactionId`` would either drop the issue
    (silent under-declaration on exactly the axis a taxpayer consults before
    filing) or pin it to a fabricated transaction that has nothing to do with
    it; this type represents the period-level case as itself.
    """

    kind: Literal["period"] = "period"


type ModeloWorkspaceLedgerIssueSubjectV1 = Annotated[
    ModeloWorkspaceLedgerTransactionSubjectV1 | ModeloWorkspaceLedgerPeriodSubjectV1,
    Field(discriminator="kind"),
]


class ModeloWorkspaceLedgerIssueV1(_WorkspaceModel):
    """One bounded ledger-preflight issue preserving its canonical typed axis."""

    subject: ModeloWorkspaceLedgerIssueSubjectV1
    reason: LedgerPreflightIssueReason
    detail: _BoundedLocalizedText


class ModeloWorkspaceReadinessV1(_WorkspaceModel):
    """Typed, axis-preserving Workspace projection of canonical Modelo readiness."""

    profile_id: ProfileId
    modelo: ModeloCode
    revision_id: RevisionId
    filing_year: FilingYear
    period: Period
    missing: Annotated[tuple[ModeloWorkspaceProfileRequirementV1, ...], Field(max_length=128)] = ()
    profile_ready: bool
    per_operation_requirements_assessed: bool
    profile_refusal: Annotated[str, Field(max_length=512)] = ""
    registry_ready: bool = True
    registry_refusal: Annotated[str, Field(max_length=512)] = ""
    binding_ready: bool = True
    missing_bindings: Annotated[tuple[ModeloWorkspaceBindingRequirementV1, ...], Field(max_length=128)] = ()
    ledger_preflight_required: bool = False
    ledger_ready: bool | None = None
    ledger_period: Period | None = None
    ledger_checked_transaction_count: Annotated[int, Field(ge=0)] = 0
    ledger_issues: Annotated[tuple[ModeloWorkspaceLedgerIssueV1, ...], Field(max_length=128)] = ()
    ready: bool

    @model_validator(mode="after")
    def _require_period_to_match_readiness_year(self) -> ModeloWorkspaceReadinessV1:
        if self.period.filing_year != self.filing_year:
            raise ValueError("workspace readiness filing_year must match period.filing_year")
        return self


class ModeloWorkspaceSnapshotScopeV1(_WorkspaceModel):
    """The explicitly requested and declared grade for one snapshot admission.

    A third ``effective_grade`` field was retired here. The registry's
    own grade check (``_check_snapshot_authority_grade``) REFUSES a snapshot
    whose declared grade is below the requested one; it never truncates and
    never returns a snapshot built at some lesser grade. Under every path
    that exists, an "effective" grade could therefore only ever equal
    ``declared_grade`` -- a field that can only restate its neighbour asserts
    a narrowing step the system never performs, and nothing in the codebase
    ever constructed or read it. Retired outright rather than migrated
    (``COMPATIBILITY_REGIME`` is ``PRE_RELEASE``; nothing persists this
    class). Reintroduction condition: if a future revision-selection path
    ever TRUNCATES instead of refusing -- admitting a snapshot at a grade
    below the one requested, rather than raising -- then an effective grade
    becomes a real, distinct fact and the field earns its place back with
    that defined meaning.
    """

    required_grade: RegistryAuthorityGrade
    declared_grade: RegistryAuthorityGrade
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
    family_dispositions: Annotated[
        tuple[ModeloWorkspaceFamilyDispositionV1, ...], Field(max_length=_MAX_SCHEMA_RELATIONSHIPS)
    ]
    contributors: Annotated[
        tuple[ModeloWorkspaceContributorIdentityV1, ...], Field(min_length=1, max_length=_MAX_CONTRIBUTORS)
    ]
    baseline: ModeloWorkspaceBaselineV1
    schema_facet: ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1]
    materialization_facet: ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceMaterializationRecordV1] | None = None
    provenance_facet: ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceProvenanceRecordV1] | None = None
    work_review: ModeloWorkspaceWorkReviewFacetV1
    readiness: ModeloWorkspaceReadinessV1 | None = None
    registry_closure_limbs: Annotated[tuple[RegistryClosureLimb, ...], Field(max_length=_MAX_CLOSURE_LIMBS)] = ()
    capabilities: Annotated[
        tuple[ModeloWorkspaceCapabilityV1, ...],
        Field(min_length=len(ModeloWorkspaceCapabilityName), max_length=len(ModeloWorkspaceCapabilityName)),
    ]

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

    @field_validator("contributors")
    @classmethod
    def _require_unique_projection_contributors(
        cls, value: tuple[ModeloWorkspaceContributorIdentityV1, ...]
    ) -> tuple[ModeloWorkspaceContributorIdentityV1, ...]:
        return _require_unique_contributor_identities(value)

    @field_validator("registry_closure_limbs")
    @classmethod
    def _require_unique_closure_limb_names(
        cls, value: tuple[RegistryClosureLimb, ...]
    ) -> tuple[RegistryClosureLimb, ...]:
        if len({limb.name for limb in value}) != len(value):
            raise ValueError("workspace registry closure limbs must be unique")
        return tuple(sorted(value, key=lambda limb: limb.name))

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
        if self.schema_facet.contract_version != self.contract_version:
            raise ValueError("workspace schema facet must retain the V1 contract version")
        if self.schema_facet.selected_revision_id != self.target.law_selected_revision_id:
            raise ValueError("workspace schema facet must retain the law-selected revision")
        if self.schema_facet.schema_identity != self.schema_identity:
            raise ValueError("workspace schema facet must retain the schema identity and fingerprint")
        if self.schema_facet.baseline != self.baseline:
            raise ValueError("workspace schema facet must retain the projection baseline")
        if self.schema_facet.contributor_epoch_digest != self.baseline.contributor_epoch_digest:
            raise ValueError("workspace schema facet must retain the contributor epoch digest")
        if self.schema_facet.contributors != self.contributors:
            raise ValueError("workspace schema facet must retain the contributor tuple")
        for capability in self.capabilities:
            if (
                capability.target != self.target
                or capability.selected_revision_id != self.target.law_selected_revision_id
            ):
                raise ValueError("workspace capabilities must retain the exact target and revision coordinate")
        if self.readiness is not None and (
            self.readiness.modelo != self.target.modelo
            or self.readiness.revision_id != self.target.law_selected_revision_id
            or self.readiness.filing_year != self.target.filing_year
            or self.readiness.period != self.target.period
        ):
            raise ValueError("workspace readiness must retain the exact target and revision coordinate")
        if any(
            limb.modelo != self.target.modelo or limb.revision != self.target.law_selected_revision_id
            for limb in self.registry_closure_limbs
        ):
            raise ValueError("workspace registry closure limbs must retain the exact target and revision coordinate")
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
        for facet in (self.materialization_facet, self.provenance_facet):
            if (
                facet.contract_version != self.contract_version
                or facet.selected_revision_id != self.target.law_selected_revision_id
                or facet.schema_identity != self.schema_identity
                or facet.baseline != self.baseline
                or facet.contributor_epoch_digest != self.baseline.contributor_epoch_digest
                or facet.contributors != self.contributors
            ):
                raise ValueError("graded workspace facets must retain the root consistency coordinates")
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


class ModeloWorkspaceRevisionMismatchRefusalV1(_WorkspaceModel):
    """A two-axis refusal that retains every independently evaluated mismatch."""

    kind: Literal["revision_assertion_mismatch"] = "revision_assertion_mismatch"
    contract_version: Literal[1] = 1
    requested_target: ModeloWorkspaceTargetV1
    selected_target: ModeloWorkspaceResolvedTargetV1
    requested_revision_assertion: ModeloWorkspaceRevisionAssertionV1
    stored_revision_assertion: ModeloWorkspaceRevisionAssertionV1
    mismatching_sources: Annotated[
        tuple[ModeloWorkspaceRevisionAssertionSource, ...],
        Field(min_length=1, max_length=2),
    ]
    responsible_owner: _BoundedCode
    reconsideration_condition: _BoundedText
    recovery_action: ActionReference | None = None

    @model_validator(mode="after")
    def _require_exact_mismatch_axes(self) -> ModeloWorkspaceRevisionMismatchRefusalV1:
        axes = (
            self.requested_revision_assertion,
            self.stored_revision_assertion,
        )
        expected_sources = tuple(
            axis.source for axis in axes if axis.disposition is ModeloWorkspaceRevisionAssertionDisposition.MISMATCHED
        )
        if self.requested_revision_assertion.source is not ModeloWorkspaceRevisionAssertionSource.REQUESTED:
            raise ValueError("revision mismatch refusal must retain the requested assertion source")
        if self.stored_revision_assertion.source is not ModeloWorkspaceRevisionAssertionSource.STORED:
            raise ValueError("revision mismatch refusal must retain the stored assertion source")
        if len(set(self.mismatching_sources)) != len(self.mismatching_sources):
            raise ValueError("revision mismatch refusal sources must be unique")
        if self.mismatching_sources != expected_sources:
            raise ValueError("revision mismatch refusal must retain every and only mismatching source")
        if (
            self.selected_target.requested_revision_assertion != self.requested_revision_assertion
            or self.selected_target.stored_revision_assertion != self.stored_revision_assertion
        ):
            raise ValueError("revision mismatch refusal must retain the selected target assertion axes")
        return self


class ModeloWorkspaceDomainRefusalV1(_WorkspaceModel):
    """Typed post-parse refusal without a partial projection or raw exception."""

    kind: Literal["domain"] = "domain"
    contract_version: Literal[1] = 1
    code: ModeloWorkspaceRefusalCode
    boundary: Literal["admission", "capability", "consistency", "locale", "schema"]
    capability: ModeloWorkspaceCapabilityName | None = None
    requested_target: ModeloWorkspaceTargetV1
    selected_target: ModeloWorkspaceResolvedTargetV1 | None = None
    facts: Annotated[tuple[ModeloWorkspaceEvidenceFactV1, ...], Field(max_length=_MAX_SAFE_FACTS)] = ()
    evidence: _BoundedRefList[ModeloWorkspaceEvidenceReferenceV1] = ()
    responsible_owner: _BoundedCode
    reconsideration_condition: _BoundedText
    source_disposition: RegistrySchemaFamilyDisposition | None = None
    recovery_action: ActionReference | None = None

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

    @model_validator(mode="after")
    def _reject_untyped_revision_mismatch(self) -> ModeloWorkspaceDomainRefusalV1:
        if self.code is ModeloWorkspaceRefusalCode.REVISION_ASSERTION_MISMATCH:
            raise ValueError("revision assertion mismatches require the typed two-axis refusal")
        return self


type ModeloWorkspaceRefusalV1 = Annotated[
    ModeloWorkspaceVersionRefusalV1 | ModeloWorkspaceRevisionMismatchRefusalV1 | ModeloWorkspaceDomainRefusalV1,
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
    "ModeloWorkspaceApplicabilityReferenceV1",
    "ModeloWorkspaceBaselineV1",
    "ModeloWorkspaceBindingReferenceV1",
    "ModeloWorkspaceBindingRequirementV1",
    "ModeloWorkspaceBoundedFacetV1",
    "ModeloWorkspaceCapabilityDisposition",
    "ModeloWorkspaceCapabilityName",
    "ModeloWorkspaceCapabilityV1",
    "ModeloWorkspaceCasillaReferenceV1",
    "ModeloWorkspaceConstraintReferenceV1",
    "ModeloWorkspaceContinuityReferenceV1",
    "ModeloWorkspaceContributorIdentityV1",
    "ModeloWorkspaceCountFactValueV1",
    "ModeloWorkspaceCursorV1",
    "ModeloWorkspaceDomainRefusalV1",
    "ModeloWorkspaceEvidenceFactV1",
    "ModeloWorkspaceEvidenceFactValueV1",
    "ModeloWorkspaceEvidenceHorizonV1",
    "ModeloWorkspaceEvidenceReferenceV1",
    "ModeloWorkspaceExactWorkUnitTargetV1",
    "ModeloWorkspaceExportExposureReferenceV1",
    "ModeloWorkspaceExportFieldReferenceV1",
    "ModeloWorkspaceFacetName",
    "ModeloWorkspaceFamilyDispositionV1",
    "ModeloWorkspaceFlagFactValueV1",
    "ModeloWorkspaceFormulaBindingOperandReferenceV1",
    "ModeloWorkspaceFormulaCasillaOperandReferenceV1",
    "ModeloWorkspaceFormulaDateBindingOperandReferenceV1",
    "ModeloWorkspaceFormulaDispatchOperandReferenceV1",
    "ModeloWorkspaceFormulaLiteralOperandReferenceV1",
    "ModeloWorkspaceFormulaOperandReferenceV1",
    "ModeloWorkspaceFormulaParameterOperandReferenceV1",
    "ModeloWorkspaceFormulaReferenceV1",
    "ModeloWorkspaceFormulaRelationOperandReferenceV1",
    "ModeloWorkspaceGradedSnapshotAdmissionV1",
    "ModeloWorkspaceGradedSnapshotResultV1",
    "ModeloWorkspaceGradedSnapshotScopeV1",
    "ModeloWorkspaceLedgerIssueSubjectV1",
    "ModeloWorkspaceLedgerIssueV1",
    "ModeloWorkspaceLedgerPeriodSubjectV1",
    "ModeloWorkspaceLedgerTransactionSubjectV1",
    "ModeloWorkspaceLegalEvidenceReferenceV1",
    "ModeloWorkspaceLocaleDisposition",
    "ModeloWorkspaceLocaleSummaryV1",
    "ModeloWorkspaceLocalizedTextV1",
    "ModeloWorkspaceMaterializationRecordV1",
    "ModeloWorkspaceParameterReferenceV1",
    "ModeloWorkspaceProfileRequirementV1",
    "ModeloWorkspaceProjectionAdmissionV1",
    "ModeloWorkspaceProjectionV1",
    "ModeloWorkspaceProvenanceRecordV1",
    "ModeloWorkspaceReadinessV1",
    "ModeloWorkspaceRecordLabelV1",
    "ModeloWorkspaceRefreshTargetV1",
    "ModeloWorkspaceRefusalCode",
    "ModeloWorkspaceRefusalV1",
    "ModeloWorkspaceRefusedResultV1",
    "ModeloWorkspaceRelationEndpointReferenceV1",
    "ModeloWorkspaceRelationReferenceV1",
    "ModeloWorkspaceRelationSourceEndpointReferenceV1",
    "ModeloWorkspaceRelationTargetEndpointReferenceV1",
    "ModeloWorkspaceRepeatedRowMaterializationRecordV1",
    "ModeloWorkspaceRepeatedRowMaterializationV1",
    "ModeloWorkspaceRequestV1",
    "ModeloWorkspaceResolvedTargetV1",
    "ModeloWorkspaceResultV1",
    "ModeloWorkspaceRevisionAssertionDisposition",
    "ModeloWorkspaceRevisionAssertionSource",
    "ModeloWorkspaceRevisionAssertionV1",
    "ModeloWorkspaceRevisionMismatchRefusalV1",
    "ModeloWorkspaceScalarMaterializationRecordV1",
    "ModeloWorkspaceScalarMaterializationV1",
    "ModeloWorkspaceSchemaClassification",
    "ModeloWorkspaceSchemaIdentityV1",
    "ModeloWorkspaceSchemaRecordV1",
    "ModeloWorkspaceSchemaReferenceV1",
    "ModeloWorkspaceSnapshotScopeV1",
    "ModeloWorkspaceSourceEvidenceReferenceV1",
    "ModeloWorkspaceStaticInspectionAdmissionV1",
    "ModeloWorkspaceStaticInspectionResultV1",
    "ModeloWorkspaceStaticInspectionScopeV1",
    "ModeloWorkspaceTargetV1",
    "ModeloWorkspaceTechnicalLabelV1",
    "ModeloWorkspaceTextFactValueV1",
    "ModeloWorkspaceVersionHeader",
    "ModeloWorkspaceVersionRefusalV1",
    "ModeloWorkspaceVisibleFilingTargetV1",
    "ModeloWorkspaceWorkReviewFacetV1",
]
