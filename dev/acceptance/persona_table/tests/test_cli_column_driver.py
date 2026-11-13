"""The CLI column's driver runs a persona's returns command by command and stops the chain at an unsettled effect.

The runner here replaces the ``aeat`` process only: it answers each command with an envelope of the shape the
backend prints, so what is under test is the driver's choice of commands, its mapping and its refusal to go on after
an unsettled effect.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest

from ..cli_column.driver import (
    Case,
    bind_profile,
    profile_check,
    run_case,
    select_rows,
)
from ..cli_column.hygiene import Redactor
from ..cli_column.intake import LineWriter
from ..cli_column.world_report import ReportError, RowPlan, WorldReport, parse_report

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = 7
_ACTOR = "operator:test"
_Handler = Callable[[Sequence[str]], Mapping[str, object]]


def _plan(
    modelo: str, period: str, *, emitted: bool = True, owed: bool = True, history_filed: bool = False, last: str = "4T"
) -> RowPlan:
    return RowPlan(modelo, _YEAR, period, owed, emitted, history_filed, last)


def _report(*rows: RowPlan, needs_statements: bool = False) -> WorldReport:
    return WorldReport(
        persona="persona-x",
        horizon=_YEAR + 1,
        storage_root="root",
        profile_id="id",
        authority_generation="gen-1",
        as_of="frozen-scenario-instant",
        scope="full",
        actor=_ACTOR,
        aeat_filings_in_process=False,
        needs_statements=needs_statements,
        rows=rows,
    )


def _ok(**result: object) -> dict[str, object]:
    return {"status": "success", "result": result}


def _still_running() -> dict[str, object]:
    context = {"operation_id": "op-1", "effect": "unknown"}
    error = {
        "code": "LOCKED_CLI_OPERATION_STILL_RUNNING",
        "category": "LOCKED",
        "message": "running",
        "context": context,
    }
    return {"status": "error", "error": error}


class _Scripted:
    """Answer each command by its leading words; record every command sent."""

    def __init__(self, exports: Path, **overrides: _Handler) -> None:
        self.sent: list[tuple[str, ...]] = []
        self._exports = exports
        self._overrides = overrides

    def __call__(self, args: Sequence[str], *, authenticated: bool = True) -> Mapping[str, object]:
        del authenticated
        command = tuple(args)
        self.sent.append(command)
        key = "export" if command[:3] == ("app", "modelo", "export") else command[3]
        if key in self._overrides:
            return self._overrides[key](command)
        return self._default(key, command)

    def _default(self, key: str, command: tuple[str, ...]) -> Mapping[str, object]:
        if key == "create":
            return _ok(
                work_unit_id=f"wu-{command[command.index('--modelo') + 1]}-{command[command.index('--period') + 1]}"
            )
        if key == "attest-m303-exonerado-390":
            return _ok(attachment_id="att-1", sha256="ab" * 32)
        if key == "calculate":
            return _ok(calculation_revision_id=f"rev-{command[4]}", casilla_values={"01": "10.50", "02": "0"})
        if key == "verify":
            return _ok(granted_verificado_completo=True, findings=[])
        if key == "export":
            Path(command[command.index("--output") + 1]).write_text("fichero", encoding="utf-8")
            return _ok(output_path=command[command.index("--output") + 1])
        return _ok()

    def keys(self) -> list[str]:
        return [
            " ".join(command[2:4]) if command[1] == "modelo" and command[2] == "work" else command[2]
            for command in self.sent
        ]


def _case(tmp_path: Path, report: WorldReport, runner: _Scripted, *, check: str | None = "") -> Case:
    writer = LineWriter(tmp_path / "cli-t.jsonl", Redactor(["synthetic-persona-passphrase"]))
    exports = tmp_path / "exports"
    exports.mkdir(exist_ok=True)
    return Case("t", report, runner, exports, writer, "case.log", export_check=lambda _plan, _path: check)


def _lines(tmp_path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in (tmp_path / "cli-t.jsonl").read_text(encoding="utf-8").splitlines()]


def test_selection_runs_the_wanted_returns_and_the_supported_replays_before_the_last_of_them() -> None:
    report = _report(
        _plan("130", "1T", emitted=False),
        _plan("303", "1T"),
        _plan("100", "0A", emitted=False),
        _plan("130", "2T", owed=False),
        _plan("303", "2T", history_filed=True),
        _plan("130", "3T"),
        _plan("303", "4T"),
    )

    selection = select_rows(report, modelos=["303", "130"], periods=["1T", "3T"])

    assert [plan.key for plan in selection.run] == [("130", _YEAR, "1T"), ("303", _YEAR, "1T"), ("130", _YEAR, "3T")]
    assert selection.wanted == {("303", _YEAR, "1T"), ("130", _YEAR, "3T")}
    assert [key for key, _ in selection.skipped] == [("100", _YEAR, "0A"), ("130", _YEAR, "2T")]


def test_a_persona_that_states_values_first_is_left_to_the_statement_step() -> None:
    report = _report(_plan("130", "1T"), needs_statements=True)

    selection = select_rows(report)

    assert selection.run == ()
    assert [why for _, why in selection.skipped] == ["the persona states values the table enters before it calculates"]


def test_a_return_runs_create_calculate_verify_export_and_file_in_the_tables_order(tmp_path: Path) -> None:
    runner = _Scripted(tmp_path / "exports")
    report = _report(_plan("130", "1T"))

    summary = run_case(_case(tmp_path, report, runner), select_rows(report))

    assert runner.keys() == ["work create", "work calculate", "work verify", "export", "work file"]
    create, calculate, verify, export, file = runner.sent
    assert create == (
        "app",
        "modelo",
        "work",
        "create",
        "--modelo",
        "130",
        "--year",
        str(_YEAR),
        "--period",
        "1T",
        "--by",
        _ACTOR,
    )
    assert calculate == ("app", "modelo", "work", "calculate", "wu-130-1T", "--by", _ACTOR)
    assert verify == ("app", "modelo", "work", "verify", "rev-wu-130-1T", "--by", _ACTOR)
    assert export[:5] == ("app", "modelo", "export", "wu-130-1T", "--output")
    assert export[5].endswith("persona-x-130-7-1T.txt")
    assert file[:5] == ("app", "modelo", "work", "file", "rev-wu-130-1T")
    assert summary.written == (("130", _YEAR, "1T"),)
    (line,) = _lines(tmp_path)
    assert (line["calculate"], line["verify"], line["export"], line["file"]) == ("pass", "pass", "pass", "pass")
    assert line["figures"] == {"01": "10.5"}
    assert line["reason"] == "filed locally"


def test_a_modelo_303_elects_no_joint_return_and_attests_the_annual_summary_only_in_the_last_period(
    tmp_path: Path,
) -> None:
    runner = _Scripted(tmp_path / "exports")
    report = _report(_plan("303", "1T", last="2T"), _plan("303", "2T", last="2T"))

    run_case(_case(tmp_path, report, runner), select_rows(report))

    calculations = [command for command in runner.sent if command[3] == "calculate"]
    assert calculations[0] == (
        "app",
        "modelo",
        "work",
        "calculate",
        "wu-303-1T",
        "--no-joint-return-elected",
        "--by",
        _ACTOR,
    )
    attestation = next(command for command in runner.sent if command[3] == "attest-m303-exonerado-390")
    assert attestation == (
        "app",
        "modelo",
        "work",
        "attest-m303-exonerado-390",
        "--year",
        str(_YEAR),
        "--period",
        "2T",
        "--observed-at",
        f"{_YEAR}-12-31T12:00Z",
        "--by",
        _ACTOR,
    )
    assert calculations[1][5:] == (
        "--no-joint-return-elected",
        "--m303-exonerado-390-attachment-id",
        "att-1",
        "--m303-exonerado-390-sha256",
        "ab" * 32,
        "--by",
        _ACTOR,
    )
    lifecycle = ["work create", "work calculate", "work verify", "export", "work file"]
    assert runner.keys() == [*lifecycle, "work create", "work attest-m303-exonerado-390", *lifecycle[1:]]


def test_a_refused_calculation_is_a_row_and_the_chain_goes_on(tmp_path: Path) -> None:
    refusal = {"code": "REFUSED_X", "category": "REFUSED", "message": "words", "context": {}}

    def calculate(command: Sequence[str]) -> Mapping[str, object]:
        if command[4] == "wu-130-1T":
            return {"status": "error", "error": refusal}
        return _ok(calculation_revision_id="rev-2", casilla_values={"01": "1"})

    runner = _Scripted(tmp_path / "exports", calculate=calculate)
    report = _report(_plan("130", "1T"), _plan("130", "2T"))

    summary = run_case(_case(tmp_path, report, runner), select_rows(report))

    first, second = _lines(tmp_path)
    assert (first["calculate"], first["verify"], first["export"], first["refusal_code"]) == (
        "refused",
        "not-reached",
        "not-reached",
        "REFUSED_X",
    )
    assert second["calculate"] == "pass"
    assert summary.stopped_at is None
    assert "file" not in first


def test_an_unsettled_verify_stops_the_chain_and_sends_nothing_more(tmp_path: Path) -> None:
    runner = _Scripted(tmp_path / "exports", verify=lambda _command: _still_running())
    report = _report(_plan("130", "1T"), _plan("130", "2T"), _plan("303", "1T"))

    summary = run_case(_case(tmp_path, report, runner), select_rows(report))

    assert summary.stopped_at == ("130", _YEAR, "1T")
    assert runner.keys() == ["work create", "work calculate", "work verify"]
    first, second, third = _lines(tmp_path)
    assert (first["calculate"], first["verify"], first["export"]) == ("pass", "error", "not-reached")
    assert "file" not in first
    assert "UNKNOWN effect, operation op-1" in str(first["reason"])
    for later in (second, third):
        assert (later["calculate"], later["verify"], later["export"]) == ("error", "not-reached", "not-reached")
        assert "chain stopped after UNKNOWN at 130/7/1T" in str(later["reason"])


def test_a_command_that_timed_out_is_not_retried(tmp_path: Path) -> None:
    runner = _Scripted(tmp_path / "exports", calculate=lambda _command: {"status": "timeout"})
    report = _report(_plan("130", "1T"))

    summary = run_case(_case(tmp_path, report, runner), select_rows(report))

    assert summary.stopped_at == ("130", _YEAR, "1T")
    assert runner.keys() == ["work create", "work calculate"]
    (line,) = _lines(tmp_path)
    assert line["calculate"] == "error"


def test_filing_waits_for_a_granted_verification_but_not_for_the_export(tmp_path: Path) -> None:
    refused = {"code": "REFUSED_EXPORT", "category": "REFUSED", "message": "no fichero", "context": {}}
    runner = _Scripted(tmp_path / "exports", export=lambda _command: {"status": "error", "error": refused})
    withheld = _Scripted(
        tmp_path / "exports", verify=lambda _command: _ok(granted_verificado_completo=False, findings=[])
    )
    report = _report(_plan("130", "1T"))

    run_case(_case(tmp_path, report, runner), select_rows(report))
    run_case(_case(tmp_path, report, withheld), select_rows(report))

    assert runner.keys()[-1] == "work file"
    assert withheld.keys()[-1] == "export"
    first, second = _lines(tmp_path)
    assert (first["verify"], first["export"], first["file"]) == ("pass", "refused", "pass")
    assert (second["verify"], second["export"], "file" in second) == ("incomplete", "pass", False)


def test_an_export_is_a_pass_only_when_the_tables_checks_found_the_file_clean(tmp_path: Path) -> None:
    report = _report(_plan("130", "1T"))
    clean = _Scripted(tmp_path / "exports")
    defective = _Scripted(tmp_path / "exports")
    unavailable = _Scripted(tmp_path / "exports")

    run_case(_case(tmp_path, report, clean, check=""), select_rows(report))
    run_case(_case(tmp_path, report, defective, check="export readback: c0505 exp 1 got 2"), select_rows(report))
    run_case(_case(tmp_path, report, unavailable, check=None), select_rows(report))

    exports = [line["export"] for line in _lines(tmp_path)]
    assert exports == ["pass", "refused", "error"]


def test_a_command_that_wrote_no_file_is_not_an_export_pass(tmp_path: Path) -> None:
    runner = _Scripted(tmp_path / "exports", export=lambda _command: _ok(output_path="never-written.txt"))
    report = _report(_plan("130", "1T"))

    run_case(_case(tmp_path, report, runner), select_rows(report))

    (line,) = _lines(tmp_path)
    assert line["export"] == "refused"
    assert "wrote no file" in str(line["reason"])


def test_the_profile_check_needs_exactly_one_profile_that_loads() -> None:
    def runner_for(
        profiles: list[dict[str, str]], listing: Mapping[str, object]
    ) -> Callable[..., Mapping[str, object]]:
        def run(args: Sequence[str], *, authenticated: bool = True) -> Mapping[str, object]:
            del authenticated
            return _ok(profiles=profiles) if args[:2] == ("config", "profile") else listing

        return run

    assert profile_check(runner_for([{"name": "persona"}], _ok(units=[]))) == (
        True,
        "profile persona loaded",
        "persona",
    )
    loads, why, _ = profile_check(runner_for([{"name": "persona"}, {"name": "other"}], _ok()))
    assert not loads
    assert "2 profiles" in why
    refusal = {
        "status": "error",
        "error": {"code": "AUTH_FAILED", "category": "REFUSED", "message": "no", "context": {}},
    }
    loads, why, name = profile_check(runner_for([{"name": "persona"}], refusal))
    assert (loads, name) == (False, "persona")
    assert "AUTH_FAILED" in why


def test_an_authenticated_command_names_the_profile_and_an_unauthenticated_one_does_not() -> None:
    seen: list[tuple[tuple[str, ...], bool]] = []

    def run(args: Sequence[str], *, authenticated: bool = True) -> Mapping[str, object]:
        seen.append((tuple(args), authenticated))
        return _ok()

    bound = bind_profile(run, "persona")
    bound(("app", "modelo", "work", "list"))
    bound(("config", "profile", "list"), authenticated=False)

    assert seen == [
        (("--profile", "persona", "app", "modelo", "work", "list"), True),
        (("config", "profile", "list"), False),
    ]


def test_a_world_report_is_parsed_and_a_mistyped_one_refused() -> None:
    document = {
        "persona": "p",
        "horizon": _YEAR,
        "storage_root": "r",
        "profile_id": "i",
        "authority_generation": "g",
        "as_of": "t",
        "scope": "full",
        "actor": "a",
        "aeat_filings_in_process": True,
        "needs_statements": False,
        "rows": [
            {
                "modelo": "130",
                "year": _YEAR,
                "period": "1T",
                "owed": True,
                "emitted": True,
                "history_filed": False,
                "last_owed_period": "4T",
                "stated_refusal": None,
            }
        ],
    }

    report = parse_report(json.dumps(document))

    assert report.rows[0].key == ("130", _YEAR, "1T")
    assert report.aeat_filings_in_process
    with pytest.raises(ReportError, match="horizon"):
        parse_report(json.dumps({**document, "horizon": str(_YEAR)}))
    with pytest.raises(ReportError, match="rows"):
        parse_report(json.dumps({**document, "rows": None}))
    with pytest.raises(ReportError, match="not JSON"):
        parse_report("{")
