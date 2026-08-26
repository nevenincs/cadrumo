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

Both of those key on the ROW. :func:`unrouted_ledger_family_quantities` is the
third shape and keys on the QUANTITY: a row a binding DOES consume can carry a
second, independent quantity that no binding draws, and the two row-keyed
screens are silent on it by construction. Its family adapters supply a fact
vocabulary, the subset of that vocabulary that measures one quantity by
different rules, and a per-fact reader.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from decimal import Decimal
from typing import NamedTuple

from ....core.aggregation import BindingSourceKind
from .errors import RegistryValidationError
from .ids import BindingId
from .schema import DataBindingDefinition, ModeloRevision

__all__ = [
    "UnroutedLedgerQuantity",
    "resolve_ledger_family_binding_values",
    "unrouted_ledger_family_quantities",
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


class UnroutedLedgerQuantity[ObservationT](NamedTuple):
    """An independent quantity the observations carry that no binding draws.

    ``fact`` is the selector fact that would have drawn it, ``total`` the sum
    the rows carry, and ``observations`` the contributing rows in input order.
    """

    fact: str
    total: Decimal
    observations: tuple[ObservationT, ...]


def unrouted_ledger_family_quantities[ObservationT, SelectorT](
    revision: ModeloRevision,
    observations: Iterable[ObservationT],
    *,
    source_kind: BindingSourceKind,
    parse_selector: Callable[[DataBindingDefinition], SelectorT],
    build_matcher: Callable[[SelectorT], Callable[[ObservationT], bool]],
    read_fact: Callable[[SelectorT], str],
    independent_facts: frozenset[str],
    readers: Mapping[str, Callable[[ObservationT], Decimal]],
) -> tuple[UnroutedLedgerQuantity[ObservationT], ...]:
    """Return independent quantities the rows carry that no binding on ``revision`` draws.

    The third ledger-family screen, watching an axis the two row-keyed screens
    cannot see. :func:`unsupported_ledger_family_observations` asks whether a
    ROW is selected by some binding; this one asks, PER ROW AND PER FACT,
    whether the quantity that row carries is drawn by a binding that actually
    reaches it.

    The distinction is load-bearing wherever one observation carries several
    quantities: a row consumed for one of them reads as routed while a second,
    independent quantity it carries reaches nothing at all, so the row-keyed
    screens stay clean while the value disappears from the filing
    (``no-silent-under-declaration``).

    The coverage question is asked per (row, fact) rather than per fact, and
    that is the whole of the difference between this screen working and this
    screen being decorative. A flat "does any binding declare this fact" set
    passes the PARTITIONED case: a fact declared by bindings whose selectors
    reach only OTHER rows counts as drawn for every row, so a quantity carried
    by the rows those bindings do not select vanishes with both screens clean —
    the same defect this screen exists to catch, one level in. Modelo 303 is a
    live instance: its base bindings cover the domestic tiers, intra-community
    supplies and exports, while its cuota bindings additionally cover the
    reverse-charge and import categories, so an intra-community acquisition's
    base imponible is reached by no base binding at all.

    Reports nothing when the rows carry nothing: a zero total is a legitimate
    zero rather than a modelling gap, and this screen must not manufacture a
    finding from it.

    Args:
        revision: The :class:`ModeloRevision` whose bindings decide which facts
            are drawn, and which rows each drawing binding reaches.
        observations: The family's typed ledger observations to screen.
        source_kind: The :class:`BindingSourceKind` this family's bindings declare.
        parse_selector: The family's selector parser.
        build_matcher: Builds a per-observation match predicate from a parsed
            selector — the same collaborator the other two shapes take, so
            "does this binding reach this row" has one definition across all
            three screens. Matchers are built once per binding, never per
            (observation, binding) pair.
        read_fact: Reads the declared fact off a parsed selector.
        independent_facts: The screened set, from
            :func:`independent_quantity_facts`.
        readers: Per-fact readers, keyed on the same selector-fact vocabulary
            the family's resolver dispatches on so a fact cannot be screened
            under one reading and resolved under another.

    Returns:
        One :class:`UnroutedLedgerQuantity` per fact with uncovered non-zero
        rows, ordered by fact name, each carrying only the rows that fact's
        bindings fail to reach. Empty when every quantity the rows carry is
        drawn by a binding selecting them.

    Raises:
        RegistryValidationError: If a screened fact declares no reader. The
            import-time gate
            (:func:`assert_quantity_readers_cover_independent_facts`) pins the
            two together, so reaching here means that gate was bypassed.
    """
    matchers_by_fact: dict[str, list[Callable[[ObservationT], bool]]] = {}
    for binding in revision.bindings:
        if binding.source != source_kind:
            continue
        selector = parse_selector(binding)
        matchers_by_fact.setdefault(read_fact(selector), []).append(build_matcher(selector))
    rows = tuple(observations)
    unrouted: list[UnroutedLedgerQuantity[ObservationT]] = []
    for fact in sorted(independent_facts):
        read = readers.get(fact)
        if read is None:
            raise RegistryValidationError(
                f"fact {fact!r} is screened as an independent quantity but declares no reader",
            )
        matchers = matchers_by_fact.get(fact, [])
        carrying = tuple(
            row for row in rows if read(row) != Decimal("0") and not any(matcher(row) for matcher in matchers)
        )
        if not carrying:
            continue
        unrouted.append(
            UnroutedLedgerQuantity(
                fact=fact,
                total=sum((read(row) for row in carrying), Decimal("0")),
                observations=carrying,
            ),
        )
    return tuple(unrouted)
