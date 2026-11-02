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

A casilla is exported when the filed return carries it, in whatever format the
revision's official layouts take: it declares ``export_refs``, or the canonical
classification of official casillas finds a layout addressing it directly or
representing it through a binding field. That covers fixed-width records and
the XML dictionary alike; the dictionary's casilla mapping is read from the
published source bytes it cites. An ``internal_only`` casilla on the way
carries reach through like any other; it never ends it. A binding read only
by verification predicates, or by casillas that reach no exported box, is not
filing-bound, and nothing of a revision declared below the filing rung is.
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId
from ....core.estado_casilla_oficial import EstadoCasillaOficial
from ....core.export_layout_format import ExportLayoutFormat
from ....core.hashing import content_hash_hex
from .binding_targets import bound_casilla_binding_ids
from .export import clasificar_casillas_oficiales, derive_export_layouts_from_bindings
from .runtime_graph import expression_binding_refs, expression_casilla_refs, expression_date_binding_refs

if TYPE_CHECKING:
    from .authority import PinnedAuthorityOperation
    from .ids import BindingId
    from .schema import ModeloRevision, RegistrySnapshot
    from .schema_references import SourceReference

__all__ = [
    "FilingBoundReach",
    "filing_bound_reach",
    "filing_bound_reach_digest",
    "official_export_casilla_ids",
    "snapshot_filing_bound_reach",
]


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


def official_export_casilla_ids(
    revision: ModeloRevision,
    *,
    sources: Mapping[str, SourceReference] | None = None,
    source_payloads: Mapping[str, bytes] | None = None,
) -> frozenset[CasillaId]:
    """The casillas of ``revision`` the filed return carries.

    A revision with an XML dictionary layout needs the published sources and
    their payloads, since the dictionary's casilla mapping lives in those bytes;
    without them the classification refuses rather than reading the
    dictionary's casillas as unexported.
    """
    classified = clasificar_casillas_oficiales(revision, sources=sources, source_payloads=source_payloads)
    return frozenset(
        casilla.id
        for casilla in revision.casillas
        if casilla.export_refs
        or classified.get(casilla.id, EstadoCasillaOficial.UNDEFINED) is not EstadoCasillaOficial.UNDEFINED
    )


def _casilla_reach(
    revision: ModeloRevision, casilla_readers: Mapping[CasillaId, set[CasillaId]], exported: Set[CasillaId]
) -> dict[CasillaId, frozenset[CasillaId]]:
    """Every casilla's exported reach, itself included when it is exported.

    Registry build refuses formula cycles, so the walk terminates; the
    ``visiting`` guard keeps a revision built outside that validation from
    recursing without end.
    """
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


def filing_bound_reach(revision: ModeloRevision, *, exported: Set[CasillaId]) -> FilingBoundReach:
    """Derive the filing-bound bindings and casillas of ``revision`` and the exported casillas each reaches.

    ``exported`` is the set the filed return carries
    (:func:`official_export_casilla_ids`). The test reads the revision's
    declared ``authority_grade``, not the rung an operation pins: a calculation
    pins the calculation rung while the revision it persists feeds check and
    export.
    """
    if revision.authority_grade is not RegistryAuthorityGrade.FILING:
        return _empty_reach()
    order = {casilla.id: index for index, casilla in enumerate(revision.casillas)}
    casilla_readers, binding_readers = _formula_edges(revision)
    casilla_reach = _casilla_reach(revision, casilla_readers, exported)
    binding_reach = _binding_reach(revision, binding_readers, casilla_reach)

    def ordered(casilla_ids: frozenset[CasillaId] | set[CasillaId]) -> tuple[CasillaId, ...]:
        return tuple(sorted(casilla_ids, key=lambda casilla_id: (order.get(casilla_id, len(order)), casilla_id)))

    bindings = {binding_id: ordered(reached) for binding_id, reached in binding_reach.items() if reached}
    casillas = {casilla_id: ordered(reached) for casilla_id, reached in casilla_reach.items() if reached}
    return FilingBoundReach(bindings=MappingProxyType(bindings), casillas=MappingProxyType(casillas))


def _binding_reach(
    revision: ModeloRevision,
    binding_readers: Mapping[BindingId, set[CasillaId]],
    casilla_reach: Mapping[CasillaId, frozenset[CasillaId]],
) -> dict[BindingId, set[CasillaId]]:
    """Give each binding the exported casillas reached through the casillas it fills and the formulas that read it."""
    binding_reach: dict[BindingId, set[CasillaId]] = {}
    for casilla in revision.casillas:
        for binding_id in bound_casilla_binding_ids(casilla):
            binding_reach.setdefault(binding_id, set()).update(casilla_reach.get(casilla.id, frozenset()))
    for binding_id, readers in binding_readers.items():
        reached = binding_reach.setdefault(binding_id, set())
        for reader in readers:
            reached.update(casilla_reach.get(reader, frozenset()))
    return binding_reach


def snapshot_filing_bound_reach(snapshot: RegistrySnapshot, *, operation: PinnedAuthorityOperation) -> FilingBoundReach:
    """Derive the filing-bound reach of ``snapshot``'s revision under ``operation``'s pinned authority.

    The XML dictionary payloads the classification needs are loaded from the
    pinned generation's published source evidence, and nothing is loaded for a
    revision below the filing rung.
    """
    revision = snapshot.revision
    if revision.authority_grade is not RegistryAuthorityGrade.FILING:
        return _empty_reach()
    dictionary_ids = sorted(
        {
            layout.dictionary_source_ref
            for layout in derive_export_layouts_from_bindings(revision)
            if layout.format is ExportLayoutFormat.XML_DICTIONARY and layout.dictionary_source_ref is not None
        }
    )
    payloads = {source_id: operation.source_evidence(source_id).payload for source_id in dictionary_ids}
    exported = official_export_casilla_ids(revision, sources=snapshot.sources, source_payloads=payloads)
    return filing_bound_reach(revision, exported=exported)


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
