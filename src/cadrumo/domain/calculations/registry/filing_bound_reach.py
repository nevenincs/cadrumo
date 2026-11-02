"""Which bindings and casillas of one revision reach an exported box.

A figure is filing-bound when the revision is declared at the filing rung and
the figure reaches a casilla the official record carries. Whether a contest
between two sources of that figure blocks a filing is decided by this set, so
it is derived from the hydrated revision rather than authored: the registry
stays free of a hand-kept flag that could drift from the graph it describes.

Reach is read from four declared edges, in one walk:

- a ``BOUND`` casilla naming a binding as its binding or a reviewed alternate;
- a formula whose expression reads a binding as a decimal, enum or date operand;
- a formula whose expression reads a casilla, carrying the casilla's reach to
  the formula's target;
- a relation fold, which is keyed by the binding it materialises, so it reaches
  wherever that binding does.

A casilla with ``export_refs`` is exported. An ``internal_only`` casilla on the
way carries reach through like any other; it never ends it. A binding read only
by verification predicates, or by casillas that reach no exported box, is not
filing-bound, and nothing of a revision declared below the filing rung is.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId
from ....core.hashing import content_hash_hex
from .binding_targets import bound_casilla_binding_ids
from .runtime_graph import expression_binding_refs, expression_casilla_refs, expression_date_binding_refs

if TYPE_CHECKING:
    from .ids import BindingId
    from .schema import ModeloRevision

__all__ = ["FilingBoundReach", "filing_bound_reach", "filing_bound_reach_digest"]


@dataclass(frozen=True, slots=True)
class FilingBoundReach:
    """The exported casillas each filing-bound binding and casilla of one revision reaches.

    Each tuple is in the revision's casilla declaration order. A key that is
    absent reaches no exported casilla, or belongs to a revision below the
    filing rung. Relations are keyed by the binding they fold into, so
    :attr:`bindings` answers for them too.
    """

    bindings: Mapping[BindingId, tuple[CasillaId, ...]]
    casillas: Mapping[CasillaId, tuple[CasillaId, ...]]

    def binding_reach(self, binding_id: BindingId) -> tuple[CasillaId, ...]:
        """The exported casillas ``binding_id`` reaches; empty when it is not filing-bound."""
        return self.bindings.get(binding_id, ())

    def casilla_reach(self, casilla_id: CasillaId) -> tuple[CasillaId, ...]:
        """The exported casillas ``casilla_id`` reaches, itself included; empty when it is not filing-bound."""
        return self.casillas.get(casilla_id, ())


def _empty_reach() -> FilingBoundReach:
    no_bindings: dict[BindingId, tuple[CasillaId, ...]] = {}
    no_casillas: dict[CasillaId, tuple[CasillaId, ...]] = {}
    return FilingBoundReach(bindings=MappingProxyType(no_bindings), casillas=MappingProxyType(no_casillas))


def _formula_edges(
    revision: ModeloRevision,
) -> tuple[dict[CasillaId, set[CasillaId]], dict[BindingId, set[CasillaId]]]:
    """Each casilla and binding mapped to the formula targets that read it."""
    casilla_readers: dict[CasillaId, set[CasillaId]] = {}
    binding_readers: dict[BindingId, set[CasillaId]] = {}
    for formula in revision.formulas:
        target = formula.target_casilla_id
        for casilla_id in expression_casilla_refs(formula.expression):
            casilla_readers.setdefault(casilla_id, set()).add(target)
        for binding_id in (
            *expression_binding_refs(formula.expression),
            *expression_date_binding_refs(formula.expression),
        ):
            binding_readers.setdefault(binding_id, set()).add(target)
    return casilla_readers, binding_readers


def _casilla_reach(
    revision: ModeloRevision, casilla_readers: Mapping[CasillaId, set[CasillaId]]
) -> dict[CasillaId, frozenset[CasillaId]]:
    """Every casilla's exported reach, itself included when it is exported.

    Registry build refuses formula cycles, so the walk terminates; the
    ``visiting`` guard keeps a revision built outside that validation from
    recursing without end.
    """
    exported = {casilla.id for casilla in revision.casillas if casilla.export_refs}
    reach: dict[CasillaId, frozenset[CasillaId]] = {}
    visiting: set[CasillaId] = set()

    def walk(casilla_id: CasillaId) -> frozenset[CasillaId]:
        known = reach.get(casilla_id)
        if known is not None:
            return known
        if casilla_id in visiting:
            return frozenset[CasillaId]()
        visiting.add(casilla_id)
        found: set[CasillaId] = {casilla_id} if casilla_id in exported else set()
        for reader in casilla_readers.get(casilla_id, ()):
            found.update(walk(reader))
        visiting.discard(casilla_id)
        reach[casilla_id] = frozenset(found)
        return reach[casilla_id]

    for casilla in revision.casillas:
        walk(casilla.id)
    return reach


def filing_bound_reach(revision: ModeloRevision) -> FilingBoundReach:
    """Derive the filing-bound bindings and casillas of ``revision`` and the exported casillas each reaches.

    The test reads the revision's declared ``authority_grade``, not the rung an
    operation pins: a calculation pins the calculation rung while the revision
    it persists feeds check and export.
    """
    if revision.authority_grade is not RegistryAuthorityGrade.FILING:
        return _empty_reach()
    order = {casilla.id: index for index, casilla in enumerate(revision.casillas)}
    casilla_readers, binding_readers = _formula_edges(revision)
    casilla_reach = _casilla_reach(revision, casilla_readers)
    binding_reach: dict[BindingId, set[CasillaId]] = {}
    for casilla in revision.casillas:
        for binding_id in bound_casilla_binding_ids(casilla):
            binding_reach.setdefault(binding_id, set()).update(casilla_reach.get(casilla.id, frozenset()))
    for binding_id, readers in binding_readers.items():
        reached = binding_reach.setdefault(binding_id, set())
        for reader in readers:
            reached.update(casilla_reach.get(reader, frozenset()))

    def ordered(casilla_ids: frozenset[CasillaId] | set[CasillaId]) -> tuple[CasillaId, ...]:
        return tuple(sorted(casilla_ids, key=lambda casilla_id: (order.get(casilla_id, len(order)), casilla_id)))

    bindings = {binding_id: ordered(reached) for binding_id, reached in binding_reach.items() if reached}
    casillas = {casilla_id: ordered(reached) for casilla_id, reached in casilla_reach.items() if reached}
    return FilingBoundReach(bindings=MappingProxyType(bindings), casillas=MappingProxyType(casillas))


def filing_bound_reach_digest(reach: FilingBoundReach) -> str:
    """Return a content digest of the filing-bound set, order-free and grounded only in the revision's graph."""
    return content_hash_hex(
        {
            "bindings": {
                str(binding_id): sorted(str(casilla_id) for casilla_id in casilla_ids)
                for binding_id, casilla_ids in reach.bindings.items()
            },
            "casillas": {
                str(casilla_id): sorted(str(reached) for reached in reached_ids)
                for casilla_id, reached_ids in reach.casillas.items()
            },
        }
    )
