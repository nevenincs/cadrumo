"""Modelo 296 perceptor row-set binding helpers.

Modelo 296 (IRNR retenciones, resumen anual) declares its own clave
vocabulary -- numeric renta-type claves with D/E naturaleza -- which the shared
:class:`~._withholding_bindings.WithholdingObservation` (claves A-L) cannot
carry, so this family holds its own observation type and row builder.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG
from ....core.aggregation import BindingAggregationOp
from ....core.identity import TaxIdIdentityToken
from ....core.percentage import PERCENTAGE_MIN, Percentage
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import (
    BindingExportDataType,
)
from .binding_selector_utils import (
    selector_as_dict as _selector_as_dict,
)
from .errors import RegistryValidationError
from .schema import DataBindingDefinition, ModeloRevision

__all__ = [
    "Withholding296Observation",
    "_Withholding296Selector",
    "resolve_withholding296_binding_row_values",
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
    representative_tax_id: str | None = Field(default=None, min_length=9, max_length=9)
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
    nif_pagador_anterior: str | None = Field(default=None, min_length=9, max_length=9)
    procedimiento_especial_flag: str | None = Field(default=None, max_length=1)
    clave_mercado: str | None = Field(default=None, pattern=r"^[A-D]$")
    codigo_lei: str | None = Field(default=None, max_length=20)
    nif_pais_residencia: str | None = Field(default=None, max_length=20)
    fecha_nacimiento: str | None = Field(default=None, pattern=r"^\d{8}$")
    ciudad_nacimiento: str | None = Field(default=None, max_length=35)
    codigo_pais: str | None = Field(default=None, min_length=2, max_length=2)
    pais_residencia_fiscal: str | None = Field(default=None, min_length=2, max_length=2)
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


def resolve_withholding296_binding_values(
    revision: ModeloRevision,
    observations: Iterable[Withholding296Observation],
) -> dict[str, Decimal]:
    available = tuple(observations)
    resolved: dict[str, Decimal] = {}
    for binding in revision.bindings:
        if str(getattr(binding, "source", "")) != "withholding296":
            continue
        selector = _withholding296_selector(binding)
        if selector.fact == "perceptor_count":
            resolved[str(binding.id)] = Decimal(len({obs.perceptor_tax_id for obs in available}))
    return resolved


def _build_withholding296_rows(
    observations: tuple[Withholding296Observation, ...],
) -> tuple[Mapping[str, Decimal | str], ...]:
    accum: dict[tuple[str, str, str, str], dict[str, Decimal | str]] = {}
    for observation in observations:
        key = (
            observation.codigo_pais or "",
            observation.perceptor_tax_id,
            observation.clave,
            observation.subclave,
        )
        identity: dict[str, Decimal | str] = {
            "perceptor_tax_id": observation.perceptor_tax_id,
            "perceptor_legal_name": observation.perceptor_legal_name,
            "naturaleza": observation.naturaleza,
            "clave": observation.clave,
            "subclave": observation.subclave,
            "base_retenciones": Decimal("0"),
            "porcentaje_retencion": Decimal("0"),
            "retencion_practicada": Decimal("0"),
            "compensaciones": Decimal("0"),
            "garantias": Decimal("0"),
            "otros_importes": Decimal("0"),
            "ingreso_a_cuenta_repercutido": Decimal("0"),
        }
        for field in (
            "representative_tax_id",
            "persona_juridica_flag",
            "codigo_bic",
            "fecha_devengo",
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
            "direccion_perceptor",
            "nif_pagador_anterior",
            "procedimiento_especial_flag",
            "clave_mercado",
            "codigo_lei",
            "nif_pais_residencia",
            "fecha_nacimiento",
            "ciudad_nacimiento",
            "codigo_pais",
            "pais_residencia_fiscal",
        ):
            value = getattr(observation, field)
            if value is not None:
                identity[field] = value
        bucket = accum.setdefault(key, identity)
        for amount_field in (
            "base_retenciones",
            "porcentaje_retencion",
            "retencion_practicada",
            "compensaciones",
            "garantias",
            "otros_importes",
            "ingreso_a_cuenta_repercutido",
        ):
            previous = bucket[amount_field]
            assert isinstance(previous, Decimal)
            bucket[amount_field] = previous + getattr(observation, amount_field)
    rows: list[dict[str, Decimal | str]] = []
    for index, key in enumerate(sorted(accum.keys()), start=1):
        row = dict(accum[key])
        row["registro_orden"] = str(index)
        if "representative_tax_id" not in row:
            row["representative_tax_id"] = " " * 9
        if "nif_pagador_anterior" not in row:
            row["nif_pagador_anterior"] = " " * 9
        if "codigo_cuenta" not in row:
            row["codigo_cuenta"] = " " * 20
        if "codigo_emisor" not in row:
            row["codigo_emisor"] = " " * 12
        if "codigo_lei" not in row:
            row["codigo_lei"] = " " * 20
        if "nif_pais_residencia" not in row:
            row["nif_pais_residencia"] = " " * 20
        if "direccion_perceptor" not in row:
            row["direccion_perceptor"] = " " * 162
        if "accrual_year" not in row:
            row["accrual_year"] = "0000"
        if "fecha_inicio_prestamo" not in row:
            row["fecha_inicio_prestamo"] = "0" * 8
        if "fecha_vencimiento_prestamo" not in row:
            row["fecha_vencimiento_prestamo"] = "0" * 8
        if "fecha_devengo" not in row:
            row["fecha_devengo"] = "0" * 8
        if "fecha_nacimiento" not in row:
            row["fecha_nacimiento"] = "0" * 8
        rows.append(row)
    return tuple(rows)


def resolve_withholding296_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[Withholding296Observation],
) -> dict[tuple[str, int], Decimal | str]:
    """Resolve every ``withholding296`` ``row_field`` binding to its per-row perceptor value."""
    available = tuple(observations)
    rows = _build_withholding296_rows(available)
    resolved: dict[tuple[str, int], Decimal | str] = {}
    for binding in revision.bindings:
        if str(getattr(binding, "source", "")) != "withholding296":
            continue
        selector = _withholding296_selector(binding)
        if selector.fact != "row_field":
            continue
        assert selector.row_field is not None
        for row_index, row in enumerate(rows, start=1):
            value = row.get(selector.row_field)
            if value is None:
                raise RegistryValidationError(
                    f"binding {binding.id!r} row_field {selector.row_field!r} not produced "
                    f"for withholding296 row {row_index}",
                )
            resolved[(str(binding.id), row_index)] = value
    return resolved
