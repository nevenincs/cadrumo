"""Single accessor for a registry binding's aggregation operator.

The per-family default op was previously re-parsed at ~10 call sites with two
divergent silent defaults: the detail-record families defaulted to ``rows``
while every scalar-folding family defaulted to ``sum``. This module centralises
that divergence into one declared mapping from binding ``source`` kind to the
default :class:`~core.aggregation.BindingAggregationOp`, exposed through the
single :func:`binding_aggregation_op` accessor every binding resolver and
validator consumes.

See Also:
    :mod:`domain.calculations.registry._bindings`
        Cross-family binding resolver and validator dispatch that consumes this
        accessor.
    :mod:`domain.calculations.registry._relation_aggregation`
        Relation sibling whose op axis is intentionally separate.
    :mod:`core.aggregation`
        Core enum/model definitions for binding source kinds and aggregation ops.
"""

from __future__ import annotations

from ....core.aggregation import ROW_SET_GROUPING_FOR_BINDING_SOURCE, BindingAggregationOp, BindingSourceKind
from .schema import DataBindingDefinition

#: Binding ``source`` kinds whose aggregation defaults to ``rows`` (one detail
#: row per observation) when the binding declares no explicit op. Every other
#: source family folds to a scalar and defaults to ``sum``.
_ROWS_DEFAULT_SOURCE_KINDS: frozenset[BindingSourceKind] = frozenset(
    source for source in ROW_SET_GROUPING_FOR_BINDING_SOURCE if source is not BindingSourceKind.WITHHOLDING
)


def default_binding_aggregation_op(source: str) -> BindingAggregationOp:
    """Return the per-family default :class:`~core.aggregation.BindingAggregationOp` for a ``source``.

    Detail-record families (related-party, foreign-asset, atribución, refund)
    default to :attr:`~core.aggregation.BindingAggregationOp.ROWS`; every
    other source family defaults to
    :attr:`~core.aggregation.BindingAggregationOp.SUM`. The ``source``
    value is interpreted through :class:`~core.aggregation.BindingSourceKind`
    before applying the row-set default table.
    """
    try:
        source_kind = BindingSourceKind(source)
    except ValueError:
        return BindingAggregationOp.SUM
    if source_kind in _ROWS_DEFAULT_SOURCE_KINDS:
        return BindingAggregationOp.ROWS
    return BindingAggregationOp.SUM


def binding_aggregation_op(binding: DataBindingDefinition) -> BindingAggregationOp:
    """Return the typed :class:`~core.aggregation.BindingAggregationOp` a binding declares, or its default.

    When the
    :class:`~domain.calculations.registry.DataBindingDefinition` carries an
    explicit :class:`~core.aggregation.BindingAggregation`, its typed ``op``
    is returned. When ``aggregation`` is ``None``, the declared per-family
    default for the binding's ``source`` is applied in this one place.
    """
    if binding.aggregation is not None:
        return binding.aggregation.op
    return default_binding_aggregation_op(str(binding.source))
