"""Modelo 202 first-period zero defaults for relation-prefill bindings."""

from __future__ import annotations

from decimal import Decimal

from ...core.aggregation import BindingSourceKind
from ...core.modelo import Modelo
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.queries import relations_by_target_binding
from ...domain.calculations.registry.schema import ModeloRevision


def relation_prefill_period_zero_default_binding_ids(
    revision: ModeloRevision,
    *,
    modelo: str,
    period: str,
) -> frozenset[BindingId]:
    """Return relation-prefill bindings calculate resolves to zero for ``period``.

    A Modelo 202 same-model previous-payment carry has no upstream filing before
    its first target period. Both calculate and readiness consume this one policy
    so their missing-binding sets remain identical.
    """
    if modelo != Modelo.M202.value:
        return frozenset[BindingId]()
    relations_by_target = relations_by_target_binding(revision)
    zero_defaulted: set[BindingId] = set()
    for binding in revision.bindings:
        if binding.source is not BindingSourceKind.RELATION_PREFILL:
            continue
        relations = relations_by_target.get(binding.id, ())
        if not relations:
            continue
        if any(not relation.target_periods or period in relation.target_periods for relation in relations):
            continue
        if all(relation.kind == "previous_period" and str(relation.source_modelo) == modelo for relation in relations):
            zero_defaulted.add(binding.id)
    return frozenset(zero_defaulted)


def modelo_202_first_period_previous_payment_defaults(
    revision: ModeloRevision,
    *,
    modelo: str,
    period: str,
) -> dict[BindingId, Decimal]:
    """Resolve M202 previous-payment carries to zero before their first target period."""
    return {
        binding_id: Decimal("0")
        for binding_id in relation_prefill_period_zero_default_binding_ids(
            revision,
            modelo=modelo,
            period=period,
        )
    }
