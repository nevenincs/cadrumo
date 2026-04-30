"""Mappings from spending categories to AEAT casilla codes."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...casillas import ModeloCode, PeriodType


class _StrictFrozenModel(BaseModel):
    """Shared strict immutable boundary model."""

    model_config = ConfigDict(strict=True, frozen=True)


class CasillaMappingSign(StrEnum):
    """Signed flow direction into a casilla bucket."""

    DEBIT = "debit"
    CREDIT = "credit"


class CasillaMapping(_StrictFrozenModel):
    """One category-to-casilla mapping for a filing modelo."""

    modelo: ModeloCode
    period_type: PeriodType
    casilla_code: str = Field(min_length=2, max_length=8)
    sign: CasillaMappingSign

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
