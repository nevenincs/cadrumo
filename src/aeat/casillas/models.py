"""Strict pydantic models for the casilla corpus."""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import StrEnum

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from ..i18n import Translatable, require_authoritative

KNOWN_MODELO_IDS = frozenset({"MODELO_130", "MODELO_303", "MODELO_390"})
_PERIOD_RE = re.compile(r"^\d{4}(Q[1-4]|-\d{2})?$")
_CASILLA_ID_RE = re.compile(r"^\d{2,4}$")


class _StrictFrozenModel(BaseModel):
    """Shared base class for strict immutable boundary models."""

    model_config = ConfigDict(strict=True, frozen=True)


class CasillaDataType(StrEnum):
    """Closed catalogue of casilla data types."""

    CURRENCY_EUR = "currency_eur"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    TEXT = "text"
    SELECT = "select"
    PERCENTAGE = "percentage"


class ModeloCode(StrEnum):
    """Stable modelo identifiers exposed by the public casillas API."""

    MODELO_130 = "MODELO_130"
    MODELO_303 = "MODELO_303"
    MODELO_390 = "MODELO_390"


class PeriodType(StrEnum):
    """Supported filing cadences for category-to-casilla mappings."""

    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class SelectOption(_StrictFrozenModel):
    """One selectable option for a select-style casilla."""

    value: str = Field(min_length=1, max_length=128)
    label: Translatable

    @model_validator(mode="after")
    def _require_spanish_label(self) -> SelectOption:
        try:
            require_authoritative(self.label, domain="aeat")
        except Exception as exc:
            raise ValueError(str(exc)) from exc
        return self


class LLMDraftProvenance(_StrictFrozenModel):
    """Metadata about an LLM-generated draft."""

    provider: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=128)
    prompt_id: str = Field(min_length=1, max_length=128)
    cache_hit: bool
    drafted_at: datetime


class FormulaReference(_StrictFrozenModel):
    """Temporary pydantic stand-in for issue #9 formula nodes."""

    expression: str = Field(min_length=1)
    references_casillas: tuple[str, ...] = Field(default_factory=tuple)


class ValidationRuleReference(_StrictFrozenModel):
    """Temporary pydantic stand-in for issue #9 validation rules."""

    rule: str = Field(min_length=1, max_length=64)
    value: str | int | float | bool | None = None
    description: str | None = Field(default=None, max_length=512)


class CasillaRecord(_StrictFrozenModel):
    """One canonical casilla entry for a modelo and period."""

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
    reviewed_by: str = Field(default="", max_length=64)
    reviewed_at: date | None = None
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
        except Exception as exc:
            raise ValueError(str(exc)) from exc
        if self.data_type is CasillaDataType.SELECT:
            if not self.select_options:
                raise ValueError("select_options are required when data_type=select")
        elif self.select_options is not None:
            raise ValueError("select_options are only allowed when data_type=select")
        return self


class CasillaCatalogue(_StrictFrozenModel):
    """In-memory catalogue for one modelo and period."""

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
