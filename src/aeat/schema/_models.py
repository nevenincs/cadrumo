"""Pydantic v2 models exposed by :mod:`aeat.schema`.

The module declares the typed intermediate representation every
:class:`~aeat.schema.Extractor` backend emits:

- :class:`SchemaProvenance` / :class:`SchemaVersion` — where the
  record came from and which pydantic shape version it conforms to.
- :class:`LiteralFormula`, :class:`CasillaRef`, :class:`BinaryOp`,
  :class:`SumFormula` — the evaluable formula AST referenced by the
  ``FormulaNode`` discriminated union.
- :class:`RangeRule`, :class:`RegexRule`, :class:`EnumRule`,
  :class:`CrossCasillaRule` — validation rule variants forming the
  ``ValidationRule`` discriminated union.
- :class:`Casilla` and :class:`Modelo` — the public, round-trippable
  extracted records.
- :func:`evaluate` — walks a ``FormulaNode`` against a casilla-value
  mapping and returns the resolved :class:`decimal.Decimal`.
- :func:`validate_period_for_modelo` — derives the period-string
  regex from the modelo's cadence metadata (no parallel cadence
  table lives here).
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from graphlib import CycleError, TopologicalSorter
from typing import Annotated, Literal

from pydantic import (
    AnyHttpUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from ..i18n import Translatable, TranslationError, require_authoritative
from ..models import ModeloCadence, ModeloCode, get_modelo
from ..portals import Portal
from ._enums import (
    BinaryFormulaOp,
    CasillaDataType,
    CompareOp,
    SchemaSource,
)
from ._errors import (
    SchemaExtractionError,
    SchemaValidationError,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CASILLA_ID_RE = re.compile(r"^\d{2,4}$")
_PERIOD_QUARTERLY_RE = re.compile(r"^\d{4}Q[1-4]$")
_PERIOD_ANNUAL_RE = re.compile(r"^\d{4}$")
_PERIOD_MONTHLY_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_PERIOD_AD_HOC_RE = re.compile(r"^\d{4}$")

_DIV_QUANT = Decimal("0.01")


class _StrictFrozenModel(BaseModel):
    """Shared base config for strict immutable boundary records."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        populate_by_name=True,
    )


class SchemaVersion(_StrictFrozenModel):
    """Schema-shape version carried alongside a :class:`Modelo`.

    Bumped when the :mod:`aeat.schema` pydantic hierarchy gains a
    field; independent of AEAT form revisions (those are tracked in
    :attr:`SchemaProvenance.document_ref`).
    """

    schema_version: int = Field(default=1, ge=1)
    boe_ref: str | None = Field(default=None, max_length=64)


class SchemaProvenance(_StrictFrozenModel):
    """Where a :class:`Modelo` record came from and how it was fetched."""

    source: SchemaSource
    origin_url: AnyHttpUrl
    document_ref: str = Field(min_length=1, max_length=64)
    sha256: str = Field(min_length=64, max_length=64)
    content_length: int = Field(ge=1)
    fetched_at: AwareDatetime

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        if not _SHA256_RE.fullmatch(value):
            raise ValueError(
                "sha256 must be 64 lowercase hexadecimal characters",
            )
        return value


class LiteralFormula(_StrictFrozenModel):
    """Numeric literal node in the formula AST."""

    kind: Literal["literal"] = "literal"
    value: Decimal


class CasillaRef(_StrictFrozenModel):
    """Reference to another casilla's runtime value."""

    kind: Literal["ref"] = "ref"
    casilla_id: str = Field(min_length=2, max_length=4)

    @field_validator("casilla_id")
    @classmethod
    def _validate_casilla_id(cls, value: str) -> str:
        if not _CASILLA_ID_RE.fullmatch(value):
            raise ValueError(f"invalid casilla id: {value!r}")
        return value


class BinaryOp(_StrictFrozenModel):
    """Binary arithmetic over two formula sub-trees."""

    kind: Literal["binop"] = "binop"
    op: BinaryFormulaOp
    left: FormulaNode
    right: FormulaNode


class SumFormula(_StrictFrozenModel):
    """Variadic sum over a non-empty tuple of sub-terms."""

    kind: Literal["sum"] = "sum"
    terms: tuple[FormulaNode, ...] = Field(min_length=1)


FormulaNode = Annotated[
    LiteralFormula | CasillaRef | BinaryOp | SumFormula,
    Field(discriminator="kind"),
]
"""Tagged union covering every formula AST node kind."""


class RangeRule(_StrictFrozenModel):
    """Numeric range rule; at least one bound must be set."""

    kind: Literal["range"] = "range"
    min_: Decimal | None = Field(default=None, alias="min")
    max_: Decimal | None = Field(default=None, alias="max")

    @model_validator(mode="after")
    def _validate_bounds(self) -> RangeRule:
        if self.min_ is None and self.max_ is None:
            raise ValueError("RangeRule requires at least one of min/max")
        if self.min_ is not None and self.max_ is not None and self.min_ > self.max_:
            raise ValueError("RangeRule: min must be <= max")
        return self


class RegexRule(_StrictFrozenModel):
    """Regex-pattern rule validated by :func:`re.compile` at parse time."""

    kind: Literal["regex"] = "regex"
    pattern: str = Field(min_length=1, max_length=1024)

    @field_validator("pattern")
    @classmethod
    def _validate_pattern(cls, value: str) -> str:
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError(f"invalid regex pattern: {exc}") from exc
        return value


class EnumRule(_StrictFrozenModel):
    """Enumeration rule whose ``values`` are a non-empty deduplicated tuple."""

    kind: Literal["enum"] = "enum"
    values: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_values(self) -> EnumRule:
        if len(set(self.values)) != len(self.values):
            raise ValueError("EnumRule values must be unique")
        if any(not v for v in self.values):
            raise ValueError("EnumRule values must be non-empty strings")
        return self


class CrossCasillaRule(_StrictFrozenModel):
    """Cross-casilla comparison rule over two formula sub-trees."""

    kind: Literal["cross"] = "cross"
    expression: FormulaNode
    compare: CompareOp
    rhs: FormulaNode


ValidationRule = Annotated[
    RangeRule | RegexRule | EnumRule | CrossCasillaRule,
    Field(discriminator="kind"),
]
"""Tagged union covering every validation rule kind."""


def _collect_refs(node: FormulaNode) -> frozenset[str]:
    """Return the set of casilla_ids referenced under a formula AST."""
    if isinstance(node, LiteralFormula):
        return frozenset()
    if isinstance(node, CasillaRef):
        return frozenset({node.casilla_id})
    if isinstance(node, BinaryOp):
        return _collect_refs(node.left) | _collect_refs(node.right)
    if isinstance(node, SumFormula):
        out: frozenset[str] = frozenset()
        for term in node.terms:
            out = out | _collect_refs(term)
        return out
    raise SchemaExtractionError(f"unknown formula node kind: {type(node)!r}")


def evaluate(node: FormulaNode, values: dict[str, Decimal]) -> Decimal:
    """Evaluate a formula AST against a casilla-value mapping.

    Args:
        node: Root of the formula AST.
        values: Mapping from casilla_id to its resolved
            :class:`~decimal.Decimal` value.

    Returns:
        The computed :class:`~decimal.Decimal`. Division results are
        quantised to two decimal places using ``ROUND_HALF_UP``.

    Raises:
        SchemaValidationError: If the AST references a casilla_id not
            present in ``values``.
        SchemaExtractionError: On division by zero.
    """
    if isinstance(node, LiteralFormula):
        return node.value
    if isinstance(node, CasillaRef):
        try:
            return values[node.casilla_id]
        except KeyError as exc:
            raise SchemaValidationError(
                f"formula references unknown casilla {node.casilla_id!r}",
            ) from exc
    if isinstance(node, BinaryOp):
        left = evaluate(node.left, values)
        right = evaluate(node.right, values)
        if node.op == BinaryFormulaOp.ADD:
            return left + right
        if node.op == BinaryFormulaOp.SUB:
            return left - right
        if node.op == BinaryFormulaOp.MUL:
            return left * right
        if node.op == BinaryFormulaOp.DIV:
            if right == 0:
                raise SchemaExtractionError("division by zero in formula AST")
            return (left / right).quantize(_DIV_QUANT, rounding=ROUND_HALF_UP)
        raise SchemaExtractionError(f"unknown binary op: {node.op!r}")
    if isinstance(node, SumFormula):
        total = Decimal("0")
        for term in node.terms:
            total = total + evaluate(term, values)
        return total
    raise SchemaExtractionError(f"unknown formula node kind: {type(node)!r}")


def validate_period_for_modelo(code: ModeloCode, period: str) -> None:
    """Assert that ``period`` matches the cadence shape of ``code``.

    Derived from the cadence metadata exposed by :mod:`aeat.models`;
    the module keeps no parallel cadence table of its own.

    Args:
        code: Modelo identifier.
        period: Filing period string (e.g. ``"2025Q4"``, ``"2025"``,
            ``"2025-03"``).

    Raises:
        SchemaValidationError: If ``period`` does not match the regex
            implied by the modelo's cadence, or if ``period`` carries
            leading / trailing whitespace (callers must strip first).
    """
    if period != period.strip():
        raise SchemaValidationError(
            f"period must not carry surrounding whitespace: {period!r}",
        )
    cadence = get_modelo(code).cadence
    if cadence == ModeloCadence.QUARTERLY:
        pattern = _PERIOD_QUARTERLY_RE
    elif cadence == ModeloCadence.ANNUAL:
        pattern = _PERIOD_ANNUAL_RE
    elif cadence == ModeloCadence.MONTHLY:
        pattern = _PERIOD_MONTHLY_RE
    elif cadence == ModeloCadence.AD_HOC:
        pattern = _PERIOD_AD_HOC_RE
    else:
        raise SchemaValidationError(f"unknown cadence: {cadence!r}")
    if not pattern.fullmatch(period):
        raise SchemaValidationError(
            f"period {period!r} does not match cadence {cadence.value!r}",
        )


class Casilla(_StrictFrozenModel):
    """A single numbered box inside an AEAT modelo.

    Attributes:
        casilla_id: Two- to four-digit AEAT casilla identifier.
        block: Optional heading the casilla sits under in the source
            document (Spanish authoritative).
        label: Trilingual label; Spanish is required. English and
            Hungarian MAY be absent in extracted records — they are
            filled downstream by the reviewer / translator workflow.
        data_type: Closed data-type enum.
        required: True when the AEAT form marks this casilla as
            required.
        computed: True iff ``formula`` is set (biconditional, enforced).
        formula: Optional formula AST when the casilla is derived from
            other casillas.
        validations: Tuple of additional rules.
        references_casillas: Tuple of casilla_ids the record
            references; must cover every ref found under ``formula``.
        source_page: Page of the source document the casilla was
            extracted from. Required when the owning modelo's
            provenance is ``BOE_ORDEN``.
    """

    casilla_id: str = Field(min_length=2, max_length=4)
    block: Translatable | None = None
    label: Translatable
    data_type: CasillaDataType
    required: bool = True
    computed: bool = False
    formula: FormulaNode | None = None
    validations: tuple[ValidationRule, ...] = Field(default_factory=tuple)
    references_casillas: tuple[str, ...] = Field(default_factory=tuple)
    source_page: int | None = Field(default=None, ge=1)

    @field_validator("casilla_id")
    @classmethod
    def _validate_casilla_id(cls, value: str) -> str:
        if not _CASILLA_ID_RE.fullmatch(value):
            raise ValueError(f"invalid casilla id: {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_casilla(self) -> Casilla:
        try:
            require_authoritative(self.label, domain="aeat")
        except TranslationError as exc:
            raise ValueError(str(exc)) from exc
        has_formula = self.formula is not None
        if has_formula != self.computed:
            raise ValueError(
                "Casilla.computed must be True iff Casilla.formula is set",
            )
        if self.formula is not None:
            referenced = _collect_refs(self.formula)
            declared = set(self.references_casillas)
            missing = referenced - declared
            if missing:
                raise ValueError(
                    f"Casilla.references_casillas must cover every formula ref; missing {sorted(missing)!r}",
                )
        if len(set(self.references_casillas)) != len(self.references_casillas):
            raise ValueError("Casilla.references_casillas must be unique")
        return self


class Modelo(_StrictFrozenModel):
    """The typed, versioned schema extracted for one modelo + period."""

    modelo_code: ModeloCode
    portal: Portal | None = None
    period: str = Field(min_length=4, max_length=16)
    casillas: tuple[Casilla, ...] = Field(min_length=1)
    provenance: SchemaProvenance
    extracted_at: AwareDatetime
    schema_version: SchemaVersion = Field(default_factory=SchemaVersion)

    @model_validator(mode="after")
    def _validate_modelo(self) -> Modelo:
        try:
            validate_period_for_modelo(self.modelo_code, self.period)
        except SchemaValidationError as exc:
            raise ValueError(str(exc)) from exc
        casilla_ids = [c.casilla_id for c in self.casillas]
        if len(set(casilla_ids)) != len(casilla_ids):
            raise ValueError("Modelo.casillas must have unique casilla_ids")
        id_set = set(casilla_ids)
        for casilla in self.casillas:
            for ref in casilla.references_casillas:
                if ref not in id_set:
                    raise ValueError(
                        f"Modelo references unknown casilla {ref!r} from casilla {casilla.casilla_id!r}",
                    )
        if self.provenance.source == SchemaSource.BOE_ORDEN:
            for casilla in self.casillas:
                if casilla.source_page is None:
                    raise ValueError(
                        "BOE_ORDEN provenance requires a source_page on every "
                        f"casilla; missing on {casilla.casilla_id!r}",
                    )
            if self.schema_version.boe_ref is None:
                raise ValueError(
                    "BOE_ORDEN provenance requires schema_version.boe_ref to be set for traceability",
                )
            if self.schema_version.boe_ref != self.provenance.document_ref:
                raise ValueError(
                    f"schema_version.boe_ref {self.schema_version.boe_ref!r} "
                    f"must match provenance.document_ref "
                    f"{self.provenance.document_ref!r}",
                )
        formula_graph: dict[str, set[str]] = {
            casilla.casilla_id: set(casilla.references_casillas) for casilla in self.casillas
        }
        try:
            TopologicalSorter(formula_graph).prepare()
        except CycleError as exc:
            raise ValueError(
                f"Modelo formula graph has a cycle: {exc.args[1] if len(exc.args) > 1 else exc}",
            ) from exc
        if self.portal is not None:
            from ..portals import get_portal

            metadata = get_portal(self.portal)
            if metadata.related_modelo != self.modelo_code:
                raise ValueError(
                    f"Modelo.portal {self.portal!r} relates to {metadata.related_modelo!r}, not {self.modelo_code!r}",
                )
        return self


BinaryOp.model_rebuild()
SumFormula.model_rebuild()
CrossCasillaRule.model_rebuild()
Casilla.model_rebuild()
Modelo.model_rebuild()
