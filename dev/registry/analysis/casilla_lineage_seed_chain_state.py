"""Index declared lineage chains and their cross-revision role contracts."""

from __future__ import annotations

import collections
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision

from .casilla_lineage_seed_rules import (
    _role_derived,
    judged_pairs,
)

type _Row = tuple[str, str]


@dataclass(slots=True)
class _ChainState:
    """Continuity ids and lineage links as they will stand once the plan is written.

    A link is the step from a row to the one predecessor-edition row carrying
    its chain; it is grounded only when the continuing row declares ``grounded``
    with evidence. Links are tracked because the registry excuses a row from
    carrying a ``semantic_role`` exactly when every link it takes part in is
    grounded.
    """

    ids: dict[_Row, str]
    members: dict[str, list[_Row]]
    role_counts: dict[str, collections.Counter[str | None]]
    roles: dict[_Row, str | None]
    position: dict[str, int]
    predecessor_of: dict[_Row, _Row]
    grounded_link: dict[_Row, bool]

    @classmethod
    def of(cls, modelo: ModeloDefinition) -> _ChainState:
        revisions = ordered_revisions(modelo)
        state = cls(
            ids={},
            members=collections.defaultdict(list),
            role_counts={},
            roles={},
            position={revision.id: index for index, revision in enumerate(revisions)},
            predecessor_of={},
            grounded_link={},
        )
        _index_declared_chains(state, revisions)
        _index_existing_links(state, modelo, revisions)
        return state

    def ids_in(self, revision: str) -> set[str]:
        return {chain for (rev, _), chain in self.ids.items() if rev == revision}

    def _role_exempt(self, row: _Row, occurrences: set[_Row], links: Mapping[_Row, tuple[_Row, bool]]) -> bool:
        """Whether ``row`` takes part in at least one link and every link it takes part in is grounded."""
        incoming = links.get(row)
        earlier = any(self.position[other[0]] < self.position[row[0]] for other in occurrences)
        incoming_grounded = incoming is not None and incoming[1]
        outgoing = [grounded for predecessor, grounded in links.values() if predecessor == row]
        incoming_ok = incoming_grounded or not earlier
        return incoming_ok and (incoming_grounded or any(outgoing)) and all(outgoing)

    def linkage_violation(self, chain: str, link: tuple[_Row, _Row], grounded: bool) -> str | None:
        """The semantic-linkage failure writing ``link`` into ``chain`` would cause, if any.

        Mirrors the load-time rule: every occurrence of a chain crossing a
        revision boundary carries a ``semantic_role`` unless every link it takes
        part in is grounded, and a chain whose declared role is unique in every
        revision it spans uses the role-derived identifier.
        """
        predecessor, successor = link
        occurrences = set(self.members.get(chain, ())) | {predecessor, successor}
        links = _links_for_occurrences(self, occurrences)
        links[successor] = (predecessor, grounded)
        missing = _missing_semantic_roles(self, occurrences, links)
        if missing:
            return (
                f"chain {chain!r} would carry rows without semantic_role whose links are not all grounded: "
                f"{missing[:3]}"
            )
        role = _single_declared_role(self, occurrences)
        if role is None or not _requires_role_derived_chain(self, chain, role, occurrences):
            return None
        return f"chain {chain!r} has role {role!r} unique in every revision and must be {_role_derived(role)!r}"

    def link(self, chain: str, rows: Iterable[_Row]) -> None:
        for row in rows:
            if row not in self.ids:
                self.ids[row] = chain
                self.members[chain].append(row)

    def record_link(self, predecessor: _Row, successor: _Row, grounded: bool) -> None:
        self.predecessor_of[successor] = predecessor
        self.grounded_link[successor] = grounded


def _index_declared_chains(state: _ChainState, revisions: tuple[ModeloRevision, ...]) -> None:
    for revision in revisions:
        state.role_counts[revision.id] = collections.Counter(casilla.semantic_role for casilla in revision.casillas)
        for casilla in revision.casillas:
            state.roles[(revision.id, casilla.id)] = casilla.semantic_role
            if casilla.continuidad_id is not None:
                state.ids[(revision.id, casilla.id)] = casilla.continuidad_id
                state.members[casilla.continuidad_id].append((revision.id, casilla.id))


def _index_existing_links(state: _ChainState, modelo: ModeloDefinition, revisions: tuple[ModeloRevision, ...]) -> None:
    for previous, successor in judged_pairs(modelo, revisions):
        for casilla in successor.casillas:
            if casilla.continuidad_id is None:
                continue
            carriers = [row for row in state.members[casilla.continuidad_id] if row[0] == previous.id]
            if len(carriers) != 1:
                continue
            row = (successor.id, casilla.id)
            state.predecessor_of[row] = carriers[0]
            evidence = casilla.continuidad_evidence
            state.grounded_link[row] = (
                casilla.continuidad_origin is CasillaLineageOrigin.GROUNDED
                and evidence is not None
                and bool(evidence.strip())
            )


def _links_for_occurrences(
    state: _ChainState,
    occurrences: set[_Row],
) -> dict[_Row, tuple[_Row, bool]]:
    return {
        row: (state.predecessor_of[row], state.grounded_link[row]) for row in occurrences if row in state.predecessor_of
    }


def _missing_semantic_roles(
    state: _ChainState,
    occurrences: set[_Row],
    links: Mapping[_Row, tuple[_Row, bool]],
) -> list[_Row]:
    return sorted(
        row for row in occurrences if state.roles[row] is None and not state._role_exempt(row, occurrences, links)
    )


def _single_declared_role(state: _ChainState, occurrences: set[_Row]) -> str | None:
    roles = {state.roles[row] for row in occurrences} - {None}
    return next(iter(roles)) if len(roles) == 1 else None


def _requires_role_derived_chain(state: _ChainState, chain: str, role: str, occurrences: set[_Row]) -> bool:
    revisions = {revision for revision, _ in occurrences}
    return all(state.role_counts[revision][role] == 1 for revision in revisions) and chain != _role_derived(role)
