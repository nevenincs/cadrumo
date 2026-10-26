"""Modelo 193 gastos-relationship row-set binding helpers.

Modelo 193's hoja anexo (registro tipo 2, relación de gastos) carries one row
per contribuyente for whom the declarante perceived the art. 26.1.a) LIRPF
gastos de administracion y deposito de valores. This family validates the
binding-selector shapes for this deferred detail-record provider. No secure
observation owner or executable ingestion route is enrolled. The required
declarante total remains a separate explicit input.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import (
    provider_member,
)
from .errors import RegistryValidationError
from .schema_exports import ExportFieldDataType

if TYPE_CHECKING:
    from .schema import BindingDefinition

__all__ = [
    "Gasto193ContributorProvider",
    "validate_gasto193_binding_selector_shape",
]

_Gasto193RowField = Literal[
    "contributor_tax_id",
    "contributor_legal_name",
    "representative_tax_id",
    "importe_gastos",
]
_Gasto193Fact = Literal["row_field"]


def _runtime_object(value: object) -> object:
    """Capture a selector token before applying its runtime invariant check."""
    return value


class Gasto193ContributorProvider(BaseModel):
    """Typed selector for deferred Modelo 193 expense-contributor bindings."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.GASTO193_CONTRIBUTOR] = BindingSourceKind.GASTO193_CONTRIBUTOR

    fact: _Gasto193Fact
    claves: tuple[str, ...] = ()
    row_field: _Gasto193RowField | None = None
    grouping: Literal["per_gasto193_contribuyente"] | None = None
    record: str | None = Field(default=None, min_length=1, max_length=64)
    data_type: ExportFieldDataType | None = None


def _gasto193_selector(binding: BindingDefinition) -> Gasto193ContributorProvider:
    return provider_member(binding, Gasto193ContributorProvider)


def validate_gasto193_binding_selector_shape(binding: BindingDefinition) -> list[str]:
    """Validate a ``gasto193`` binding's fact/aggregation invariants.

    The provider shape is the union member's own gate; only the fact/op
    cross-invariant needs lifting to build time.
    """
    selector = _gasto193_selector(binding)
    try:
        op = binding_aggregation_op(binding)
        fact = _runtime_object(selector.fact)
        if fact == "row_field":
            if op != BindingAggregationOp.ROWS:
                raise RegistryValidationError("gasto193 fact 'row_field' requires aggregation op 'rows'")
            if selector.row_field is None:
                raise RegistryValidationError("gasto193 fact 'row_field' requires a 'row_field' selector key")
            if selector.grouping is None:
                raise RegistryValidationError("gasto193 fact 'row_field' requires a 'grouping' selector key")
    except RegistryValidationError as exc:
        return [f"binding {binding.id!r} (source={binding.source!r}) gasto193 invariants violated: {exc}"]
    return []
