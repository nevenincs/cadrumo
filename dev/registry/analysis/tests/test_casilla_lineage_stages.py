"""Lineage stage refusals and one-to-one writes at their owning package boundary."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions

from ...tests.casilla_lineage_planted_support import (
    PLANTED_MODELO,
    absence_modelo,
    design_oracle,
    held_modelo,
    held_pair_ruling,
    planted_casilla,
    planted_modelo,
    planted_revision,
)
from ..casilla_lineage_seed_absence import classify_absence
from ..casilla_lineage_seed_chain_writing import write_chain
from ..casilla_lineage_seed_modelo_planner import ModeloPlanner
from ..casilla_lineage_seed_pair_walk import walk_pair
from ..casilla_lineage_seed_ruling_application import apply_ruling
from ..casilla_lineage_seed_stamp_settlement import partial_stamp_records, settle_partial_stamps

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_split_lineage_stages_preserve_refusal_and_one_to_one_chain_boundaries() -> None:
    """The extracted public stages enforce their own evidence and cardinality guards."""
    previous = planted_revision("2023", date(2023, 1, 1), date(2023, 12, 31), (2023,), (planted_casilla(),))
    successor = planted_revision("2024", date(2024, 1, 1), None, (2024,), (planted_casilla(),))
    planner = ModeloPlanner(PLANTED_MODELO, planted_modelo(previous, successor), design_oracle(), [], frozenset())
    claimed: set[str] = set()
    assert (
        write_chain(
            planner,
            previous.casillas[0],
            successor.casillas[0],
            ("2023", "2024"),
            CasillaLineageOrigin.SEEDED,
            None,
            claimed,
        )
        is None
    )
    assert set(planner.plan.edits) == {("2023", "01"), ("2024", "01")}
    repeated_refusal = write_chain(
        planner,
        previous.casillas[0],
        successor.casillas[0],
        ("2023", "2024"),
        CasillaLineageOrigin.SEEDED,
        None,
        claimed,
    )
    assert repeated_refusal is not None and "one-to-one" in repeated_refusal
    assert settle_partial_stamps(planner) == frozenset()
    assert partial_stamp_records(planner, frozenset()) == ()

    missing = absence_modelo(origin=None)
    before, after = ordered_revisions(missing)
    before = before.model_copy(update={"casillas": ()})
    after = after.model_copy(update={"casillas": (after.casillas[-1],)})
    missing = planted_modelo(before, after)
    walker = ModeloPlanner(PLANTED_MODELO, missing, design_oracle(), [], frozenset())
    walk_pair(walker, before, after)
    assert walker.plan.refusals and not walker.plan.edits
    direct = ModeloPlanner(PLANTED_MODELO, missing, design_oracle(), [], frozenset())
    classify_absence(direct, before, after, after.casillas[0], "unreadable", "unreadable", "unreadable")
    assert direct.plan.refusals and not direct.plan.edits

    held = held_modelo(origin=None)
    held_before, held_after = ordered_revisions(held)
    ruled = ModeloPlanner(PLANTED_MODELO, held, design_oracle(), [], frozenset())
    handled = apply_ruling(
        ruled, held_pair_ruling(str(held_before.id), str(held_after.id)), held_before, held_after, set()
    )
    assert handled
    assert ruled.plan.refusals and not ruled.plan.edits
