"""Retenciones-aggregation registry binding helpers (RET-1).

The per-family module for the ``retenciones_aggregation`` binding source — the
calc-mesh source that materialises retenciones-family scalars from the dedicated
per-perceptor retención store.
Extracted as its own family module per ``aeat-architecture-boundaries``;
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
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, BeforeValidator, ConfigDict

from ....core import CasillaId
from ....core.aggregation import BindingSourceKind
from ....core.aggregation import RetencionScheme
from .binding_selector_utils import selector_against_model
from .binding_selector_utils import selector_as_dict as _selector_as_dict
from .ids import BindingId
from .schema import DataBindingDefinition, ModeloRevision
from .schema_base import coerce_enum_tuple


class _RetencionesAggregationProtocol(Protocol):
    """The scalar totals the retenciones-aggregation source materialises."""

    @property
    def rollups(self) -> tuple[_RetencionesRollupProtocol, ...]: ...

    @property
    def total_perceptors(self) -> int: ...

    @property
    def total_taxable_base(self) -> Decimal: ...

    @property
    def total_retencion(self) -> Decimal: ...


class _RetencionesRollupProtocol(Protocol):
    """One per-perceptor/scheme rollup row exposed by the retenciones source."""

    @property
    def perceptor_nif(self) -> str: ...

    @property
    def scheme(self) -> RetencionScheme: ...

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

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    target_casilla_id: CasillaId
    schemes: Annotated[tuple[RetencionScheme, ...], BeforeValidator(coerce_enum_tuple(RetencionScheme))] = ()
    fact: Literal["perceptor_count_distinct", "taxable_base_sum", "retencion_amount_sum"] = "perceptor_count_distinct"


def validate_retenciones_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Accumulating registry-build validator for a ``retenciones_aggregation`` binding.

    Validates the selector shape against :class:`_RetencionesAggregationSelector`
    (the single build-time contract per ``aeat-registry-bindings``),
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
    resolved: dict[BindingId, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.RETENCIONES_AGGREGATION:
            continue
        selector = _RetencionesAggregationSelector.model_validate(_selector_as_dict(binding))
        resolved[binding.id] = _retenciones_selector_value(selector, aggregation)
    return resolved


def _retenciones_selector_value(
    selector: _RetencionesAggregationSelector,
    aggregation: _RetencionesAggregationProtocol,
) -> Decimal:
    if not selector.schemes:
        values = {
            "perceptor_count_distinct": Decimal(aggregation.total_perceptors),
            "taxable_base_sum": aggregation.total_taxable_base,
            "retencion_amount_sum": aggregation.total_retencion,
        }
        return values[selector.fact]

    selected = tuple(row for row in aggregation.rollups if row.scheme in selector.schemes)
    if selector.fact == "perceptor_count_distinct":
        return Decimal(len({row.perceptor_nif for row in selected}))
    if selector.fact == "taxable_base_sum":
        return sum((row.total_taxable_base for row in selected), Decimal("0"))
    return sum((row.total_retencion for row in selected), Decimal("0"))


__all__ = [
    "RetencionesAggregationSelector",
    "resolve_retenciones_aggregation_binding_values",
    "validate_retenciones_aggregation_binding",
]


RetencionesAggregationSelector = _RetencionesAggregationSelector
