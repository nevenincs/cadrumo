"""Mappings from spending categories to AEAT casilla codes.

Defines the closed enum / model pair that links one
:class:`~aeat.domain.categories.SpendingCategory` (held inside a
:class:`~aeat.domain.categories.CategoryProfile`) to the casilla
buckets it feeds on a given AEAT modelo. The validator enforces the
period-cadence rules baked into the autónomo modelo set: 390 is
annual; 130 and 303 are quarterly.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..casillas import ModeloCode, PeriodType


class _CategoryMappingStrictFrozenModel(BaseModel):
    """Shared strict immutable boundary model."""

    model_config = ConfigDict(strict=True, frozen=True)


class CasillaMappingSign(StrEnum):
    """Signed flow direction into a casilla bucket.

    Attributes:
        DEBIT: The category contributes to the debit / outgoing
            side of the casilla.
        CREDIT: The category contributes to the credit / incoming
            side of the casilla.
    """

    DEBIT = "debit"
    CREDIT = "credit"


class CasillaMapping(_CategoryMappingStrictFrozenModel):
    """One category-to-casilla mapping for a filing modelo.

    Attributes:
        modelo: Target :class:`~aeat.domain.casillas.ModeloCode`.
        period_type: Filing cadence; must satisfy the modelo's
            cadence rules (annual for 390; quarterly for 130 / 303).
        casilla_code: Numeric casilla identifier (string-typed so
            leading zeros survive round-trips).
        sign: Flow direction encoded by :class:`CasillaMappingSign`.
    """

    modelo: ModeloCode
    period_type: PeriodType
    casilla_code: str = Field(min_length=2, max_length=8)
    sign: CasillaMappingSign

    @field_validator("period_type", mode="before")
    @classmethod
    def _coerce_period_type(cls, value: object) -> object:
        if isinstance(value, str):
            return PeriodType(value.lower())
        return value

    @model_validator(mode="after")
    def _validate_period_type(self) -> CasillaMapping:
        if self.modelo is ModeloCode.MODELO_390 and self.period_type is not PeriodType.ANNUAL:
            raise ValueError("MODELO_390 mappings must be annual")
        if (
            self.modelo in {ModeloCode.MODELO_130, ModeloCode.MODELO_303}
            and self.period_type is not PeriodType.QUARTERLY
        ):
            raise ValueError("MODELO_130 and MODELO_303 mappings must be quarterly")
        return self
