"""Classify a successor row with no predecessor from the pinned record designs."""

from __future__ import annotations

from typing import Protocol

from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from .casilla_lineage_seed_design import DesignInventory, _cite, printed_box
from .casilla_lineage_seed_types import LineagePlan, LineageRefusalCategory


class _PlannerContext(Protocol):
    """The mutation needed to record or refuse an absence classification."""

    plan: LineagePlan

    def _write_absence(
        self,
        revision: str,
        casilla: CasillaDefinition,
        origin: CasillaLineageOrigin,
        evidence: str,
    ) -> None: ...


def classify_absence(
    planner: _PlannerContext,
    previous: ModeloRevision,
    successor: ModeloRevision,
    casilla: CasillaDefinition,
    previous_design: DesignInventory | str,
    successor_design: DesignInventory | str,
    design_trust: str | None,
) -> None:
    """Write a proven absence kind or refuse it in the plan."""
    box = printed_box(casilla)
    if box is None:
        _refuse_absence(
            planner,
            successor,
            casilla,
            LineageRefusalCategory.ABSENCE_UNCLASSIFIED,
            "no predecessor row and no printed box, so no record design can say which kind of absence this is",
        )
        return
    if design_trust is not None or isinstance(previous_design, str) or isinstance(successor_design, str):
        reason = design_trust or "the record design pair cannot be read"
        _refuse_absence(planner, successor, casilla, LineageRefusalCategory.ABSENCE_UNCLASSIFIED, reason)
        return
    if _predecessor_declares_box(planner, previous, successor, casilla, box):
        return
    _classify_printed_box(planner, previous, successor, casilla, box, previous_design, successor_design)


def _predecessor_declares_box(
    planner: _PlannerContext,
    previous: ModeloRevision,
    successor: ModeloRevision,
    casilla: CasillaDefinition,
    box: int | str,
) -> bool:
    declarers = sorted(other.id for other in previous.casillas if printed_box(other) == box)
    if not declarers:
        return False
    _refuse_absence(
        planner,
        successor,
        casilla,
        LineageRefusalCategory.PRINTED_BOX_FORK,
        f"the predecessor edition declares printed box [{box}] on {declarers[:2]}; identity is read from "
        "form_number alone and lineage is one-to-one, so this is not an absence",
    )
    return True


def _classify_printed_box(
    planner: _PlannerContext,
    previous: ModeloRevision,
    successor: ModeloRevision,
    casilla: CasillaDefinition,
    box: int | str,
    previous_design: DesignInventory,
    successor_design: DesignInventory,
) -> None:
    successor_line = successor_design.defining_line(box)
    if successor_line is None:
        _refuse_unlocalised_box(planner, successor, casilla, successor_design, box)
        return
    if box in previous_design.boxes:
        _classify_predecessor_printing(planner, previous, successor, casilla, previous_design, box)
        return
    planner._write_absence(
        successor.id,
        casilla,
        CasillaLineageOrigin.NEW_ON_FORM,
        f"{_cite(successor_design, successor_line)} prints box [{box}]; {_cite(previous_design, None)} prints no box "
        f"[{box}] and retires none",
    )


def _classify_predecessor_printing(
    planner: _PlannerContext,
    previous: ModeloRevision,
    successor: ModeloRevision,
    casilla: CasillaDefinition,
    previous_design: DesignInventory,
    box: int | str,
) -> None:
    previous_line = previous_design.defining_line(box)
    if previous_line is None:
        _refuse_unlocalised_box(planner, successor, casilla, previous_design, box)
        return
    planner._write_absence(
        successor.id,
        casilla,
        CasillaLineageOrigin.PREDECESSOR_EDITION_SILENT,
        f"{_cite(previous_design, previous_line)} prints box [{box}] ({previous_design.snippet(previous_line)}); "
        f"edition {previous.id} declares no row for it",
    )


def _refuse_unlocalised_box(
    planner: _PlannerContext,
    revision: ModeloRevision,
    casilla: CasillaDefinition,
    design: DesignInventory,
    box: int | str,
) -> None:
    planner.plan.refuse(
        revision.id,
        casilla.id,
        LineageRefusalCategory.ABSENCE_UNCLASSIFIED,
        f"box [{box}] is printed on more than one line of {design.relative_path}; page is unqualified: "
        f"{design.unlocalised_reason(box)}",
    )


def _refuse_absence(
    planner: _PlannerContext,
    revision: ModeloRevision,
    casilla: CasillaDefinition,
    category: LineageRefusalCategory,
    reason: str,
) -> None:
    planner.plan.refuse(revision.id, casilla.id, category, reason)
