"""The annual IVA-compensation partition provider.

Modelo 390's boxes 97 and 662 are two halves of ONE FIFO partition of the
compensation the taxpayer carried through the year, which is why both read the
same four Modelo 303 state casillas over the same four quarters and differ only
in which half of the partition they take.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, field_validator

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.models import STRICT_FROZEN_CONFIG
from .errors import RegistryValidationError

__all__ = [
    "M303_COMPENSATION_APLICADA_CASILLA",
    "M303_COMPENSATION_AVAILABLE_CASILLA",
    "M303_COMPENSATION_GENERADA_CASILLA",
    "M303_COMPENSATION_PENDING_PRIOR_CASILLA",
    "M303_COMPENSATION_POSTERIOR_CASILLA",
    "M303_COMPENSATION_RESULTADO_CASILLA",
    "M303_COMPENSATION_RESULTADO_FINAL_CASILLA",
    "M390_COMPENSATION_GENERATED_OUTSIDE_LAST_PERIOD_CASILLA",
    "M390_COMPENSATION_LAST_PERIOD_CASILLA",
    "IvaCompensationAnnualPartition",
    "IvaCompensationAnnualPartitionProvider",
    "IvaCompensationAnnualPartitionValue",
]


class IvaCompensationAnnualPartition(StrEnum):
    """Which half of the annual IVA compensation partition a binding reads."""

    LAST_PERIOD_AMOUNT = "last_period_amount"
    GENERATED_NOT_IN_LAST_AMOUNT = "generated_not_in_last_amount"


IvaCompensationAnnualPartitionValue = Literal[
    IvaCompensationAnnualPartition.LAST_PERIOD_AMOUNT,
    IvaCompensationAnnualPartition.GENERATED_NOT_IN_LAST_AMOUNT,
]
"""The same vocabulary for a strict model field."""


#: The Modelo 303 and 390 casillas that carry the compensation state a filing
#: leaves behind. They are registry vocabulary, so they are declared once here
#: and read from here by every consumer rather than re-spelled per caller.
M303_COMPENSATION_AVAILABLE_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-disponible-fin-periodo",
    surface="M303_COMPENSATION_AVAILABLE_CASILLA",
)
M303_COMPENSATION_POSTERIOR_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-posteriores",
    surface="M303_COMPENSATION_POSTERIOR_CASILLA",
)
M303_COMPENSATION_GENERADA_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-generada-periodo",
    surface="M303_COMPENSATION_GENERADA_CASILLA",
)
M303_COMPENSATION_APLICADA_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-aplicada-periodo",
    surface="M303_COMPENSATION_APLICADA_CASILLA",
)
M303_COMPENSATION_RESULTADO_CASILLA: CasillaId = validated_casilla_id(
    "iva.resultado",
    surface="M303_COMPENSATION_RESULTADO_CASILLA",
)
M303_COMPENSATION_PENDING_PRIOR_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores",
    surface="M303_COMPENSATION_PENDING_PRIOR_CASILLA",
)
M303_COMPENSATION_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id(
    "71",
    surface="M303_COMPENSATION_RESULTADO_FINAL_CASILLA",
)
M390_COMPENSATION_GENERATED_OUTSIDE_LAST_PERIOD_CASILLA: CasillaId = validated_casilla_id(
    "iva.anual.compensacion-generada-ejercicio-no-97",
    surface="M390_COMPENSATION_GENERATED_OUTSIDE_LAST_PERIOD_CASILLA",
)

M390_COMPENSATION_LAST_PERIOD_CASILLA: CasillaId = validated_casilla_id(
    "iva.anual.compensacion-ultimo-periodo-97",
    surface="M390_COMPENSATION_LAST_PERIOD_CASILLA",
)

_IVA_COMPENSATION_ANNUAL_PARTITION_SOURCE_IDS: tuple[CasillaId, ...] = (
    M303_COMPENSATION_GENERADA_CASILLA,
    M303_COMPENSATION_APLICADA_CASILLA,
    M303_COMPENSATION_AVAILABLE_CASILLA,
    M303_COMPENSATION_POSTERIOR_CASILLA,
)
_IVA_COMPENSATION_ANNUAL_PARTITION_PERIODS: tuple[str, ...] = ("1T", "2T", "3T", "4T")


class IvaCompensationAnnualPartitionProvider(BaseModel):
    """Selector for Modelo 390 AEAT boxes 97 / 662 as one FIFO partition."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION] = (
        BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION
    )

    source_modelo: Literal["303"]
    source_casilla_ids: tuple[CasillaId, ...]
    source_periods: tuple[str, ...]
    partition_output: IvaCompensationAnnualPartitionValue

    @field_validator("source_casilla_ids")
    @classmethod
    def _source_casilla_ids_match_fifo_state(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if value != _IVA_COMPENSATION_ANNUAL_PARTITION_SOURCE_IDS:
            raise RegistryValidationError(
                "iva_compensation_annual_partition selector must declare the current Modelo 303 "
                "compensation state casilla ids in canonical order",
            )
        return value

    @field_validator("source_periods")
    @classmethod
    def _source_periods_are_full_year(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != _IVA_COMPENSATION_ANNUAL_PARTITION_PERIODS:
            raise RegistryValidationError(
                "iva_compensation_annual_partition selector must declare source_periods ('1T', '2T', '3T', '4T')",
            )
        return value
