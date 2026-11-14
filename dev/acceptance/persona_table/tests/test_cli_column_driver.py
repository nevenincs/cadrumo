"""The CLI column's driver runs a persona's returns command by command and stops the chain at an unsettled effect.

The runner here replaces the ``aeat`` process only: it answers each command with an envelope of the shape the
backend prints, so what is under test is the driver's choice of commands, its mapping and its refusal to go on after
an unsettled effect.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from ..cli_column.driver import (
    READ_BACK_WORKAROUND,
    CalculateMode,
    Case,
    bind_profile,
    profile_check,
    run_case,
    select_rows,
)
from ..cli_column.hygiene import Redactor
from ..cli_column.intake import LineWriter
from ..cli_column.world_report import (
    Phase,
    ReportError,
    RowPlan,
    Statement,
    StatementKind,
    WorldReport,
    parse_report,
    statement_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = 7
_ACTOR = "operator:test"
_Handler = Callable[[Sequence[str]], Mapping[str, object]]


def _plan(
    modelo: str,
    period: str,
    *,
    emitted: bool = True,
    owed: bool = True,
    history_filed: bool = False,
    last: str = "4T",
    statements: tuple[Statement, ...] = (),
) -> RowPlan:
    return RowPlan(modelo, _YEAR, period, owed, emitted, history_filed, last, statements=statements)


def _report(*rows: RowPlan) -> WorldReport:
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
        key = {("app", "modelo", "export"): "export", ("app", "overview", "calendar"): "calendar"}.get(
            command[:3], command[3]
        )
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
        if key == "revision":
            return _ok(calculation_revision_id=command[4], casilla_values={"01": "10.50", "02": "0"})
        if key == "verify":
            return _ok(granted_verificado_completo=True, findings=[])
        if key == "calendar":
            return _ok(entries=[], suppressed_entries=[])
        if key == "export":
            Path(command[command.index("--output") + 1]).write_text("fichero", encoding="utf-8")
            return _ok(output_path=command[command.index("--output") + 1])
        return _ok()

    def keys(self) -> list[str]:
        return [
            " ".join(command[2:4]) if command[1] == "modelo" and command[2] == "work" else command[2]
            for command in self.sent
        ]


def _case(
    tmp_path: Path,
    report: WorldReport,
    runner: _Scripted,
    *,
    check: str | None = "",
    calculate: CalculateMode = CalculateMode.READ_BACK,
) -> Case:
    writer = LineWriter(tmp_path / "cli-t.jsonl", Redactor(["synthetic-persona-passphrase"]))
    exports = tmp_path / "exports"
    exports.mkdir(exist_ok=True)
    return Case(
        "t", report, runner, exports, writer, "case.log", export_check=lambda _plan, _path: check, calculate=calculate
    )


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

    assert [plan.key for plan in selection.run] == [
        ("130", _YEAR, "1T"),
        ("303", _YEAR, "1T"),
        ("100", _YEAR, "0A"),
        ("130", _YEAR, "2T"),
        ("130", _YEAR, "3T"),
    ]
    assert selection.wanted == {("303", _YEAR, "1T"), ("130", _YEAR, "3T")}
    assert selection.skipped == ()


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
    assert "workaround" not in line


def _suppressed(modelo: str, period: str, verdict: str, reason: str = "outside the instalment rule") -> dict[str, str]:
    return {"modelo": modelo, "period": period, "verdict": verdict, "reason": reason}


def test_a_return_stated_not_owed_is_calculated_then_read_from_the_calendar_and_never_verified(tmp_path: Path) -> None:
    calendar = _ok(entries=[], suppressed_entries=[_suppressed("202", f"{_YEAR} 2P", "not_applicable")])
    runner = _Scripted(tmp_path / "exports", calendar=lambda _command: calendar)
    report = _report(_plan("202", "2P", owed=False))

    summary = run_case(_case(tmp_path, report, runner), select_rows(report))

    assert runner.keys() == ["work create", "work calculate", "calendar"]
    assert runner.sent[-1] == (
        "app",
        "overview",
        "calendar",
        "--from",
        f"{_YEAR}-01-01",
        "--to",
        f"{_YEAR + 1}-12-31",
        "--show-suppressed",
    )
    assert summary.written == (("202", _YEAR, "2P"),)
    (line,) = _lines(tmp_path)
    assert (line["calculate"], line["verify"], line["export"]) == ("pass", "not-owed", "not-reached")
    assert "file" not in line
    assert line["figures"] == {"01": "10.5"}


@pytest.mark.parametrize(
    "calendar",
    [
        _ok(entries=[{"modelo": "202", "period": f"{_YEAR} 2P"}], suppressed_entries=[]),
        _ok(entries=[], suppressed_entries=[_suppressed("202", f"{_YEAR} 2P", "undetermined")]),
        _ok(entries=[], suppressed_entries=[]),
        _ok(entries=[], suppressed_entries=[_suppressed("202", f"{_YEAR} 3P", "not_applicable")]),
    ],
    ids=["a window", "another verdict", "no mention", "another period"],
)
def test_a_return_stated_not_owed_is_incomplete_when_the_calendar_does_not_suppress_it(
    tmp_path: Path, calendar: dict[str, object]
) -> None:
    runner = _Scripted(tmp_path / "exports", calendar=lambda _command: calendar)
    report = _report(_plan("202", "2P", owed=False))

    run_case(_case(tmp_path, report, runner), select_rows(report))

    (line,) = _lines(tmp_path)
    assert (line["calculate"], line["verify"], line["export"]) == ("pass", "incomplete", "not-reached")
    assert str(line["reason"]).startswith("overview: stated not owed, the calendar says ")


def test_a_refused_calendar_read_is_the_verify_stage_of_a_return_stated_not_owed(tmp_path: Path) -> None:
    refusal = {"status": "error", "error": {"code": "REFUSED_OVERVIEW", "category": "REFUSED", "message": "no read"}}
    runner = _Scripted(tmp_path / "exports", calendar=lambda _command: refusal)
    report = _report(_plan("202", "2P", owed=False))

    run_case(_case(tmp_path, report, runner), select_rows(report))

    (line,) = _lines(tmp_path)
    assert (line["calculate"], line["verify"]) == ("pass", "refused")
    assert line["refusal_code"] == "REFUSED_OVERVIEW"


def test_a_return_whose_line_exists_runs_for_the_chain_but_is_not_written_again(tmp_path: Path) -> None:
    runner = _Scripted(tmp_path / "exports")
    report = _report(_plan("130", "1T"), _plan("303", "1T"))
    case = replace(_case(tmp_path, report, runner), done=frozenset({("130", _YEAR, "1T")}))

    summary = run_case(case, select_rows(report))

    assert runner.keys().count("work create") == 2
    assert summary.written == (("303", _YEAR, "1T"),)
    assert [(line["modelo"], line["period"]) for line in _lines(tmp_path)] == [("303", "1T")]


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
                "statements": [],
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


def _stated(kind: StatementKind, phase: Phase, target: str = "", value: str = "") -> Statement:
    return Statement(kind, phase, target=target, value=value)


def _applying(command: Sequence[str]) -> Mapping[str, object]:
    """An applied statement, whose edit printed the calculation it made, named by the statement's command."""
    return _ok(applied=True, receipt_id="r-1", calculation_revision_id=f"rev-{command[3]}")


_STATEMENT_COMMANDS: dict[str, _Handler] = {
    "attest-prior-carries": _applying,
    "attest-prior-value": _applying,
    "set-value": _applying,
    "attest-work-income": _applying,
    "attest-no-amount": _applying,
}


def _every_kind() -> tuple[Statement, ...]:
    """One statement of each kind; the phases are listed out of order, each phase's own statements in the table's."""
    return (
        _stated(StatementKind.RENTAL_CARRY, Phase.AFTER_RECALCULATION, "bind-rental"),
        _stated(StatementKind.PRIOR_VALUE, Phase.AFTER_CALCULATION, "bind-prior", "21000"),
        _stated(StatementKind.WORK_INCOME_NONE, Phase.AFTER_CALCULATION),
        _stated(StatementKind.WORK_INPUT, Phase.AT_CALCULATION, "00501", "25400"),
        _stated(StatementKind.PRIOR_CARRIES, Phase.BEFORE_EVIDENCE),
        _stated(StatementKind.PRIOR_VALUE, Phase.BEFORE_EVIDENCE, "bind-prior", "21000"),
    )


def test_a_returns_statements_are_made_around_its_calculation_in_the_tables_order(tmp_path: Path) -> None:
    runner = _Scripted(tmp_path / "exports", **_STATEMENT_COMMANDS)
    report = _report(_plan("100", "0A", statements=_every_kind()))

    run_case(_case(tmp_path, report, runner), select_rows(report))

    assert runner.keys() == [
        "work create",
        "work attest-prior-carries",
        "work attest-prior-value",
        "work set-value",
        "work revision",
        "work attest-prior-value",
        "work attest-work-income",
        "work revision",
        "work attest-no-amount",
        "work revision",
        "work verify",
        "export",
        "work file",
    ]
    revisions = [command[4] for command in runner.sent if command[3] in {"revision", "verify", "file"}]
    assert (
        revisions == ["rev-set-value", "rev-attest-work-income", "rev-attest-no-amount"] + ["rev-attest-no-amount"] * 2
    )
    (line,) = _lines(tmp_path)
    assert (line["calculate"], line["verify"], line["export"], line["file"]) == ("pass", "pass", "pass", "pass")
    for made in (
        "state prior_carries applied",
        "state prior_value bind-prior applied",
        "state work_input 00501 applied",
        "state work_income_none applied",
        "state rental_carry bind-rental applied",
    ):
        assert made in str(line["reason"])
    assert line["workaround"] == READ_BACK_WORKAROUND == "cli_calculate_drops_statements"


def test_a_modelo_303_with_statements_sends_no_calculate_that_would_drop_them(tmp_path: Path) -> None:
    statements = (
        _stated(StatementKind.PRIOR_VALUE, Phase.BEFORE_EVIDENCE, "bind-prior", "5"),
        _stated(StatementKind.WORK_INPUT, Phase.AT_CALCULATION, "00501", "7"),
    )
    runner = _Scripted(tmp_path / "exports", **_STATEMENT_COMMANDS)
    report = _report(_plan("303", "4T", statements=statements))

    run_case(_case(tmp_path, report, runner), select_rows(report))

    assert runner.keys() == [
        "work create",
        "work attest-prior-value",
        "work attest-m303-exonerado-390",
        "work set-value",
    ]
    (line,) = _lines(tmp_path)
    assert line["calculate"] == "error"
    assert "calculate carries the Modelo 303 evidence but drops the statements made" in str(line["reason"])
    assert "workaround" not in line


def test_a_return_is_calculated_again_only_after_a_phase_that_applied_a_statement(tmp_path: Path) -> None:
    statements = (_stated(StatementKind.WORK_INCOME_NONE, Phase.AFTER_CALCULATION),)
    declining: dict[str, _Handler] = {"attest-work-income": lambda _command: _ok(applied=False)}
    runner = _Scripted(tmp_path / "exports", **declining)
    report = _report(_plan("100", "0A", statements=statements))

    run_case(_case(tmp_path, report, runner), select_rows(report))

    assert runner.keys().count("work calculate") == 1
    (line,) = _lines(tmp_path)
    assert "state work_income_none not applied" in str(line["reason"])
    assert "workaround" not in line


def test_an_optional_statement_the_application_refuses_is_named_and_the_calculation_goes_on(tmp_path: Path) -> None:
    refusal = {"code": "REFUSED_HELD_SOURCE", "category": "REFUSED", "message": "held", "context": {}}
    held: dict[str, _Handler] = {"attest-prior-value": lambda _command: {"status": "error", "error": refusal}}
    statements = (_stated(StatementKind.PRIOR_VALUE, Phase.BEFORE_EVIDENCE, "bind-prior", "5"),)
    runner = _Scripted(tmp_path / "exports", **held)
    report = _report(_plan("130", "1T", statements=statements))

    run_case(_case(tmp_path, report, runner), select_rows(report))

    assert runner.keys().count("work calculate") == 1
    (line,) = _lines(tmp_path)
    assert line["calculate"] == "pass"
    assert "state prior_value bind-prior refused REFUSED_HELD_SOURCE" in str(line["reason"])


def test_a_required_statement_the_application_refuses_ends_the_return_at_calculate(tmp_path: Path) -> None:
    refusal = {"code": "REFUSED_VALUE", "category": "REFUSED", "message": "no", "context": {}}
    refusing: dict[str, _Handler] = {"set-value": lambda _command: {"status": "error", "error": refusal}}
    statements = (_stated(StatementKind.WORK_INPUT, Phase.AT_CALCULATION, "00501", "7"),)
    runner = _Scripted(tmp_path / "exports", **refusing)
    report = _report(_plan("200", "0A", statements=statements), _plan("200", "0B"))

    summary = run_case(_case(tmp_path, report, runner), select_rows(report))

    assert runner.keys()[:3] == ["work create", "work set-value", "work create"]
    first, _second = _lines(tmp_path)
    assert (first["calculate"], first["verify"], first["refusal_code"]) == ("refused", "not-reached", "REFUSED_VALUE")
    assert summary.stopped_at is None


def test_the_tables_own_refusal_of_a_statement_is_a_refused_calculation_without_a_command(tmp_path: Path) -> None:
    refused = Statement(StatementKind.RENTAL_CARRY, Phase.AFTER_RECALCULATION, refusal="a pending total of 5")
    runner = _Scripted(tmp_path / "exports", **_STATEMENT_COMMANDS)
    report = _report(_plan("100", "0A", statements=(refused,)))

    run_case(_case(tmp_path, report, runner), select_rows(report))

    assert runner.keys() == ["work create", "work calculate"]
    (line,) = _lines(tmp_path)
    assert line["calculate"] == "refused"
    assert "a pending total of 5" in str(line["reason"])


def test_an_unsettled_statement_stops_the_chain_and_nothing_more_is_sent(tmp_path: Path) -> None:
    unsettled: dict[str, _Handler] = {"attest-prior-value": lambda _command: _still_running()}
    statements = (_stated(StatementKind.PRIOR_VALUE, Phase.BEFORE_EVIDENCE, "bind-prior", "5"),)
    runner = _Scripted(tmp_path / "exports", **unsettled)
    report = _report(_plan("130", "1T", statements=statements), _plan("130", "2T"))

    summary = run_case(_case(tmp_path, report, runner), select_rows(report))

    assert summary.stopped_at == ("130", _YEAR, "1T")
    assert runner.keys() == ["work create", "work attest-prior-value"]
    first, second = _lines(tmp_path)
    assert first["calculate"] == "error"
    assert "chain stopped after UNKNOWN at 130/7/1T" in str(second["reason"])


def test_a_return_with_a_statement_no_command_says_is_left_out_and_named() -> None:
    said = _stated(StatementKind.PRIOR_VALUE, Phase.BEFORE_EVIDENCE, "bind-prior", "5")
    carries = Statement(StatementKind.PRIOR_CARRIES, Phase.BEFORE_EVIDENCE, gap="box 1380 states 0.001")
    report = _report(
        _plan("130", "1T", statements=(said,)),
        _plan("100", "0A", statements=(carries,)),
        _plan("130", "2T"),
    )

    with_doors = select_rows(report)
    without = select_rows(report, doors={})

    assert [plan.key for plan in with_doors.run] == [("130", _YEAR, "1T"), ("130", _YEAR, "2T")]
    assert with_doors.skipped == (
        (("100", _YEAR, "0A"), "no CLI door for modelo.edit.apply (prior_carries: box 1380 states 0.001)"),
    )
    assert without.skipped == (
        (("130", _YEAR, "1T"), "no CLI door for modelo.edit.apply (prior_value)"),
        (("100", _YEAR, "0A"), "no CLI door for modelo.edit.apply (prior_carries)"),
    )
    assert [plan.key for plan in without.run] == [("130", _YEAR, "2T")]


def test_a_world_report_carries_the_statements_and_refuses_a_malformed_one() -> None:
    statement = Statement(
        StatementKind.PRIOR_CARRIES,
        Phase.BEFORE_EVIDENCE,
        families=("renta_negative_general_bases_pending",),
        amounts=(("1380", "10.5"),),
    )
    row: dict[str, object] = {
        "modelo": "100",
        "year": _YEAR,
        "period": "0A",
        "owed": True,
        "emitted": True,
        "history_filed": False,
        "last_owed_period": "0A",
        "stated_refusal": None,
        "statements": [statement_record(statement)],
    }
    document = {
        "persona": "p",
        "horizon": _YEAR,
        "storage_root": "r",
        "profile_id": "i",
        "authority_generation": "g",
        "as_of": "t",
        "scope": "full",
        "actor": "a",
        "aeat_filings_in_process": False,
        "rows": [row],
    }

    report = parse_report(json.dumps(document))

    assert report.rows[0].statements == (statement,)
    bad_kind = {**row, "statements": [{**statement_record(statement), "kind": "invented"}]}
    with pytest.raises(ReportError, match="unknown kind or phase"):
        parse_report(json.dumps({**document, "rows": [bad_kind]}))
    with pytest.raises(ReportError, match="statements"):
        parse_report(json.dumps({**document, "rows": [{**row, "statements": None}]}))
    bad_amounts = {**row, "statements": [{**statement_record(statement), "amounts": [["1380"]]}]}
    with pytest.raises(ReportError, match="amounts"):
        parse_report(json.dumps({**document, "rows": [bad_amounts]}))


def test_only_the_returns_whose_calculation_was_read_back_state_the_workaround(tmp_path: Path) -> None:
    statements = (_stated(StatementKind.WORK_INPUT, Phase.AT_CALCULATION, "00501", "7"),)
    runner = _Scripted(tmp_path / "exports", **_STATEMENT_COMMANDS)
    report = _report(_plan("100", "0A", statements=statements), _plan("130", "1T"))

    run_case(_case(tmp_path, report, runner), select_rows(report))

    stated, plain = _lines(tmp_path)
    assert (stated["modelo"], plain["modelo"]) == ("100", "130")
    assert stated["workaround"] == READ_BACK_WORKAROUND
    assert runner.keys().count("work revision") == 1
    assert "workaround" not in plain
    assert runner.keys().count("work calculate") == 1


def test_as_run_always_sends_calculate_after_the_statements_and_never_reads_a_calculation_back(tmp_path: Path) -> None:
    runner = _Scripted(tmp_path / "exports", **_STATEMENT_COMMANDS)
    report = _report(_plan("100", "0A", statements=_every_kind()))

    run_case(_case(tmp_path, report, runner, calculate=CalculateMode.AS_RUN), select_rows(report))

    keys = runner.keys()
    assert "work revision" not in keys
    assert keys.count("work calculate") == 3
    assert keys.index("work calculate") > keys.index("work set-value")
    verified = [command[4] for command in runner.sent if command[3] == "verify"]
    assert verified == ["rev-wu-100-0A"]
    (line,) = _lines(tmp_path)
    assert (line["calculate"], line["verify"], line["export"], line["file"]) == ("pass", "pass", "pass", "pass")
    assert "workaround" not in line
    assert "state work_input 00501 applied" in str(line["reason"])


def test_as_run_calculates_a_modelo_303_that_holds_statements_with_its_evidence(tmp_path: Path) -> None:
    statements = (
        _stated(StatementKind.PRIOR_VALUE, Phase.BEFORE_EVIDENCE, "bind-prior", "5"),
        _stated(StatementKind.WORK_INPUT, Phase.AT_CALCULATION, "00501", "7"),
    )
    runner = _Scripted(tmp_path / "exports", **_STATEMENT_COMMANDS)
    report = _report(_plan("303", "4T", statements=statements))

    run_case(_case(tmp_path, report, runner, calculate=CalculateMode.AS_RUN), select_rows(report))

    calculate = next(command for command in runner.sent if command[3] == "calculate")
    assert "--m303-exonerado-390-attachment-id" in calculate
    (line,) = _lines(tmp_path)
    assert line["calculate"] == "pass"
    assert "workaround" not in line


def test_the_default_mode_is_as_run_and_the_read_back_is_only_taken_when_asked_for(tmp_path: Path) -> None:
    statements = (_stated(StatementKind.WORK_INPUT, Phase.AT_CALCULATION, "00501", "7"),)
    report = _report(_plan("100", "0A", statements=statements))
    plain = _Scripted(tmp_path / "plain", **_STATEMENT_COMMANDS)
    writer = LineWriter(tmp_path / "cli-t.jsonl", Redactor(["synthetic-persona-passphrase"]))
    exports = tmp_path / "plain"
    exports.mkdir()

    run_case(Case("t", report, plain, exports, writer, "case.log", export_check=lambda *_: ""), select_rows(report))

    assert Case.__dataclass_fields__["calculate"].default is CalculateMode.AS_RUN
    sent = plain.keys()
    assert "work revision" not in sent
    asked = _Scripted(tmp_path / "exports", **_STATEMENT_COMMANDS)
    run_case(_case(tmp_path, report, asked, calculate=CalculateMode.READ_BACK), select_rows(report))
    assert asked.keys().count("work revision") == 1


def test_selection_by_keys_wants_only_those_keys_and_still_runs_the_chain_before_the_last() -> None:
    report = _report(
        _plan("130", "1T"),
        _plan("303", "1T"),
        _plan("130", "2T"),
        _plan("303", "2T"),
        _plan("130", "3T"),
    )

    selection = select_rows(report, keys=frozenset({("130", _YEAR, "2T")}))

    assert selection.wanted == {("130", _YEAR, "2T")}
    assert [plan.key for plan in selection.run] == [
        ("130", _YEAR, "1T"),
        ("303", _YEAR, "1T"),
        ("130", _YEAR, "2T"),
    ]
    assert select_rows(report, keys=frozenset()).wanted == frozenset()
    assert select_rows(report, keys=None).wanted == {plan.key for plan in report.rows}


def _cell(casilla: str, value: str) -> dict[str, object]:
    return {"column_key": casilla, "casilla_id": casilla, "kind": "decimal", "value": value, "value_text": None}


def _saved_rows(command: Sequence[str]) -> Mapping[str, object]:
    del command
    records = [
        {"index": 1, "values": [_cell("0063", "12000.00"), _cell("01", "9"), _cell("0065", "3500")]},
        {"index": 2, "values": [_cell("0065", "10")]},
    ]
    return _ok(blocks=[{"block_id": "inmueble-rows", "rows_known": True, "records": records}])


def test_without_the_form_leaf_the_saved_rows_are_not_read_and_the_figures_are_the_calculations(tmp_path: Path) -> None:
    runner = _Scripted(tmp_path / "exports", form=_saved_rows)
    report = _report(_plan("130", "1T"))
    case = _case(tmp_path, report, runner)

    run_case(case, select_rows(report))

    assert case.form_door is False
    sent = runner.keys()
    assert "work form" not in sent
    (line,) = _lines(tmp_path)
    assert line["figures"] == {"01": "10.5"}
    assert line["reason"] == "filed locally"


def test_with_the_form_leaf_the_saved_rows_are_read_once_after_the_final_calculation_and_merged(tmp_path: Path) -> None:
    runner = _Scripted(tmp_path / "exports", form=_saved_rows)
    report = _report(_plan("130", "1T"))

    run_case(replace(_case(tmp_path, report, runner), form_door=True), select_rows(report))

    assert runner.keys() == ["work create", "work calculate", "work form", "work verify", "export", "work file"]
    assert runner.sent[2] == ("app", "modelo", "work", "form", "wu-130-1T")
    (line,) = _lines(tmp_path)
    assert line["figures"] == {"01": "10.5", "0063": "12000"}
    assert line["calculate"] == "pass"
    assert line["reason"] == "row figures: casilla 01 scalar 10.5 differs from its row figure 9 | filed locally"


def test_the_form_is_read_after_the_recalculation_a_statement_makes(tmp_path: Path) -> None:
    statements = (_stated(StatementKind.RENTAL_CARRY, Phase.AFTER_RECALCULATION, "irpf.opening"),)
    runner = _Scripted(tmp_path / "exports", form=_saved_rows, **_STATEMENT_COMMANDS)
    report = _report(_plan("100", "0A", statements=statements))
    case = replace(_case(tmp_path, report, runner, calculate=CalculateMode.AS_RUN), form_door=True)

    run_case(case, select_rows(report))

    keys = runner.keys()
    assert keys.count("work form") == 1
    assert keys.index("work form") > len(keys) - 1 - keys[::-1].index("work calculate")
    assert keys.index("work form") < keys.index("work verify")


def test_a_form_read_that_prints_nothing_readable_adds_no_figure_and_a_refused_read_is_named(tmp_path: Path) -> None:
    def refused(_command: Sequence[str]) -> Mapping[str, object]:
        error = {"code": "MODELO_WORK_NOT_FOUND", "category": "VALIDATION", "message": "no such work"}
        return {"status": "error", "error": error}

    report = _report(_plan("130", "1T"), _plan("130", "2T"))
    unreadable = _Scripted(tmp_path / "exports", form=lambda _command: _ok(blocks="not rows"))
    case = replace(_case(tmp_path, report, unreadable), form_door=True)
    run_case(case, select_rows(report, keys=frozenset({("130", _YEAR, "1T")})))
    refusing = _Scripted(tmp_path / "exports", form=refused)
    run_case(
        replace(_case(tmp_path, report, refusing), form_door=True),
        select_rows(report, keys=frozenset({("130", _YEAR, "2T")})),
    )

    first, second = _lines(tmp_path)
    assert first["figures"] == second["figures"] == {"01": "10.5"}
    assert first["reason"] == "filed locally"
    assert str(second["reason"]).startswith("work form: MODELO_WORK_NOT_FOUND: no such work")
    assert (first["calculate"], second["calculate"]) == ("pass", "pass")
