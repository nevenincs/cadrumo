"""Strict pydantic models for the casilla corpus.

Defines the immutable schema that every other module reads when it
asks "what does field X on modelo Y look like?". Every model is
``strict=True, frozen=True`` so the catalogue is safe to share by
reference and the schema rejects implicit type coercion.

The validators enforce:

* Real corpus data only: ``synthetic`` must always be ``False`` —
  the catalogue is sourced from BOE / Manual práctico, never from
  fixtures.
* :class:`~aeat.domain.modelos.ModeloCode` membership for the
  ``modelo`` field.
* ``YYYY``, ``YYYYQ[1-4]``, or ``YYYY-MM`` shape for ``period``.
* Authoritative Spanish text on every label, help, and select option.
* ``select_options`` if and only if ``data_type`` is
  :attr:`CasillaDataType.SELECT`.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import StrEnum

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from ...core.i18n import Translatable, TranslationError, require_authoritative
from ..modelos import ModeloCode

KNOWN_MODELO_IDS = frozenset(value for code in ModeloCode for value in (code.name, code.value))
_PERIOD_RE = re.compile(r"^\d{4}(Q[1-4]|-\d{2})?$")
_CASILLA_ID_RE = re.compile(r"^\d{2,5}$")  # widened for Modelo 200 5-digit IDs


class _SchemaStrictFrozenModel(BaseModel):
    """Shared base class for strict immutable boundary models."""

    model_config = ConfigDict(strict=True, frozen=True)


class CasillaDataType(StrEnum):
    """Closed catalogue of casilla data types.

    Attributes:
        CURRENCY_EUR: Euro-denominated monetary value.
        INTEGER: Plain integer count.
        BOOLEAN: Yes / no flag.
        DATE: ISO-8601 date.
        TEXT: Free-form text field.
        SELECT: One of an enumerated set of values; the record must
            also carry ``select_options``.
        PERCENTAGE: Percentage value.
    """

    CURRENCY_EUR = "currency_eur"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    TEXT = "text"
    SELECT = "select"
    PERCENTAGE = "percentage"


class PeriodType(StrEnum):
    """Supported filing cadences for category-to-casilla mappings.

    Attributes:
        QUARTERLY: Quarterly cadence (e.g. ``2025Q4``).
        ANNUAL: Annual cadence (e.g. ``2025``).
    """

    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class SelectOption(_SchemaStrictFrozenModel):
    """One selectable option for a ``select``-typed casilla.

    Attributes:
        value: Stable machine identifier sent to AEAT.
        label: Authoritative Spanish (and optional translated)
            display label. Must carry non-empty ``es`` text per
            :func:`aeat.core.i18n.require_authoritative`.
    """

    value: str = Field(min_length=1, max_length=128)
    label: Translatable

    @model_validator(mode="after")
    def _require_spanish_label(self) -> SelectOption:
        try:
            require_authoritative(self.label, domain="aeat")
        except TranslationError as exc:
            raise ValueError(str(exc)) from exc
        return self


class LLMDraftProvenance(_SchemaStrictFrozenModel):
    """Provenance metadata for an LLM-generated draft record.

    Attributes:
        provider: Vendor / provider identifier of the LLM.
        model: Concrete model identifier within the provider.
        prompt_id: Stable identifier of the prompt template used.
        cache_hit: Whether the response came from a cached call.
        drafted_at: Wall-clock timestamp the draft was produced.
    """

    provider: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=128)
    prompt_id: str = Field(min_length=1, max_length=128)
    cache_hit: bool
    drafted_at: datetime


class FormulaReference(_SchemaStrictFrozenModel):
    """Lightweight pydantic stand-in for a formula node.

    Carries just enough shape for the casilla schema to reference
    formulas by expression text and the casillas they consume; the
    full evaluation engine lives in :mod:`aeat.domain.formulas`.

    Attributes:
        expression: Raw formula expression string.
        references_casillas: Casilla ids the formula reads.
    """

    expression: str = Field(min_length=1)
    references_casillas: tuple[str, ...] = Field(default_factory=tuple)


class ValidationRuleReference(_SchemaStrictFrozenModel):
    """Lightweight pydantic stand-in for a validation rule node.

    Attributes:
        rule: Rule identifier.
        value: Optional comparison / threshold value.
        description: Optional human-readable explanation.
    """

    rule: str = Field(min_length=1, max_length=64)
    value: str | int | float | bool | None = None
    description: str | None = Field(default=None, max_length=512)


class CasillaRecord(_SchemaStrictFrozenModel):
    """One canonical casilla entry for a modelo / period.

    Attributes:
        synthetic: Must be ``False`` — the corpus is real data only.
        modelo: Modelo identifier (e.g. ``"MODELO_303"``).
        period: Period label, validated against the
            ``YYYY[Q[1-4]|-MM]`` shape.
        casilla_id: 2 to 5 digit casilla identifier.
        label: Authoritative Spanish (and optional translated) label.
        help: Authoritative Spanish (and optional translated) help.
        data_type: One of :class:`CasillaDataType`.
        select_options: Allowed options when ``data_type`` is
            :attr:`CasillaDataType.SELECT`; must be ``None``
            otherwise.
        required: Whether the casilla is mandatory on the form.
        computed: Whether the value is computed from other casillas
            via a formula in the engine registry.
        formula: Optional :class:`FormulaReference` describing the
            calculation.
        references_casillas: Other casilla ids this record's
            formula or validation rules read.
        references_rules: Engine ``formula_id`` strings this record
            is bound to.
        validation: Tuple of validation-rule references.
        source_manual_url: Optional URL into the source manual or
            BOE order.
        source_page: Optional page reference inside the source
            document.
        source_section: Optional section heading inside the source
            document.
        definition_reviewed_by: Reviewer id; required when the
            project is configured to enforce review metadata.
        definition_reviewed_at: Review date; required when the
            project is configured to enforce review metadata.
        llm_draft_provenance: Optional provenance attached to LLM-
            drafted records before human review.
    """

    synthetic: bool = Field(default=False)
    modelo: str = Field(min_length=1, max_length=64)
    period: str = Field(min_length=4, max_length=16)
    casilla_id: str = Field(min_length=2, max_length=8)
    label: Translatable
    help: Translatable
    data_type: CasillaDataType
    select_options: tuple[SelectOption, ...] | None = None
    required: bool
    computed: bool
    formula: FormulaReference | None = None
    references_casillas: tuple[str, ...] = Field(default_factory=tuple)
    references_rules: tuple[str, ...] = Field(default_factory=tuple)
    validation: tuple[ValidationRuleReference, ...] = Field(default_factory=tuple)
    source_manual_url: AnyHttpUrl | None = None
    source_page: int | None = Field(default=None, ge=1)
    source_section: str | None = Field(default=None, max_length=128)
    definition_reviewed_by: str = Field(default="", max_length=64)
    definition_reviewed_at: date | None = None
    llm_draft_provenance: LLMDraftProvenance | None = None

    @model_validator(mode="after")
    def _validate_record(self) -> CasillaRecord:
        if self.synthetic:
            raise ValueError("casilla records must be real corpus data and use synthetic=false")
        if self.modelo not in KNOWN_MODELO_IDS:
            raise ValueError(f"unsupported modelo id: {self.modelo}")
        if not _PERIOD_RE.fullmatch(self.period):
            raise ValueError(f"invalid period format: {self.period}")
        if not _CASILLA_ID_RE.fullmatch(self.casilla_id):
            raise ValueError(f"invalid casilla id: {self.casilla_id}")
        try:
            require_authoritative(self.label, domain="aeat")
            require_authoritative(self.help, domain="aeat")
        except TranslationError as exc:
            raise ValueError(str(exc)) from exc
        if self.data_type is CasillaDataType.SELECT:
            if not self.select_options:
                raise ValueError("select_options are required when data_type=select")
        elif self.select_options is not None:
            raise ValueError("select_options are only allowed when data_type=select")
        return self


class CasillaCatalogue(_SchemaStrictFrozenModel):
    """In-memory catalogue for one modelo / period.

    The catalogue's records must all share the catalogue's
    ``modelo`` and ``period``; duplicate casilla ids are rejected
    by the validator. A private ``_index`` is materialised for
    O(1) :meth:`get` lookups.

    Attributes:
        modelo: Modelo identifier (e.g. ``"MODELO_303"``).
        period: Period label, validated against the
            ``YYYY[Q[1-4]|-MM]`` shape.
        records: Tuple of :class:`CasillaRecord` entries.
    """

    modelo: str = Field(min_length=1, max_length=64)
    period: str = Field(min_length=4, max_length=16)
    records: tuple[CasillaRecord, ...] = Field(default_factory=tuple)

    _index: dict[tuple[str, str, str], CasillaRecord] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def _validate_catalogue(self) -> CasillaCatalogue:
        if self.modelo not in KNOWN_MODELO_IDS:
            raise ValueError(f"unsupported modelo id: {self.modelo}")
        if not _PERIOD_RE.fullmatch(self.period):
            raise ValueError(f"invalid period format: {self.period}")

        index: dict[tuple[str, str, str], CasillaRecord] = {}
        for record in self.records:
            if record.modelo != self.modelo:
                raise ValueError("all records must match catalogue.modelo")
            if record.period != self.period:
                raise ValueError("all records must match catalogue.period")
            key = (record.modelo, record.period, record.casilla_id)
            if key in index:
                raise ValueError(f"duplicate casilla key: {record.casilla_id}")
            index[key] = record
        self._index = index
        return self

    def get(self, casilla_id: str) -> CasillaRecord | None:
        """Return a record by casilla identifier.

        Args:
            casilla_id: Casilla identifier inside this catalogue.

        Returns:
            The matching record or ``None`` if absent.
        """
        return self._index.get((self.modelo, self.period, casilla_id))
