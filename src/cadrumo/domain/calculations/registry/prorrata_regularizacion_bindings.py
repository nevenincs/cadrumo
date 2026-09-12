"""The annual prorrata regularisation provider and its landing casillas."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, field_validator

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.models import STRICT_FROZEN_CONFIG
from .errors import RegistryValidationError

__all__ = [
    "ProrrataRegularizacionOutput",
    "ProrrataRegularizacionOutputValue",
    "ProrrataRegularizacionProvider",
]


class ProrrataRegularizacionOutput(StrEnum):
    """Which casilla a prorrata regularizacion lands in."""

    MODELO_303_CASILLA_44 = "modelo_303_casilla_44"
    MODELO_390_REGULARIZACION_ANUAL = "modelo_390_regularizacion_anual"


ProrrataRegularizacionOutputValue = Literal[
    ProrrataRegularizacionOutput.MODELO_303_CASILLA_44,
    ProrrataRegularizacionOutput.MODELO_390_REGULARIZACION_ANUAL,
]
"""The same vocabulary for a strict model field."""


_PRORRATA_REGULARIZACION_SOURCE_IDS: tuple[CasillaId, ...] = (
    "iva.cuota-deducible-total",
    "iva.prorrata-volumen-con-derecho",
    "iva.prorrata-volumen-total",
    "iva.prorrata-porcentaje",
)
_PRORRATA_REGULARIZACION_SOURCE_PERIODS: tuple[str, ...] = ("1T", "2T", "3T", "4T")


class ProrrataRegularizacionProvider(BaseModel):
    """Selector for annual prorrata regularisation filing targets."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.PRORRATA_REGULARIZACION] = BindingSourceKind.PRORRATA_REGULARIZACION

    source_modelo: Literal["303"]
    source_casilla_ids: tuple[CasillaId, ...]
    source_periods: tuple[str, ...]
    regularizacion_output: ProrrataRegularizacionOutputValue

    @field_validator("source_casilla_ids")
    @classmethod
    def _source_casilla_ids_match_prorrata_inputs(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if value != _PRORRATA_REGULARIZACION_SOURCE_IDS:
            raise RegistryValidationError(
                "prorrata_regularizacion selector must declare the Modelo 303 deductible-total, "
                "annual prorrata volume, and definitive-percentage casilla ids in canonical order",
            )
        return value

    @field_validator("source_periods")
    @classmethod
    def _source_periods_are_full_year(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != _PRORRATA_REGULARIZACION_SOURCE_PERIODS:
            raise RegistryValidationError(
                "prorrata_regularizacion selector must declare source_periods ('1T', '2T', '3T', '4T')",
            )
        return value
