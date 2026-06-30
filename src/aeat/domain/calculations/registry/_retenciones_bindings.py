"""Retenciones-aggregation registry binding helpers (RET-1).

The per-family module for the ``retenciones_aggregation`` binding source — the
calc-mesh source that materialises retenciones-family scalars from the dedicated
per-perceptor retención store.
Extracted as its own family module per ``registry-resolver-family-extraction``;
the cross-family validator dispatch in :mod:`._bindings` registers this family's
``validate(binding) -> list[str]`` entry.

The materialisation depends on a :class:`_RetencionesAggregationProtocol` rather
than the application-layer ``RetencionesAggregation``, so the domain layer stays
independent of the application aggregation service.

The resolver walks the declared :class:`ModeloRevision` bindings and emits only
canonical binding values for this source family.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from ....core import BindingSourceKind
from ._binding_selector_utils import selector_against_model
from ._binding_selector_utils import selector_as_dict as _selector_as_dict
from ._ids import BindingId, CasillaId
from ._schema import DataBindingDefinition, ModeloRevision


class _RetencionesAggregationProtocol(Protocol):
    """The scalar totals the retenciones-aggregation source materialises."""

    @property
    def total_perceptors(self) -> int: ...

    @property
    def total_taxable_base(self) -> Decimal: ...

    @property
    def total_retencion(self) -> Decimal: ...


class _RetencionesAggregationSelector(BaseModel):
    """Validated form of a ``retenciones_aggregation`` binding selector.

    Carries the target casilla id and the scalar fact this source serves. Annual
    summary modelos still keep their monetary totals on relation-prefill
    bindings; Modelo 115 uses the same per-perceptor store directly for its
    quarterly perceptor count and taxable base.
    """

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

    target_casilla_id: CasillaId
    fact: Literal["perceptor_count_distinct", "taxable_base_sum", "retencion_amount_sum"] = (
        "perceptor_count_distinct"
    )


def validate_retenciones_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Accumulating registry-build validator for a ``retenciones_aggregation`` binding.

    Validates the selector shape against :class:`_RetencionesAggregationSelector`
    (the single build-time contract per ``binding-validation-single-contract``),
    preserving the underlying pydantic field message in the diagnostic.
    """
    return selector_against_model(binding, _RetencionesAggregationSelector)


def resolve_retenciones_aggregation_binding_values(
    revision: ModeloRevision,
    aggregation: _RetencionesAggregationProtocol,
) -> dict[BindingId, Decimal]:
    """Materialise every ``retenciones_aggregation`` binding on a :class:`ModeloRevision`.

    Returns a binding value for every binding whose ``source`` is
    :attr:`BindingSourceKind.RETENCIONES_AGGREGATION`, keyed by the selector's
    declared fact.
    """
    values = {
        "perceptor_count_distinct": Decimal(aggregation.total_perceptors),
        "taxable_base_sum": aggregation.total_taxable_base,
        "retencion_amount_sum": aggregation.total_retencion,
    }
    resolved: dict[BindingId, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.RETENCIONES_AGGREGATION:
            continue
        selector = _RetencionesAggregationSelector.model_validate(_selector_as_dict(binding))
        resolved[binding.id] = values[selector.fact]
    return resolved


__all__ = [
    "resolve_retenciones_aggregation_binding_values",
    "validate_retenciones_aggregation_binding",
]
