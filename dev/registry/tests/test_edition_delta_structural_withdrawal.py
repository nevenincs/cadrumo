"""The edition migration withdraws a structural succession's source lineages exactly as the loader does.

A split or merge relation authored in the successor is the single declaration
that its source lineages end at that boundary. The loader drops them from what
the successor inherits; a migration that read only ``retired`` evolutions would
instead see an unretired withdrawal and block an edition the loader accepts.
Each case runs over a tree that loads cleanly, through the migration's real
edition reader and planner.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..compiler.loader import load_modelo_directory
from ..edition_delta_row_delta import choose_drops
from ..edition_delta_source import Placed, edition_lift, read_edition, row_id
from .test_casilla_structural_succession import tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize(
    ("merge", "withdrawn"),
    [(False, frozenset({"combined"})), (True, frozenset({"surname", "given"}))],
    ids=["split", "merge"],
)
def test_a_structural_succession_withdraws_its_source_lineages(
    tmp_path: Path, merge: bool, withdrawn: frozenset[str]
) -> None:
    modelo_dir = tree(tmp_path, delta=False, merge=merge)
    definition = load_modelo_directory(modelo_dir)
    predecessor_id, successor_id = sorted(definition.revisions)
    predecessor = edition_lift(read_edition(modelo_dir, predecessor_id))
    source = read_edition(modelo_dir, successor_id)
    successor = edition_lift(source)

    assert source.retired == withdrawn

    causes, _drops, _kept, _not_exact, _overrides, _removals, _positions, _attested, order, _normalised = choose_drops(
        definition=definition,
        revision_id=successor_id,
        predecessor=predecessor_id,
        inherited=[Placed(lift.row, predecessor_id) for lift in predecessor.lifts.values()],
        full_rows=list(successor.rows),
        lifts=successor.lifts,
        source=source,
        defaults=successor.defaults,
        storage_only=False,
    )

    assert causes == []
    assert order == tuple(row_id(row) for row in successor.rows)
    assert not set(order) & {row_id(row) for row in predecessor.rows}
