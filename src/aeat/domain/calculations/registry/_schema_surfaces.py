"""Casilla, relation, export, and record schema models."""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .._export_field_kind import CasillaFieldKind, CasillaFieldKindValue
from ._errors import RegistryValidationError
from ._ids import (
    BindingId,
    CasillaId,
    ExportFieldId,
    ExportLayoutId,
    FormulaId,
    ModeloId,
    ParameterId,
    RecordId,
    RelationId,
    RevisionId,
    SourceRefId,
)
from ._record_spec import ENCODING_ALIAS_MAP
from ._schema_base import ContinuidadId, LegalRefs, RegistryModel, SourceRefs
from ._schema_input_kind import InputKind, InputKindValue
from ._schema_scalars import DecimalValue

__all__ = [
    "AlgorithmBindingDefinition",
    "AlgorithmProviderDefinition",
    "CalculationCompletenessCasilla",
    "CalculationCompletenessManifest",
    "CasillaAlias",
    "CasillaConstraints",
    "CasillaContinuidadEvolutionDefinition",
    "CasillaDefinition",
    "ExportFieldDefinition",
    "ExportLayoutDefinition",
    "ExportRecordDefinition",
    "RecordDiscriminator",
    "RelationDefinition",
]


class CasillaContinuidadEvolutionDefinition(RegistryModel):
    """Declared cross-revision evolution for one casilla continuity chain."""

    id: RecordId
    continuidad_id: ContinuidadId
    from_revision: RevisionId
    to_revision: RevisionId
    evolution_kind: Literal[
        "unchanged",
        "label_evolved",
        "legal_refs_evolved",
        "label_and_legal_refs_evolved",
        "repurposed",
        "retired",
    ]
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_revision_pair(self) -> CasillaContinuidadEvolutionDefinition:
        if self.from_revision == self.to_revision:
            raise RegistryValidationError(
                f"casilla continuidad evolution {self.id!r} must span two different revisions",
            )
        return self


class CasillaAlias(RegistryModel):
    """A label variant for a casilla, carrying its own legal grounding.

    Used by Plan C's semantic-role validator: two casillas in
    different modelos can share a ``semantic_role`` even though
    their primary ``label`` strings differ verbatim, provided each
    declares the divergent phrasing via an ``aliases`` entry with
    a documented BOE or AEAT source.
    """

    label: str = Field(min_length=1, max_length=512)
    legal_refs: LegalRefs
    source_refs: SourceRefs


class CasillaConstraints(RegistryModel):
    """Declarative value constraints applied after a casilla is evaluated.

    Captures the legal sign / range rules AEAT mandates per LIRPF /
    LIVA / LIS articles: a withholding casilla cannot carry a
    negative value, a deductibility cap restricts the maximum, a
    non-negativity floor on a cuota líquida prevents arithmetic
    underflow propagating through downstream formulas.

    Each constraint declares its own legal grounding so the engine
    can surface a BOE permalink in the violation envelope when a
    computed value falls outside the declared bounds. The runtime
    raises a typed `CasillaConstraintViolationError`; the Sheets apply
    adapter renders the same record as a `setDataValidation` rule
    on the corresponding cell so the operator sees the constraint
    directly in the workbook UI.
    """

    sign: Literal["any", "non_negative", "non_positive"] = "any"
    min_value: DecimalValue | None = None
    max_value: DecimalValue | None = None
    pattern: str | None = None
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=0)
    enum: tuple[str, ...] | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_bounds(self) -> CasillaConstraints:
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise RegistryValidationError(
                f"casilla constraints: min_value {self.min_value} > max_value {self.max_value}",
            )
        if self.sign == "non_negative" and self.max_value is not None and self.max_value < Decimal("0"):
            raise RegistryValidationError(
                "casilla constraints: sign='non_negative' is incompatible with negative max_value",
            )
        if self.sign == "non_positive" and self.min_value is not None and self.min_value > Decimal("0"):
            raise RegistryValidationError(
                "casilla constraints: sign='non_positive' is incompatible with positive min_value",
            )
        if self.min_length is not None and self.max_length is not None and self.min_length > self.max_length:
            raise RegistryValidationError(
                f"casilla constraints: min_length {self.min_length} > max_length {self.max_length}",
            )
        if self.enum is not None and len(self.enum) == 0:
            raise RegistryValidationError("casilla constraints: enum must declare at least one value")
        if self.enum is not None and len(set(self.enum)) != len(self.enum):
            raise RegistryValidationError("casilla constraints: enum values must be unique")
        if self.pattern is not None:
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise RegistryValidationError(
                    f"casilla constraints: pattern {self.pattern!r} is not a valid regex: {exc}",
                ) from exc
        return self

    def violates(self, value: Decimal) -> str | None:
        """Return a short reason string if a Decimal `value` violates this constraint, else None.

        Numeric-only violation check preserved for downstream consumers
        of computed casilla values. Text constraints (`pattern`,
        `min_length`, `max_length`, `enum`) are surfaced through the
        sibling :meth:`violates_text` method.
        """
        if self.sign == "non_negative" and value < Decimal("0"):
            return f"value {value} violates sign=non_negative"
        if self.sign == "non_positive" and value > Decimal("0"):
            return f"value {value} violates sign=non_positive"
        if self.min_value is not None and value < self.min_value:
            return f"value {value} below min_value {self.min_value}"
        if self.max_value is not None and value > self.max_value:
            return f"value {value} above max_value {self.max_value}"
        return None

    def violates_text(self, value: str) -> str | None:
        """Return a short reason string if a text `value` violates the text constraints, else None.

        Checks the four text-shape constraints introduced by Plan B:
        ``pattern``, ``min_length``, ``max_length``, and ``enum``. Used
        by consumers that resolve a casilla value into a string at
        evaluation time.
        """
        length = len(value)
        if self.min_length is not None and length < self.min_length:
            return f"value length {length} below min_length {self.min_length}"
        if self.max_length is not None and length > self.max_length:
            return f"value length {length} above max_length {self.max_length}"
        if self.pattern is not None and not re.fullmatch(self.pattern, value):
            return f"value {value!r} does not match pattern {self.pattern!r}"
        if self.enum is not None and value not in self.enum:
            return f"value {value!r} not in enum {self.enum!r}"
        return None


class CasillaDefinition(RegistryModel):
    """A single AEAT casilla within a modelo revision.

    A casilla's identity is the pair ``(segmento, number)``. For
    single-segment modelos ``segmento`` is unset and ``number`` alone is
    unique within the revision. Multi-segment AEAT modelos (e.g. Modelo
    200) reuse the same five-digit ``number`` across distinct record
    segments with a different meaning in each; those casillas carry the
    AEAT record-segment code in ``segmento`` to disambiguate.
    """

    id: CasillaId
    number: str
    segmento: str | None = Field(
        default=None,
        min_length=1,
        max_length=32,
        description=(
            "AEAT record-segment code (e.g. 'DP200014') for multi-segment "
            "modelos that reuse a casilla number across record segments. "
            "Unset for single-segment modelos; a casilla's identity is the "
            "pair (segmento, number)."
        ),
    )
    label: str
    localized_labels: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Optional localized label overrides mapped by locale code (e.g., 'en', 'ca', 'hu'). "
            "The primary 'label' field remains the official Spanish invariant."
        ),
    )
    localized_help: dict[str, str] = Field(
        default_factory=dict,
        description=("Optional localized help/hint texts mapped by locale code (e.g., 'en', 'ca', 'hu')."),
    )
    section: tuple[str, ...]
    data_type: Literal[
        "decimal",
        "money",
        "integer",
        "ratio",
        "text",
        "boolean",
        "nif",
        "year",
        "period_code",
        "country_code",
        "iban",
        "name",
        "nif_iva",
        "ccaa_code",
        "province_code",
        "postal_code",
        "municipality_code",
        "bic",
        "date",
    ] = "money"
    required: bool = False
    input_kind: InputKindValue = InputKind.MANUAL
    formula: FormulaId | None = None
    binding: BindingId | None = None
    export_refs: tuple[ExportFieldId, ...] = ()
    constraints: CasillaConstraints | None = None
    form_number: str | None = Field(default=None, min_length=1, max_length=16)
    continuidad_id: ContinuidadId | None = Field(
        default=None,
        description=(
            "Stable cross-revision continuity key for non-overlapping annual "
            "forms. When present, it identifies the legal concept continuity "
            "chain independently of the revision-local casilla id."
        ),
    )
    semantic_role: str | None = Field(default=None, min_length=1, max_length=128)
    semantic_role_cardinality: Literal["shared", "intentional_singleton"] = "shared"
    semantic_role_cardinality_reason: str | None = Field(default=None, min_length=1, max_length=256)
    aliases: tuple[CasillaAlias, ...] = ()
    internal_only: bool = Field(
        default=False,
        description=(
            "App-internal computed casilla that participates in the calculation "
            "graph but is intentionally absent from the AEAT-published Diseño de "
            "Registros. Typically a regulatory ceiling or intermediate the app "
            "materialises as a casilla so verification predicates and downstream "
            "formulas can reference it. An internal_only casilla MUST be computed "
            "(``input_kind = COMPUTED``), MUST carry no ``export_refs``, and MUST "
            "carry legal_refs / source_refs grounding the internal computation in "
            "real regulatory authority."
        ),
    )
    legal_refs: LegalRefs
    source_refs: SourceRefs

    def get_label(self, locale: str) -> str:
        """Return the localized label for `locale`, falling back to the Spanish invariant `label`."""
        return self.localized_labels.get(locale, self.label)

    def get_help(self, locale: str) -> str | None:
        """Return the localized help/hint text for `locale`, or None if not defined."""
        return self.localized_help.get(locale)

    @model_validator(mode="after")
    def _validate_input_kind(self) -> CasillaDefinition:
        if self.input_kind == InputKind.COMPUTED and self.formula is None:
            raise RegistryValidationError(f"computed casilla {self.id!r} must declare formula")
        if self.input_kind == InputKind.COMPUTED and self.binding is not None:
            raise RegistryValidationError(f"computed casilla {self.id!r} must not declare binding")
        if self.input_kind == InputKind.BOUND and self.binding is None:
            raise RegistryValidationError(f"bound casilla {self.id!r} must declare binding")
        if self.input_kind == InputKind.BOUND and self.formula is not None:
            raise RegistryValidationError(f"bound casilla {self.id!r} must not declare formula")
        if self.internal_only and self.export_refs:
            raise RegistryValidationError(
                f"internal_only casilla {self.id!r} must not declare export_refs "
                "(an app-internal casilla cannot also be exported to a fichero record)",
            )
        if self.internal_only and self.input_kind != InputKind.COMPUTED:
            raise RegistryValidationError(
                f"internal_only casilla {self.id!r} must be computed "
                "(an internal ceiling has no legitimate computation surface unless formula-derived)",
            )
        if self.semantic_role_cardinality == "intentional_singleton":
            if self.semantic_role is None:
                raise RegistryValidationError(
                    f"casilla {self.id!r} declares intentional singleton role cardinality without semantic_role",
                )
            if self.semantic_role_cardinality_reason is None:
                raise RegistryValidationError(
                    f"casilla {self.id!r} declares intentional singleton role cardinality without reason",
                )
        elif self.semantic_role_cardinality_reason is not None:
            raise RegistryValidationError(
                f"casilla {self.id!r} declares semantic_role_cardinality_reason "
                "without intentional singleton cardinality",
            )
        return self


class CalculationCompletenessCasilla(RegistryModel):
    """One required ``(segmento, number)`` casilla in a calculation-completeness manifest.

    A casilla's identity is the pair ``(segmento, number)``. A
    single-segment modelo leaves ``segmento`` unset, so the pair degrades
    to ``(None, number)`` and the manifest enumerates bare numbers.

    ``number`` carries the registry ``number`` of the closure casilla
    verbatim. Only Modelo 200's casilla numbers are five-digit AEAT
    Diseño tags; the other calculation-bearing modelos identify casillas
    by semantic slug (``iva.cuota-devengada-total``) or short ordinal
    (``01``-``19``), so the manifest carries whatever vocabulary the
    modelo's registry uses. The field is unbounded above to match the
    unconstrained ``CasillaDefinition.number``.

    The manifest enumerates only the casillas inside a modelo's
    *calculation closure* — formula targets, the casillas referenced
    inside any formula expression, formula and binding endpoint casillas,
    and verification-expectation operands. Pure accounting-statement
    data-entry fields that feed no calculation are intentionally absent
    from this required set.
    """

    number: str = Field(min_length=1)
    segmento: str | None = Field(
        default=None,
        min_length=1,
        max_length=32,
        description=(
            "AEAT record-segment code (e.g. 'DP200014') for multi-segment "
            "modelos that reuse a casilla number across record segments. "
            "Unset for single-segment modelos."
        ),
    )

    def identity(self) -> tuple[str | None, str]:
        """Return the ``(segmento, number)`` identity pair for this casilla."""
        return (self.segmento, self.number)


class CalculationCompletenessManifest(RegistryModel):
    """The required calculation-closure casilla set for a modelo revision.

    Enumerates the ``(segmento, number)`` casillas in a modelo's
    *calculation closure* — the casillas the cross-connecting
    calculation engine traverses: every formula target, every casilla
    referenced inside a formula expression, every binding and relation
    endpoint casilla, and every verification-expectation operand. It is
    derived from the official AEAT Diseño de Registros *intersected
    with* the modelo's calculation surface — Diseño-authoritative on
    each casilla's segment, number, and label, but bounded to what the
    engine needs (an off-load-path derivation step, never parsed on the
    snapshot-build hot path) and checked into the registry as reviewed
    data.

    The registry validator enforces ``manifest-required ⊆ declared``
    plus a ``(segmento, number)`` identity check and a
    ``legal_refs`` / ``source_refs`` grounding check on each required
    casilla. A casilla the revision declares but the manifest does not
    list (a pure accounting-statement field) is *not* a failure.

    ``manual_extraction`` flags a manifest authored from a manual read
    of a PDF-only Diseño that resists machine extraction; the
    off-load-path drift re-verification skips the machine re-derivation
    for such manifests and records ``manual_extraction_reason`` instead
    of failing silently.
    """

    source_ref: SourceRefId = Field(
        description="Catalogue source id of the AEAT Diseño de Registros the manifest was derived from.",
    )
    casillas: tuple[CalculationCompletenessCasilla, ...]
    manual_extraction: bool = False
    manual_extraction_reason: str | None = Field(default=None, min_length=1, max_length=512)
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_manifest(self) -> CalculationCompletenessManifest:
        if not self.casillas:
            raise RegistryValidationError("calculation-completeness manifest must enumerate at least one casilla")
        identities = [casilla.identity() for casilla in self.casillas]
        duplicates = sorted({pair for pair in identities if identities.count(pair) > 1})
        if duplicates:
            rendered = ", ".join(
                f"{number!r}" if segmento is None else f"{number!r} within segmento {segmento!r}"
                for segmento, number in duplicates
            )
            raise RegistryValidationError(
                f"calculation-completeness manifest declares duplicate casilla identities: {rendered}",
            )
        if self.source_ref not in self.source_refs:
            raise RegistryValidationError(
                "calculation-completeness manifest source_ref must be included in source_refs",
            )
        if self.manual_extraction and self.manual_extraction_reason is None:
            raise RegistryValidationError(
                "calculation-completeness manifest with manual_extraction must declare manual_extraction_reason",
            )
        if not self.manual_extraction and self.manual_extraction_reason is not None:
            raise RegistryValidationError(
                "calculation-completeness manifest declares manual_extraction_reason without manual_extraction",
            )
        return self

    def identities(self) -> frozenset[tuple[str | None, str]]:
        """Return the frozenset of required ``(segmento, number)`` identity pairs."""
        return frozenset(casilla.identity() for casilla in self.casillas)


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
    source_output: CasillaId
    target_binding: BindingId
    period_alignment: Mapping[str, str | int]
    source_periods: tuple[str, ...] = ()
    target_periods: tuple[str, ...] = ()
    source_period_offset_from_target: int | None = None
    aggregation: Mapping[str, str | int | DecimalValue | bool] | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("source_periods", "target_periods")
    @classmethod
    def _relation_periods_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("relation periods must be unique")
        return value

    @model_validator(mode="after")
    def _validate_dependency_role(self) -> RelationDefinition:
        if self.kind == "annual_summary" and self.dependency_role != "periodic_to_annual_summary":
            raise RegistryValidationError(
                f"annual summary relation {self.id!r} must use periodic_to_annual_summary role",
            )
        if self.source_period_offset_from_target is not None:
            # The offset declares "for each target_period, derive source_period
            # by adding the offset to the target's ordinal". It is incompatible
            # with explicit source_periods which fixes a single static source set.
            if self.source_periods:
                raise RegistryValidationError(
                    f"relation {self.id!r} cannot declare source_periods together with "
                    "source_period_offset_from_target",
                )
            if self.source_period_offset_from_target == 0:
                raise RegistryValidationError(f"relation {self.id!r} source_period_offset_from_target must be non-zero")
        return self


class ExportFieldDefinition(RegistryModel):
    id: ExportFieldId
    offset: int | None = Field(default=None, ge=0)
    length: int | None = Field(default=None, gt=0)
    kind: CasillaFieldKindValue
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
        if self.kind == CasillaFieldKind.CASILLA and self.casilla is None:
            raise RegistryValidationError(f"export field {self.id!r} must declare casilla")
        if self.kind == CasillaFieldKind.BINDING and self.binding is None:
            raise RegistryValidationError(f"export field {self.id!r} must declare binding")
        if self.kind == CasillaFieldKind.LITERAL and self.literal is None:
            raise RegistryValidationError(f"export field {self.id!r} must declare literal")
        if self.kind == CasillaFieldKind.HEADER and self.header_key is None:
            raise RegistryValidationError(f"export field {self.id!r} must declare header_key")
        if self.kind == CasillaFieldKind.DRAFT and self.draft_attribute is None:
            raise RegistryValidationError(f"export field {self.id!r} must declare draft_attribute")
        if self.kind == CasillaFieldKind.COMPUTED and self.computed_key is None:
            raise RegistryValidationError(f"export field {self.id!r} must declare computed_key")
        if self.kind == CasillaFieldKind.FILLER and self.length is None:
            raise RegistryValidationError(f"export field {self.id!r} filler must declare length")
        return self


class RecordDiscriminator(RegistryModel):
    """Record-shape discriminator for record types that share literal prefixes.

    A record's literal-prefix matcher cannot tell two records apart when they
    share their leading literal fields (AEAT models several Tipo-2 record
    sub-shapes that all start with the same record-type literal). The
    discriminator declares a contiguous byte range whose populated-or-blank
    pattern uniquely identifies this record subtype, letting the parser pick
    the correct record while reading binding-row sequences.
    """

    offset: int = Field(ge=1)
    length: int = Field(gt=0)
    requires: Literal["blank", "non_blank"]


class ExportRecordDefinition(RegistryModel):
    id: RecordId
    record_type: str
    order: int = Field(ge=0)
    encoding: str
    line_ending: Literal["crlf", "lf", "none"]
    required: bool = True
    repeat: Literal["binding_rows"] | None = None
    binding_record: str | None = None
    row_field_casillas: Mapping[str, CasillaId] = Field(default_factory=dict)
    discriminator: RecordDiscriminator | None = None
    requires_positive_casilla: CasillaId | None = None
    fields: tuple[ExportFieldDefinition, ...] = Field(default_factory=tuple)

    @field_validator("binding_record")
    @classmethod
    def _binding_record_non_empty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise RegistryValidationError("export record binding_record must be non-empty")
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
                raise RegistryValidationError(f"export layout {self.id!r} must declare dictionary_source_ref")
            if self.dictionary_source_ref not in self.source_refs:
                raise RegistryValidationError(
                    f"export layout {self.id!r} dictionary source must be included in source_refs",
                )
        return self

    @model_validator(mode="after")
    def _validate_encoding_consistency(self) -> ExportLayoutDefinition:
        """Enforce one encoding per fixed-width export layout.

        AEAT publishes one wire encoding per modelo-year fichero-BOE
        spec; mixing encodings across records inside a single layout
        is a registry-author error that would produce a payload no
        single decoder can faithfully re-parse. ``latin-1`` and
        ``iso-8859-1`` are normalised to the same encoding before
        comparison (Python codec aliases for the same charset).

        Cross-domain encoding-lock: every record within one layout
        must declare an encoding that normalises to the same value.
        XML-dictionary layouts have no record-level encoding (the
        records tuple is typically empty), so this check is a no-op
        for them.
        """
        if self.format != "fixed_width":
            return self
        normalised: dict[str, str] = {}
        for record in self.records:
            normalised[record.id] = _normalise_fichero_boe_encoding(record.encoding)
        unique_encodings = set(normalised.values())
        if len(unique_encodings) > 1:
            per_record = ", ".join(f"{record_id}={encoding!r}" for record_id, encoding in sorted(normalised.items()))
            raise RegistryValidationError(
                f"export layout {self.id!r} declares inconsistent encodings "
                f"across its records: {per_record}. A single fichero-BOE "
                f"layout must use one wire encoding so the published payload "
                f"decodes uniformly.",
            )
        return self


def _normalise_fichero_boe_encoding(declared: str) -> str:
    """Return the canonical form of a fichero-BOE encoding declaration."""
    return ENCODING_ALIAS_MAP.get(declared.strip().lower(), declared.strip().lower())


# Single source of truth for the predicate-DSL operator names. The
# registry-load validator
# (_validate_surfaces.validate_verification_expectation_section)
# uses this set to reject unknown operators at authoring time. The
# runtime evaluator
# (aeat.application.modelo._verification_actions._evaluate_predicate_expression)
# carries its own regex per operator but MUST keep its set of operators
# identical to this constant — drift between the two sets is a
# silent-pass hazard at the predicate layer (a typo would silently pass
# the gate that's missing the operator). A gate test asserts the
# runtime evaluator recognises every name in this constant.
