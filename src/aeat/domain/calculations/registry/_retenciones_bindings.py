"""Retenciones-aggregation registry binding helpers (RET-1).

The per-family module for the ``retenciones_aggregation`` binding source — the
calc-mesh source that materialises the Modelo 180/190/193 "número total de
perceptores" DISTINCT-NIF count from the dedicated per-perceptor retención store.
Extracted as its own family module per ``registry-resolver-family-extraction``;
the cross-family validator dispatch in :mod:`._bindings` registers this family's
``validate(binding) -> list[str]`` entry.

The materialisation depends on a :class:`_RetencionesPerceptorCountProtocol`
(the scalar ``total_perceptors`` distinct-NIF count) rather than the
application-layer ``RetencionesAggregation``, so the domain layer stays
independent of the application aggregation service.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from ....core import BindingSourceKind
from ._binding_selector_utils import selector_against_model
from ._ids import CasillaId
from ._schema import DataBindingDefinition, ModeloRevision


class _RetencionesPerceptorCountProtocol(Protocol):
    """The single scalar the retenciones-aggregation source materialises."""

    @property
    def total_perceptors(self) -> int: ...


class _RetencionesAggregationSelector(BaseModel):
    """Validated form of a ``retenciones_aggregation`` binding selector.

    Carries the target casilla (the annual "número total de perceptores" box) and
    the single fact this source serves: the distinct perceptor-NIF count. The
    monetary base/retenciones annual totals stay additive ``sum`` relations
    (``calculation-source-canonical-mechanism``); this source serves only the
    count.
    """

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

    target_casilla: CasillaId
    fact: Literal["perceptor_count_distinct"] = "perceptor_count_distinct"


def validate_retenciones_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Accumulating registry-build validator for a ``retenciones_aggregation`` binding.

    Validates the selector shape against :class:`_RetencionesAggregationSelector`
    (the single build-time contract per ``binding-validation-single-contract``),
    preserving the underlying pydantic field message in the diagnostic.
    """
    return selector_against_model(binding, _RetencionesAggregationSelector)


def resolve_retenciones_aggregation_binding_values(
    revision: ModeloRevision,
    aggregation: _RetencionesPerceptorCountProtocol,
) -> dict[str, Decimal]:
    """Materialise every ``retenciones_aggregation`` binding on ``revision``.

    Each such binding is the annual perceptor-count box; it materialises the
    validated distinct-NIF count (``aggregation.total_perceptors``) — never the sum
    of the quarterly Modelo 115 aggregate counts. Returns ``{binding_id: count}``
    for every binding whose ``source`` is :attr:`BindingSourceKind.RETENCIONES_AGGREGATION`.
    """
    count = Decimal(aggregation.total_perceptors)
    return {
        str(binding.id): count
        for binding in revision.bindings
        if binding.source == BindingSourceKind.RETENCIONES_AGGREGATION
    }


__all__ = [
    "resolve_retenciones_aggregation_binding_values",
    "validate_retenciones_aggregation_binding",
]
