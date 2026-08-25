"""Casilla, relation, export, and record schema models."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from ....core import (
    CasillaId,
    FilingPeriodCode,
    RegistrySelectorPeriodCode,
)
from ....core.aggregation import RelationAggregation
from ....core.identity import AeatBoxNumber, ContinuidadId
from .errors import RegistryValidationError
from .ids import (
    BindingId,
    ExportFieldId,
    FormulaId,
    ModeloId,
    RecordId,
    RelationId,
    RevisionId,
    SourceRefId,
)
from .modelo_localization import resolve_modelo_localization
from .schema_base import LegalRefs, RegistryModel, SourceRefs
from ._schema_export_exemption import ExportExemptionReasonValue
from .schema_input_kind import InputKind, InputKindValue
from .schema_scalars import DecimalValue

__all__ = [
    "CalculationCompletenessCasilla",
    "CalculationCompletenessManifest",
    "CasillaAlias",
    "CasillaConstraints",
    "CasillaContinuidadEvolutionDefinition",
    "CasillaDefinition",
    "RelationDefinition",
    "RelationPeriodAlignment",
    "RelationRevisionSelector",
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
    """A localized label variant for a casilla, carrying its own grounding.

    Used by Plan C's semantic-role validator: two casillas in
    different modelos can share a ``semantic_role`` even though their
    primary labels differ, provided each declares the divergent phrasing via
    an ``aliases`` entry with a documented BOE or AEAT source. The text is
    resolved from the shared locale catalogue; the revision loader derives
    ``localization_key`` from the containing casilla and alias occurrence.
    """

    localization_key: str = Field(min_length=1, exclude=True, repr=False)
    legal_refs: LegalRefs
    source_refs: SourceRefs

    def get_label(self, locale: str) -> str:
        """Resolve the alias label through the shared catalogue."""
        resolved = resolve_modelo_localization((self.localization_key,), locale=locale, required=True)
        assert resolved is not None
        return resolved

    @property
    def label(self) -> str:
        """Return the strict official-Spanish alias label."""
        return self.get_label("es")


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

    ``id`` is the canonical reference identity. ``number`` and
    ``segmento`` are reviewed AEAT record-design metadata. For
    single-segment modelos ``segmento`` is unset and ``number`` alone is
    unique within the revision. Multi-segment AEAT modelos (e.g. Modelo
    200) reuse the same five-digit ``number`` across distinct record
    segments with a different meaning in each; those casillas carry the
    AEAT record-segment code in ``segmento`` to disambiguate metadata.
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
            "Unset for single-segment modelos; references still use canonical "
            "casilla.id, not this metadata pair."
        ),
    )
    localization_keys: tuple[str, ...] = Field(min_length=1, exclude=True, repr=False)
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
    alternate_bindings: tuple[BindingId, ...] = Field(
        default_factory=tuple,
        description=(
            "Equivalent binding slots that may populate the same bound casilla. "
            "Used only when the registry has reviewed multiple legally grounded "
            "source paths for the same factual amount; conflicting supplied "
            "values are rejected before calculation."
        ),
    )
    export_refs: tuple[ExportFieldId, ...] = ()
    export_exemption_reason: ExportExemptionReasonValue | None = Field(
        default=None,
        description=(
            "Why this casilla files no slot on the official fixed-width record. "
            "Required by registry build for a completeness-manifest casilla that "
            "the export completeness gate would otherwise demand -- one declaring "
            "a formula or marked required -- but that no export field addresses. "
            "Without it, exemption from that gate is expressed by absence alone, "
            "which reads identically whether the casilla genuinely cannot reach a "
            "box or was simply never annotated. A casilla the record DOES address "
            "must not declare one, and ``internal_only`` already asserts the "
            "internal-intermediate case on its own."
        ),
    )
    constraints: CasillaConstraints | None = None
    form_number: AeatBoxNumber | None = Field(default=None)
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
        """Resolve one label scalar through the canonical shared catalogues."""
        resolved = resolve_modelo_localization(self.localization_keys, locale=locale, required=True)
        assert resolved is not None
        return resolved

    def get_help(self, locale: str) -> str | None:
        """Resolve optional help through the same identity and fallback chain."""
        help_keys = tuple(f"{key.removesuffix('.label')}.help" for key in self.localization_keys)
        return resolve_modelo_localization(help_keys, locale=locale, required=False)

    @property
    def label(self) -> str:
        """Return the strict official-Spanish regulatory label."""
        return self.get_label("es")

    @model_validator(mode="after")
    def _validate_input_kind(self) -> CasillaDefinition:
        # Localization is resolved by the registry authority after its shared
        # catalogue has been selected. Constructing a schema from an arbitrary
        # test or operator-supplied root must not consult the bundled catalogue;
        # the structural validator still enforces every non-localized rule here.
        if self.input_kind == InputKind.COMPUTED and self.formula is None:
            raise RegistryValidationError(f"computed casilla {self.id!r} must declare formula")
        if self.input_kind == InputKind.COMPUTED and self.binding is not None:
            raise RegistryValidationError(f"computed casilla {self.id!r} must not declare binding")
        if self.input_kind != InputKind.BOUND and self.alternate_bindings:
            raise RegistryValidationError(f"non-bound casilla {self.id!r} must not declare alternate_bindings")
        if self.input_kind == InputKind.BOUND and self.binding is None:
            raise RegistryValidationError(f"bound casilla {self.id!r} must declare binding")
        if self.binding is not None and self.binding in self.alternate_bindings:
            raise RegistryValidationError(
                f"casilla {self.id!r} alternate_bindings must not repeat primary binding {self.binding!r}",
            )
        if len(set(self.alternate_bindings)) != len(self.alternate_bindings):
            raise RegistryValidationError(f"casilla {self.id!r} alternate_bindings must be unique")
        if self.input_kind == InputKind.BOUND and self.formula is not None:
            raise RegistryValidationError(f"bound casilla {self.id!r} must not declare formula")
        if self.input_kind == InputKind.PROJECTION_ONLY and any(
            value
            for value in (
                self.formula,
                self.binding,
                self.alternate_bindings,
            )
        ):
            raise RegistryValidationError(
                f"projection-only casilla {self.id!r} must not declare formula, binding, or alternate_bindings",
            )
        self._validate_export_exposure()
        self._validate_singleton_role_declaration()
        return self

    def _validate_export_exposure(self) -> None:
        """Hold internal_only, export_refs and the exemption reason coherent.

        All three axes answer one question -- whether an official record
        addresses this casilla -- so a casilla may assert at most one of
        "app-internal", "exported" and "exempt from the completeness gate".
        """
        if self.internal_only and self.export_refs:
            raise RegistryValidationError(
                f"internal_only casilla {self.id!r} must not declare export_refs "
                "(an app-internal casilla cannot also be exported to a fichero record)",
            )
        if self.export_exemption_reason is not None and self.export_refs:
            raise RegistryValidationError(
                f"casilla {self.id!r} declares export_exemption_reason "
                f"{self.export_exemption_reason.value!r} while also declaring export_refs "
                "(a casilla the official record addresses is not exempt from the export "
                "completeness gate)",
            )
        if self.internal_only and self.export_exemption_reason is not None:
            raise RegistryValidationError(
                f"internal_only casilla {self.id!r} must not declare export_exemption_reason "
                f"{self.export_exemption_reason.value!r} "
                "(internal_only already asserts the internal-intermediate exemption)",
            )
        if self.internal_only and self.input_kind != InputKind.COMPUTED:
            raise RegistryValidationError(
                f"internal_only casilla {self.id!r} must be computed "
                "(an internal ceiling has no legitimate computation surface unless formula-derived)",
            )

    def _validate_singleton_role_declaration(self) -> None:
        """Require a declared singleton cardinality to carry its role and reason.

        This is the per-casilla coherence half; the cross-casilla check that a
        role claimed as a singleton is not actually shared runs at registry
        scope over the whole modelo tuple.
        """
        if self.semantic_role_cardinality != "intentional_singleton":
            if self.semantic_role_cardinality_reason is not None:
                raise RegistryValidationError(
                    f"casilla {self.id!r} declares semantic_role_cardinality_reason "
                    "without intentional singleton cardinality",
                )
            return
        if self.semantic_role is None:
            raise RegistryValidationError(
                f"casilla {self.id!r} declares intentional singleton role cardinality without semantic_role",
            )
        if self.semantic_role_cardinality_reason is None:
            raise RegistryValidationError(
                f"casilla {self.id!r} declares intentional singleton role cardinality without reason",
            )


class CalculationCompletenessCasilla(RegistryModel):
    """One required canonical ``casilla.id`` in a calculation-completeness manifest.

    ``casilla_id`` is the authoritative reference key consumed by the
    validator. ``number`` and ``segmento`` remain official record-design
    metadata for drift review: the validator cross-checks them against
    the referenced casilla, but no consumer may resolve the manifest by
    those metadata fields.

    The manifest enumerates only the casillas inside a modelo's
    *calculation closure* — formula targets, the casillas referenced
    inside any formula expression, formula and binding endpoint casillas,
    and verification-expectation operands. Pure accounting-statement
    data-entry fields that feed no calculation are intentionally absent
    from this required set.
    """

    casilla_id: CasillaId
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

    def record_design_metadata(self) -> tuple[str | None, str]:
        """Return the reviewed ``(segmento, number)`` metadata pair."""
        return (self.segmento, self.number)

    def manifest_key(self) -> tuple[str, str | None, str]:
        """Return the canonical id plus its reviewed record-design metadata."""
        return (self.casilla_id, self.segmento, self.number)


class CalculationCompletenessManifest(RegistryModel):
    """The required calculation-closure casilla set for a modelo revision.

    Enumerates the canonical ``casilla.id`` values in a modelo's
    *calculation closure* — the casillas the cross-connecting
    calculation engine traverses: every formula target, every casilla
    referenced inside a formula expression, every binding and relation
    endpoint casilla, and every verification-expectation operand. It is
    derived from the official AEAT Diseño de Registros *intersected
    with* the modelo's calculation surface — Diseño-authoritative on
    each casilla's segment, number, and label, but the checked-in
    reference key is the registry's canonical ``casilla.id``. The
    segment/number metadata is retained as reviewed evidence and
    cross-checked against that id.

    The registry validator enforces ``manifest-required ⊆ declared``
    by canonical ``casilla.id`` plus a segment/number metadata check and a
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
        casilla_ids = [casilla.casilla_id for casilla in self.casillas]
        duplicate_ids = sorted({casilla_id for casilla_id in casilla_ids if casilla_ids.count(casilla_id) > 1})
        if duplicate_ids:
            rendered_ids = ", ".join(repr(casilla_id) for casilla_id in duplicate_ids)
            raise RegistryValidationError(
                f"calculation-completeness manifest declares duplicate casilla ids: {rendered_ids}",
            )
        metadata_pairs = [casilla.record_design_metadata() for casilla in self.casillas]
        duplicates = sorted({pair for pair in metadata_pairs if metadata_pairs.count(pair) > 1})
        if duplicates:
            rendered = ", ".join(
                f"{number!r}" if segmento is None else f"{number!r} within segmento {segmento!r}"
                for segmento, number in duplicates
            )
            raise RegistryValidationError(
                f"calculation-completeness manifest declares duplicate casilla record-design metadata: {rendered}",
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

    def casilla_ids(self) -> frozenset[CasillaId]:
        """Return the frozenset of required canonical ``casilla.id`` values."""
        return frozenset(casilla.casilla_id for casilla in self.casillas)

    def manifest_keys(self) -> frozenset[tuple[str, str | None, str]]:
        """Return canonical ids paired with their reviewed record-design metadata."""
        return frozenset(casilla.manifest_key() for casilla in self.casillas)


class RelationRevisionSelector(RegistryModel):
    year: int | None = None
    year_from: int | None = None
    year_to: int | None = None
    filing_year_delta: int | None = None

    @model_validator(mode="after")
    def _validate_shape(self) -> RelationRevisionSelector:
        if self.year_to is not None and self.year_from is None:
            raise RegistryValidationError("relation source revision selector year_to requires year_from")
        if self.year is None and self.year_from is None and self.filing_year_delta is None:
            raise RegistryValidationError(
                "relation source revision selector must declare year, year_from, or filing_year_delta",
            )
        absolute_selector = self.year is not None or self.year_from is not None or self.year_to is not None
        if absolute_selector and self.filing_year_delta is not None:
            raise RegistryValidationError(
                "relation source revision selector must use absolute year bounds or filing_year_delta, not both",
            )
        if self.year is not None and (self.year_from is not None or self.year_to is not None):
            raise RegistryValidationError(
                "relation source revision selector must use year or year_from/year_to, not both",
            )
        if self.year_from is not None and self.year_to is not None and self.year_to < self.year_from:
            raise RegistryValidationError(
                "relation source revision selector year_to must be on or after year_from",
            )
        return self


class RelationPeriodAlignment(RegistryModel):
    mode: Literal["previous_quarter", "prior_pagos_cumulative"] | None = None
    source_periods: Literal["quarters", "months", "annual_summary"] | None = None
    source_period_kind: Literal["quarterly"] | None = None
    source_period: FilingPeriodCode | None = None
    target_period: FilingPeriodCode | None = None
    filing_year_delta: int | None = None

    @model_validator(mode="after")
    def _validate_shape(self) -> RelationPeriodAlignment:
        if not any(
            value is not None
            for value in (
                self.mode,
                self.source_periods,
                self.source_period_kind,
                self.source_period,
                self.target_period,
                self.filing_year_delta,
            )
        ):
            raise RegistryValidationError("relation period alignment must declare a current alignment shape")
        if self.mode is not None:
            if any(
                value is not None
                for value in (
                    self.source_periods,
                    self.source_period_kind,
                    self.source_period,
                    self.target_period,
                    self.filing_year_delta,
                )
            ):
                raise RegistryValidationError("relation period alignment mode cannot be combined with period fields")
            return self
        if self.source_periods is not None:
            if self.target_period is None:
                raise RegistryValidationError("relation period alignment source_periods requires target_period")
            if (
                self.source_period_kind is not None
                or self.source_period is not None
                or self.filing_year_delta is not None
            ):
                raise RegistryValidationError(
                    "relation period alignment source_periods cannot be combined with source_period_kind, "
                    "source_period, or filing_year_delta",
                )
            return self
        if self.source_period_kind is not None:
            if self.target_period is None:
                raise RegistryValidationError("relation period alignment source_period_kind requires target_period")
            if self.source_period is not None or self.filing_year_delta is not None:
                raise RegistryValidationError(
                    "relation period alignment source_period_kind cannot be combined with source_period "
                    "or filing_year_delta",
                )
            return self
        if self.source_period is not None:
            if self.target_period is None or self.filing_year_delta is None:
                raise RegistryValidationError(
                    "relation period alignment source_period requires target_period and filing_year_delta",
                )
            return self
        raise RegistryValidationError("relation period alignment declares target/delta fields without source alignment")


class RelationDefinition(RegistryModel):
    id: RelationId
    kind: Literal["previous_period", "annual_summary", "cross_model_output"]
    dependency_role: Literal[
        "periodic_to_annual_summary",
        "instalment_to_final_settlement",
        "direct_calculation",
        "factual_evidence",
    ]
    source_modelo: ModeloId
    source_revision_selector: RelationRevisionSelector
    source_casilla_id: CasillaId
    target_binding: BindingId
    period_alignment: RelationPeriodAlignment
    source_periods: tuple[RegistrySelectorPeriodCode, ...] = ()
    target_periods: tuple[RegistrySelectorPeriodCode, ...] = ()
    source_period_offset_from_target: int | None = None
    aggregation: RelationAggregation | None = None
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


# Single source of truth for the predicate-DSL operator names. The
# registry-load validator
# (_validate_surfaces.validate_verification_expectation_section)
# uses this set to reject unknown operators at authoring time. The
# runtime evaluator
# (cadrumo.application.modelo._verification_actions._evaluate_predicate_expression)
# carries its own regex per operator but MUST keep its set of operators
# identical to this constant — drift between the two sets is a
# silent-pass hazard at the predicate layer (a typo would silently pass
# the gate that's missing the operator). A gate test asserts the
# runtime evaluator recognises every name in this constant.
