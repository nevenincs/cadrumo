"""Strict schema authority for AEAT registry definitions."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from ._ids import (
    ApplicationLinkId,
    BindingId,
    CasillaId,
    ConstructId,
    CrossReferenceId,
    DeadlineWindowId,
    DependencyClassificationId,
    ExportFieldId,
    ExportLayoutId,
    ExtractionProfileId,
    FormulaId,
    LegalRefId,
    ModeloId,
    ParameterId,
    RecordId,
    RelationId,
    RevisionId,
    SourceRefId,
    SupportRemovalDecisionId,
    VerificationExpectationId,
    WorkbookParityRefId,
)


def _coerce_decimal(value: Any) -> Any:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool | float):
        raise ValueError("decimal values must not be booleans or floats")
    if isinstance(value, int | str):
        return Decimal(value)
    return value


DecimalValue = Annotated[Decimal, BeforeValidator(_coerce_decimal)]

ReviewStatus = Literal["reviewed", "provisional", "rejected"]
DateAxis = Literal["filing_period", "devengo_date", "transaction_date", "invoice_date", "submission_date"]
EvidenceTier = Literal[
    "legal_authority",
    "official_source_guidance",
    "executable_parity_evidence",
    "layout_authority",
]
LegalRefs = Annotated[tuple[LegalRefId, ...], Field(min_length=1)]
SourceRefs = Annotated[tuple[SourceRefId, ...], Field(min_length=1)]
SourceCitationText = Annotated[tuple[str, ...], Field(min_length=1)]
FormulaOperator = Literal[
    "add",
    "subtract",
    "multiply",
    "divide",
    "percent",
    "less_than",
    "less_equal",
    "greater_than",
    "greater_equal",
    "equal",
    "sum",
    "min",
    "max",
    "clamp",
    "negate",
    "copy",
    "if_then_else",
    "lookup_parameter",
    "previous_period_value",
    "previous_period_sum",
    "cross_model_sum",
]


class RegistryModel(BaseModel):
    """Strict frozen base for registry schema objects."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class PeriodSelector(RegistryModel):
    years: tuple[int, ...] = ()
    year_from: int | None = None
    year_to: int | None = None
    periods: tuple[str, ...] = Field(min_length=1)

    @field_validator("periods")
    @classmethod
    def _periods_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("period_selector periods must be unique")
        return value

    @model_validator(mode="after")
    def _validate_year_selector(self) -> PeriodSelector:
        if self.years and self.year_from is not None:
            raise ValueError("period_selector must use either years or year_from/year_to")
        if not self.years and self.year_from is None:
            raise ValueError("period_selector must declare years or year_from")
        if len(set(self.years)) != len(self.years):
            raise ValueError("period_selector years must be unique")
        if self.year_to is not None and self.year_from is None:
            raise ValueError("period_selector year_to requires year_from")
        if self.year_from is not None and self.year_to is not None and self.year_to < self.year_from:
            raise ValueError("period_selector year_to must be on or after year_from")
        return self

    def includes_year(self, year: int) -> bool:
        """Return whether the selector covers a filing year."""

        if self.years:
            return year in self.years
        if self.year_from is None:
            return False
        return year >= self.year_from and (self.year_to is None or year <= self.year_to)


class TemporalApplicability(RegistryModel):
    date_axis: DateAxis
    valid_from: date
    valid_to: date | None = None
    period_selector: PeriodSelector | None = None

    @model_validator(mode="after")
    def _validate_window(self) -> TemporalApplicability:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to must be on or after valid_from")
        return self


class LegalReference(RegistryModel):
    id: LegalRefId
    evidence_tier: Literal["legal_authority"]
    authority: Literal["boe", "aeat", "eu", "autonomous_community", "other"]
    kind: Literal[
        "ley",
        "real_decreto",
        "real_decreto_ley",
        "orden",
        "reglamento",
        "directiva",
        "manual",
        "instruction",
    ]
    corpus_ref: str
    document_id: str
    article: str | None = None
    section: str | None = None
    permalink: str
    published_at: date | None = None
    effective_from: date
    effective_to: date | None = None
    consolidated_as_of: date | None = None
    review_status: ReviewStatus
    reviewed_at: date | None = None
    reviewed_by: str | None = None
    notes: str | None = None
    required_text: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_legal_reference(self) -> LegalReference:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("legal reference effective_to must be on or after effective_from")
        if self.review_status != "reviewed":
            raise ValueError(f"legal reference {self.id!r} is not reviewed")
        if any(not item.strip() for item in self.required_text):
            raise ValueError("legal reference required_text entries must be non-empty")
        if len(set(self.required_text)) != len(self.required_text):
            raise ValueError("legal reference required_text entries must be unique")
        return self


class SourceReference(RegistryModel):
    id: SourceRefId
    evidence_tier: EvidenceTier
    authority: Literal["aeat", "boe", "eu", "autonomous_community", "other"]
    kind: Literal["record_design", "manual_pdf", "instructions", "xsd", "dictionary", "form_spec"]
    corpus_path: str
    sha256: str = Field(min_length=64, max_length=64)
    bytes: int = Field(gt=0)
    retrieved_at: date
    published_at: date | None = None
    applies_from: date | None = None
    applies_to: date | None = None
    source_url: str
    review_status: ReviewStatus

    @model_validator(mode="after")
    def _validate_source_reference(self) -> SourceReference:
        if self.review_status != "reviewed":
            raise ValueError(f"source reference {self.id!r} is not reviewed")
        if self.applies_to is not None and self.applies_from is not None and self.applies_to < self.applies_from:
            raise ValueError("source reference applies_to must be on or after applies_from")
        if "\\" in self.corpus_path or self.corpus_path.startswith(("/", ".")):
            raise ValueError("source reference corpus_path must be repository-relative POSIX style")
        return self

    @field_validator("sha256")
    @classmethod
    def _sha256_lower_hex(cls, value: str) -> str:
        lowered = value.lower()
        if lowered != value or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("sha256 must be lowercase hexadecimal")
        return value


class SourceCitation(RegistryModel):
    source_ref: SourceRefId
    required_text: SourceCitationText

    @field_validator("required_text")
    @classmethod
    def _required_text_non_empty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise ValueError("source citation required_text entries must be non-empty")
        if len(set(value)) != len(value):
            raise ValueError("source citation required_text entries must be unique")
        return value


class ExtractionProfileDefinition(RegistryModel):
    id: ExtractionProfileId
    surface: Literal["borrador_pdf", "declaracion_pdf", "justificante_pdf", "export_record", "official_workbook"]
    artefact_kind: str
    accepted_artefact_kinds: tuple[
        Literal["submitted_file", "declaration_pdf", "justificante_pdf", "official_workbook"],
        ...,
    ] = Field(min_length=1)
    parser: str
    target_casillas: tuple[CasillaId, ...] = Field(min_length=1)
    confidence: Literal["strict", "review_required"]
    min_coverage: DecimalValue = Field(ge=Decimal("0"), le=Decimal("1"))
    failure_semantics: Literal["fail_hard"]
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("accepted_artefact_kinds", "target_casillas")
    @classmethod
    def _tuple_values_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("extraction profile tuple entries must be unique")
        return value


class LiveCrossReferenceDecision(RegistryModel):
    id: CrossReferenceId
    evidence_tier: EvidenceTier
    surface: Literal[
        "open_simulator",
        "integration_test_service",
        "public_read_surface",
        "authenticated_read_surface",
        "static_official_documentation",
    ]
    guard_policy_id: str
    allowed_hosts: tuple[str, ...] = ()
    allowed_methods: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = Field(min_length=1)
    synthetic_data_allowed: bool
    requires_authentication: bool
    requires_aeat_authorization: bool
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_cross_reference(self) -> LiveCrossReferenceDecision:
        if (
            self.surface in {"open_simulator", "integration_test_service"}
            and self.evidence_tier != "executable_parity_evidence"
        ):
            raise ValueError(f"cross-reference {self.id!r} live surface requires executable parity evidence")
        if self.surface in {"public_read_surface", "authenticated_read_surface"} and (
            self.evidence_tier == "executable_parity_evidence"
        ):
            raise ValueError(f"cross-reference {self.id!r} read surface is observation evidence, not parity")
        if self.surface == "static_official_documentation" and self.evidence_tier == "executable_parity_evidence":
            raise ValueError(f"cross-reference {self.id!r} static documentation is not executable parity evidence")
        if (
            self.surface
            in {"open_simulator", "integration_test_service", "public_read_surface", "authenticated_read_surface"}
            and not self.allowed_hosts
        ):
            raise ValueError(f"cross-reference {self.id!r} must declare allowed_hosts")
        if self.surface == "open_simulator" and self.requires_authentication:
            raise ValueError(f"cross-reference {self.id!r} open simulator must not require authentication")
        if self.surface == "public_read_surface" and self.requires_authentication:
            raise ValueError(f"cross-reference {self.id!r} public read surface must not require authentication")
        if self.surface == "authenticated_read_surface" and not self.requires_authentication:
            raise ValueError(f"cross-reference {self.id!r} authenticated read surface must require authentication")
        if self.surface == "authenticated_read_surface" and not self.requires_aeat_authorization:
            raise ValueError(f"cross-reference {self.id!r} authenticated read surface must require authorization")
        if self.surface in {"public_read_surface", "authenticated_read_surface"} and self.synthetic_data_allowed:
            raise ValueError(f"cross-reference {self.id!r} read surface must not accept synthetic data")
        if self.surface == "static_official_documentation" and self.synthetic_data_allowed:
            raise ValueError(f"cross-reference {self.id!r} static documentation cannot accept synthetic data")
        for method in self.allowed_methods:
            if method.upper() != method:
                raise ValueError(f"cross-reference {self.id!r} allowed_methods must be uppercase")
            if self.surface in {"public_read_surface", "authenticated_read_surface"} and method not in {
                "GET",
                "HEAD",
                "OPTIONS",
            }:
                raise ValueError(f"cross-reference {self.id!r} read surface method {method!r} is not read-only")
        return self


class WorkbookParityReference(RegistryModel):
    id: WorkbookParityRefId
    workbook_source: SourceRefId
    fixture_id: str
    formula_coverage: Literal["formula_form", "static_layout", "record_design_layout", "unsupported_binary_xls"]
    runner_required: bool
    output_cells: Mapping[str, str] = Field(default_factory=dict)
    tolerance: DecimalValue = Decimal("0.00")
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_workbook_reference(self) -> WorkbookParityReference:
        if self.formula_coverage == "formula_form" and not self.runner_required:
            raise ValueError(f"workbook parity reference {self.id!r} formula coverage requires a runner")
        if self.formula_coverage != "formula_form" and self.runner_required:
            raise ValueError(f"workbook parity reference {self.id!r} runner requires formula coverage")
        if self.runner_required and not self.output_cells:
            raise ValueError(f"workbook parity reference {self.id!r} requires output_cells")
        if self.workbook_source not in self.source_refs:
            raise ValueError(f"workbook parity reference {self.id!r} source_refs must include workbook_source")
        return self


class VerificationExpectationDefinition(RegistryModel):
    id: VerificationExpectationId
    computed_casillas: tuple[CasillaId, ...]
    reconciliation_totals: Mapping[Literal["ingresar", "devolver"], CasillaId] = Field(default_factory=dict)
    tolerance: DecimalValue
    rounding: str
    min_coverage: DecimalValue = Field(ge=Decimal("0"), le=Decimal("1"))
    discrepancy_causes: tuple[
        Literal["extraction_unreliable", "unmodelled_rule", "rounding", "correctness_divergence"],
        ...,
    ] = Field(min_length=1)
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("computed_casillas")
    @classmethod
    def _computed_casillas_unique(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if len(set(value)) != len(value):
            raise ValueError("verification expectation computed_casillas must be unique")
        return value


class ApplicationLinkDefinition(RegistryModel):
    id: ApplicationLinkId
    surface: Literal[
        "calculation",
        "filing",
        "review",
        "verification",
        "export",
        "deadline",
        "portal",
        "extractor",
        "workflow",
    ]
    consumer: str
    requires_snapshot: Literal[True]
    legal_refs: LegalRefs
    source_refs: SourceRefs


class SupportRemovalDecisionDefinition(RegistryModel):
    id: SupportRemovalDecisionId
    subject_type: Literal[
        "export_layout",
        "extraction_profile",
        "filing_path",
        "application_link",
        "live_cross_reference",
        "workbook_parity_ref",
        "verification_expectation",
        "deadline_window",
        "filing_schedule",
    ]
    subject_id: str = Field(min_length=1, max_length=160)
    decision: Literal["remove_from_filing_grade"]
    reason: Literal[
        "missing_legal_authority",
        "missing_official_source",
        "unsafe_remote_state",
        "unsupported_official_format",
        "out_of_scope",
    ]
    evidence_note: str = Field(min_length=1, max_length=2048)
    legal_refs: LegalRefs
    source_refs: SourceRefs


class ConstructDefinition(RegistryModel):
    id: ConstructId
    title: str = Field(min_length=1, max_length=200)
    legal_refs: LegalRefs
    source_refs: SourceRefs
    casillas: tuple[CasillaId, ...] = ()
    formulas: tuple[FormulaId, ...] = ()
    parameters: tuple[ParameterId, ...] = ()
    bindings: tuple[BindingId, ...] = ()
    algorithm_providers: tuple[str, ...] = ()
    algorithm_bindings: tuple[str, ...] = ()
    relations: tuple[RelationId, ...] = ()
    export_layouts: tuple[ExportLayoutId, ...] = ()
    extraction_profiles: tuple[ExtractionProfileId, ...] = ()
    live_cross_references: tuple[CrossReferenceId, ...] = ()
    workbook_parity_refs: tuple[WorkbookParityRefId, ...] = ()
    verification_expectations: tuple[VerificationExpectationId, ...] = ()
    application_links: tuple[ApplicationLinkId, ...] = ()
    deadline_windows: tuple[DeadlineWindowId, ...] = ()
    filing_schedules: tuple[str, ...] = ()
    support_removal_decisions: tuple[SupportRemovalDecisionId, ...] = ()
    dependency_classifications: tuple[DependencyClassificationId, ...] = ()

    @field_validator(
        "casillas",
        "formulas",
        "parameters",
        "bindings",
        "algorithm_providers",
        "algorithm_bindings",
        "relations",
        "export_layouts",
        "extraction_profiles",
        "live_cross_references",
        "workbook_parity_refs",
        "verification_expectations",
        "application_links",
        "deadline_windows",
        "filing_schedules",
        "support_removal_decisions",
        "dependency_classifications",
    )
    @classmethod
    def _member_ids_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("construct member ids must be unique")
        return value

    @model_validator(mode="after")
    def _validate_membership(self) -> ConstructDefinition:
        member_groups = (
            self.casillas,
            self.formulas,
            self.parameters,
            self.bindings,
            self.algorithm_providers,
            self.algorithm_bindings,
            self.relations,
            self.export_layouts,
            self.extraction_profiles,
            self.live_cross_references,
            self.workbook_parity_refs,
            self.verification_expectations,
            self.application_links,
            self.deadline_windows,
            self.filing_schedules,
            self.support_removal_decisions,
            self.dependency_classifications,
        )
        if not any(member_groups):
            raise ValueError(f"construct {self.id!r} must declare at least one revision member")
        return self


class DependencyClassificationDefinition(RegistryModel):
    id: DependencyClassificationId
    source_modelo: ModeloId
    treatment: Literal["direct_annual_settlement", "factual_evidence", "non_dependency"]
    target_constructs: tuple[ConstructId, ...] = ()
    relation_refs: tuple[RelationId, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("target_constructs", "relation_refs")
    @classmethod
    def _tuple_values_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("dependency classification tuple entries must be unique")
        return value

    @model_validator(mode="after")
    def _validate_classification(self) -> DependencyClassificationDefinition:
        if self.treatment == "non_dependency":
            if self.target_constructs or self.relation_refs:
                raise ValueError(f"non-dependency classification {self.id!r} must not declare target members")
            return self
        if not self.target_constructs:
            raise ValueError(f"dependency classification {self.id!r} must declare target_constructs")
        if not self.relation_refs:
            raise ValueError(f"dependency classification {self.id!r} must declare relation_refs")
        return self


ProfileFactValue = bool | int | str


class ProfilePredicateDefinition(RegistryModel):
    field: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*$")
    op: Literal["equals", "not_equals"]
    value: ProfileFactValue
    explanation: str = Field(min_length=1)
    legal_refs: LegalRefs
    source_refs: SourceRefs


class DeadlineApplicabilityCondition(ProfilePredicateDefinition):
    pass


class DeadlineWindowDefinition(RegistryModel):
    id: DeadlineWindowId
    filing_year: int = Field(ge=1900, le=2999)
    period: str = Field(min_length=1)
    period_kind: Literal["monthly", "quarterly", "annual", "ad_hoc"]
    opens_on: date
    closes_on: date
    payment_cutoff_on: date | None = None
    applicability_condition_mode: Literal["all", "any"] = "all"
    applicability_conditions: tuple[DeadlineApplicabilityCondition, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_window(self) -> DeadlineWindowDefinition:
        if self.opens_on > self.closes_on:
            raise ValueError(f"deadline window {self.id!r} opens_on must not be after closes_on")
        if self.payment_cutoff_on is not None and self.payment_cutoff_on > self.closes_on:
            raise ValueError(f"deadline window {self.id!r} payment_cutoff_on must not be after closes_on")
        if self.applicability_condition_mode == "any" and not self.applicability_conditions:
            raise ValueError(f"deadline window {self.id!r} any-mode requires applicability conditions")
        return self


class FilingScheduleDefinition(RegistryModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    period_kind: Literal["monthly", "quarterly", "annual", "ad_hoc"]
    periods: tuple[str, ...] = Field(min_length=1)
    profile_condition_mode: Literal["all", "any"] = "all"
    profile_conditions: tuple[ProfilePredicateDefinition, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("periods")
    @classmethod
    def _periods_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("filing schedule periods must be unique")
        return value

    @model_validator(mode="after")
    def _validate_schedule(self) -> FilingScheduleDefinition:
        if self.profile_condition_mode == "any" and not self.profile_conditions:
            raise ValueError(f"filing schedule {self.id!r} any-mode requires profile conditions")
        return self


class FormulaExpression(RegistryModel):
    op: FormulaOperator | None = None
    args: tuple[FormulaExpression, ...] = ()
    casilla: CasillaId | None = None
    binding: BindingId | None = None
    parameter: ParameterId | None = None
    relation: RelationId | None = None
    literal: DecimalValue | None = None

    @model_validator(mode="after")
    def _validate_expression(self) -> FormulaExpression:
        populated_leaves = [
            self.casilla is not None,
            self.binding is not None,
            self.parameter is not None,
            self.relation is not None,
            self.literal is not None,
        ]
        if self.op is None:
            if self.args:
                raise ValueError("formula leaf must not declare args")
            if sum(populated_leaves) != 1:
                raise ValueError("formula leaf must declare exactly one source")
            return self
        if sum(populated_leaves):
            raise ValueError("formula operator must not declare leaf sources")
        if not self.args:
            raise ValueError("formula operator must declare args")
        return self


class DatedValue(RegistryModel):
    value: DecimalValue
    date_axis: DateAxis
    valid_from: date
    valid_to: date | None = None

    @model_validator(mode="after")
    def _validate_window(self) -> DatedValue:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("dated value valid_to must be on or after valid_from")
        return self


class ParameterDefinition(RegistryModel):
    id: ParameterId
    data_type: Literal["decimal", "money", "integer", "ratio", "text", "boolean"]
    unit: str
    values: tuple[DatedValue, ...] = Field(default_factory=tuple)
    legal_refs: LegalRefs
    source_refs: SourceRefs
    source_citations: tuple[SourceCitation, ...] = Field(default_factory=tuple)


class DataBindingDefinition(RegistryModel):
    id: BindingId
    source: Literal["ledger", "invoice", "rental", "vat", "category", "profile", "previous_filing", "manual_input"]
    selector: Mapping[str, str | int | DecimalValue | bool | tuple[str, ...]]
    aggregation: Mapping[str, str | int | DecimalValue | bool] | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs
    source_citations: tuple[SourceCitation, ...] = Field(default_factory=tuple)


class FormulaDefinition(RegistryModel):
    id: FormulaId
    target: CasillaId
    expression: FormulaExpression
    rounding: str | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs
    source_citations: tuple[SourceCitation, ...] = Field(default_factory=tuple)


class CasillaDefinition(RegistryModel):
    id: CasillaId
    number: str
    label: str
    section: tuple[str, ...]
    data_type: Literal["decimal", "money", "integer", "ratio", "text", "boolean"]
    required: bool
    input_kind: Literal["manual", "bound", "computed", "informational"]
    formula: FormulaId | None = None
    binding: BindingId | None = None
    validation_refs: tuple[str, ...] = ()
    export_refs: tuple[ExportFieldId, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_input_kind(self) -> CasillaDefinition:
        if self.input_kind == "computed" and self.formula is None:
            raise ValueError(f"computed casilla {self.id!r} must declare formula")
        if self.input_kind == "computed" and self.binding is not None:
            raise ValueError(f"computed casilla {self.id!r} must not declare binding")
        if self.input_kind == "bound" and self.binding is None:
            raise ValueError(f"bound casilla {self.id!r} must declare binding")
        if self.input_kind == "bound" and self.formula is not None:
            raise ValueError(f"bound casilla {self.id!r} must not declare formula")
        return self


class AlgorithmProviderDefinition(RegistryModel):
    id: str
    import_path: str
    callable_name: str
    deterministic: Literal[True]
    side_effect_free: Literal[True]
    allowed_input_schema: Mapping[str, str]
    output_schema: Mapping[str, str]
    trace_contract: str
    legal_refs: LegalRefs
    source_refs: SourceRefs


class AlgorithmBindingDefinition(RegistryModel):
    id: str
    provider: str
    target: CasillaId | str
    inputs: Mapping[str, BindingId | CasillaId | ParameterId | RelationId]
    outputs: Mapping[str, CasillaId | str]
    constants: tuple[ParameterId, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs


class RelationDefinition(RegistryModel):
    id: RelationId
    kind: Literal["previous_period", "annual_summary", "cross_model_output"]
    dependency_role: Literal[
        "profile_schedule",
        "periodic_to_annual_summary",
        "instalment_to_final_settlement",
        "direct_calculation",
        "factual_evidence",
    ]
    source_modelo: ModeloId
    source_revision_selector: Mapping[str, str | int]
    source_output: CasillaId | str
    target_binding: BindingId
    period_alignment: Mapping[str, str | int]
    source_periods: tuple[str, ...] = ()
    target_periods: tuple[str, ...] = ()
    aggregation: Mapping[str, str | int | DecimalValue | bool] | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("source_periods", "target_periods")
    @classmethod
    def _relation_periods_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("relation periods must be unique")
        return value

    @model_validator(mode="after")
    def _validate_dependency_role(self) -> RelationDefinition:
        if self.kind == "annual_summary" and self.dependency_role != "periodic_to_annual_summary":
            raise ValueError(f"annual summary relation {self.id!r} must use periodic_to_annual_summary role")
        return self


class ExportFieldDefinition(RegistryModel):
    id: ExportFieldId
    offset: int | None = Field(default=None, ge=0)
    length: int | None = Field(default=None, gt=0)
    kind: Literal["literal", "casilla", "binding", "computed", "draft", "filler", "header", "checksum"]
    casilla: CasillaId | None = None
    binding: BindingId | None = None
    literal: str | None = None
    header_key: str | None = None
    draft_attribute: Literal["modelo", "period", "profile_tax_id", "filing_year", "period_code"] | None = None
    computed_key: Literal["envelope_closing_tag"] | None = None
    data_type: Literal["text", "integer", "decimal", "money", "date", "boolean"]
    required: bool
    padding: Literal["left_zero", "left_space", "right_space", "none"]
    justification: Literal["left", "right", "none"]
    date_format: str | None = None
    signed: bool
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_field_kind(self) -> ExportFieldDefinition:
        if self.kind == "casilla" and self.casilla is None:
            raise ValueError(f"export field {self.id!r} must declare casilla")
        if self.kind == "binding" and self.binding is None:
            raise ValueError(f"export field {self.id!r} must declare binding")
        if self.kind == "literal" and self.literal is None:
            raise ValueError(f"export field {self.id!r} must declare literal")
        if self.kind == "header" and self.header_key is None:
            raise ValueError(f"export field {self.id!r} must declare header_key")
        if self.kind == "draft" and self.draft_attribute is None:
            raise ValueError(f"export field {self.id!r} must declare draft_attribute")
        if self.kind == "computed" and self.computed_key is None:
            raise ValueError(f"export field {self.id!r} must declare computed_key")
        if self.kind == "filler" and self.length is None:
            raise ValueError(f"export field {self.id!r} filler must declare length")
        return self


class ExportRecordDefinition(RegistryModel):
    id: RecordId
    record_type: str
    order: int = Field(ge=0)
    encoding: str
    line_ending: Literal["crlf", "lf", "none"]
    required: bool = True
    repeat: Literal["binding_rows"] | None = None
    binding_record: str | None = None
    requires_positive_casilla: CasillaId | None = None
    fields: tuple[ExportFieldDefinition, ...] = Field(default_factory=tuple)

    @field_validator("binding_record")
    @classmethod
    def _binding_record_non_empty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("export record binding_record must be non-empty")
        return value


class ExportLayoutDefinition(RegistryModel):
    id: ExportLayoutId
    format: Literal["fixed_width", "xml_dictionary"] = "fixed_width"
    dictionary_source_ref: SourceRefId | None = None
    source_refs: SourceRefs
    legal_refs: LegalRefs
    records: tuple[ExportRecordDefinition, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_layout_format(self) -> ExportLayoutDefinition:
        if self.format == "xml_dictionary":
            if self.dictionary_source_ref is None:
                raise ValueError(f"export layout {self.id!r} must declare dictionary_source_ref")
            if self.dictionary_source_ref not in self.source_refs:
                raise ValueError(f"export layout {self.id!r} dictionary source must be included in source_refs")
        return self


class ModeloRevision(RegistryModel):
    id: RevisionId
    label: str | None = None
    valid_from: date
    valid_to: date | None = None
    period_selector: PeriodSelector
    legal_refs: LegalRefs
    source_refs: SourceRefs
    parameters: tuple[ParameterDefinition, ...] = ()
    casillas: tuple[CasillaDefinition, ...] = ()
    formulas: tuple[FormulaDefinition, ...] = ()
    bindings: tuple[DataBindingDefinition, ...] = ()
    algorithm_providers: tuple[AlgorithmProviderDefinition, ...] = ()
    algorithm_bindings: tuple[AlgorithmBindingDefinition, ...] = ()
    relations: tuple[RelationDefinition, ...] = ()
    export_layouts: tuple[ExportLayoutDefinition, ...] = ()
    extraction_profiles: tuple[ExtractionProfileDefinition, ...] = ()
    live_cross_references: tuple[LiveCrossReferenceDecision, ...] = ()
    workbook_parity_refs: tuple[WorkbookParityReference, ...] = ()
    verification_expectations: tuple[VerificationExpectationDefinition, ...] = ()
    application_links: tuple[ApplicationLinkDefinition, ...] = ()
    deadline_windows: tuple[DeadlineWindowDefinition, ...] = ()
    filing_schedules: tuple[FilingScheduleDefinition, ...] = ()
    support_removal_decisions: tuple[SupportRemovalDecisionDefinition, ...] = ()
    constructs: tuple[ConstructDefinition, ...] = ()
    dependency_classifications: tuple[DependencyClassificationDefinition, ...] = ()

    @model_validator(mode="after")
    def _validate_window(self) -> ModeloRevision:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("revision valid_to must be on or after valid_from")
        return self


class ModeloDefinition(RegistryModel):
    id: ModeloId
    title: str
    official_name: str
    tax_domain: str
    cadence: Literal["monthly", "quarterly", "annual", "ad_hoc", "profile_based"]
    jurisdiction: Literal["ES-AEAT"]
    legal_refs: LegalRefs
    source_refs: SourceRefs
    revisions: Mapping[RevisionId, ModeloRevision]

    @model_validator(mode="after")
    def _validate_revisions(self) -> ModeloDefinition:
        if not self.revisions:
            raise ValueError(f"modelo {self.id!r} must declare at least one revision")
        for key, revision in self.revisions.items():
            if key != revision.id:
                raise ValueError(f"revision key {key!r} does not match revision id {revision.id!r}")
        return self


class RegistryCatalogues(RegistryModel):
    legal: Mapping[LegalRefId, LegalReference]
    sources: Mapping[SourceRefId, SourceReference]


class RegistrySnapshot(RegistryModel):
    modelo: ModeloDefinition
    revision: ModeloRevision
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=8)
    legal: Mapping[LegalRefId, LegalReference]
    sources: Mapping[SourceRefId, SourceReference]
    extraction_profiles: Mapping[ExtractionProfileId, ExtractionProfileDefinition]
    live_cross_references: Mapping[CrossReferenceId, LiveCrossReferenceDecision]
    workbook_parity_refs: Mapping[WorkbookParityRefId, WorkbookParityReference]
    verification_expectations: Mapping[VerificationExpectationId, VerificationExpectationDefinition]
    application_links: Mapping[ApplicationLinkId, ApplicationLinkDefinition]
    deadline_windows: Mapping[DeadlineWindowId, DeadlineWindowDefinition]
    filing_schedules: Mapping[str, FilingScheduleDefinition]
    support_removal_decisions: Mapping[SupportRemovalDecisionId, SupportRemovalDecisionDefinition]
    constructs: Mapping[ConstructId, ConstructDefinition]
    dependency_classifications: Mapping[DependencyClassificationId, DependencyClassificationDefinition]
