"""Single accessor for a registry binding's aggregation operator.

The per-family default op was previously re-parsed at ~10 call sites with two
divergent silent defaults: the detail-record families defaulted to ``rows``
while every scalar-folding family defaulted to ``sum``. This module centralises
that divergence into one declared mapping from binding ``source`` kind to the
default :class:`~core.aggregation.BindingAggregationOp`, exposed through the
single :func:`binding_aggregation_op` accessor every binding resolver and
validator consumes.

See Also:
    :mod:`domain.calculations.registry.bindings`
        Cross-family binding resolver and validator dispatch that consumes this
        accessor.
    :mod:`~domain.calculations.registry.binding_aggregation`
        Relation sibling whose op axis is intentionally separate.
    :mod:`core.aggregation`
        Core enum/model definitions for binding source kinds and aggregation ops.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from .errors import RegistryValidationError

if TYPE_CHECKING:
    from .schema import BindingDefinition


def default_binding_aggregation_op(source: str) -> BindingAggregationOp:
    """Return the default :class:`~core.aggregation.BindingAggregationOp` for a ``source``.

    The default is derived from the kind's registration, the one authority for
    which operations the kind permits (see
    :attr:`~.binding_provider_registration.BindingProviderRegistration.default_aggregation_op`):
    a kind that permits a single operation takes it, so a copy-only kind
    defaults to ``copy`` rather than a ``sum`` it cannot run.

    Raises:
        RegistryValidationError: ``source`` is not a registered provider kind.
            There is no fallback default for an unknown kind.
    """
    from .binding_provider_registration import registration_for

    try:
        source_kind = BindingSourceKind(source)
    except ValueError as exc:
        raise RegistryValidationError(
            f"binding provider kind {source!r} has no registration",
            context={"kind": source},
        ) from exc
    return registration_for(source_kind).default_aggregation_op


def binding_aggregation_op(binding: BindingDefinition) -> BindingAggregationOp:
    """Return the typed :class:`~core.aggregation.BindingAggregationOp` a binding declares, or its default.

    When the
    :class:`~domain.calculations.registry.schema.BindingDefinition` carries an
    explicit :class:`~core.aggregation.BindingAggregation`, its typed ``op``
    is returned. When ``aggregation`` is ``None``, the declared per-family
    default derived from the binding's registered ``source`` is applied in this one place.
    """
    if binding.aggregation is not None:
        return binding.aggregation.op
    return default_binding_aggregation_op(str(binding.source))
