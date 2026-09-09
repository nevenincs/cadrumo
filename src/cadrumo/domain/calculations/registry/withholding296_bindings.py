"""Modelo 296 perceptor row-set binding helpers.

Modelo 296 (IRNR retenciones, resumen anual) declares its own clave
vocabulary -- numeric renta-type claves with D/E naturaleza -- which the shared
:class:`~._withholding_bindings.WithholdingObservation` (claves A-L) cannot
carry, so this family holds its own observation type and selector validation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from ....core.aggregation import BindingAggregationOp
from ....core.country_code import CountryCodeAlpha2
from ....core.identity import TaxIdIdentityToken
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.percentage import PERCENTAGE_MIN, Percentage
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import (
    BindingExportDataType,
)
from .binding_selector_utils import (
    selector_as_dict as _selector_as_dict,
)
from .errors import RegistryValidationError
from .schema import DataBindingDefinition

__all__ = [
    "Withholding296Observation",
    "_Withholding296Selector",
    "validate_withholding296_binding_selector_shape",
]

_Withholding296RowField = Literal[
    "perceptor_tax_id",
    "representative_tax_id",
    "persona_juridica_flag",
    "perceptor_legal_name",
    "registro_orden",
    "codigo_bic",
    "fecha_devengo",
    "naturaleza",
    "clave",
    "subclave",
    "base_retenciones",
    "porcentaje_retencion",
    "retencion_practicada",
    "perceptor_mediador_flag",
    "codigo",
    "codigo_emisor",
    "pago",
    "tipo_codigo",
    "codigo_cuenta",
    "pendiente_flag",
    "accrual_year",
    "fecha_inicio_prestamo",
    "fecha_vencimiento_prestamo",
    "compensaciones",
    "garantias",
    "otros_importes",
    "direccion_perceptor",
    "ingreso_a_cuenta_repercutido",
    "nif_pagador_anterior",
    "procedimiento_especial_flag",
    "clave_mercado",
    "codigo_lei",
    "nif_pais_residencia",
    "fecha_nacimiento",
    "ciudad_nacimiento",
    "codigo_pais",
    "pais_residencia_fiscal",
]
_Withholding296Fact = Literal["row_field", "perceptor_count"]


class Withholding296Observation(BaseModel):
    """One Modelo 296 perceptor row: IRNR renta plus the payer's retentions."""

    model_config = STRICT_FROZEN_CONFIG

    source_id: str = Field(min_length=1, max_length=128)
    perceptor_tax_id: TaxIdIdentityToken = Field(min_length=1, max_length=64)
    representative_tax_id: TaxIdIdentityToken | None = Field(default=None, min_length=9, max_length=9)
    persona_juridica_flag: str | None = Field(default=None, max_length=1)
    perceptor_legal_name: str = Field(default="", max_length=200)
    codigo_bic: str | None = Field(default=None, max_length=6)
    fecha_devengo: str | None = Field(default=None, pattern=r"^\d{8}$")
    naturaleza: str = Field(default="D", pattern=r"^[DE]$")
    clave: str = Field(default="01", pattern=r"^\d{2}$")
    # The official 296 perceptor record declares subclave as a non-required
    # two-character slot, so an undeclared subclave is a legitimate empty
    # value rather than a code this model may invent one for.
    subclave: str = Field(default="", pattern=r"^(\d{2})?$")
    base_retenciones: Decimal = Decimal("0")
    porcentaje_retencion: Percentage = PERCENTAGE_MIN
    retencion_practicada: Decimal = Decimal("0")
    perceptor_mediador_flag: str | None = Field(default=None, max_length=1)
    codigo: str | None = Field(default=None, max_length=1)
    codigo_emisor: str | None = Field(default=None, max_length=12)
    pago: int | None = Field(default=None, ge=1, le=5)
    tipo_codigo: str | None = Field(default=None, pattern=r"^[COP]$")
    codigo_cuenta: str | None = Field(default=None, max_length=20)
    pendiente_flag: str | None = Field(default=None, max_length=1)
    accrual_year: int | None = Field(default=None, ge=1900, le=2100)
    fecha_inicio_prestamo: str | None = Field(default=None, pattern=r"^\d{8}$")
    fecha_vencimiento_prestamo: str | None = Field(default=None, pattern=r"^\d{8}$")
    compensaciones: Decimal = Decimal("0")
    garantias: Decimal = Decimal("0")
    otros_importes: Decimal = Decimal("0")
    direccion_perceptor: str | None = Field(default=None, max_length=162)
    ingreso_a_cuenta_repercutido: Decimal = Decimal("0")
    nif_pagador_anterior: TaxIdIdentityToken | None = Field(default=None, min_length=9, max_length=9)
    procedimiento_especial_flag: str | None = Field(default=None, max_length=1)
    clave_mercado: str | None = Field(default=None, pattern=r"^[A-D]$")
    codigo_lei: str | None = Field(default=None, max_length=20)
    # The perceptor's identifier in their OWN country, so it takes the
    # normalising token and never the checksum-validating alias: Modelo 296 is
    # IRNR withholding and this field exists precisely for a non-resident, whose
    # identifier no Spanish control character can validate. Normalising it still
    # matters -- the token is what grouping keys and stored rows compare on, and
    # an unfolded value makes two canonically-equal identifiers into two rollups.
    nif_pais_residencia: TaxIdIdentityToken | None = Field(default=None, max_length=20)
    fecha_nacimiento: str | None = Field(default=None, pattern=r"^\d{8}$")
    ciudad_nacimiento: str | None = Field(default=None, max_length=35)
    codigo_pais: CountryCodeAlpha2 | None = None
    pais_residencia_fiscal: CountryCodeAlpha2 | None = None
    transaction_date: date


class _Withholding296Selector(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    fact: _Withholding296Fact
    claves: tuple[str, ...] = ()
    row_field: _Withholding296RowField | None = None
    grouping: Literal["per_perceptor"] | None = None
    record: str | None = Field(default=None, min_length=1, max_length=64)
    data_type: BindingExportDataType | None = None


def _withholding296_selector(binding: DataBindingDefinition) -> _Withholding296Selector:
    try:
        return _Withholding296Selector.model_validate(_selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed withholding296 selector") from exc


def validate_withholding296_binding_selector_shape(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``withholding296`` binding's selector shape and fact/aggregation invariants."""
    try:
        selector = _withholding296_selector(binding)
    except ValueError as exc:
        return [
            f"binding {binding.id!r} (source={binding.source!r}) selector violates "
            f"{_Withholding296Selector.__name__}: {exc}",
        ]
    try:
        op = binding_aggregation_op(binding)
        if selector.fact == "row_field":
            if op != BindingAggregationOp.ROWS:
                raise RegistryValidationError("withholding296 fact 'row_field' requires aggregation op 'rows'")
            if selector.row_field is None:
                raise RegistryValidationError("withholding296 fact 'row_field' requires a 'row_field' selector key")
            if selector.grouping is None:
                raise RegistryValidationError("withholding296 fact 'row_field' requires a 'grouping' selector key")
        elif selector.fact == "perceptor_count":
            if op != BindingAggregationOp.COUNT_DISTINCT:
                raise RegistryValidationError(
                    "withholding296 fact 'perceptor_count' requires aggregation op 'count_distinct'"
                )
    except RegistryValidationError as exc:
        return [f"binding {binding.id!r} (source={binding.source!r}) withholding296 invariants violated: {exc}"]
    return []

