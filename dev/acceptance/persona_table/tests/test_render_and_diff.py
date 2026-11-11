"""The rendered summary counts each verdict apart, and the diff names rows that turned green or regressed."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from ..__main__ import main
from ..diff import diff_tables, render_diff, row_id
from ..render import counts, render_table, summary_line, unchecked_causes
from ..rows import PlannedRow, Stage, TableRow, Verdict, write_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = 7
"""Any year: these tests exercise bookkeeping, not the registry envelope."""


def _row(
    period: str, calculate: Stage, verify: Stage = Stage.NOT_REACHED, export: Stage = Stage.NOT_REACHED
) -> TableRow:
    plan = PlannedRow(
        persona="persona",
        modelo="303",
        year=_YEAR,
        period=period,
        horizon=_YEAR + 1,
        has_values=True,
        grounding="verified",
        sources=("ley:art-1",),
    )
    return TableRow.from_plan(plan, calculate, verify=verify, export=export)


_GREEN = _row("1T", Stage.PASSED, Stage.PASSED, Stage.PASSED)
_HISTORY = _row("2T", Stage.HISTORY_FILED, Stage.HISTORY_FILED)
_RED_VERIFY = _row("3T", Stage.PASSED, Stage.INCOMPLETE, Stage.REFUSED)
_RED_CALCULATE = _row("4T", Stage.MISMATCH, Stage.PASSED, Stage.PASSED)


def test_the_summary_never_counts_history_filed_as_green() -> None:
    rows = [_GREEN, _HISTORY, _RED_VERIFY, _RED_CALCULATE]
    counted = counts(rows)
    assert counted[Verdict.PASSED.value] == 1
    assert counted[Verdict.HISTORY_FILED.value] == 1
    assert counted["fail:verify"] == 1
    assert counted["fail:calculate"] == 1
    assert summary_line(rows).startswith("green 1 / 4")


def test_the_table_lists_every_row_with_its_verdict() -> None:
    text = render_table([_GREEN, _HISTORY], head="abc", lanes={"303": "IVA"})
    assert "# Persona table at abc" in text
    assert "IVA 1/2" in text
    assert "| persona | 303 | 7 | 2T | history-filed |" in text


def test_each_lane_carries_its_unchecked_rows_beside_green_and_total() -> None:
    unchecked = dataclasses.replace(_GREEN, period="3T", unchecked=("role:dr303-46",))
    assert unchecked.verdict is Verdict.UNCHECKED
    text = render_table([_GREEN, _HISTORY, unchecked], head="abc", lanes={"303": "IVA"})
    assert "IVA 1/3 (unchecked 1)" in text
    assert "Summary: green 1 / 3," in text


def test_unchecked_rows_are_counted_per_cause_and_a_row_with_two_causes_under_each() -> None:
    gap = dataclasses.replace(_GREEN, period="2T", unchecked=("not-sourced:0003", "not-sourced:0017"))
    both = dataclasses.replace(_GREEN, period="3T", unchecked=("concept:cuota", "not-sourced:0003"))
    concept = dataclasses.replace(_GREEN, period="4T", unchecked=("concept:base",))
    rows = [_GREEN, gap, both, concept]
    assert unchecked_causes(rows) == {"concept": 2, "not-sourced": 2}
    text = render_table(rows, head="abc")
    assert "Unchecked rows by cause (a row with several causes counts under each): concept 2, not-sourced 2." in text


def test_the_diff_separates_green_regression_and_stage_moves() -> None:
    before = {row.key: row for row in (_GREEN, _RED_VERIFY, _RED_CALCULATE)}
    after = {
        _GREEN.key: _row("1T", Stage.PASSED, Stage.INCOMPLETE),
        _RED_VERIFY.key: _row("3T", Stage.PASSED, Stage.PASSED, Stage.PASSED),
        _RED_CALCULATE.key: _row("4T", Stage.MISMATCH, Stage.INCOMPLETE),
        _HISTORY.key: _HISTORY,
    }
    diff = diff_tables(before, after)
    assert diff.regressed == (_GREEN.key,)
    assert diff.turned_green == (_RED_VERIFY.key,)
    assert diff.stage_regressed == ((_RED_CALCULATE.key, "verify"), (_RED_CALCULATE.key, "export"))
    assert diff.added == (_HISTORY.key,)
    assert row_id(_GREEN.key) in render_diff(diff, before="a", after="b")


def test_check_fails_only_when_a_baseline_green_row_is_not_green(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    write_rows(baseline / "persona.jsonl", [_GREEN, _RED_VERIFY])
    held = tmp_path / "held.jsonl"
    write_rows(held, [_GREEN, _RED_CALCULATE])
    lost = tmp_path / "lost.jsonl"
    write_rows(lost, [dataclasses.replace(_GREEN, export=Stage.REFUSED)])
    assert main(["check", str(held), "--baseline", str(baseline)]) == 0
    assert main(["check", str(lost), "--baseline", str(baseline)]) == 1


def test_baseline_writes_one_file_per_persona(tmp_path: Path) -> None:
    rows = tmp_path / "rows.jsonl"
    write_rows(rows, [_GREEN, _HISTORY])
    assert main(["baseline", str(rows), "--dir", str(tmp_path / "baseline")]) == 0
    assert [path.name for path in (tmp_path / "baseline").iterdir()] == ["persona.jsonl"]


def test_render_prints_run_provenance_in_the_header() -> None:
    text = render_table([_GREEN], head="abc", provenance={"tree": "t1", "logical_generation": "g1"})
    assert "Run provenance: logical_generation `g1`, tree `t1`." in text
    assert "Run provenance" not in render_table([_GREEN], head="abc")
