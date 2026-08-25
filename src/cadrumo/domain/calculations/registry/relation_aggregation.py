"""Single accessor for a registry relation's aggregation operator.

The relation ``aggregation.op`` was re-parsed inline as
``str((relation.aggregation or {}).get("op", "copy"))`` at the requirement-keying,
resolve, and M390-partition sites — exactly the untyped re-parse the
``aeat-registry-bindings`` rule forbids for bindings, on the relation half it
skipped. ``RelationDefinition.aggregation`` is now the typed
:class:`~core.aggregation.RelationAggregation` model (an unknown op is rejected
at registry-build by its strict ``op`` field). This module centralises the read into
one :func:`relation_aggregation_op` accessor returning the typed
:class:`~core.aggregation.RelationAggregationOp`, applying the per-relation
default in one place.

The relation op axis is deliberately separate from the binding op axis
(:func:`domain.calculations.registry.binding_aggregation_op`): relations
carry only ``copy`` / ``sum``, never the binding-only ``rows`` /
``count_distinct`` / ``prior_pagos_fraccionados``.

See Also:
    :mod:`domain.calculations.registry._relations`
        Requirement and resolve paths that call this accessor.
    :mod:`domain.calculations.registry._observation_fold`
        Shared ``copy`` / ``sum`` arithmetic applied after this accessor selects
        the relation op.
    :mod:`core.aggregation`
        Core enum/model definitions for relation and binding aggregation axes.
"""

from __future__ import annotations

from ....core.aggregation import RelationAggregationOp
from .schema import RelationDefinition


def relation_aggregation_op(relation: RelationDefinition) -> RelationAggregationOp:
    """Return the typed :class:`~core.aggregation.RelationAggregationOp` a relation declares.

    Reads the
    :class:`~domain.calculations.registry.RelationDefinition` aggregation
    field. Defaults to
    :attr:`~core.aggregation.RelationAggregationOp.COPY` when
    ``aggregation`` is absent, preserving the conformant single-period carry
    default used by relation source requirements.
    """
    if relation.aggregation is None:
        return RelationAggregationOp.COPY
    return relation.aggregation.op
