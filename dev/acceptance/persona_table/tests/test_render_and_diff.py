"""The rendered summary counts each verdict apart, and the diff names rows that turned green or regressed."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from ..__main__ import _envelope, main
from ..diff import diff_tables, render_diff, row_id
from ..render import CoverageGap, counts, load_coverage_gaps, render_table, summary_line, unchecked_causes
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


def test_the_summary_counts_a_not_owed_row_as_green_and_names_it_apart() -> None:
    not_owed = dataclasses.replace(_row("1P", Stage.PASSED, Stage.NOT_OWED), modelo="202")
    owed_shown = dataclasses.replace(_row("2P", Stage.PASSED, Stage.OWED_SHOWN), modelo="202")
    rows = [_GREEN, not_owed, owed_shown]
    assert (not_owed.verdict, owed_shown.verdict) == (Verdict.NOT_OWED, Verdict.FAIL)
    line = summary_line(rows)
    assert line.startswith("green 2 / 3")
    assert "not-owed 1" in line
    assert counts(rows)["fail:verify"] == 1


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


def test_the_diff_keeps_the_unchecked_items_an_earlier_table_was_written_with(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    horizon = _envelope().horizon
    plan = PlannedRow(
        persona="autonomo-electricista",
        modelo="100",
        year=horizon - 1,
        period="0A",
        horizon=horizon,
        has_values=True,
        grounding="verified",
        sources=("ley:art-1",),
    )
    passed = TableRow.from_plan(plan, Stage.PASSED, verify=Stage.PASSED, export=Stage.PASSED)
    before, after = tmp_path / "before.jsonl", tmp_path / "after.jsonl"
    write_rows(before, [dataclasses.replace(passed, unchecked=("concept:retired",))])
    write_rows(after, [passed])
    assert main(["diff", str(before), str(after), "--before-label", "old", "--after-label", "new"]) == 0
    turned = capsys.readouterr().out.split("## Turned green (1)", 1)[1].split("##", 1)[0]
    assert "autonomo-electricista|100|" in turned


def test_baseline_writes_one_file_per_persona(tmp_path: Path) -> None:
    rows = tmp_path / "rows.jsonl"
    write_rows(rows, [_GREEN, _HISTORY])
    assert main(["baseline", str(rows), "--dir", str(tmp_path / "baseline")]) == 0
    assert [path.name for path in (tmp_path / "baseline").iterdir()] == ["persona.jsonl"]


def test_render_prints_run_provenance_in_the_header() -> None:
    text = render_table([_GREEN], head="abc", provenance={"tree": "t1", "logical_generation": "g1"})
    assert "Run provenance: logical_generation `g1`, tree `t1`." in text
    assert "Run provenance" not in render_table([_GREEN], head="abc")


_NOT_RUN = _row("2T", Stage.NOT_RUN)


def test_the_rows_line_without_coverage_says_the_expected_count_is_the_table_plan_only() -> None:
    text = render_table([_GREEN, _HISTORY, _NOT_RUN], head="abc")
    assert "Rows: expected 3 (table plan only; no coverage audit) / run 2\n" in text
    assert "Coverage gaps" not in text


def test_not_run_rows_are_expected_but_never_run() -> None:
    assert _NOT_RUN.verdict is Verdict.NOT_RUN
    text = render_table([_NOT_RUN, _dup("3T"), _dup("4T")], head="abc", coverage_gaps=())
    assert "Rows: expected 3 / run 2\n" in text


def _dup(period: str) -> TableRow:
    return dataclasses.replace(_GREEN, period=period)


def test_coverage_with_no_gaps_expects_only_the_planned_rows_and_adds_no_section() -> None:
    text = render_table([_GREEN, _HISTORY], head="abc", coverage_gaps=())
    assert "Rows: expected 2 / run 2\n" in text
    assert "table plan only" not in text
    assert "Coverage gaps" not in text


def test_coverage_gaps_raise_the_expected_count_and_are_listed_sorted() -> None:
    gaps = (CoverageGap("persona", "303", _YEAR, "4T"), CoverageGap("alpha", "130", _YEAR, "1T"))
    text = render_table([_GREEN, _HISTORY], head="abc", coverage_gaps=gaps)
    lines = text.splitlines()
    assert lines[lines.index(next(line for line in lines if line.startswith("Summary: "))) + 1] == (
        "Rows: expected 4 / run 2"
    )
    section = text.split("## Coverage gaps (2)", 1)[1].split("Verdicts:", 1)[0]
    assert section.split() == ["-", f"alpha|130|{_YEAR}|1T", "-", f"persona|303|{_YEAR}|4T"]


def test_coverage_gaps_load_from_the_coverage_file(tmp_path: Path) -> None:
    path = tmp_path / "coverage.json"
    path.write_text(
        '{"horizon": 9, "gaps": [{"persona": "p", "modelo": "303", "year": 7, "period": "1T", "source": "calendar"}]}',
        encoding="utf-8",
    )
    assert load_coverage_gaps(path) == (CoverageGap("p", "303", 7, "1T"),)


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        "[]",
        '{"horizon": 9}',
        '{"gaps": ["x"]}',
        '{"gaps": [{"persona": "p", "modelo": "303", "year": 7}]}',
        '{"gaps": [{"persona": "p", "modelo": "303", "year": "7", "period": "1T"}]}',
    ],
)
def test_a_malformed_coverage_file_is_refused(tmp_path: Path, content: str) -> None:
    path = tmp_path / "coverage.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="coverage file"):
        load_coverage_gaps(path)
