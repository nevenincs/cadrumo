"""Lineage totality: every successor-edition casilla row says how it stands.

A successor-edition row is a casilla of an edition that has a predecessor
edition. An edition naming a :class:`~.revision_contracts.DeclaredPredecessor` has the
edition it names, wherever that sits in validity order. An edition declaring
:class:`~.revision_contracts.NoPredecessor` has none. An edition omitting the key has the
adjacent earlier edition in validity order, and the first edition has none.
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
resolves, has been removed, or belongs to a modelo the corpus does not hold.
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
- the first edition, and any edition declaring no predecessor, is not judged;
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
        predecessor = _judging_predecessor(modelo, ordered, index)
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


def _judging_predecessor(
    modelo: ModeloDefinition,
    ordered: tuple[ModeloRevision, ...],
    index: int,
) -> ModeloRevision | None:
    """Return the edition a revision's rows are judged against, or ``None`` when it is not judged.

    A named predecessor is resolved by id; the modelo's forest validation has
    already refused a name that is not one of its editions.
    """
    revision = ordered[index]
    match revision.predecessor:
        case NoPredecessor():
            return None
        case DeclaredPredecessor(revision_id=predecessor_id):
            return modelo.revisions[predecessor_id]
        case None:
            return ordered[index - 1] if index > 0 else None


def _carried_chains(revision: ModeloRevision) -> frozenset[str]:
    return frozenset(casilla.continuidad_id for casilla in revision.casillas if casilla.continuidad_id is not None)
