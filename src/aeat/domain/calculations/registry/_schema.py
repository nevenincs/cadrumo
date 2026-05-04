"""Strict schema authority for AEAT registry definitions."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from ._ids import (
    BindingId,
    CasillaId,
    ExportFieldId,
    ExportLayoutId,
    FormulaId,
    LegalRefId,
    ModeloId,
    ParameterId,
    RecordId,
    RelationId,
    RevisionId,
    SourceRefId,
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
LegalRefs = Annotated[tuple[LegalRefId, ...], Field(min_length=1)]
SourceRefs = Annotated[tuple[SourceRefId, ...], Field(min_length=1)]
FormulaOperator = Literal[
    "add",
    "subtract",
    "multiply",
    "divide",
    "percent",
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
    authority: Literal["boe", "aeat", "eu", "autonomous_community", "other"]
    kind: Literal["ley", "real_decreto", "orden", "reglamento", "directiva", "manual", "instruction"]
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

    @model_validator(mode="after")
    def _validate_legal_reference(self) -> LegalReference:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("legal reference effective_to must be on or after effective_from")
        if self.review_status != "reviewed":
            raise ValueError(f"legal reference {self.id!r} is not reviewed")
        return self


class SourceReference(RegistryModel):
    id: SourceRefId
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


class FormulaExpression(RegistryModel):
    op: FormulaOperator | None = None
    args: tuple[FormulaExpression, ...] = ()
    casilla: CasillaId | None = None
    parameter: ParameterId | None = None
    relation: RelationId | None = None
    literal: DecimalValue | None = None

    @model_validator(mode="after")
    def _validate_expression(self) -> FormulaExpression:
        populated_leaves = [
            self.casilla is not None,
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


class DataBindingDefinition(RegistryModel):
    id: BindingId
    source: Literal["ledger", "invoice", "rental", "vat", "category", "profile", "previous_filing", "manual_input"]
    selector: Mapping[str, str | int | DecimalValue | bool]
    aggregation: Mapping[str, str | int | DecimalValue | bool] | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs


class FormulaDefinition(RegistryModel):
    id: FormulaId
    target: CasillaId
    expression: FormulaExpression
    rounding: str | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs


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
    source_modelo: ModeloId
    source_revision_selector: Mapping[str, str | int]
    source_output: CasillaId | str
    target_binding: BindingId
    period_alignment: Mapping[str, str | int]
    aggregation: Mapping[str, str | int | DecimalValue | bool] | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs


class ExportFieldDefinition(RegistryModel):
    id: ExportFieldId
    offset: int | None = Field(default=None, ge=0)
    length: int | None = Field(default=None, gt=0)
    kind: Literal["literal", "casilla", "computed", "filler", "checksum"]
    casilla: CasillaId | None = None
    literal: str | None = None
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
        if self.kind == "literal" and self.literal is None:
            raise ValueError(f"export field {self.id!r} must declare literal")
        return self


class ExportRecordDefinition(RegistryModel):
    id: RecordId
    record_type: str
    order: int = Field(ge=0)
    encoding: str
    line_ending: Literal["crlf", "lf", "none"]
    fields: tuple[ExportFieldDefinition, ...] = Field(default_factory=tuple)


class ExportLayoutDefinition(RegistryModel):
    id: ExportLayoutId
    source_refs: SourceRefs
    legal_refs: LegalRefs
    records: tuple[ExportRecordDefinition, ...] = Field(default_factory=tuple)


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
    cadence: Literal["monthly", "quarterly", "annual", "ad_hoc"]
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
    legal: Mapping[LegalRefId, LegalReference]
    sources: Mapping[SourceRefId, SourceReference]
