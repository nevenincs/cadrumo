"""A contradiction in an excluded modelo is recorded, not refused; elsewhere it still refuses.

An excluded modelo is adjudicated by hand outside the seeder, so its plan
proposes no edit and a contradiction found in it survives every run. The write
gate must therefore not refuse the corpus on its behalf -- the ledger is
whole-corpus or nothing, so that deadlocks every other modelo against a repair
the seeder cannot make. These tests pin both halves: the record is written with
its rows named, and the gate keeps its teeth where the seeder can actually act.
"""

from __future__ import annotations

import pytest

from cadrumo.core.toml import parse_toml
from dev.registry.analysis.casilla_lineage_seed import (
    EXCLUDED_MODELOS,
    partition_contradictions,
    render_ledger,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PLANTED = "2024/0570: grounded but chain 'irpf-cuota-liquida-estatal' absent from 2023"


def _an_excluded_modelo() -> str:
    return sorted(EXCLUDED_MODELOS)[0]


def _a_seeded_modelo() -> str:
    """A modelo id the seeder does seed, so the gate owns its contradictions."""
    candidate = "303"
    assert candidate not in EXCLUDED_MODELOS
    return candidate


def test_contradiction_in_an_excluded_modelo_does_not_block_the_write() -> None:
    blocking, excluded = partition_contradictions({_an_excluded_modelo(): [_PLANTED]})

    assert blocking == {}
    assert excluded == {_an_excluded_modelo(): [_PLANTED]}


def test_the_same_contradiction_in_a_seeded_modelo_still_blocks_the_write() -> None:
    blocking, excluded = partition_contradictions({_a_seeded_modelo(): [_PLANTED]})

    assert blocking == {_a_seeded_modelo(): [_PLANTED]}
    assert excluded == {}


def test_a_mixed_run_refuses_only_for_the_modelo_the_seeder_can_repair() -> None:
    blocking, excluded = partition_contradictions(
        {_an_excluded_modelo(): [_PLANTED], _a_seeded_modelo(): [_PLANTED], "038": []},
    )

    assert set(blocking) == {_a_seeded_modelo()}
    assert set(excluded) == {_an_excluded_modelo()}


def test_the_ledger_names_every_row_of_an_excluded_contradiction() -> None:
    second = "2024/0571: grounded but chain 'irpf-cuota-liquida-autonomica' absent from 2023"

    rendered = render_ledger(
        [],
        {},
        (),
        (),
        excluded_contradictions={_an_excluded_modelo(): [_PLANTED, second]},
        judged_at="test-run",
    )
    parsed = parse_toml(rendered)

    assert parsed["excluded_contradiction"] == [
        {"modelo": _an_excluded_modelo(), "contradictions": [_PLANTED, second]},
    ]


def test_the_ledger_omits_the_record_when_no_excluded_modelo_contradicts() -> None:
    rendered = render_ledger([], {}, (), (), excluded_contradictions={}, judged_at="test-run")

    assert "excluded_contradiction" not in parse_toml(rendered)
