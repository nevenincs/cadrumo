"""Single accessor for a registry binding's aggregation operator.

The per-family default op was previously re-parsed at ~10 call sites with two
divergent silent defaults: the detail-record families defaulted to ``rows``
while every scalar-folding family defaulted to ``sum``. This module centralises
that divergence into one declared mapping from binding ``source`` kind to the
default :class:`~aeat.core.aggregation.BindingAggregationOp`, exposed through the
single :func:`binding_aggregation_op` accessor every binding resolver and
validator consumes.
"""

from __future__ import annotations

from ....core.aggregation import BindingAggregationOp, RowSetGroupingKind
from ._schema import DataBindingDefinition

#: Binding ``source`` kinds whose aggregation defaults to ``rows`` (one detail
#: row per observation) when the binding declares no explicit op. Every other
#: source family folds to a scalar and defaults to ``sum``.
_ROWS_DEFAULT_SOURCE_KINDS: frozenset[str] = frozenset(
    {
        "related_party_operation",
        RowSetGroupingKind.FOREIGN_ASSET,
        "atribucion_member",
        "refund_operation",
    },
)


def default_binding_aggregation_op(source: str) -> BindingAggregationOp:
    """Return the per-family default :class:`~aeat.core.aggregation.BindingAggregationOp` for a ``source``.

    Detail-record families (related-party, foreign-asset, atribución, refund)
    default to :attr:`~aeat.core.aggregation.BindingAggregationOp.ROWS`; every
    other source family defaults to
    :attr:`~aeat.core.aggregation.BindingAggregationOp.SUM`.
    """
    if source in _ROWS_DEFAULT_SOURCE_KINDS:
        return BindingAggregationOp.ROWS
    return BindingAggregationOp.SUM


def binding_aggregation_op(binding: DataBindingDefinition) -> BindingAggregationOp:
    """Return the typed :class:`~aeat.core.aggregation.BindingAggregationOp` a binding declares, or its default.

    When the binding carries an explicit :class:`BindingAggregation`, its typed
    ``op`` is returned. When ``aggregation`` is ``None``, the declared
    per-family default for the binding's ``source`` is applied in this one
    place.
    """
    if binding.aggregation is not None:
        return binding.aggregation.op
    return default_binding_aggregation_op(str(binding.source))
