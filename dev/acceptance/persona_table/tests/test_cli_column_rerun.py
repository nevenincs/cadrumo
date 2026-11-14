"""A rerun drives an exact list of returns, and the CLI results that did not match the table are what the list holds."""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest

from ..cli_column.case import CasePlace, CaseSpec
from ..cli_column.driver import CalculateMode, CaseSummary
from ..cli_column.hygiene import Redactor
from ..cli_column.intake import LineWriter
from ..cli_column.keys import KeysFileError, RerunKey, allowed_at, personas_of, read_keys, write_keys
from ..cli_column.runtime import e2e_parent
from ..cli_column.sweep import HorizonPlan, SweepSettings, TreeVenv, horizon_plans, parse_settings, run_sweep
from ..cli_column.unmatched import count_lines, counts_by_persona, main, split_personas, unmatched_keys
from ..cli_column.world_report import ReturnKey
from ..planner import registry_envelope
from ..rows import PlannedRow, Stage, TableRow, canonical_figures, write_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PERSONA = "autonomo-alta-reciente"
_YEAR = 7
_FIGURES = canonical_figures({"0505": "1200.5"})
_LEAK = "synthetic-persona-passphrase"


def test_a_keys_file_round_trips_and_a_malformed_one_is_refused(tmp_path: Path) -> None:
    keys = [RerunKey("p", "130", 2, "1T", 3), RerunKey("p", "303", 2, "1T"), RerunKey("q", "100", 2, "0A")]
    path = tmp_path / "keys.json"
    write_keys(path, [*keys, keys[0]])

    assert read_keys(path) == tuple(keys)
    assert personas_of(keys) == ("p", "q")
    assert allowed_at(keys, "p", 3) == {("130", 2, "1T"), ("303", 2, "1T")}
    assert allowed_at(keys, "p", 4) == {("303", 2, "1T")}
    assert allowed_at(keys, "absent", 3) == frozenset()
    for text, message in [
        ("{", "not JSON"),
        ("{}", "list"),
        ("[1]", "object"),
        ('[{"persona": "p", "modelo": "130", "year": "x", "period": "1T"}]', "year"),
        ('[{"persona": "p", "modelo": "130", "year": 2, "period": ""}]', "period"),
        ('[{"persona": "p", "modelo": "130", "year": 2, "period": "1T", "horizon": "3"}]', "horizon"),
    ]:
        path.write_text(text, encoding="utf-8")
        with pytest.raises(KeysFileError, match=message):
            read_keys(path)


def _envelope_horizons() -> list[int]:
    envelope = registry_envelope()
    return list(range(envelope.horizon, envelope.floor - 1, -1))


def test_the_plans_of_a_keys_list_hold_only_its_returns_at_the_horizons_that_emit_them() -> None:
    newest, middle, _oldest = _envelope_horizons()[:3]
    keys = [
        RerunKey(_PERSONA, "303", middle, "1T", middle),
        RerunKey(_PERSONA, "130", newest, "1T"),
        RerunKey(_PERSONA, "130", newest, "4T"),
    ]

    plans = horizon_plans([_PERSONA], keys=keys)

    assert [(plan.horizon, plan.keys) for plan in plans] == [
        (newest, frozenset({("130", newest, "1T")})),
        (middle, frozenset({("303", middle, "1T")})),
    ]
    assert horizon_plans([_PERSONA], keys=[]) == []
    assert [plan.horizon for plan in horizon_plans([_PERSONA], keys=None)] == _envelope_horizons()


class _Driver:
    """Stands in for the live case and records the spec each horizon was driven with."""

    def __init__(self) -> None:
        self.specs: list[CaseSpec] = []

    def __call__(
        self,
        spec: CaseSpec,
        template: Path,
        writer: LineWriter,
        redactor: Redactor,
        place: CasePlace,
        done: frozenset[ReturnKey],
    ) -> CaseSummary:
        del template, writer, redactor, place, done
        self.specs.append(spec)
        return CaseSummary()


@pytest.fixture
def outside_git() -> Iterator[Path]:
    """A folder in the account's temporary folder: a disposable root may not be made inside a Git project."""
    with tempfile.TemporaryDirectory(dir=e2e_parent(), prefix="rerun-test-") as folder:
        yield Path(folder)


def _settings(
    tmp_path: Path,
    parent: Path,
    keys: tuple[RerunKey, ...] | None = None,
    calculate: CalculateMode = CalculateMode.AS_RUN,
) -> SweepSettings:
    return SweepSettings(
        "t",
        tmp_path / "snap-t",
        tmp_path / "authority-t",
        tmp_path / "cli-t.jsonl",
        None,
        True,
        (_PERSONA,),
        root_parent=parent,
        keys=keys,
        calculate=calculate,
    )


def test_a_keys_sweep_hands_each_case_its_keys_and_the_calculate_mode(tmp_path: Path, outside_git: Path) -> None:
    keys = (RerunKey(_PERSONA, "130", 5, "2T"), RerunKey(_PERSONA, "303", 5, "1T"))
    plan = HorizonPlan(_PERSONA, 5, frozenset({("130", 5, "2T"), ("303", 5, "1T")}))
    venv = TreeVenv(tmp_path / "snap-t", lambda: tmp_path / "snap-t" / ".venv")
    redactor = Redactor([_LEAK])
    sinks = (LineWriter(tmp_path / "cli-t.jsonl", redactor), redactor)
    driver = _Driver()

    run_sweep(_settings(tmp_path, outside_git, keys), [plan], venv, sinks, driver)
    run_sweep(_settings(tmp_path, outside_git, None, CalculateMode.READ_BACK), [plan], venv, sinks, driver)

    keyed, plain = driver.specs
    assert keyed.keys == plan.keys
    assert keyed.modelos == ("130", "303")
    assert keyed.calculate is CalculateMode.AS_RUN
    assert plain.keys is None
    assert plain.modelos == ()
    assert plain.calculate is CalculateMode.READ_BACK


def test_the_command_line_takes_a_keys_file_and_defaults_to_the_as_run_calculation(tmp_path: Path) -> None:
    keys = [RerunKey(_PERSONA, "130", 2, "1T", 3), RerunKey(_PERSONA, "303", 2, "1T")]
    path = tmp_path / "keys.json"
    write_keys(path, keys)
    base = ["--tree", "t", "--snapshot", "s", "--authority", "a", "--out", "o"]

    default = parse_settings(base)
    asked = parse_settings([*base, "--calculate", "read-back", "--keys-file", str(path)])

    assert (default.calculate, default.keys) == (CalculateMode.AS_RUN, None)
    assert default.personas[0] != "" and len(default.personas) > 1
    assert (asked.calculate, asked.keys, asked.personas) == (CalculateMode.READ_BACK, tuple(keys), (_PERSONA,))
    for refused in (["--calculate", "sometimes"], ["--keys-file", str(tmp_path / "absent.json")]):
        with pytest.raises(SystemExit):
            parse_settings([*base, *refused])


def _row(
    persona: str, modelo: str, period: str, *, horizon: int = _YEAR + 1, calculate: Stage = Stage.PASSED
) -> TableRow:
    plan = PlannedRow(
        persona=persona,
        modelo=modelo,
        year=_YEAR,
        period=period,
        horizon=horizon,
        has_values=True,
        grounding="verified",
        sources=("ley:art-1",),
    )
    return TableRow.from_plan(plan, calculate, verify=Stage.PASSED, export=Stage.PASSED, figures=_FIGURES)


def _result(persona: str, modelo: str, period: str, **more: object) -> dict[str, object]:
    line: dict[str, object] = {
        "surface": "cli",
        "tree": "t",
        "persona": persona,
        "modelo": modelo,
        "year": _YEAR,
        "period": period,
        "loads": True,
        "calculate": "pass",
        "verify": "pass",
        "export": "pass",
        "figures": {"0505": "1200.5"},
    }
    return line | more


def _frontend(tmp_path: Path, lines: list[dict[str, object]]) -> Path:
    directory = tmp_path / "frontend"
    directory.mkdir()
    (directory / "cli-t.jsonl").write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    return directory


def test_the_unmatched_keys_hold_every_cli_row_that_is_not_matched(tmp_path: Path) -> None:
    rows = [
        _row("a", "303", "1T"),
        _row("a", "303", "2T"),
        _row("a", "303", "3T"),
        _row("a", "303", "4T"),
        _row("b", "130", "1T"),
        _row("b", "130", "2T"),
        _row("c", "130", "1T", calculate=Stage.NOT_RUN),
    ]
    directory = _frontend(
        tmp_path,
        [
            _result("a", "303", "1T"),
            _result("a", "303", "2T", workaround="cli_calculate_drops_statements"),
            _result("a", "303", "3T", calculate="refused"),
            _result("b", "130", "1T"),
            _result("b", "130", "2T", figures={"0505": "9"}),
            _result("c", "130", "1T"),
        ],
    )

    found = unmatched_keys(rows, directory)

    assert [(key.persona, key.period, key.horizon, outcome) for key, outcome in found] == [
        ("a", "2T", _YEAR + 1, "differs"),
        ("a", "3T", _YEAR + 1, "differs"),
        ("a", "4T", _YEAR + 1, "not-run"),
        ("b", "2T", _YEAR + 1, "differs"),
    ]
    listed = {outcome for _key, outcome in unmatched_keys(rows, directory, include_not_comparable=True)}
    assert listed == {"differs", "not-run", "not-comparable"}


def test_a_persona_whose_profile_did_not_load_lists_all_its_rows_as_load_failed(tmp_path: Path) -> None:
    rows = [_row("a", "303", "1T"), _row("a", "303", "2T"), _row("b", "303", "1T")]
    persona_line: dict[str, object] = {
        "surface": "cli",
        "tree": "t",
        "persona": "a",
        "modelo": None,
        "year": None,
        "period": None,
        "loads": False,
        "reason": f"horizon {_YEAR + 1}: the world was not materialised",
        "horizon": _YEAR + 1,
    }
    directory = _frontend(tmp_path, [persona_line, _result("b", "303", "1T")])

    found = unmatched_keys(rows, directory)

    assert [(key.persona, key.period, outcome) for key, outcome in found] == [
        ("a", "1T", "load-failed"),
        ("a", "2T", "load-failed"),
    ]
    assert counts_by_persona(found) == {"a": Counter({"load-failed": 2})}


def test_the_counts_are_listed_per_persona_and_the_split_keeps_whole_personas_balanced() -> None:
    sizes = (("a", 5), ("b", 3), ("c", 3), ("d", 1))
    keys = [RerunKey(persona, "130", 2, f"{n}T") for persona, count in sizes for n in range(count)]
    counts = {"a": Counter({"differs": 4, "not-run": 1}), "b": Counter({"differs": 3})}

    assert count_lines(counts) == ["a: 5 (differs 4, not-run 1)", "b: 3 (differs 3)", "total: 8"]
    first, second = split_personas(keys, 2)
    assert {key.persona for key in first}.isdisjoint({key.persona for key in second})
    assert sorted([len(first), len(second)]) == [6, 6]
    assert sorted(first + second, key=repr) == sorted(keys, key=repr)


def test_the_command_writes_the_keys_the_parts_and_the_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = [_row("a", "303", "1T"), _row("b", "303", "1T"), _row("b", "303", "2T")]
    rows_file = tmp_path / "rows-x.jsonl"
    write_rows(rows_file, rows)
    directory = _frontend(tmp_path, [_result("a", "303", "1T")])
    out = tmp_path / "keys.json"

    status = main(["--rows", str(rows_file), "--frontend", str(directory), "--out", str(out), "--split", "2"])

    assert status == 0
    assert {(key.persona, key.period) for key in read_keys(out)} == {("b", "1T"), ("b", "2T")}
    assert read_keys(tmp_path / "keys.part1.json") == read_keys(out)
    assert read_keys(tmp_path / "keys.part2.json") == ()
    assert "b: 2 (not-run 2)" in capsys.readouterr().out
    assert main(["--rows", str(rows_file), "--frontend", str(tmp_path / "missing"), "--out", str(out)]) == 2
