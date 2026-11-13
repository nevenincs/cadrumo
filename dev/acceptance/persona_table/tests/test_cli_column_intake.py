"""The CLI column maps what the backend printed to intake stages; an unsettled effect is never a pass."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dev.packaging.google_oauth import GOOGLE_OAUTH_ENV

from ..cli_column.hygiene import OAUTH_CLIENT_ENV, REDACTED, Redactor, SecretLeakError, remove_secret_bearing
from ..cli_column.intake import (
    NON_JSON_CODE,
    STILL_RUNNING_CODE,
    TIMEOUT_STATUS,
    Kind,
    LineWriter,
    ReturnScope,
    RowResult,
    StageResult,
    calculate_stage,
    classify,
    export_stage,
    failed,
    figures_of,
    file_stage,
    persona_line,
    return_line,
    verify_stage,
)
from ..frontend import DIFFERS, MATCHED, parity, parse_result, read_results
from ..rows import PlannedRow, Stage, TableRow

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CREDENTIAL = "synthetic-persona-passphrase"
_CLIENT_KEY = "GOCSPX-secret-value-0001"
_CLIENT_ID = "1234-abcdefghij.apps.example"
_CLIENT = json.dumps({"installed": {"client_id": _CLIENT_ID, "client_secret": _CLIENT_KEY}})
_YEAR = 7


def _success(**result: object) -> dict[str, object]:
    return {"status": "success", "result": result}


def _error(code: str, *, category: str = "REFUSED", **context: object) -> dict[str, object]:
    error = {"code": code, "category": category, "message": "served words", "context": context}
    return {"status": "error", "error": error}


def test_calculate_figures_are_the_non_zero_typed_values_of_the_result() -> None:
    outcome = classify(_success(casilla_values={"01": "1200.50", "02": "0.00", "03": "812.4", "07": "-3.100"}))

    stage, figures = calculate_stage(outcome)

    assert stage == StageResult("pass")
    assert figures == (("01", "1200.5"), ("03", "812.4"), ("07", "-3.1"))


def test_a_result_without_casilla_values_has_no_figures() -> None:
    assert figures_of({}) == ()
    assert figures_of({"casilla_values": "not a mapping"}) == ()


def test_a_served_refusal_keeps_its_code_and_words() -> None:
    outcome = classify(_error("REFUSED_MODELO_NOT_APPLICABLE"))

    stage, figures = calculate_stage(outcome)

    assert outcome.kind is Kind.REFUSED
    assert (stage.word, stage.code, stage.uncertain, figures) == ("refused", "REFUSED_MODELO_NOT_APPLICABLE", False, ())
    assert stage.reason == "calculate: REFUSED_MODELO_NOT_APPLICABLE: served words"


def test_an_internal_fault_is_an_error_not_a_refusal() -> None:
    outcome = classify(_error("INTERNAL_UNEXPECTED", category="INTERNAL"))

    assert outcome.kind is Kind.ERROR
    assert failed(outcome, "calculate").word == "error"


@pytest.mark.parametrize(
    "document",
    [None, "text", [], {"status": "unexpected"}, {"status": "error"}, {"status": "error", "error": "no object"}],
    ids=["none", "text", "list", "other-status", "no-error", "error-not-object"],
)
def test_no_envelope_or_a_malformed_one_is_an_error(document: object) -> None:
    outcome = classify(document)

    assert outcome.kind is Kind.ERROR
    assert failed(outcome, "calculate").word == "error"


def test_the_installed_adapter_document_for_a_command_without_envelope_is_an_error() -> None:
    outcome = classify(_error(NON_JSON_CODE))

    assert outcome.kind is Kind.ERROR
    assert outcome.reason == "the command printed no JSON envelope"


@pytest.mark.parametrize(
    "document",
    [
        _error(STILL_RUNNING_CODE, category="LOCKED", operation_id="op-1", effect="unknown"),
        _error("INTERNAL_X", category="INTERNAL", operation_id="op-2", effect="unknown", terminal_condition="failed"),
        _error("REFUSED_X", operation_id="op-3", effect="settling"),
        _error("REFUSED_X", operation_id="op-4", effect="none", terminal_condition="timed_out"),
        _error("REFUSED_X", operation_id="op-5", effect="updated", terminal_condition="interrupted"),
        {"status": TIMEOUT_STATUS},
    ],
    ids=["still-running", "failed-unknown", "settling", "timed-out", "interrupted", "command-timeout"],
)
def test_an_unsettled_effect_is_never_a_pass_and_stops_the_chain(document: dict[str, object]) -> None:
    outcome = classify(document)

    assert outcome.kind is Kind.UNKNOWN
    for stage in (calculate_stage(outcome)[0], verify_stage(outcome), export_stage(outcome, ""), file_stage(outcome)):
        assert stage.word == "error"
        assert stage.uncertain
        assert "UNKNOWN" in stage.reason
    assert RowResult(calculate_stage(outcome)[0]).uncertain


def test_a_refusal_that_settled_stays_a_refusal_even_with_an_unknown_effect() -> None:
    outcome = classify(_error("REFUSED_X", operation_id="op-6", effect="unknown", terminal_condition="refused"))

    assert outcome.kind is Kind.REFUSED
    assert not failed(outcome, "verify").uncertain


def test_verify_passes_only_when_verificado_completo_was_granted() -> None:
    granted = classify(_success(granted_verificado_completo=True, findings=[]))
    findings = [
        {"kind": "missing_required_casilla", "severity": "blocking", "casilla_id": "0505"},
        {"kind": "advisory_note", "severity": "advisory", "casilla_id": "0600"},
    ]
    withheld = classify(
        _success(granted_verificado_completo=False, completeness_status="incomplete", findings=findings)
    )
    silent = classify(_success(findings=[]))

    assert verify_stage(granted) == StageResult("pass")
    incomplete = verify_stage(withheld)
    assert incomplete.word == "incomplete"
    assert incomplete.reason == "verify: incomplete; 2 findings; blocking: missing_required_casilla 0505"
    assert verify_stage(silent).word == "incomplete"


def test_export_passes_only_after_the_tables_checks_found_the_file_clean() -> None:
    written = classify(_success(output_path="out.txt"))

    assert export_stage(written, "") == StageResult("pass")
    assert export_stage(written, "export: c0505 exp 1 got 2") == StageResult(
        "refused", reason="export: c0505 exp 1 got 2"
    )
    unchecked = export_stage(written, None)
    assert unchecked.word == "error"
    assert not unchecked.uncertain


def test_file_states_filed_locally_and_a_refusal_keeps_its_code() -> None:
    assert file_stage(classify(_success())) == StageResult("pass", reason="filed locally")
    refused = file_stage(classify(_error("REFUSED_NO_PENDING_OBLIGATION")))
    assert (refused.word, refused.code) == ("refused", "REFUSED_NO_PENDING_OBLIGATION")


def _scope() -> ReturnScope:
    return ReturnScope("abc123", "persona-x", "303", _YEAR, "1T")


def _row(figures: tuple[tuple[str, str], ...]) -> TableRow:
    plan = PlannedRow(
        persona="persona-x",
        modelo="303",
        year=_YEAR,
        period="1T",
        horizon=_YEAR + 1,
        has_values=True,
        grounding="verified",
        sources=("ley:art-1",),
    )
    return TableRow.from_plan(plan, Stage.PASSED, verify=Stage.PASSED, export=Stage.PASSED, figures=figures)


def _writer(tmp_path: Path) -> LineWriter:
    return LineWriter(tmp_path / "cli-abc123.jsonl", Redactor([_CREDENTIAL]))


def _passed(figures: tuple[tuple[str, str], ...]) -> RowResult:
    return RowResult(StageResult("pass"), StageResult("pass"), StageResult("pass"), figures=figures)


def test_a_written_line_reads_back_as_the_result_the_intake_expects(tmp_path: Path) -> None:
    figures = (("0505", "1200.5"), ("0700", "-2104.67"))
    result = RowResult(
        StageResult("pass"),
        StageResult("pass"),
        StageResult("pass"),
        StageResult("pass", reason="filed locally"),
        figures,
    )
    writer = _writer(tmp_path)
    persona = persona_line(tree="abc123", persona="persona-x", loads=True, reason="seeded in process", log="case.log")
    writer.write(persona)
    writer.write(return_line(_scope(), result, "case.log"))

    held = read_results(tmp_path)

    shown = held["cli", "persona-x", "303", _YEAR, "1T"]
    assert (shown.calculate, shown.verify, shown.export, shown.file) == ("pass", "pass", "pass", "pass")
    assert shown.figures == figures
    assert shown.reason == "filed locally"
    assert held["cli", "persona-x", None, None, None].loads is True
    assert parity(_row(figures), "cli", shown).outcome == MATCHED


def test_a_row_whose_stage_or_figure_differs_does_not_match_the_table_row() -> None:
    oracle = _row((("0505", "1200.5"),))
    refusal = RowResult(StageResult("refused", "REFUSED_X", "calculate: x"))
    refused = parse_result(json.dumps(return_line(_scope(), refusal, "l")))
    changed = parse_result(json.dumps(return_line(_scope(), _passed((("0505", "1200.6"),)), "l")))

    assert parity(oracle, "cli", refused).outcome == DIFFERS
    assert parity(oracle, "cli", changed).causes == ("casilla 0505 cli 1200.6, table 1200.5",)


def test_an_unsettled_row_never_matches_a_table_row_that_passed() -> None:
    stage, _ = calculate_stage(classify({"status": TIMEOUT_STATUS}))
    line = parse_result(json.dumps(return_line(_scope(), RowResult(stage), "l")))

    assert line.calculate == "error"
    assert parity(_row((("0505", "1200.5"),)), "cli", line).outcome == DIFFERS


def test_the_first_failing_stage_gives_the_refusal_code_and_the_reasons_are_joined() -> None:
    result = RowResult(
        StageResult("pass"),
        StageResult("incomplete", reason="verify: incomplete"),
        StageResult("refused", "REFUSED_EXPORT", "export: refused"),
        None,
    )

    assert result.refusal_code == "REFUSED_EXPORT"
    assert result.reason == "verify: incomplete | export: refused"


def test_the_writer_does_not_write_a_line_the_intake_would_refuse(tmp_path: Path) -> None:
    writer = _writer(tmp_path)

    with pytest.raises(ValueError, match="unknown key"):
        writer.write({**persona_line(tree="t", persona="p", loads=True, reason="", log=""), "colour": "red"})

    assert not writer.path.exists()


def test_the_writer_ends_lines_with_a_line_feed_only(tmp_path: Path) -> None:
    writer = _writer(tmp_path)
    writer.write(persona_line(tree="t", persona="p", loads=False, reason="", log=""))

    assert writer.path.read_bytes().endswith(b"}\n")
    assert b"\r" not in writer.path.read_bytes()


def test_the_oauth_variable_the_hygiene_names_is_the_one_the_build_reads() -> None:
    assert OAUTH_CLIENT_ENV == GOOGLE_OAUTH_ENV


def test_secrets_in_the_environment_never_reach_a_written_line(tmp_path: Path) -> None:
    redactor = Redactor.for_run(_CREDENTIAL, {OAUTH_CLIENT_ENV: _CLIENT})
    writer = LineWriter(tmp_path / "cli-t.jsonl", redactor)
    echoed = f"calculate: echoed {_CREDENTIAL} and {_CLIENT} and {_CLIENT_KEY}"
    hostile = RowResult(StageResult("refused", "REFUSED_X", echoed), figures=((f"k-{_CREDENTIAL}", "1"),))

    text = writer.write(return_line(_scope(), hostile, f"log-{_CREDENTIAL}"))

    written = writer.path.read_text(encoding="utf-8")
    for secret in (_CREDENTIAL, _CLIENT, _CLIENT_KEY, _CLIENT_ID):
        assert secret not in written
        assert secret not in text
        assert json.dumps(secret)[1:-1] not in written
    assert REDACTED in written


def test_secrets_never_survive_in_error_text() -> None:
    redactor = Redactor.for_run(_CREDENTIAL, {OAUTH_CLIENT_ENV: _CLIENT})
    error = RuntimeError(f"build failed with {_CLIENT} after {_CREDENTIAL}")

    text = redactor.error_text(error)

    assert _CREDENTIAL not in text
    assert _CLIENT_KEY not in text
    assert text.startswith("RuntimeError: build failed")


def test_a_record_that_still_holds_a_secret_is_refused_without_repeating_it() -> None:
    redactor = Redactor([_CREDENTIAL])

    with pytest.raises(SecretLeakError) as raised:
        redactor.guard(f"leaks {_CREDENTIAL}", "a result line")

    assert _CREDENTIAL not in str(raised.value)


def test_a_file_that_holds_a_secret_is_removed_and_the_others_stay(tmp_path: Path) -> None:
    redactor = Redactor([_CREDENTIAL])
    (tmp_path / "leak.log").write_text(f"x {_CREDENTIAL} y", encoding="utf-8")
    (tmp_path / "wide.log").write_bytes(_CREDENTIAL.encode("utf-16-le"))
    (tmp_path / "clean.log").write_text("nothing here", encoding="utf-8")

    removed = remove_secret_bearing(tmp_path, redactor)

    assert sorted(path.name for path in tmp_path.iterdir()) == ["clean.log"]
    assert len(removed) == 2
    assert all(_CREDENTIAL not in item for item in removed)


def test_a_short_value_is_not_treated_as_a_secret() -> None:
    assert Redactor(["abc"]).text("abc abc") == "abc abc"
