"""Apply adjudicated lineage rulings to a single ordered edition boundary."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Protocol

from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from .casilla_lineage_seed_chain_state import _ChainState
from .casilla_lineage_seed_chain_writing import write_chain
from .casilla_lineage_seed_design import (
    DesignInventory,
    DesignOracle,
    _cite,
    _grounded_evidence,
    _ruled_new_evidence,
    printed_box,
)
from .casilla_lineage_seed_rules import _PARTIAL_STAMP
from .casilla_lineage_seed_types import LineagePlan, LineageRefusalCategory, Ruling


class _PlannerContext(Protocol):
    """The planner operations the ruling stage may mutate or consult."""

    modelo_id: str
    forbidden: frozenset[str]
    oracle: DesignOracle
    plan: LineagePlan
    state: _ChainState

    def _new_chain_id(
        self, previous: CasillaDefinition, successor: CasillaDefinition, pair: tuple[str, str]
    ) -> str: ...

    def _already_disposed(self, casilla: CasillaDefinition) -> bool: ...

    def _write_absence(
        self,
        revision: str,
        casilla: CasillaDefinition,
        origin: CasillaLineageOrigin,
        evidence: str,
    ) -> None: ...


def apply_ruling(
    planner: _PlannerContext,
    ruling: Ruling,
    previous: ModeloRevision,
    successor: ModeloRevision,
    claimed: set[str],
) -> set[str]:
    """Apply each ruling section in its authored order and return handled rows."""
    pair = (previous.id, successor.id)
    previous_rows = {casilla.id: casilla for casilla in previous.casillas}
    successor_rows = {casilla.id: casilla for casilla in successor.casillas}
    previous_design = planner.oracle.for_revision(previous)
    successor_design = planner.oracle.for_revision(successor)
    handled: set[str] = set()

    _apply_grounded_entries(
        planner,
        ruling,
        pair,
        previous_rows,
        successor_rows,
        previous_design,
        successor_design,
        claimed,
        handled,
    )
    _apply_contested_entries(planner, ruling, pair, previous_rows, successor_rows, handled)
    _apply_absence_entries(
        planner,
        ruling,
        previous,
        successor,
        previous_rows,
        successor_rows,
        previous_design,
        successor_design,
        handled,
    )
    _validate_ruling_names(planner, ruling, pair, previous_rows, successor_rows, previous)
    return handled


def _require_row(
    planner: _PlannerContext,
    pair: tuple[str, str],
    rows: Mapping[str, CasillaDefinition],
    casilla_id: str,
    side: str,
) -> CasillaDefinition:
    if casilla_id not in rows:
        raise ValueError(f"modelo {planner.modelo_id} ruling {pair}: unknown {side} row {casilla_id!r}")
    return rows[casilla_id]


def _apply_grounded_entries(
    planner: _PlannerContext,
    ruling: Ruling,
    pair: tuple[str, str],
    previous_rows: Mapping[str, CasillaDefinition],
    successor_rows: Mapping[str, CasillaDefinition],
    previous_design: DesignInventory | str,
    successor_design: DesignInventory | str,
    claimed: set[str],
    handled: set[str],
) -> None:
    for previous_id, successor_id in ruling.grounded:
        previous_row = _require_row(planner, pair, previous_rows, previous_id, "predecessor")
        successor_row = _require_row(planner, pair, successor_rows, successor_id, "successor")
        handled.add(successor_id)
        if planner._already_disposed(successor_row):
            continue
        if previous_id in planner.forbidden or successor_id in planner.forbidden:
            planner.plan.refuse(
                pair[1], successor_id, LineageRefusalCategory.PARTIAL_STAMP, _PARTIAL_STAMP, predecessor=previous_id
            )
            continue
        evidence = _grounded_evidence(previous_row, successor_row, previous_design, successor_design, ruling.rationale)
        if evidence is None:
            planner.plan.refuse(
                pair[1],
                successor_id,
                LineageRefusalCategory.GROUNDED_UNLOCALISED,
                "the ruling proves this continuation but neither a printed-box line nor a record campo "
                "locates both rows in the pinned designs",
                predecessor=previous_id,
            )
            continue
        refused = write_chain(
            planner,
            previous_row,
            successor_row,
            pair,
            CasillaLineageOrigin.GROUNDED,
            evidence,
            claimed,
        )
        if refused is not None:
            planner.plan.refuse(
                pair[1],
                successor_id,
                LineageRefusalCategory.GROUNDED_BLOCKED,
                f"{refused}. Evidence: {evidence}",
                predecessor=previous_id,
            )


def _apply_contested_entries(
    planner: _PlannerContext,
    ruling: Ruling,
    pair: tuple[str, str],
    previous_rows: Mapping[str, CasillaDefinition],
    successor_rows: Mapping[str, CasillaDefinition],
    handled: set[str],
) -> None:
    contested = (
        (ruling.held, ruling.held_reason, LineageRefusalCategory.HELD),
        (ruling.withheld, ruling.withheld_reason, LineageRefusalCategory.WITHHELD),
        (ruling.merged, ruling.merged_reason, LineageRefusalCategory.MERGED),
    )
    for entries, reason, category in contested:
        for previous_ids, successor_id in entries:
            _require_contested_predecessors(planner, pair, previous_rows, previous_ids)
            successor_row = _require_row(planner, pair, successor_rows, successor_id, "successor")
            handled.add(successor_id)
            if planner._already_disposed(successor_row):
                continue
            planner.plan.refuse(pair[1], successor_id, category, reason, predecessor=previous_ids or None)


def _require_contested_predecessors(
    planner: _PlannerContext,
    pair: tuple[str, str],
    previous_rows: Mapping[str, CasillaDefinition],
    previous_ids: str,
) -> None:
    for part in filter(None, (piece.strip() for piece in previous_ids.split(" + "))):
        _require_row(planner, pair, previous_rows, part, "predecessor")


def _apply_absence_entries(
    planner: _PlannerContext,
    ruling: Ruling,
    previous: ModeloRevision,
    successor: ModeloRevision,
    previous_rows: Mapping[str, CasillaDefinition],
    successor_rows: Mapping[str, CasillaDefinition],
    previous_design: DesignInventory | str,
    successor_design: DesignInventory | str,
    handled: set[str],
) -> None:
    for casilla_id, casilla in successor_rows.items():
        if _apply_absence_entry(
            planner,
            ruling,
            previous,
            successor,
            previous_rows,
            casilla_id,
            casilla,
            previous_design,
            successor_design,
            handled,
        ):
            continue


def _apply_absence_entry(
    planner: _PlannerContext,
    ruling: Ruling,
    previous: ModeloRevision,
    successor: ModeloRevision,
    previous_rows: Mapping[str, CasillaDefinition],
    casilla_id: str,
    casilla: CasillaDefinition,
    previous_design: DesignInventory | str,
    successor_design: DesignInventory | str,
    handled: set[str],
) -> bool:
    if casilla_id in handled:
        return True
    stem = _stem(casilla_id) if casilla_id not in previous_rows else None
    if stem is not None and stem in ruling.held_stems:
        handled.add(casilla_id)
        if not planner._already_disposed(casilla):
            planner.plan.refuse(successor.id, casilla_id, LineageRefusalCategory.HELD, ruling.held_reason)
        return True
    if casilla_id in ruling.new_on_form or (stem is not None and stem in ruling.new_on_form_stems):
        _apply_new_on_form_entry(planner, ruling, successor, casilla, previous_design, successor_design, handled)
        return True
    if casilla_id in ruling.not_on_form:
        _apply_not_on_form_entry(planner, ruling, successor, casilla, successor_design, handled)
        return True
    return False


def _apply_new_on_form_entry(
    planner: _PlannerContext,
    ruling: Ruling,
    successor: ModeloRevision,
    casilla: CasillaDefinition,
    previous_design: DesignInventory | str,
    successor_design: DesignInventory | str,
    handled: set[str],
) -> None:
    handled.add(casilla.id)
    if planner._already_disposed(casilla):
        return
    evidence = _ruled_new_evidence(casilla, previous_design, successor_design, ruling.rationale)
    if evidence is None:
        planner.plan.refuse(
            successor.id,
            casilla.id,
            LineageRefusalCategory.ABSENCE_UNLOCALISED,
            "the ruling finds no predecessor, but neither a printed-box line nor a record campo "
            "range locates the row in the pinned design",
        )
        return
    planner._write_absence(successor.id, casilla, CasillaLineageOrigin.NEW_ON_FORM, evidence)


def _apply_not_on_form_entry(
    planner: _PlannerContext,
    ruling: Ruling,
    successor: ModeloRevision,
    casilla: CasillaDefinition,
    successor_design: DesignInventory | str,
    handled: set[str],
) -> None:
    handled.add(casilla.id)
    if planner._already_disposed(casilla):
        return
    if printed_box(casilla) is not None:
        raise ValueError(f"modelo {planner.modelo_id}: not_on_form row {casilla.id!r} states a printed box")
    design = successor_design if isinstance(successor_design, DesignInventory) else None
    where = _cite(design, None) if design is not None else f"the {successor.id} record design"
    planner._write_absence(
        successor.id,
        casilla,
        CasillaLineageOrigin.NOT_ON_FORM,
        f"{where} numbers no box for this row and it states none; {ruling.rationale}",
    )


def _validate_ruling_names(
    planner: _PlannerContext,
    ruling: Ruling,
    pair: tuple[str, str],
    previous_rows: Mapping[str, CasillaDefinition],
    successor_rows: Mapping[str, CasillaDefinition],
    previous: ModeloRevision,
) -> None:
    named = set(ruling.new_on_form) | set(ruling.not_on_form)
    unknown = sorted(named - set(successor_rows))
    if unknown:
        raise ValueError(f"modelo {planner.modelo_id} ruling {pair}: unknown successor rows {unknown[:5]}")
    for casilla_id in sorted(ruling.discontinued):
        _require_row(planner, pair, previous_rows, casilla_id, "predecessor")
        planner.plan.notes.append(f"{previous.id} -> {pair[1]}: {casilla_id} is discontinued ({ruling.rationale})")


def _stem(casilla_id: str) -> str:
    return re.sub(r"-\d+$", "", casilla_id)
