"""Walk one adjacent edition pair and dispose of its successor rows in order."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from .casilla_lineage_seed_absence import classify_absence
from .casilla_lineage_seed_chain_state import _ChainState
from .casilla_lineage_seed_chain_writing import write_chain
from .casilla_lineage_seed_design import DesignInventory, DesignOracle, _design_trust
from .casilla_lineage_seed_rules import _PARTIAL_STAMP, admit_bare_chain, positional_hold
from .casilla_lineage_seed_ruling_application import apply_ruling
from .casilla_lineage_seed_types import LineagePlan, LineageRefusalCategory, Ruling

type _Pair = tuple[str, str]


class _PlannerContext(Protocol):
    """Mutable planner state used by the edition-pair walk."""

    modelo_id: str
    forbidden: frozenset[str]
    oracle: DesignOracle
    plan: LineagePlan
    rulings: dict[_Pair, Ruling]
    state: _ChainState

    def _already_disposed(self, casilla: CasillaDefinition) -> bool: ...

    def _new_chain_id(self, previous: CasillaDefinition, successor: CasillaDefinition, pair: _Pair) -> str: ...

    def _write_absence(
        self,
        revision: str,
        casilla: CasillaDefinition,
        origin: CasillaLineageOrigin,
        evidence: str,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class _PairContext:
    pair: _Pair
    ruling: Ruling | None
    claimed: set[str]
    handled: set[str]
    hold: str | None
    previous_by_id: dict[str, CasillaDefinition]
    previous_design: DesignInventory | str
    successor_design: DesignInventory | str
    design_trust: str | None
    prior_chains: set[str]


def walk_pair(planner: _PlannerContext, previous: ModeloRevision, successor: ModeloRevision) -> None:
    """Apply rulings and then judge every remaining successor row once."""
    context = _prepare_pair(planner, previous, successor)
    _walk_successors(planner, context, previous, successor)


def _prepare_pair(
    planner: _PlannerContext,
    previous: ModeloRevision,
    successor: ModeloRevision,
) -> _PairContext:
    pair = (previous.id, successor.id)
    ruling = planner.rulings.get(pair)
    claimed = _initial_claimed(previous, successor)
    handled = apply_ruling(planner, ruling, previous, successor, claimed) if ruling is not None else set()
    hold = None if ruling is not None else positional_hold(previous, successor)
    if hold is not None:
        planner.plan.notes.append(f"{previous.id} -> {successor.id}: {hold}")
    previous_design = planner.oracle.for_revision(previous)
    successor_design = planner.oracle.for_revision(successor)
    return _PairContext(
        pair=pair,
        ruling=ruling,
        claimed=claimed,
        handled=handled,
        hold=hold,
        previous_by_id={casilla.id: casilla for casilla in previous.casillas},
        previous_design=previous_design,
        successor_design=successor_design,
        design_trust=_design_trust(previous, successor, previous_design, successor_design),
        prior_chains=planner.state.ids_in(previous.id),
    )


def _initial_claimed(previous: ModeloRevision, successor: ModeloRevision) -> set[str]:
    successor_chains = {casilla.continuidad_id for casilla in successor.casillas}
    return {
        casilla.id
        for casilla in previous.casillas
        if casilla.continuidad_id is not None and casilla.continuidad_id in successor_chains
    }


def _walk_successors(
    planner: _PlannerContext,
    context: _PairContext,
    previous: ModeloRevision,
    successor: ModeloRevision,
) -> None:
    for casilla in successor.casillas:
        _judge_successor(planner, context, previous, successor, casilla)


def _judge_successor(
    planner: _PlannerContext,
    context: _PairContext,
    previous: ModeloRevision,
    successor: ModeloRevision,
    casilla: CasillaDefinition,
) -> None:
    if casilla.id in context.handled or planner._already_disposed(casilla):
        return
    if casilla.continuidad_id is not None and casilla.continuidad_id in context.prior_chains:
        planner.plan.counts["declared"] += 1
        return
    candidate = context.previous_by_id.get(casilla.id)
    if candidate is None:
        classify_absence(
            planner,
            previous,
            successor,
            casilla,
            context.previous_design,
            context.successor_design,
            context.design_trust,
        )
        return
    _judge_continuation(planner, context, candidate, casilla, successor)


def _judge_continuation(
    planner: _PlannerContext,
    context: _PairContext,
    candidate: CasillaDefinition,
    casilla: CasillaDefinition,
    successor: ModeloRevision,
) -> None:
    if context.ruling is not None and context.ruling.refuse_bare:
        _refuse_continuation(
            planner,
            successor,
            casilla,
            LineageRefusalCategory.RULING_REFUSES_BARE,
            "adjudication proves the identifier space was reassigned across this boundary",
            candidate,
        )
        return
    if context.hold is not None:
        _refuse_continuation(
            planner,
            successor,
            casilla,
            LineageRefusalCategory.POSITIONAL_HOLD,
            context.hold,
            candidate,
        )
        return
    category, detail = admit_bare_chain(candidate, casilla)
    if category is not None:
        _refuse_continuation(planner, successor, casilla, category, detail, candidate)
        return
    if casilla.id in planner.forbidden:
        _refuse_continuation(
            planner,
            successor,
            casilla,
            LineageRefusalCategory.PARTIAL_STAMP,
            _PARTIAL_STAMP,
            candidate,
        )
        return
    refusal = write_chain(
        planner,
        candidate,
        casilla,
        context.pair,
        CasillaLineageOrigin.SEEDED,
        None,
        context.claimed,
    )
    if refusal is not None:
        _refuse_continuation(
            planner,
            successor,
            casilla,
            LineageRefusalCategory.CHAIN_CONTRACT,
            refusal,
            candidate,
        )


def _refuse_continuation(
    planner: _PlannerContext,
    successor: ModeloRevision,
    casilla: CasillaDefinition,
    category: LineageRefusalCategory,
    reason: str,
    predecessor: CasillaDefinition,
) -> None:
    planner.plan.refuse(
        successor.id,
        casilla.id,
        category,
        reason,
        predecessor=predecessor.id,
    )
