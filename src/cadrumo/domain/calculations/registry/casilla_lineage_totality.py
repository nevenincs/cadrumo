"""Lineage totality: every successor-edition casilla row says how it stands.

A successor-edition row is a casilla of an edition that has a predecessor
edition. An edition naming a :class:`~.revision_contracts.DeclaredPredecessor` has the
edition it names, wherever that sits in validity order. An edition declaring
:class:`~.revision_contracts.NoPredecessor`, and an edition omitting the key, both have the
adjacent earlier edition in validity order. The first edition has none, and so
does a none-rooted edition whose validity overlaps the edition before it: those
are concurrent scheme variants of one modelo, siblings rather than a
succession, and neither continues the other.

A none is an EDITION-level statement -- this edition cannot be produced from
the one before it by the merge -- and casilla continuity is a separate per-row
axis that the corpus declares independently. Rows in none-rooted editions do
carry ``continuidad_id`` values the adjacent earlier edition carries, and do
declare continuation origins, so a none cannot stand as a blanket exemption
for every row of the edition: that would put exactly those rows beyond
judgement and let lineage vanish unreported.

Such a row is RESOLVED when it either

- carries lineage: its ``continuidad_id`` is also carried by a row of its
  edition's predecessor edition, or it declares a continuation origin
  (``seeded`` or ``grounded``); or
- declares its kind of none: an absence origin (``new_on_form``,
  ``predecessor_edition_silent`` or ``not_on_form``).

Every other successor-edition row is UNRESOLVED. That includes a row whose
``continuidad_id`` starts its chain in its own edition: an id nothing in the
predecessor edition carries claims no predecessor, so it is an undeclared
absence, not lineage. A ``continuidad_id`` alone is therefore not enough.

An unset ``continuidad_origin`` is not split into "authored" and "not yet
examined" here, because the rule does not need that split. An unmarked row
whose id resolves in the predecessor edition carries lineage whoever wrote it.
An unmarked row whose id does not resolve, or that has no id, is unresolved
whoever did or did not examine it.

Completeness is judged against an explicit exception set keyed per row. An
unresolved row that no exception names is UNCOVERED. An exception naming a
row that is not unresolved in the corpus given is STALE, whether the row now
resolves, has been removed, belongs to a modelo the corpus does not hold, or
sits in an edition this rule never judges at all -- a first edition, or a
none-rooted edition concurrent with the one before it. That last cause means
the opposite of the others: not "no longer needed" but "never assessable
here", and the report cannot tell them apart. An unjudged row emits nothing,
and nothing emitted is not evidence the row is covered.
Pass the whole corpus, or every exception outside it reads as stale.

Where this rule stops:

- a declared origin is taken as declared. Whether a continuation holds
  against its predecessor is judged by the lineage-origin continuity policy,
  and whether an absence origin's evidence proves that kind of none is a
  review question;
- an unmarked row whose id resolves is not held to any seeding predicate, and
  a predecessor edition carrying that id on several rows still resolves it;
- exactly one predecessor edition is consulted per edition. A named edge is
  followed one step, not up its chain, so an id carried only by the named
  edition's own predecessor does not resolve. An edition omitting the key is
  judged against the adjacent earlier edition even when the two share a
  validity window, and even when that edition is a key-less root of a modelo
  whose other editions declare the key;
- whether the named edition is a legal predecessor is not judged here: the
  forest and date-agreement rules own that, and ran when the modelo loaded;
- the first edition is not judged, having no earlier edition to be judged
  against; and a none-rooted edition whose validity OVERLAPS the edition
  before it is not judged, being a concurrent sibling rather than a
  successor. A none-rooted edition following a CLOSED earlier edition IS
  judged: the declaration says this edition cannot be produced from the
  one before it by the merge, not that its individual casillas do not
  continue;
- exceptions are matched by key alone. Their classification and reason belong
  to whoever keeps the exception set, and are not read here.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass

from .revision_contracts import DeclaredPredecessor, NoPredecessor
from .revision_order import ordered_revisions
from .schema import ModeloDefinition, ModeloRevision

__all__ = (
    "CasillaRowKey",
    "LineageTotalityReport",
    "judging_predecessor",
    "lineage_totality",
    "unresolved_successor_rows",
)


@dataclass(frozen=True, slots=True, order=True)
class CasillaRowKey:
    """One casilla row of one edition of one modelo."""

    modelo: str
    revision: str
    casilla: str


@dataclass(frozen=True, slots=True)
class LineageTotalityReport:
    """Unresolved rows no exception covers, and exceptions no row needs."""

    uncovered: tuple[CasillaRowKey, ...]
    stale: tuple[CasillaRowKey, ...]

    @property
    def is_total(self) -> bool:
        """Whether every unresolved row is covered and no exception is stale."""
        return not self.uncovered and not self.stale


def unresolved_successor_rows(modelo: ModeloDefinition) -> tuple[CasillaRowKey, ...]:
    """Return the successor-edition rows that neither carry lineage nor declare a none."""
    unresolved: list[CasillaRowKey] = []
    ordered = ordered_revisions(modelo)
    for index, revision in enumerate(ordered):
        predecessor = judging_predecessor(modelo, ordered, index)
        if predecessor is None:
            continue
        carried = _carried_chains(predecessor)
        for casilla in revision.casillas:
            if casilla.continuidad_origin is not None:
                continue
            if casilla.continuidad_id is not None and casilla.continuidad_id in carried:
                continue
            unresolved.append(CasillaRowKey(modelo=modelo.id, revision=str(revision.id), casilla=str(casilla.id)))
    return tuple(unresolved)


def lineage_totality(
    modelos: Iterable[ModeloDefinition],
    exceptions: Collection[CasillaRowKey],
) -> LineageTotalityReport:
    """Judge ``modelos`` for lineage totality against a per-row exception set."""
    unresolved = {key for modelo in modelos for key in unresolved_successor_rows(modelo)}
    excepted = frozenset(exceptions)
    return LineageTotalityReport(
        uncovered=tuple(sorted(unresolved - excepted)),
        stale=tuple(sorted(excepted - unresolved)),
    )


def judging_predecessor(
    modelo: ModeloDefinition,
    ordered: tuple[ModeloRevision, ...],
    index: int,
) -> ModeloRevision | None:
    """Return the edition a revision's rows are judged against, or ``None`` when it is not judged.

    Public because pairing editions is one rule, not two. Anything that
    disposes of successor-edition rows -- this gate, and the seeder that writes
    the ledger it reads -- pairs them here, so the two cannot disagree about
    which edition a row continues from and re-refuse a row the other resolves.

    A named predecessor is resolved by id; the modelo's forest validation has
    already refused a name that is not one of its editions.

    A ``NoPredecessor`` edition is still judged, against the adjacent earlier
    edition. Declaring a none says this EDITION cannot be produced from the one
    before it by the merge; it says nothing about whether an individual casilla
    continues. The corpus states the two axes separately and they disagree in
    practice: rows in none-rooted editions carry ``continuidad_id`` values that
    the adjacent earlier edition also carries, and carry continuation origins
    outright. Treating the edition-level declaration as an exemption for every
    row in it puts those rows beyond judgement, which is how a row can lose its
    lineage without anything reporting it.

    Two cases still return ``None``. A first edition has no earlier edition to
    be judged against at all. And a none-rooted edition whose validity OVERLAPS
    the edition before it is a concurrent sibling rather than a successor: the
    parallel scheme variants of one modelo all take effect on the same day and
    none of them ever closes, so the earlier one is not a predecessor in any
    sense and pairing them would invent a lineage relationship the corpus never
    declared. Only a closed earlier edition -- one whose validity ends before
    this edition begins -- can be the edition these rows continue from.
    """
    revision = ordered[index]
    match revision.predecessor:
        case NoPredecessor():
            if index == 0:
                return None
            earlier = ordered[index - 1]
            closed_before = earlier.valid_to is not None and earlier.valid_to < revision.valid_from
            return earlier if closed_before else None
        case DeclaredPredecessor(revision_id=predecessor_id):
            return modelo.revisions[predecessor_id]
        case None:
            return ordered[index - 1] if index > 0 else None


def _carried_chains(revision: ModeloRevision) -> frozenset[str]:
    return frozenset(casilla.continuidad_id for casilla in revision.casillas if casilla.continuidad_id is not None)
