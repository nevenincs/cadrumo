"""Modelo 202 first-period zero defaults for relation-prefill bindings."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from ...core.aggregation import BindingSourceKind
from ...core.modelo import Modelo
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.queries import relations_by_target_binding
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_surfaces import RelationDefinition


def _relation_targets_period(relations: Sequence[RelationDefinition], period: str) -> bool:
    """Return whether one declared relation is active in ``period``."""
    return any(not relation.target_periods or period in relation.target_periods for relation in relations)


def _same_modelo_previous_period_relations(
    relations: Sequence[RelationDefinition],
    modelo: str,
) -> bool:
    """Return whether every relation is a same-model previous-period carry."""
    return all(relation.kind == "previous_period" and str(relation.source_modelo) == modelo for relation in relations)


def _is_period_zero_default_binding(
    source: BindingSourceKind,
    relations: Sequence[RelationDefinition],
    *,
    modelo: str,
    period: str,
) -> bool:
    """Return whether a binding has only same-model prior defaults for ``period``."""
    if source is not BindingSourceKind.RELATION_PREFILL:
        return False
    if not relations:
        return False
    if _relation_targets_period(relations, period):
        return False
    return _same_modelo_previous_period_relations(relations, modelo)


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
    return frozenset(
        binding.id
        for binding in revision.bindings
        if _is_period_zero_default_binding(
            binding.source,
            relations_by_target.get(binding.id, ()),
            modelo=modelo,
            period=period,
        )
    )


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
