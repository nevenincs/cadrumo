"""Validate and record one lineage continuation in a modelo plan."""

from __future__ import annotations

from typing import Protocol

from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from .casilla_id_grammar import classify_casilla_id
from .casilla_lineage_seed_chain_state import _ChainState
from .casilla_lineage_seed_rules import _CONTINUIDAD_ID
from .casilla_lineage_seed_types import LineagePlan

type _Pair = tuple[str, str]
type _Row = tuple[str, str]


class _PlannerContext(Protocol):
    """The narrow planner state needed while writing a continuation."""

    state: _ChainState
    plan: LineagePlan

    def _new_chain_id(self, previous: CasillaDefinition, successor: CasillaDefinition, pair: _Pair) -> str: ...


def write_chain(
    planner: _PlannerContext,
    previous: CasillaDefinition,
    successor: CasillaDefinition,
    pair: _Pair,
    origin: CasillaLineageOrigin,
    evidence: str | None,
    claimed: set[str],
) -> str | None:
    """Plan a continuation, returning its refusal reason when validation fails."""
    identifiers = _validated_chain(planner, previous, successor, pair, claimed)
    if isinstance(identifiers, str):
        return identifiers
    prev_key, succ_key, prev_chain, succ_chain, chain = identifiers
    grounded = origin is CasillaLineageOrigin.GROUNDED and bool(evidence and evidence.strip())
    violation = planner.state.linkage_violation(chain, (prev_key, succ_key), grounded)
    if violation is not None:
        return violation
    _record_chain(
        planner,
        previous,
        successor,
        pair,
        origin,
        evidence,
        claimed,
        prev_key,
        succ_key,
        prev_chain,
        succ_chain,
        chain,
        grounded,
    )
    return None


def _validated_chain(
    planner: _PlannerContext,
    previous: CasillaDefinition,
    successor: CasillaDefinition,
    pair: _Pair,
    claimed: set[str],
) -> tuple[_Row, _Row, str | None, str | None, str] | str:
    if classify_casilla_id(previous.id) != classify_casilla_id(successor.id):
        return "the two identifiers use different grammars; no chain may cross a grammar"
    prev_key, succ_key = (pair[0], previous.id), (pair[1], successor.id)
    prev_chain, succ_chain = planner.state.ids.get(prev_key), planner.state.ids.get(succ_key)
    if prev_chain is not None and succ_chain is not None and prev_chain != succ_chain:
        return f"declared lineage disagrees: predecessor carries {prev_chain!r}, successor {succ_chain!r}"
    chain = prev_chain or succ_chain or planner._new_chain_id(previous, successor, pair)
    if not _CONTINUIDAD_ID.match(chain):
        return f"no valid continuidad_id derivable from {previous.id!r}"
    if previous.id in claimed:
        return f"predecessor {previous.id!r} is already continued by another row; lineage is one-to-one"
    conflict = _existing_chain_conflict(planner, pair, prev_key, succ_key, prev_chain, succ_chain, chain)
    if conflict is not None:
        return conflict
    return prev_key, succ_key, prev_chain, succ_chain, chain


def _existing_chain_conflict(
    planner: _PlannerContext,
    pair: _Pair,
    prev_key: _Row,
    succ_key: _Row,
    prev_chain: str | None,
    succ_chain: str | None,
    chain: str,
) -> str | None:
    holders = {
        row for row in planner.state.members.get(chain, ()) if row[0] in pair and row not in (prev_key, succ_key)
    }
    if holders:
        return f"chain {chain!r} is already carried by {sorted(holders)[:2]} in this pair"
    if prev_chain is None and succ_chain is None and planner.state.members.get(chain):
        return f"derived chain id {chain!r} already names another chain in this modelo"
    return None


def _record_chain(
    planner: _PlannerContext,
    previous: CasillaDefinition,
    successor: CasillaDefinition,
    pair: _Pair,
    origin: CasillaLineageOrigin,
    evidence: str | None,
    claimed: set[str],
    prev_key: _Row,
    succ_key: _Row,
    prev_chain: str | None,
    succ_chain: str | None,
    chain: str,
    grounded: bool,
) -> None:
    planner.state.link(chain, (prev_key, succ_key))
    planner.state.record_link(prev_key, succ_key, grounded)
    claimed.add(previous.id)
    if prev_chain is None:
        planner.plan.set_keys(pair[0], previous.id, continuidad_id=chain)
    keys = {"continuidad_origin": origin.value}
    if succ_chain is None:
        keys["continuidad_id"] = chain
    if evidence is not None:
        keys["continuidad_evidence"] = planner.plan.record_evidence(pair[1], successor.id, evidence)
    planner.plan.set_keys(pair[1], successor.id, **keys)
    planner.plan.counts[origin.value] += 1
