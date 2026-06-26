"""Single accessor for a registry relation's aggregation operator.

The relation ``aggregation.op`` was re-parsed inline as
``str((relation.aggregation or {}).get("op", "copy"))`` at the requirement-keying,
resolve, and M390-partition sites — exactly the untyped re-parse the
``binding-aggregation-is-typed`` rule forbids for bindings, on the relation half it
skipped. ``RelationDefinition.aggregation`` is now the typed
:class:`~aeat.core.aggregation.RelationAggregation` model (an unknown op is rejected
at registry-build by its strict ``op`` field). This module centralises the read into
one :func:`relation_aggregation_op` accessor returning the typed
:class:`~aeat.core.aggregation.RelationAggregationOp`, applying the per-relation
default in one place.

The relation op axis is deliberately separate from the binding op axis
(:func:`binding_aggregation_op`): relations carry only ``copy`` / ``sum``, never
the binding-only ``rows`` / ``count_distinct`` / ``prior_pagos_fraccionados``.
"""

from __future__ import annotations

from ....core.aggregation import RelationAggregationOp
from ._schema import RelationDefinition


def relation_aggregation_op(relation: RelationDefinition) -> RelationAggregationOp:
    """Return the typed :class:`~aeat.core.aggregation.RelationAggregationOp` a relation declares.

    Reads the relation's typed :class:`~aeat.core.aggregation.RelationAggregation`
    ``op``. Defaults to :attr:`~aeat.core.aggregation.RelationAggregationOp.COPY`
    when ``aggregation`` is absent — the conformant single-period carry default.
    """
    if relation.aggregation is None:
        return RelationAggregationOp.COPY
    return relation.aggregation.op
