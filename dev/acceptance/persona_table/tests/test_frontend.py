"""The frontend column compares what the TUI, the window and the CLI displayed with the Python row, stage by stage and
figure by figure, and a surface that was not run, did not load, or has nothing to compare never counts as matched."""

from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path

import pytest

from ..__main__ import main
from ..frontend import (
    EXPORT_WITHHELD_UNVERIFIED,
    STAGE_OF,
    FrontendResultError,
    PersonaCell,
    ResultKey,
    SurfaceResult,
    cell_text,
    compare_frontend,
    export_refusal_code,
    extra_figures,
    figure_causes,
    parity,
    parse_result,
    read_results,
)
from ..render import render_table, unavailable_exports_lines
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
    horizon: int = _YEAR + 1,
    figures: tuple[tuple[str, str], ...] | None = _FIGURES,
    internal_figures: tuple[tuple[str, str], ...] = (),
    reason: str = "",
) -> TableRow:
    plan = PlannedRow(
        persona=persona,
        modelo="303",
        year=_YEAR,
        period=period,
        horizon=horizon,
        has_values=True,
        grounding="verified",
        sources=("ley:art-1",),
    )
    return TableRow.from_plan(
        plan, calculate, verify=verify, export=export, figures=figures, internal_figures=internal_figures, reason=reason
    )


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


def _write(directory: Path, name: str, lines: list[dict[str, object]]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    return path


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


def test_the_latest_line_wins_by_file_age_then_line_order(tmp_path: Path) -> None:
    older = _write(tmp_path, "z.jsonl", [_line(calculate="refused")])
    newer = _write(tmp_path, "a.jsonl", [_line(calculate="error"), _line(calculate="incomplete")])
    _write(tmp_path, "c.jsonl", [_line(surface="window", calculate="error")])
    os.utime(older, ns=(1_000_000_000, 1_000_000_000))
    os.utime(newer, ns=(2_000_000_000, 2_000_000_000))
    found = read_results(tmp_path)
    assert found[("tui", "persona", "303", _YEAR, "1T")].calculate == "incomplete"
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
    )
    assert (outcome.extra_names, outcome.extra_casillas) == (("0123",), 1)


def test_casillas_beyond_the_table_row_never_make_a_row_differ_and_are_counted() -> None:
    shown = _result(
        figures={"0505": "1200.5", "0700": "-2104.67", "DPNIF_D": "12345678Z", "0002": "21", "0003": "0.00"}
    )
    outcome = parity(_row(), "tui", shown)
    assert (outcome.outcome, outcome.causes) == ("matched", ())
    assert (outcome.extra_names, outcome.extra_casillas) == (("0002", "DPNIF_D"), 2)
    assert extra_figures({"0505": "1"}, {"0505": "1", "0002": "0", "0003": "7"}) == ("0003",)
    assert parity(_row(), "tui", _result(figures=dict(_FIGURES))).extra_casillas == 0


def test_the_cell_counts_rows_showing_extra_casillas_only_when_there_are_some() -> None:
    rows = [_row("1T"), _row("2T"), _row("3T")]
    lines = [
        _line(period="1T", figures={"0505": "1200.50", "0700": "-2104.67", "SEXO_D": "H"}),
        _line(period="2T", figures={"0505": "1200.50", "0700": "-2104.67", "02": "21", "05": "10"}),
        _line(period="3T"),
    ]
    results = {parse_result(json.dumps(line)).key: parse_result(json.dumps(line)) for line in lines}
    cell = compare_frontend(rows, results).cells["persona", "tui"]
    assert cell.extra_rows == 2
    assert cell_text(cell) == "loads, 3/3 matched, 0 differs, 0 not run, 2 rows show extra casillas"
    assert "show extra" not in cell_text(PersonaCell(True, 1, {"matched": 1}))


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
    outcome = parity(_row(figures=None), "tui", _result())
    assert outcome.outcome == "not-comparable"
    assert "no figures" in outcome.causes[0]


def test_a_calculated_row_recorded_with_no_figures_is_compared_on_its_stages() -> None:
    not_owed = _row(verify=Stage.NOT_OWED, export=Stage.NOT_REACHED, figures=())
    assert not_owed.figures_recorded
    matching = _result(verify="not-owed", export="not-reached", figures={})
    assert parity(not_owed, "tui", matching).outcome == "matched"
    differing = parity(not_owed, "tui", _result(verify="pass", export="not-reached", figures={}))
    assert differing.outcome == "differs"
    shown = parity(not_owed, "tui", _result(verify="not-owed", export="not-reached", figures={"0505": "3"}))
    assert (shown.outcome, shown.extra_names) == ("matched", ("0505",))


def test_recorded_ness_is_the_presence_of_the_figures_object_in_a_json_line() -> None:
    recorded = _row(figures=())
    line = json.loads(recorded.to_json())
    assert line["figures"] == {}
    assert "figures_recorded" not in line
    assert TableRow.from_json(recorded.to_json()).figures_recorded
    unrecorded = _row(figures=None)
    older = json.loads(unrecorded.to_json())
    assert "figures" not in older
    assert not TableRow.from_json(json.dumps(older)).figures_recorded
    assert TableRow.from_json(unrecorded.to_json()) == unrecorded
    assert TableRow.from_json(recorded.to_json()) == recorded
    baseline = recorded.to_baseline_json(recorded.horizon)
    assert not TableRow.from_json(baseline, horizon=recorded.horizon).figures_recorded


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
    assert "internal_figures" not in json.loads(row.to_baseline_json(row.horizon))


_INTERNAL = (("PH18", "1"), ("RESINGDEV", "-2158.99"))


def test_internal_figures_round_trip_through_json_and_an_older_line_has_none() -> None:
    row = _row(internal_figures=_INTERNAL)
    assert json.loads(row.to_json())["internal_figures"] == dict(_INTERNAL)
    again = TableRow.from_json(row.to_json())
    assert (again.figures, again.internal_figures) == (_FIGURES, _INTERNAL)
    older = json.loads(row.to_json())
    del older["internal_figures"]
    assert TableRow.from_json(json.dumps(older)).internal_figures == ()
    older["internal_figures"] = ["PH18"]
    with pytest.raises(ValueError, match="figures"):
        TableRow.from_json(json.dumps(older))


def test_a_surface_is_not_held_to_a_rows_internal_figures_and_they_are_not_extras() -> None:
    row = _row(internal_figures=_INTERNAL)
    outcome = parity(row, "window", _result(figures=dict(_FIGURES)))
    assert (outcome.outcome, outcome.causes, outcome.extra_casillas) == ("matched", (), 0)
    shown = parity(row, "tui", _result(figures={**dict(_FIGURES), "PH18": "1", "0002": "21"}))
    assert (shown.outcome, shown.extra_names) == ("matched", ("0002",))


def _comparison() -> tuple[list[TableRow], dict[ResultKey, SurfaceResult]]:
    rows = [
        _row("1T"),
        _row("2T"),
        _row("3T"),
        _row("4T", figures=None),
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
    assert "Frontend: TUI matched 1 / 7, window matched 0 / 7, CLI matched 0 / 7 (7 rows)\n" in text
    assert "| grounding | run | reason | tui | window | cli |" in text
    assert "\nTrees folded: tui abc (3)\n" in text
    lines = text.splitlines()
    first = next(line for line in lines if line.startswith(f"| persona | 303 | {_YEAR} | 1T |"))
    second = next(line for line in lines if line.startswith(f"| persona | 303 | {_YEAR} | 2T |"))
    assert first.endswith("| matched | not run | not run |")
    assert second.endswith("| differs | not run | not run |")
    matrix = text.split("## Frontend matrix", 1)[1]
    assert "| persona | TUI | window | CLI |" in matrix
    assert (
        "| persona | loads, 1/4 matched, 1 differs, 1 not run, 1 not comparable | not yet run | not yet run |" in matrix
    )
    assert (
        "| locked | does not load, 0/1 matched, 0 differs, 0 not run, 1 load failed | not yet run | not yet run |"
        in matrix
    )
    differing = matrix.split("### Rows differing", 1)[1]
    assert f"- persona|303|{_YEAR}|2T: tui differs: verify tui incomplete, table pass" in differing
    assert f"- persona|303|{_YEAR}|0A: tui extra: no table row" in differing
    assert f"- persona|303|{_YEAR}|4T: tui not-comparable: table row calculated but records no figures" in differing


def test_a_tree_other_than_the_head_is_named_in_the_cell() -> None:
    rows, _ = _comparison()
    result = _result(tree="def")
    comparison = compare_frontend(rows[:1], {result.key: result})
    text = render_table(rows[:1], head="abc", frontend=comparison)
    assert "| matched @def | not run | not run |" in text


def _tree_results(trees: dict[str, str]) -> dict[ResultKey, SurfaceResult]:
    """TUI results for the rows of the given periods (period to tree)."""
    results = [_result(period=period, tree=tree) for period, tree in trees.items()]
    return {result.key: result for result in results}


def test_a_cell_on_the_head_tree_is_unchanged_and_names_no_tree() -> None:
    rows = [_row("1T"), _row("2T")]
    comparison = compare_frontend(rows, _tree_results({"1T": "abc", "2T": "abc"}))
    cell = comparison.cells["persona", "tui"]
    assert cell.trees == ("abc",)
    assert cell_text(cell, "abc") == "loads, 2/2 matched, 0 differs, 0 not run"
    assert cell_text(cell) == "loads, 2/2 matched, 0 differs, 0 not run"


def test_a_cell_names_one_older_tree_after_its_counts() -> None:
    rows = [_row("1T"), _row("2T")]
    comparison = compare_frontend(rows, _tree_results({"1T": "abc", "2T": "old"}))
    text = render_table(rows, head="abc", frontend=comparison)
    matrix = text.split("## Frontend matrix", 1)[1]
    assert "| persona | loads, 2/2 matched, 0 differs, 0 not run @old | not yet run | not yet run |" in matrix


def test_a_cell_names_several_trees_sorted_and_leaves_the_head_out() -> None:
    rows = [_row("1T"), _row("2T"), _row("3T")]
    comparison = compare_frontend(rows, _tree_results({"1T": "zzz", "2T": "abc", "3T": "mmm"}))
    assert cell_text(comparison.cells["persona", "tui"], "abc") == "loads, 3/3 matched, 0 differs, 0 not run @mmm,zzz"


def test_a_differing_row_names_the_tree_of_its_result_only_when_it_is_not_the_head() -> None:
    rows = [_row("1T"), _row("2T")]
    results = _tree_results({"1T": "old", "2T": "abc"})
    results |= {
        result.key: result
        for result in (_result(period="1T", tree="old", verify="incomplete"), _result(period="2T", verify="incomplete"))
    }
    text = render_table(rows, head="abc", frontend=compare_frontend(rows, results))
    differing = text.split("### Rows differing", 1)[1]
    assert f"- persona|303|{_YEAR}|1T: tui@old differs: verify tui incomplete, table pass" in differing
    assert f"- persona|303|{_YEAR}|2T: tui differs: verify tui incomplete, table pass" in differing


def test_the_trees_folded_line_counts_table_rows_per_tree_and_surface() -> None:
    rows = [_row("1T"), _row("2T"), _row("3T")]
    results = _tree_results({"1T": "old", "2T": "abc", "3T": "abc"})
    cli = _result(surface="cli", period="1T", tree="new")
    results[cli.key] = cli
    comparison = compare_frontend(rows, results)
    text = render_table(rows, head="abc", frontend=comparison)
    assert "\nTrees folded: tui abc (2), old (1); cli new (1)\n" in text
    assert "Trees folded: none" in render_table(rows, head="abc", frontend=compare_frontend(rows, {}))


def test_render_with_frontend_publishes_the_columns_even_when_nothing_was_run(tmp_path: Path) -> None:
    rows_file, empty = tmp_path / "rows.jsonl", tmp_path / "frontend"
    empty.mkdir()
    write_rows(rows_file, [_row("1T"), _row("2T")])
    plain, with_frontend = tmp_path / "plain.md", tmp_path / "frontend.md"
    assert main(["render", str(rows_file), "--head", "abc", "--out", str(plain)]) == 0
    assert main(["render", str(rows_file), "--head", "abc", "--frontend", str(empty), "--out", str(with_frontend)]) == 0
    text = with_frontend.read_text(encoding="utf-8")
    assert "Frontend: TUI matched 0 / 2, window matched 0 / 2, CLI matched 0 / 2 (2 rows)" in text
    assert "| persona | not yet run | not yet run | not yet run |" in text
    assert "not run | not run | not run |" in text
    assert "Frontend" not in plain.read_text(encoding="utf-8")


def test_render_with_a_bad_frontend_line_exits_2_and_names_the_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows_file = tmp_path / "rows.jsonl"
    write_rows(rows_file, [_row("1T")])
    _write(tmp_path / "frontend", "a.jsonl", [_line(calculate="passed")])
    assert main(["render", str(rows_file), "--head", "abc", "--frontend", str(tmp_path / "frontend")]) == 2
    assert "a.jsonl:1" in capsys.readouterr().err


def test_a_cli_line_parses_and_an_unknown_surface_or_key_is_still_refused() -> None:
    result = _result(surface="cli")
    assert (result.surface, result.key[0]) == ("cli", "cli")
    assert result.file is None
    with pytest.raises(ValueError, match="surface must be one of tui, window, cli"):
        _result(surface="browser")
    with pytest.raises(ValueError, match="unknown key extra"):
        _result(surface="cli", extra=1)


def test_the_optional_file_stage_parses_is_kept_and_is_ignored_by_parity() -> None:
    stated = _result(surface="cli", file="refused")
    assert stated.file == "refused"
    assert _result(surface="cli", file=None).file is None
    persona_level = {"modelo": None, "year": None, "period": None, "calculate": None, "verify": None, "export": None}
    assert _result(file="pass", **persona_level).file == "pass"
    with pytest.raises(ValueError, match="file must be one of"):
        _result(surface="cli", file="saved")
    row = _row()
    assert parity(row, "cli", _result(surface="cli")) == parity(row, "cli", stated)
    assert parity(row, "cli", stated).outcome == "matched"


def test_the_cli_column_is_counted_beside_tui_and_window_and_an_empty_one_is_not_yet_run() -> None:
    rows = [_row("1T"), _row("2T")]
    results = {result.key: result for result in (_result(surface="cli", period="1T"), _result(period="1T"))}
    comparison = compare_frontend(rows, results)
    assert (comparison.matched("tui"), comparison.matched("window"), comparison.matched("cli")) == (1, 0, 1)
    assert cell_text(comparison.cells["persona", "cli"]) == "loads, 1/2 matched, 0 differs, 1 not run"
    text = render_table(rows, head="abc", frontend=comparison)
    assert "TUI matched 1 / 2, window matched 0 / 2, CLI matched 1 / 2 (2 rows)" in text
    first = next(line for line in text.splitlines() if line.startswith(f"| persona | 303 | {_YEAR} | 1T |"))
    assert first.endswith("| matched | not run | matched |")
    nothing = compare_frontend(rows, {})
    assert cell_text(nothing.cells["persona", "cli"]) == "not yet run"


_NOT_SEALED = "REFUSED_MODELO_REVISION_NOT_SEALED"
_NOT_SEALED_REASON = f"verify: blocked; 1 findings | export: modelo.export refused {_NOT_SEALED} :: not verified"
_UNAVAILABLE = f"export unavailable (refused | not served) {_NOT_SEALED}"


def _sealed_row(period: str = "1T", reason: str = _NOT_SEALED_REASON, export: Stage = Stage.REFUSED) -> TableRow:
    return _row(period, verify=Stage.INCOMPLETE, export=export, reason=reason)


def _unserved(**overrides: object) -> SurfaceResult:
    return _result(verify="incomplete", export="not-reached", export_served=False, **overrides)


def test_an_export_door_not_served_matches_the_unsealed_refusal_and_records_the_code() -> None:
    outcome = parity(_sealed_row(), "tui", _unserved())
    assert (outcome.outcome, outcome.causes, outcome.gated_stages) == ("matched", (), (_UNAVAILABLE,))


@pytest.mark.parametrize(
    ("row", "result", "cause"),
    [
        (_sealed_row(), _result(verify="incomplete", export="not-reached"), "export tui not-reached, table refused"),
        (
            _sealed_row(),
            _result(verify="incomplete", export="not-reached", export_served=True),
            "export tui not-reached, table refused",
        ),
        (
            _sealed_row(reason="export: modelo.export refused REFUSED_MODELO_OTHER :: x"),
            _unserved(),
            "export tui not-reached, table refused",
        ),
        (_sealed_row(reason=""), _unserved(), "export tui not-reached, table refused"),
        (_sealed_row(export=Stage.PASSED), _unserved(), "export tui not-reached, table pass"),
    ],
)
def test_every_other_export_difference_stays_a_difference(row: TableRow, result: SurfaceResult, cause: str) -> None:
    outcome = parity(row, "tui", result)
    assert (outcome.outcome, cause in outcome.causes, outcome.gated_stages) == ("differs", True, ())


def test_a_surface_export_refusal_against_the_table_refusal_is_a_plain_match() -> None:
    outcome = parity(_sealed_row(), "tui", _result(verify="incomplete", export="refused", export_served=False))
    assert (outcome.outcome, outcome.gated_stages) == ("matched", ())


def test_a_verify_difference_stays_a_difference_even_when_the_export_door_is_not_served() -> None:
    outcome = parity(_sealed_row(), "tui", _result(verify="pass", export="not-reached", export_served=False))
    assert outcome.outcome == "differs"
    assert "verify tui pass, table incomplete" in outcome.causes


@pytest.mark.parametrize(
    ("reason", "code"),
    [
        (_NOT_SEALED_REASON, _NOT_SEALED),
        ("export: modelo.export refused ERROR_MODELO_EXPORT :: x", "ERROR_MODELO_EXPORT"),
        ("verify: blocked | export: modelo.export refused REFUSED_B :: x", "REFUSED_B"),
        ("verify: refused REFUSED_VERIFY :: x", None),
        ("export: modelo.export passed", None),
        ("", None),
    ],
)
def test_the_export_refusal_code_is_read_after_the_export_marker(reason: str, code: str | None) -> None:
    assert export_refusal_code(reason) == code
    assert _NOT_SEALED in EXPORT_WITHHELD_UNVERIFIED


@pytest.mark.parametrize(("value", "expected"), [(True, True), (False, False), (None, None)])
def test_export_served_is_read_as_true_false_or_unknown(value: bool | None, expected: bool | None) -> None:
    assert _result(export_served=value).export_served is expected
    line = _line()
    assert parse_result(json.dumps(line)).export_served is None


@pytest.mark.parametrize("value", ["false", 0, 1, []])
def test_a_non_boolean_export_served_is_refused(value: object) -> None:
    with pytest.raises(ValueError, match="export_served must be true, false or null"):
        parse_result(json.dumps(_line(export_served=value)))


def test_the_cell_names_rows_matched_by_gating_only_when_there_are_some() -> None:
    rows = [_sealed_row("1T"), _row("2T"), _row("3T")]
    lines = [
        _line(period="1T", verify="incomplete", export="not-reached", export_served=False),
        _line(period="2T"),
        _line(period="3T"),
    ]
    results = {parse_result(json.dumps(line)).key: parse_result(json.dumps(line)) for line in lines}
    cell = compare_frontend(rows, results).cells["persona", "tui"]
    assert cell.gated_rows == 1
    assert cell_text(cell) == "loads, 3/3 matched, 0 differs, 0 not run, 1 rows matched by gating"
    plain = compare_frontend(rows[1:], results).cells["persona", "tui"]
    assert plain.gated_rows == 0
    assert cell_text(plain) == "loads, 2/2 matched, 0 differs, 0 not run"
    assert "gating" not in cell_text(PersonaCell(True, 1, {"matched": 1}))


def test_the_report_lists_the_rows_matched_as_export_unavailable_only_when_there_are_some() -> None:
    rows = [_sealed_row("1T"), _row("2T")]
    lines = [_line(period="1T", verify="incomplete", export="not-reached", export_served=False), _line(period="2T")]
    results = {parse_result(json.dumps(line)).key: parse_result(json.dumps(line)) for line in lines}
    comparison = compare_frontend(rows, results)
    assert unavailable_exports_lines(comparison) == [
        f"Export unavailable (refused | not served), matched: persona|303|{_YEAR}|1T {_NOT_SEALED} [tui]"
    ]
    text = render_table(rows, head="abc", frontend=comparison)
    assert f"Export unavailable (refused | not served), matched: persona|303|{_YEAR}|1T {_NOT_SEALED} [tui]" in text
    assert text.index("Export unavailable (refused") < text.index("### Rows differing")
    quiet = render_table(rows[1:], head="abc", frontend=compare_frontend(rows[1:], results))
    assert "Export unavailable" not in quiet


_H0, _H1, _H2 = _YEAR + 1001, _YEAR + 1002, _YEAR + 1003


def _persona_line(horizon: int | None, *, loads: bool = True, reason: str = "") -> dict[str, object]:
    line = _line(modelo=None, year=None, period=None, loads=loads, reason=reason)
    for name in ("calculate", "verify", "export", "figures"):
        del line[name]
    return line | ({} if horizon is None else {"horizon": horizon})


def _fold(rows: list[TableRow], lines: list[dict[str, object]]) -> tuple[PersonaCell, dict[str, str], dict[str, str]]:
    """The tui cell of ``persona``, each row's outcome by period, and the cause of each row that has one."""
    parsed = [parse_result(json.dumps(line)) for line in lines]
    comparison = compare_frontend(rows, {result.key: result for result in parsed})
    found = comparison.parities["tui"]
    return (
        comparison.cells["persona", "tui"],
        {item.key[3]: item.outcome for item in found},
        {item.key[3]: item.causes[0] for item in found if item.causes},
    )


def _horizon_rows() -> list[TableRow]:
    return [_row("1T", horizon=_H0), _row("2T", horizon=_H1), _row("3T", horizon=_H1), _row("4T", horizon=_H2)]


def test_a_load_failure_at_one_horizon_fails_only_the_rows_of_that_horizon_without_a_line_of_their_own() -> None:
    lines = [
        _persona_line(_H0),
        _persona_line(_H1, loads=False, reason=f"horizon {_H1}: not loaded officers"),
        _persona_line(_H2),
        _line(period="1T"),
        _line(period="3T"),
        _line(period="4T"),
    ]
    cell, outcomes, causes = _fold(_horizon_rows(), lines)
    assert outcomes == {"1T": "matched", "2T": "load-failed", "3T": "matched", "4T": "matched"}
    assert causes == {"2T": f"horizon {_H1}: not loaded officers"}
    assert cell.loads is True
    assert cell_text(cell) == "loads, 3/4 matched, 0 differs, 0 not run, 1 load failed"


def test_the_cell_says_does_not_load_only_when_every_row_failed_to_load() -> None:
    reason = "not loaded"
    failing = [_persona_line(horizon, loads=False, reason=reason) for horizon in (_H0, _H1, _H2)]
    cell, outcomes, _ = _fold(_horizon_rows(), failing)
    assert set(outcomes.values()) == {"load-failed"}
    assert cell_text(cell) == "does not load, 0/4 matched, 0 differs, 0 not run, 4 load failed"
    cell, _, _ = _fold(_horizon_rows(), [*failing[:2], _persona_line(_H2)])
    assert cell_text(cell) == "loads, 0/4 matched, 0 differs, 1 not run, 3 load failed"


def test_a_persona_line_without_a_horizon_speaks_for_the_horizons_no_line_answers_for() -> None:
    lines = [_persona_line(None, loads=False, reason="profile locked"), _persona_line(_H1), _line(period="2T")]
    cell, outcomes, causes = _fold(_horizon_rows(), lines)
    assert outcomes == {"1T": "load-failed", "2T": "matched", "3T": "not-run", "4T": "load-failed"}
    assert causes["1T"] == "profile locked"
    assert cell_text(cell) == "loads, 1/4 matched, 0 differs, 1 not run, 2 load failed"


def test_a_persona_with_lines_for_other_horizons_only_loaded_by_default_at_a_horizon_without_one() -> None:
    cell, outcomes, _ = _fold(_horizon_rows(), [_persona_line(_H1, loads=False, reason="no")])
    assert outcomes == {"1T": "not-run", "2T": "load-failed", "3T": "load-failed", "4T": "not-run"}
    assert cell.loads is True


def test_without_any_horizon_a_failed_persona_line_fails_every_row_as_before() -> None:
    rows = [_row("1T"), _row("2T", horizon=_H2)]
    cell, outcomes, causes = _fold(rows, [_persona_line(None, loads=False, reason="profile locked")])
    assert outcomes == {"1T": "load-failed", "2T": "load-failed"}
    assert causes == {"1T": "profile locked", "2T": "profile locked"}
    assert cell_text(cell) == "does not load, 0/2 matched, 0 differs, 0 not run, 2 load failed"


def test_the_latest_persona_line_of_a_horizon_wins_over_an_earlier_one() -> None:
    lines = [_persona_line(_H1, loads=False, reason="first"), _persona_line(_H1)]
    _, outcomes, _ = _fold(_horizon_rows(), lines)
    assert set(outcomes.values()) == {"not-run"}


def test_the_horizon_is_read_from_the_field_and_a_bad_one_is_refused() -> None:
    assert parse_result(json.dumps(_persona_line(_H1))).horizon == _H1
    assert parse_result(json.dumps(_persona_line(None) | {"horizon": None})).horizon is None
    assert parse_result(json.dumps(_persona_line(_H1, reason=f"horizon {_H2}: x"))).horizon == _H1
    for bad in ("text", _H1 + 0.5, True, [_H1]):
        with pytest.raises(ValueError, match="horizon must be an integer or null"):
            parse_result(json.dumps(_persona_line(None) | {"horizon": bad}))
    with pytest.raises(ValueError, match="a line with a modelo has no horizon"):
        parse_result(json.dumps(_line(horizon=_H1)))


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (f"horizon {_H1}: not loaded officers", _H1),
        (f"horizon {_H1}", _H1),
        (f"persona@{_H2}: not loaded", _H2),
        (f"other@{_H2}: not loaded", None),
        (f"horizon {_H1}0: x", None),
        (f"the horizon {_H1}: x", None),
        (f"persona@{_H1}9", None),
        ("", None),
    ],
)
def test_the_horizon_is_read_from_the_reason_prefix_when_the_field_is_absent(reason: str, expected: int | None) -> None:
    assert parse_result(json.dumps(_persona_line(None, reason=reason))).horizon == expected
