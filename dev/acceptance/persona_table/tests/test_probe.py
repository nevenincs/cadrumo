"""The probe classifies what verify answered: typed findings and refusals pass, untyped and unsettled fail."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from cadrumo.application.modelo.work_verification_contracts import ModeloWorkVerifyPublicResultV2
from cadrumo.core.decimal.coercion import coerce_decimal_strict
from cadrumo.entrypoints.tests.persona_materialisation import PersonaMaterialisationError

from ..probe import (
    EXECUTOR_LOGGER,
    OWNER_LIFECYCLE,
    OWNER_UNKNOWN,
    Outcome,
    ProbeLine,
    classify,
    innermost_cadrumo_frame,
    read_probes,
    render_markdown,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_VERIFY = "modelo.work.verify"
_FRAME = "C:\\work\\acceptance\\src\\cadrumo\\application\\modelo\\verification_actions.py:123:verify_work"
_RECORD = (
    "operation failed definition=modelo.work.verify operation=op-1 diagnostic_ref=ref-1 "
    f"exception_type=ValidationError raising_frame=pydantic_core:1:x application_frame={_FRAME}"
)


def _verified(*, granted: bool = False, findings: int = 2) -> ModeloWorkVerifyPublicResultV2:
    """A published verification carrying the summary fields the probe reads."""
    return ModeloWorkVerifyPublicResultV2.model_construct(
        completeness_status="open", granted_verificado_completo=granted, finding_count=findings
    )


def _settled(condition: str, code: str, detail: str) -> PersonaMaterialisationError:
    """The error the table's operation settler raises for a settled operation that did not succeed."""
    return PersonaMaterialisationError(f"{_VERIFY} settled {condition} ({code}): {detail}")


def _validation_error() -> ValidationError:
    with pytest.raises(ValidationError) as caught:
        TypeAdapter(int).validate_python("not a number")
    return caught.value


def test_a_published_verification_is_typed_findings_whether_granted_or_not() -> None:
    for granted in (True, False):
        answer = classify("verify", _verified(granted=granted))
        assert answer.outcome is Outcome.TYPED_FINDINGS
        assert answer.owner is None
        assert f"granted={granted}" in answer.message


def test_another_published_result_is_a_typed_refusal() -> None:
    answer = classify("verify", object())
    assert answer.outcome is Outcome.TYPED_REFUSAL
    assert answer.code == "object"


def test_a_settled_refusal_is_typed_and_names_its_registered_code() -> None:
    answer = classify("verify", _settled("refused", "MODELO_SOURCE_INCOMPLETE", "a required casilla is missing"))
    assert answer.outcome is Outcome.TYPED_REFUSAL
    assert answer.code == "MODELO_SOURCE_INCOMPLETE"
    assert answer.owner is None


def test_a_settled_failure_is_untyped_and_the_supervisor_record_names_the_exception_and_where_it_was_raised() -> None:
    sentence = "A record Cadrumo created did not pass its own check."
    answer = classify("verify", _settled("failed", "None", sentence), failure=_RECORD)
    assert answer.outcome is Outcome.UNTYPED_EXCEPTION
    assert answer.code == "ValidationError"
    assert answer.message.endswith(sentence)
    assert answer.raised_in == "cadrumo/application/modelo/verification_actions.py:123:verify_work"
    assert answer.owner == OWNER_LIFECYCLE


def test_a_settled_failure_without_a_record_is_still_untyped() -> None:
    answer = classify("calculate", _settled("failed", "None", "no detail"))
    assert answer.outcome is Outcome.UNTYPED_EXCEPTION
    assert answer.code == "failed"
    assert answer.raised_in is None
    assert answer.owner == OWNER_UNKNOWN


def test_the_supervisor_logger_the_probe_listens_on_is_the_module_that_logs_failures() -> None:
    assert import_module(EXECUTOR_LOGGER).__name__ == EXECUTOR_LOGGER


@pytest.mark.parametrize("condition", ["timed_out", "interrupted", "cancelled"])
def test_a_settlement_that_did_not_conclude_is_unknown(condition: str) -> None:
    answer = classify("verify", _settled(condition, "None", "no detail"))
    assert answer.outcome is Outcome.UNKNOWN_SETTLEMENT
    assert answer.owner == OWNER_LIFECYCLE


def test_an_operation_that_could_not_be_observed_is_unknown() -> None:
    answer = classify("verify", PersonaMaterialisationError(f"{_VERIFY} could not be observed"))
    assert answer.outcome is Outcome.UNKNOWN_SETTLEMENT


def test_a_pydantic_validation_error_is_untyped() -> None:
    answer = classify("verify", _validation_error())
    assert answer.outcome is Outcome.UNTYPED_EXCEPTION
    assert answer.code == "ValidationError"
    assert answer.message.startswith("ValidationError: ")
    assert len(answer.message) <= 300
    assert answer.owner == OWNER_LIFECYCLE


def test_a_materialisation_error_without_a_settlement_is_untyped() -> None:
    answer = classify("verify", PersonaMaterialisationError(f"{_VERIFY} published no X"))
    assert answer.outcome is Outcome.UNTYPED_EXCEPTION
    assert answer.code == "PersonaMaterialisationError"


def test_a_failure_before_verify_is_owned_by_unknown() -> None:
    answer = classify("calculate", KeyError("casilla"))
    assert answer.outcome is Outcome.UNTYPED_EXCEPTION
    assert answer.owner == OWNER_UNKNOWN


def test_the_raising_module_is_the_innermost_in_tree_frame_of_the_traceback() -> None:
    with pytest.raises(Exception) as caught:
        coerce_decimal_strict("not a number")
    frame = innermost_cadrumo_frame(caught.value)
    assert frame is not None
    assert frame.startswith("cadrumo/core/decimal/coercion.py:")
    assert frame.endswith(":coerce_decimal_strict")
    assert classify("verify", caught.value).raised_in == frame


def test_an_error_raised_outside_the_tree_names_no_module() -> None:
    assert innermost_cadrumo_frame(_validation_error()) is None


def _line(outcome: Outcome, *, period: str = "1T", message: str = "m | n") -> ProbeLine:
    return ProbeLine("p", "130", 2025, period, 2025, "verify", outcome, "C", message, "cadrumo/x.py:1:f", "LIFECYCLE")


def test_lines_round_trip_through_the_file_and_the_summary_lists_failures_only(tmp_path: Path) -> None:
    lines = [_line(Outcome.UNTYPED_EXCEPTION, period="2T"), _line(Outcome.TYPED_REFUSAL), _line(Outcome.TYPED_FINDINGS)]
    out = tmp_path / "probe.jsonl"
    out.write_text("".join(line.to_json() + "\n" for line in lines), encoding="utf-8")
    read = read_probes(out)
    assert sorted(read, key=lambda line: line.period) == sorted(lines, key=lambda line: line.period)
    summary = render_markdown(read)
    assert "Probed 3 returns: 1 typed-findings, 1 typed-refusal, 1 untyped-exception, 0 unknown-settlement." in summary
    assert (
        "| p | M130 2025 2T | 2025 | verify | untyped-exception | LIFECYCLE | cadrumo/x.py:1:f | C | m \\| n |"
        in summary
    )
    assert "1T" not in summary


def test_the_summary_of_clean_probes_says_so() -> None:
    assert "No failures." in render_markdown([_line(Outcome.TYPED_FINDINGS)])
