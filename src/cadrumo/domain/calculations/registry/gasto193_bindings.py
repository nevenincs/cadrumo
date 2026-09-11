"""Modelo 193 gastos-relationship row-set binding helpers.

Modelo 193's hoja anexo (registro tipo 2, relación de gastos) carries one row
per contribuyente for whom the declarante perceived the art. 26.1.a) LIRPF
gastos de administracion y deposito de valores. This family validates the
observation and binding-selector shapes consumed by row-set ingestion. The
required declarante total is a separate explicit input until a secure
observation owner exists.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from ....core.aggregation import BindingAggregationOp
from ....core.identity.tax_id import TaxIdIdentityToken
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import (
    selector_as_dict as _selector_as_dict,
)
from .errors import RegistryValidationError
from .schema import DataBindingDefinition
from .schema_exports import ExportFieldDataType

__all__ = [
    "Gasto193Observation",
    "_Gasto193Selector",
    "validate_gasto193_binding_selector_shape",
]

_Gasto193RowField = Literal[
    "contributor_tax_id",
    "contributor_legal_name",
    "representative_tax_id",
    "importe_gastos",
]
_Gasto193Fact = Literal["row_field"]


class Gasto193Observation(BaseModel):
    """One modelo 193 gastos-relationship row: contribuyente plus annual gastos."""

    model_config = STRICT_FROZEN_CONFIG

    source_id: str = Field(min_length=1, max_length=128)
    contributor_tax_id: TaxIdIdentityToken = Field(min_length=1, max_length=64)
    contributor_legal_name: str = Field(default="", max_length=200)
    representative_tax_id: TaxIdIdentityToken | None = Field(default=None, min_length=9, max_length=9)
    """NIF of the minor's legal representative, declared by the design only when
    the contribuyente is a minor; spaces elsewhere."""
    transaction_date: date
    importe_gastos: Decimal = Decimal("0")
    """The annual gastos de administracion y deposito amount (positions 195-206),
    the design's own zeros when none."""

    def _non_negative_gastos(self) -> None:
        if self.importe_gastos < Decimal("0"):
            raise RegistryValidationError("gasto amounts must be non-negative")


class _Gasto193Selector(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    fact: _Gasto193Fact
    claves: tuple[str, ...] = ()
    row_field: _Gasto193RowField | None = None
    grouping: Literal["per_gasto193_contribuyente"] | None = None
    record: str | None = Field(default=None, min_length=1, max_length=64)
    data_type: ExportFieldDataType | None = None


def _gasto193_selector(binding: DataBindingDefinition) -> _Gasto193Selector:
    try:
        return _Gasto193Selector.model_validate(_selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed gasto193 selector") from exc


def validate_gasto193_binding_selector_shape(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``gasto193`` binding's selector shape and fact/aggregation invariants."""
    try:
        selector = _gasto193_selector(binding)
    except ValueError as exc:
        return [
            f"binding {binding.id!r} (source={binding.source!r}) selector violates {_Gasto193Selector.__name__}: {exc}",
        ]
    try:
        op = binding_aggregation_op(binding)
        if selector.fact == "row_field":
            if op != BindingAggregationOp.ROWS:
                raise RegistryValidationError("gasto193 fact 'row_field' requires aggregation op 'rows'")
            if selector.row_field is None:
                raise RegistryValidationError("gasto193 fact 'row_field' requires a 'row_field' selector key")
            if selector.grouping is None:
                raise RegistryValidationError("gasto193 fact 'row_field' requires a 'grouping' selector key")
    except RegistryValidationError as exc:
        return [f"binding {binding.id!r} (source={binding.source!r}) gasto193 invariants violated: {exc}"]
    return []
