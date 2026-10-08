"""Settle identifiers whose lineage ids are present on only some occurrences."""

from __future__ import annotations

import collections
from typing import Protocol

from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from .casilla_lineage_seed_chain_state import _ChainState
from .casilla_lineage_seed_rules import _CONTINUIDAD_ID, _role_derived, _slug
from .casilla_lineage_seed_types import LineagePlan, PartialStamping, Ruling

type _Row = tuple[str, str]
type _Pair = tuple[str, str]


class _PlannerContext(Protocol):
    """The model and mutable chain index required for stamp settlement."""

    modelo_id: str
    modelo: ModeloDefinition
    plan: LineagePlan
    rulings: dict[_Pair, Ruling]
    state: _ChainState


def settle_partial_stamps(planner: _PlannerContext) -> frozenset[str]:
    """Start eligible unstamped occurrences or return identifiers left unresolved."""
    revisions = ordered_revisions(planner.modelo)
    first = revisions[0].id
    ruled_first = _ruled_first_rows(planner, first)
    occurrences = _occurrences_by_id(revisions)
    unsettled, starts = _partial_start_candidates(planner, occurrences, first, ruled_first)
    if unsettled:
        return frozenset(unsettled)
    _apply_chain_starts(planner, starts)
    return frozenset[str]()


def partial_stamp_records(planner: _PlannerContext, unsettled: frozenset[str]) -> tuple[PartialStamping, ...]:
    """Describe the source corpus's unresolved stamped and unstamped occurrences."""
    records = [_partial_stamp_record(planner, casilla_id) for casilla_id in sorted(unsettled)]
    return tuple(records)


def _ruled_first_rows(planner: _PlannerContext, first: str) -> set[str]:
    return {
        part.strip()
        for ruling in planner.rulings.values()
        if ruling.predecessor == first
        for group in (ruling.grounded, ruling.held, ruling.withheld, ruling.merged)
        for left, _ in group
        for part in left.split(" + ")
        if part.strip()
    }


def _occurrences_by_id(revisions) -> dict[str, list[str]]:
    occurrences: dict[str, list[str]] = collections.defaultdict(list)
    for revision in revisions:
        for casilla in revision.casillas:
            occurrences[casilla.id].append(revision.id)
    return occurrences


def _partial_start_candidates(
    planner: _PlannerContext,
    occurrences: dict[str, list[str]],
    first: str,
    ruled_first: set[str],
) -> tuple[set[str], list[_Row]]:
    unsettled: set[str] = set()
    starts: list[_Row] = []
    for casilla_id, found in occurrences.items():
        unstamped = [revision for revision in found if (revision, casilla_id) not in planner.state.ids]
        if len(found) < 2 or not unstamped or len(unstamped) == len(found):
            continue
        if all(_may_start_chain(planner, revision, casilla_id, first, ruled_first) for revision in unstamped):
            starts.extend((revision, casilla_id) for revision in unstamped)
        else:
            unsettled.add(casilla_id)
    return unsettled, starts


def _may_start_chain(
    planner: _PlannerContext,
    revision: str,
    casilla_id: str,
    first: str,
    ruled_first: set[str],
) -> bool:
    planned = planner.plan.edits.get((revision, casilla_id), {}).get("continuidad_origin")
    if planned is not None:
        return not CasillaLineageOrigin(planned).continues_a_chain
    for casilla in planner.modelo.revisions[revision].casillas:
        if casilla.id == casilla_id and casilla.continuidad_origin is not None:
            return not casilla.continuidad_origin.continues_a_chain
    return revision == first and casilla_id in ruled_first


def _apply_chain_starts(planner: _PlannerContext, starts: list[_Row]) -> None:
    for revision, casilla_id in starts:
        chain = _fresh_chain_id(planner, revision, casilla_id)
        planner.state.link(chain, ((revision, casilla_id),))
        planner.plan.set_keys(revision, casilla_id, continuidad_id=chain)
        planner.plan.counts["chain_start"] += 1


def _fresh_chain_id(planner: _PlannerContext, revision: str, casilla_id: str) -> str:
    role = planner.state.roles[(revision, casilla_id)]
    candidates: list[str] = [_role_derived(role)] if role is not None else []
    candidates += [_slug(casilla_id), _slug(f"{casilla_id}-{revision}")]
    for candidate in candidates:
        if candidate and _CONTINUIDAD_ID.match(candidate) and not planner.state.members.get(candidate):
            return candidate
    raise ValueError(f"modelo {planner.modelo_id}: no free continuidad_id for {revision}/{casilla_id}")


def _partial_stamp_record(planner: _PlannerContext, casilla_id: str) -> PartialStamping:
    stamped: list[str] = []
    unstamped: list[str] = []
    chains: list[str] = []
    for revision in ordered_revisions(planner.modelo):
        if all(casilla.id != casilla_id for casilla in revision.casillas):
            continue
        chain = planner.state.ids.get((revision.id, casilla_id))
        if chain is None:
            unstamped.append(revision.id)
            continue
        stamped.append(revision.id)
        if chain not in chains:
            chains.append(chain)
    return PartialStamping(
        modelo=planner.modelo_id,
        casilla=casilla_id,
        chain=" + ".join(chains),
        stamped=tuple(stamped),
        unstamped=tuple(unstamped),
    )
