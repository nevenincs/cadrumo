"""A return the table reports at two horizons is driven at each, and every line the pilot writes names its horizon."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...persona_table.frontend import read_results
from ...persona_table.rows import PlannedRow, Stage, TableRow
from ...persona_table.rows import write_rows as write_table_rows
from ..intake import OUT_ENV, PASSED, TREE_ENV, PilotRow, write_rows
from ..plan import expected_rows, plan_replays

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PERSONA = "synthetic-asalariada"
_YEAR = 7
"""A synthetic year: these rows meet no registry."""
_LOWER = _YEAR + 1
_HIGHER = _YEAR + 2
_KEY = (_PERSONA, "100", _YEAR, "0A")


def _table(horizon: int, figure: str) -> TableRow:
    return TableRow(
        persona=_PERSONA,
        modelo="100",
        year=_YEAR,
        period="0A",
        horizon=horizon,
        grounding="verified",
        sources=("ley-35-2006:art-19",),
        has_values=True,
        calculate=Stage.PASSED,
        verify=Stage.PASSED,
        export=Stage.PASSED,
        figures=(("0611", figure),),
    )


def _planned(year: int, horizon: int) -> PlannedRow:
    return PlannedRow(
        persona=_PERSONA,
        modelo="100",
        year=year,
        period="0A",
        horizon=horizon,
        has_values=True,
        grounding="verified",
        sources=(),
    )


def _owed(horizon: int) -> list[PlannedRow]:
    """Every annual return of the synthetic persona from ``_YEAR`` up to the year before ``horizon``."""
    return [_planned(year, horizon) for year in range(_YEAR, horizon)]


def test_a_return_the_table_reports_at_two_horizons_is_expected_and_driven_at_each(tmp_path: Path) -> None:
    rows = tmp_path / "rows.jsonl"
    write_table_rows(rows, [_table(_LOWER, "1200"), _table(_HIGHER, "1000")])

    expected = expected_rows(_PERSONA, rows)
    plan = plan_replays(expected, _owed)

    assert set(expected) == {(_KEY, _LOWER), (_KEY, _HIGHER)}
    assert dict(expected[_KEY, _LOWER].figures) == {"0611": "1200"}
    assert dict(expected[_KEY, _HIGHER].figures) == {"0611": "1000"}
    assert [replay.horizon for replay in plan.replays] == [_HIGHER, _LOWER]
    assert all(_KEY in replay.reported for replay in plan.replays)
    assert all(replay.returns[-1].key == _KEY for replay in plan.replays)
    assert plan.unplanned == ()


def test_a_table_row_its_horizon_does_not_owe_is_unplanned_at_that_horizon_only(tmp_path: Path) -> None:
    rows = tmp_path / "rows.jsonl"
    write_table_rows(rows, [_table(_LOWER, "1200"), _table(_HIGHER, "1000")])

    plan = plan_replays(expected_rows(_PERSONA, rows), lambda horizon: _owed(horizon) if horizon == _HIGHER else [])

    assert [replay.horizon for replay in plan.replays] == [_HIGHER]
    assert [(row.key, row.horizon) for row in plan.unplanned] == [(_KEY, _LOWER)]


def test_every_line_the_pilot_writes_states_its_horizon_and_reads_back_with_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(OUT_ENV, str(tmp_path / "tui.jsonl"))
    monkeypatch.setenv(TREE_ENV, "abc")
    lower, higher = (
        PilotRow(
            persona=_PERSONA,
            modelo="100",
            year=_YEAR,
            period="0A",
            horizon=horizon,
            calculate=PASSED,
            verify=PASSED,
            export=PASSED,
        )
        for horizon in (_LOWER, _HIGHER)
    )
    persona = PilotRow(persona=_PERSONA, loads=False, horizon=_LOWER, reasons=["the replay failed"])

    write_rows([lower, higher, persona])

    assert lower.result().horizon == _LOWER
    results = read_results(tmp_path)
    assert results["tui", _PERSONA, "100", _YEAR, "0A", _LOWER].horizon == _LOWER
    assert results["tui", _PERSONA, "100", _YEAR, "0A", _HIGHER].horizon == _HIGHER
    persona_line = results["tui", _PERSONA, None, _LOWER, None]
    assert (persona_line.horizon, persona_line.loads) == (_LOWER, False)
