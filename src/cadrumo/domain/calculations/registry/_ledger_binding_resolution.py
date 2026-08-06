"""Shared skeleton for the ledger-family binding value resolvers.

Every ``ledger_<family>_aggregation`` source (OSS, IVA, renta income, renta
gastos estimación directa, renta gastos pago fraccionado, IRNR, impatriado)
resolves its bindings with the same shape: filter ``revision.bindings`` by
source kind, parse each binding's selector, build a per-selector match
predicate over the ledger observations, and fold the matched set through a
fact-dispatched Decimal aggregation. The fail-closed sibling
(``unsupported_ledger_*_observations``) shares the same source-filter and
predicate machinery, screening for observations no binding selects.

:func:`resolve_ledger_family_binding_values` and
:func:`unsupported_ledger_family_observations` factor that shape out once.
Each family module supplies its own selector parser, a ``build_matcher``
that closes over the selector's per-axis membership sets — precomputed once
per binding (or once per binding-selector in the fail-closed screen), never
rebuilt once per observation — a fact-dispatch ``aggregate``, and, for the
fail-closed sibling, an ``is_declarable`` false-fire guard plus an optional
``extra_exclusion`` for a documented family-specific carve-out (the IVA
family's cuota-less-category exclusion is the sole instance).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from decimal import Decimal

from ....core.aggregation import BindingSourceKind
from ._ids import BindingId
from ._schema import DataBindingDefinition, ModeloRevision

__all__ = [
    "resolve_ledger_family_binding_values",
    "unsupported_ledger_family_observations",
]


def resolve_ledger_family_binding_values[ObservationT, SelectorT](
    revision: ModeloRevision,
    observations: Iterable[ObservationT],
    *,
    source_kind: BindingSourceKind,
    parse_selector: Callable[[DataBindingDefinition], SelectorT],
    build_matcher: Callable[[SelectorT], Callable[[ObservationT], bool]],
    aggregate: Callable[[Sequence[ObservationT], SelectorT], Decimal],
) -> dict[BindingId, Decimal]:
    """Resolve every ``source_kind`` binding on ``revision`` into a Decimal aggregate.

    Shared core for the ledger-family scalar resolvers (OSS, IVA, renta
    income/gastos, IRNR, impatriado). For each matching binding: parse its
    selector, build that selector's match predicate once (``build_matcher``
    closes over any per-axis membership sets so they are computed once per
    binding, not once per observation), filter the available observations,
    and fold the matched set through the family's fact-dispatch
    ``aggregate``.

    Args:
        revision: The :class:`ModeloRevision` whose bindings to resolve.
        observations: The family's typed ledger observations to aggregate.
        source_kind: The :class:`BindingSourceKind` this family's bindings
            declare.
        parse_selector: The family's selector parser, raising
            :class:`RegistryValidationError` on a malformed selector.
        build_matcher: Builds a per-observation match predicate from a
            parsed selector, closing over any membership sets once.
        aggregate: Folds the matched observations for one binding, per the
            selector's declared fact, into the resolved Decimal.

    Returns:
        Mapping of binding id to its resolved Decimal aggregate. A binding
        whose selector matches no observation resolves to ``Decimal("0")``.
    """
    available = tuple(observations)
    resolved: dict[BindingId, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != source_kind:
            continue
        selector = parse_selector(binding)
        matcher = build_matcher(selector)
        matched = tuple(observation for observation in available if matcher(observation))
        resolved[binding.id] = aggregate(matched, selector)
    return resolved


def unsupported_ledger_family_observations[ObservationT, SelectorT](
    revision: ModeloRevision,
    observations: Iterable[ObservationT],
    *,
    source_kind: BindingSourceKind,
    parse_selector: Callable[[DataBindingDefinition], SelectorT],
    build_matcher: Callable[[SelectorT], Callable[[ObservationT], bool]],
    is_declarable: Callable[[ObservationT], bool],
    extra_exclusion: Callable[[ObservationT], bool] | None = None,
) -> tuple[ObservationT, ...]:
    """Return the ``observations`` no ``source_kind`` binding on ``revision`` can consume.

    Fail-closed counterpart to :func:`resolve_ledger_family_binding_values`,
    shared by every ledger family's ``unsupported_ledger_*_observations``. An
    observation matched by no declared binding has its value silently
    dropped from the filing — a modelling gap, not a legitimate zero
    (``no-silent-under-declaration``).

    Args:
        revision: The :class:`ModeloRevision` whose bindings define the
            supported selector set.
        observations: The family's typed ledger observations to screen.
        source_kind: The :class:`BindingSourceKind` this family's bindings
            declare.
        parse_selector: The family's selector parser.
        build_matcher: Builds a per-observation match predicate from a
            parsed selector; matchers are built once per binding before
            screening observations, never rebuilt per (observation, binding)
            pair.
        is_declarable: False-fire guard excluding observations that
            contribute nothing whether or not they are routed (e.g. a
            zero-amount row). Every family except IVA declares one; IVA has
            no such guard and MUST pass ``lambda observation: True`` to
            preserve that documented asymmetry.
        extra_exclusion: Optional family-specific carve-out evaluated before
            ``is_declarable``. The sole documented instance is the IVA
            family's ``CUOTA_LESS_M303_IVA_CATEGORIES`` exclusion; omit for
            every other family.

    Returns:
        Tuple of observations selected by no binding, in input order.
    """
    matchers = tuple(
        build_matcher(parse_selector(binding)) for binding in revision.bindings if binding.source == source_kind
    )
    unsupported: list[ObservationT] = []
    for observation in observations:
        if extra_exclusion is not None and extra_exclusion(observation):
            continue
        if not is_declarable(observation):
            continue
        if not any(matcher(observation) for matcher in matchers):
            unsupported.append(observation)
    return tuple(unsupported)
