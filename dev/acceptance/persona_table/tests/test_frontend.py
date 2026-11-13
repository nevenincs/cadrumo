"""The frontend column compares what the TUI and the window displayed with the Python row, stage by stage and figure by
figure, and a surface that was not run, did not load, or has nothing to compare never counts as matched."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from ..__main__ import main
from ..frontend import (
    STAGE_OF,
    FrontendResultError,
    PersonaCell,
    ResultKey,
    SurfaceResult,
    cell_text,
    compare_frontend,
    figure_causes,
    parity,
    parse_result,
    read_results,
)
from ..render import render_table
from ..rows import PlannedRow, Stage, TableRow, canonical_figures, write_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = 7
"""Any year: these tests exercise bookkeeping, not the registry envelope."""
_FIGURES = (("0505", "1200.5"), ("0700", "-2104.67"))


def _row(
    period: str = "1T",
    calculate: Stage = Stage.PASSED,
    verify: Stage = Stage.PASSED,
    export: Stage = Stage.PASSED,
    *,
    persona: str = "persona",
    figures: tuple[tuple[str, str], ...] = _FIGURES,
) -> TableRow:
    plan = PlannedRow(
        persona=persona,
        modelo="303",
        year=_YEAR,
        period=period,
        horizon=_YEAR + 1,
        has_values=True,
        grounding="verified",
        sources=("ley:art-1",),
    )
    return TableRow.from_plan(plan, calculate, verify=verify, export=export, figures=figures)


def _line(**overrides: object) -> dict[str, object]:
    line: dict[str, object] = {
        "surface": "tui",
        "tree": "abc",
        "persona": "persona",
        "modelo": "303",
        "year": _YEAR,
        "period": "1T",
        "loads": True,
        "calculate": "pass",
        "verify": "pass",
        "export": "pass",
        "figures": dict(_FIGURES),
    }
    return line | overrides


def _result(**overrides: object) -> SurfaceResult:
    return parse_result(json.dumps(_line(**overrides)))


def _write(directory: Path, name: str, lines: list[dict[str, object]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")


def test_every_python_stage_is_mapped_to_the_surface_vocabulary() -> None:
    assert set(STAGE_OF) == set(Stage)
    assert {stage for stage, word in STAGE_OF.items() if word is None} == {Stage.HISTORY_FILED, Stage.NOT_RUN}
    assert STAGE_OF[Stage.MISMATCH] == "pass"
    assert STAGE_OF[Stage.EXPECTED_REFUSAL] == "refused"
    assert STAGE_OF[Stage.OWED_SHOWN] == "incomplete"


@pytest.mark.parametrize(
    "overrides",
    [
        {"extra": 1},
        {"calculate": "passed"},
        {"surface": "browser"},
        {"loads": "yes"},
        {"year": "7"},
        {"year": True},
        {"figures": {"0505": 12}},
        {"figures": []},
        {"modelo": None},
        {"refusal_code": 3},
    ],
)
def test_a_result_line_with_an_unknown_key_or_a_bad_value_is_refused_naming_file_and_line(
    tmp_path: Path, overrides: dict[str, object]
) -> None:
    _write(tmp_path, "a.jsonl", [_line(), _line(**overrides)])
    with pytest.raises(FrontendResultError, match=r"a\.jsonl:2: "):
        read_results(tmp_path)


def test_a_line_missing_a_required_key_or_stage_is_refused(tmp_path: Path) -> None:
    without_tree = _line()
    del without_tree["tree"]
    without_export = _line()
    del without_export["export"]
    for line, word in ((without_tree, "tree"), (without_export, "export")):
        _write(tmp_path, "a.jsonl", [line])
        with pytest.raises(FrontendResultError, match=f"missing key {word}"):
            read_results(tmp_path)


def test_a_line_that_is_not_json_or_not_an_object_is_refused(tmp_path: Path) -> None:
    for text in ("{", "[]"):
        (tmp_path / "a.jsonl").write_text(text + "\n", encoding="utf-8")
        with pytest.raises(FrontendResultError, match=r"a\.jsonl:1: "):
            read_results(tmp_path)


def test_a_missing_directory_is_refused_and_an_empty_one_holds_no_result(tmp_path: Path) -> None:
    with pytest.raises(FrontendResultError, match="does not exist"):
        read_results(tmp_path / "absent")
    assert read_results(tmp_path) == {}


def test_a_persona_level_line_needs_no_stages_and_no_year() -> None:
    line = {"surface": "window", "tree": "abc", "persona": "p", "modelo": None, "year": None, "period": None}
    result = parse_result(json.dumps(line | {"loads": False, "reason": "profile locked"}))
    assert (result.modelo, result.loads, result.reason) == (None, False, "profile locked")
    with pytest.raises(ValueError, match="no year or period"):
        parse_result(json.dumps(line | {"loads": True, "year": _YEAR}))


def test_a_persona_level_line_may_state_its_stages_as_null() -> None:
    line = {
        "surface": "tui",
        "tree": "abc",
        "persona": "p",
        "modelo": None,
        "year": None,
        "period": None,
        "loads": True,
    }
    result = parse_result(json.dumps(line | {"calculate": None, "verify": None, "export": None}))
    assert (result.modelo, result.loads) == (None, True)
    with pytest.raises(ValueError, match="calculate must be one of"):
        parse_result(json.dumps(_line(calculate=None)))


def test_the_latest_line_wins_by_file_name_then_line_order(tmp_path: Path) -> None:
    _write(tmp_path, "b.jsonl", [_line(calculate="refused")])
    _write(tmp_path, "a.jsonl", [_line(calculate="error"), _line(calculate="incomplete")])
    _write(tmp_path, "c.jsonl", [_line(surface="window", calculate="error")])
    found = read_results(tmp_path)
    assert found[("tui", "persona", "303", _YEAR, "1T")].calculate == "refused"
    assert found[("window", "persona", "303", _YEAR, "1T")].calculate == "error"
    assert len(found) == 2


def test_a_matching_surface_is_matched_even_with_the_value_written_differently() -> None:
    shown = _result(figures={"0505": "1200.50", "0700": "-2104.670", "0999": "0.00"})
    outcome = parity(_row(), "tui", shown)
    assert (outcome.outcome, outcome.causes) == ("matched", ())


def test_a_stage_or_figure_that_differs_is_named_with_both_values() -> None:
    shown = _result(verify="incomplete", figures={"0505": "1200.5", "0700": "-3095.05", "0123": "10.00"})
    outcome = parity(_row(), "window", shown)
    assert outcome.outcome == "differs"
    assert outcome.causes == (
        "verify window incomplete, table pass",
        "casilla 0700 window -3095.05, table -2104.67",
        "casilla 0123 shown 10.00, table has none",
    )


def test_a_casilla_the_surface_does_not_show_differs() -> None:
    outcome = parity(_row(), "tui", _result(figures={"0700": "-2104.67"}))
    assert (outcome.outcome, outcome.causes) == ("differs", ("casilla 0505 not shown",))


def test_text_figures_compare_as_text() -> None:
    assert figure_causes("tui", {"0001": "ES12"}, {"0001": "ES12"}) == []
    assert figure_causes("tui", {"0001": "ES12"}, {"0001": "es12"}) == ["casilla 0001 tui es12, table ES12"]
    assert figure_causes("tui", {"0001": "10"}, {"0001": "ten"}) == ["casilla 0001 tui ten, table 10"]


def test_a_refused_python_row_matches_a_refusing_surface_with_no_figures() -> None:
    row = _row(calculate=Stage.REFUSED, verify=Stage.NOT_REACHED, export=Stage.NOT_REACHED, figures=())
    refusing = _result(calculate="refused", verify="not-reached", export="not-reached", figures={})
    assert parity(row, "tui", refusing).outcome == "matched"
    assert parity(row, "tui", _result()).outcome == "differs"


def test_a_row_that_calculated_without_recorded_figures_is_not_comparable() -> None:
    outcome = parity(_row(figures=()), "tui", _result())
    assert outcome.outcome == "not-comparable"
    assert "no figures" in outcome.causes[0]


@pytest.mark.parametrize("stage", [Stage.HISTORY_FILED, Stage.NOT_RUN])
def test_a_history_filed_or_not_run_row_is_not_comparable(stage: Stage) -> None:
    row = _row(calculate=stage, verify=Stage.NOT_REACHED, export=Stage.NOT_REACHED, figures=())
    assert parity(row, "tui", _result()).outcome == "not-comparable"


def test_a_row_without_a_surface_result_is_not_run_and_a_failed_load_is_load_failed() -> None:
    assert parity(_row(), "tui", None).outcome == "not-run"
    failed = parity(_row(), "tui", None, loads=False, load_reason="profile locked")
    assert (failed.outcome, failed.causes) == ("load-failed", ("profile locked",))
    assert parity(_row(), "tui", _result(loads=False, reason="no key")).outcome == "load-failed"


def test_figures_are_canonical_non_zero_and_sorted() -> None:
    figures = canonical_figures(
        {
            "0700": Decimal("-2104.670"),
            "0100": 100,
            "0200": Decimal("0.00"),
            "0300": 0,
            "0400": "ES12",
            "0500": True,
            "0600": False,
            "0800": "",
            "0150": Decimal("1E+2"),
        }
    )
    assert figures == (
        ("0100", "100"),
        ("0150", "100"),
        ("0400", "ES12"),
        ("0500", "True"),
        ("0700", "-2104.67"),
    )


def test_figures_round_trip_through_json_and_an_older_line_has_none(tmp_path: Path) -> None:
    row = _row()
    assert json.loads(row.to_json())["figures"] == dict(_FIGURES)
    write_rows(tmp_path / "rows.jsonl", [row])
    assert TableRow.from_json(row.to_json()).figures == _FIGURES
    older = json.loads(row.to_json())
    del older["figures"]
    assert TableRow.from_json(json.dumps(older)).figures == ()
    older["figures"] = ["0505"]
    with pytest.raises(ValueError, match="figures"):
        TableRow.from_json(json.dumps(older))


def test_a_baseline_line_holds_no_figures() -> None:
    row = _row()
    assert "figures" not in json.loads(row.to_baseline_json(row.horizon))


def _comparison() -> tuple[list[TableRow], dict[ResultKey, SurfaceResult]]:
    rows = [
        _row("1T"),
        _row("2T"),
        _row("3T"),
        _row("4T", figures=()),
        _row("1T", persona="other"),
        _row("1T", persona="locked"),
        _row("1T", persona="unrun"),
    ]
    lines = [
        _line(period="1T"),
        _line(period="2T", verify="incomplete"),
        _line(period="4T"),
        _line(period="0A"),
        _line(persona="other", loads=False, modelo=None, year=None, period=None, reason="locked"),
        _line(persona="locked", modelo=None, year=None, period=None, loads=False, reason="profile locked"),
    ]
    return rows, {parse_result(json.dumps(line)).key: parse_result(json.dumps(line)) for line in lines}


def test_the_persona_cell_counts_matched_differing_not_run_and_the_rest() -> None:
    rows, results = _comparison()
    comparison = compare_frontend(rows[:4], results)
    assert cell_text(comparison.cells["persona", "tui"]) == "loads, 1/4 matched, 1 differs, 1 not run, 1 not comparable"
    assert cell_text(comparison.cells["persona", "window"]) == "not yet run"
    assert [item.key[3] for item in comparison.extras["tui"]] == ["0A"]
    assert comparison.extras["tui"][0].causes == ("no table row",)


def test_the_cell_reads_as_documented_and_a_failed_load_fails_every_row() -> None:
    assert cell_text(PersonaCell(True, 7, {"matched": 5, "differs": 1, "not-run": 1})) == (
        "loads, 5/7 matched, 1 differs, 1 not run"
    )
    rows, results = _comparison()
    comparison = compare_frontend(rows, results)
    assert (
        cell_text(comparison.cells["locked", "tui"])
        == "does not load, 0/1 matched, 0 differs, 0 not run, 1 load failed"
    )
    locked = next(item for item in comparison.parities["tui"] if item.key[0] == "locked")
    assert (locked.outcome, locked.causes) == ("load-failed", ("profile locked",))
    assert cell_text(comparison.cells["unrun", "tui"]) == "not yet run"


def test_a_render_without_a_frontend_is_unchanged_and_with_one_adds_columns_line_and_matrix() -> None:
    rows, results = _comparison()
    plain = render_table(rows, head="abc")
    assert "Frontend" not in plain
    assert plain.count("| tui |") == 0
    text = render_table(rows, head="abc", frontend=compare_frontend(rows, results))
    assert "Frontend: TUI matched 1 / 7, window matched 0 / 7 (7 rows)\n" in text
    assert "| grounding | run | reason | tui | window |" in text
    lines = text.splitlines()
    first = next(line for line in lines if line.startswith(f"| persona | 303 | {_YEAR} | 1T |"))
    second = next(line for line in lines if line.startswith(f"| persona | 303 | {_YEAR} | 2T |"))
    assert first.endswith("| matched | not run |")
    assert second.endswith("| differs | not run |")
    matrix = text.split("## Frontend matrix", 1)[1]
    assert "| persona | TUI | window |" in matrix
    assert "| persona | loads, 1/4 matched, 1 differs, 1 not run, 1 not comparable | not yet run |" in matrix
    assert "| locked | does not load, 0/1 matched, 0 differs, 0 not run, 1 load failed | not yet run |" in matrix
    differing = matrix.split("### Rows differing", 1)[1]
    assert f"- persona|303|{_YEAR}|2T: tui differs: verify tui incomplete, table pass" in differing
    assert f"- persona|303|{_YEAR}|0A: tui extra: no table row" in differing
    assert f"- persona|303|{_YEAR}|4T: tui not-comparable: table row calculated but records no figures" in differing


def test_a_tree_other_than_the_head_is_named_in_the_cell() -> None:
    rows, _ = _comparison()
    result = _result(tree="def")
    comparison = compare_frontend(rows[:1], {result.key: result})
    text = render_table(rows[:1], head="abc", frontend=comparison)
    assert "| matched @def | not run |" in text


def test_render_with_frontend_publishes_the_columns_even_when_nothing_was_run(tmp_path: Path) -> None:
    rows_file, empty = tmp_path / "rows.jsonl", tmp_path / "frontend"
    empty.mkdir()
    write_rows(rows_file, [_row("1T"), _row("2T")])
    plain, with_frontend = tmp_path / "plain.md", tmp_path / "frontend.md"
    assert main(["render", str(rows_file), "--head", "abc", "--out", str(plain)]) == 0
    assert main(["render", str(rows_file), "--head", "abc", "--frontend", str(empty), "--out", str(with_frontend)]) == 0
    text = with_frontend.read_text(encoding="utf-8")
    assert "Frontend: TUI matched 0 / 2, window matched 0 / 2 (2 rows)" in text
    assert "| persona | not yet run | not yet run |" in text
    assert "not run | not run |" in text
    assert "Frontend" not in plain.read_text(encoding="utf-8")


def test_render_with_a_bad_frontend_line_exits_2_and_names_the_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows_file = tmp_path / "rows.jsonl"
    write_rows(rows_file, [_row("1T")])
    _write(tmp_path / "frontend", "a.jsonl", [_line(calculate="passed")])
    assert main(["render", str(rows_file), "--head", "abc", "--frontend", str(tmp_path / "frontend")]) == 2
    assert "a.jsonl:1" in capsys.readouterr().err
