"""Modelo 296 perceptor row-set binding helpers.

Modelo 296 (IRNR retenciones, resumen anual) has its own perceptor field
vocabulary. This family declares the typed provider selector and validates its
aggregation invariants. Its provider registration remains deferred without an
executable observation route; filing detail rows are supplied through the typed
producer snapshot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import provider_member
from .errors import RegistryValidationError
from .schema_exports import ExportFieldDataType

if TYPE_CHECKING:
    from .schema import BindingDefinition

__all__ = [
    "Withholding296Provider",
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


def _runtime_object(value: object) -> object:
    """Capture a selector token before applying its runtime invariant check."""
    return value


class Withholding296Provider(BaseModel):
    """Typed selector for deferred Modelo 296 non-resident withholding bindings."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.WITHHOLDING296] = BindingSourceKind.WITHHOLDING296

    fact: _Withholding296Fact
    claves: tuple[str, ...] = ()
    row_field: _Withholding296RowField | None = None
    grouping: Literal["per_perceptor"] | None = None
    record: str | None = Field(default=None, min_length=1, max_length=64)
    data_type: ExportFieldDataType | None = None


def validate_withholding296_binding_selector_shape(binding: BindingDefinition) -> list[str]:
    """Validate a ``withholding296`` binding's selector shape and fact/aggregation invariants."""
    selector = provider_member(binding, Withholding296Provider)
    try:
        op = binding_aggregation_op(binding)
        fact = _runtime_object(selector.fact)
        if fact == "row_field":
            if op != BindingAggregationOp.ROWS:
                raise RegistryValidationError("withholding296 fact 'row_field' requires aggregation op 'rows'")
            if selector.row_field is None:
                raise RegistryValidationError("withholding296 fact 'row_field' requires a 'row_field' selector key")
            if selector.grouping is None:
                raise RegistryValidationError("withholding296 fact 'row_field' requires a 'grouping' selector key")
        elif fact == "perceptor_count":
            if op != BindingAggregationOp.COUNT_DISTINCT:
                raise RegistryValidationError(
                    "withholding296 fact 'perceptor_count' requires aggregation op 'count_distinct'"
                )
    except RegistryValidationError as exc:
        return [f"binding {binding.id!r} (source={binding.source!r}) withholding296 invariants violated: {exc}"]
    return []
