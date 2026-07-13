"""Real-behaviour tests for the ``cli-sequence`` frame-grammar parser.

There is no external numeric oracle for a parser, so these tests prove the
GRAMMAR and the STRUCTURAL CONTRACT (ADR rulings D1 / D4): the worked example
from the ADR parses into the expected typed frames with every capture, expect,
and placeholder preserved; every refusal mode raises an accumulating
:class:`SequenceParseError` whose problems name the offending line; and multiple
independent faults surface together rather than one-at-a-time.
"""

from __future__ import annotations

import pytest

from .. import (
    CaptureBinding,
    ExpectAssertion,
    FrameKind,
    SequenceParseError,
    parse_sequence,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


_VERIFY = "Verify the calculation before exporting."
# The ADR D1 worked example, minus its ``:seed:`` (seed inlining is exercised in
# ``test_seeds.py``).
_WORKED_EXAMPLE = """\
aeat app modelo create 303 --year 2026 --period 1T
@capture work_unit_id result.work_unit_id
aeat app modelo calculate {work_unit_id}
@result aeat app modelo verify {work_unit_id}
@expect result.status == "verified_complete"
"""


def _parse(body: str, *, verify: str | None = _VERIFY, seed: str | None = None):
    return parse_sequence(
        sequence_id="modelo-303-first-quarter",
        options={"verify": verify, "seed": seed},
        body=body,
    )


def _problems(body: str, **kwargs) -> tuple[str, ...]:
    with pytest.raises(SequenceParseError) as excinfo:
        _parse(body, **kwargs)
    return excinfo.value.problems


def test_worked_example_parses_into_typed_frames() -> None:
    sequence = _parse(_WORKED_EXAMPLE)

    assert sequence.sequence_id == "modelo-303-first-quarter"
    assert sequence.verify == _VERIFY
    assert sequence.seed is None
    assert len(sequence.frames) == 3

    create, calculate, result = sequence.frames

    assert create.kind is FrameKind.COMMAND
    assert create.argv == ("aeat", "app", "modelo", "create", "303", "--year", "2026", "--period", "1T")
    assert create.captures == (CaptureBinding(name="work_unit_id", json_path="result.work_unit_id"),)
    assert create.placeholder_names == ()

    assert calculate.kind is FrameKind.COMMAND
    assert calculate.argv == ("aeat", "app", "modelo", "calculate", "{work_unit_id}")
    assert calculate.placeholder_names == ("work_unit_id",)

    assert result.kind is FrameKind.RESULT
    assert result is sequence.result_frame
    assert result.expects == (ExpectAssertion(json_path="result.status", expected="verified_complete"),)
    assert result.placeholder_names == ("work_unit_id",)

    assert sequence.capture_names == ("work_unit_id",)
    assert all(frame.source == "body" for frame in sequence.frames)


def test_setup_frame_is_classified_and_argv_decomposed() -> None:
    body = (
        "@setup aeat app ledger import --file fixtures/2026-1t-statement.csv\n"
        "@result aeat app modelo verify\n"
        '@expect result.status == "verified_complete"\n'
    )
    sequence = _parse(body)

    setup = sequence.frames[0]
    assert setup.kind is FrameKind.SETUP
    assert setup.argv == ("aeat", "app", "ledger", "import", "--file", "fixtures/2026-1t-statement.csv")
    assert setup.command_line == "aeat app ledger import --file fixtures/2026-1t-statement.csv"


def test_expect_parses_json_literals_by_type() -> None:
    body = (
        "@result aeat app modelo verify\n"
        '@expect result.status == "verified_complete"\n'
        "@expect exit_code == 1\n"
        "@expect result.count == 3\n"
        "@expect result.ready == true\n"
    )
    sequence = _parse(body)
    expects = {assertion.json_path: assertion.expected for assertion in sequence.result_frame.expects}
    assert expects == {
        "result.status": "verified_complete",
        "exit_code": 1,
        "result.count": 3,
        "result.ready": True,
    }


def test_blank_lines_are_ignored() -> None:
    body = (
        "aeat app modelo create 303 --year 2026 --period 1T\n"
        "\n"
        "   \n"
        "@result aeat app modelo verify\n"
        '@expect result.status == "verified_complete"\n'
    )
    sequence = _parse(body)
    assert [frame.line_number for frame in sequence.frames] == [1, 4]


def test_missing_verify_option_is_refused() -> None:
    problems = _problems(_WORKED_EXAMPLE, verify=None)
    assert any(":verify: option is required" in problem for problem in problems)


def test_whitespace_only_verify_is_refused() -> None:
    problems = _problems(_WORKED_EXAMPLE, verify="   ")
    assert any(":verify: option is required" in problem for problem in problems)


def test_zero_result_frames_is_refused() -> None:
    body = "aeat app modelo create 303 --year 2026 --period 1T\n"
    problems = _problems(body)
    assert any("exactly one @result frame; found none" in problem for problem in problems)


def test_multiple_result_frames_is_refused() -> None:
    body = (
        "@result aeat app modelo verify\n"
        '@expect result.status == "verified_complete"\n'
        "@result aeat app modelo view\n"
        '@expect result.status == "verified_complete"\n'
    )
    problems = _problems(body)
    assert any("exactly one @result frame; found 2" in problem for problem in problems)


def test_non_terminal_result_frame_is_refused() -> None:
    body = '@result aeat app modelo verify\n@expect result.status == "verified_complete"\naeat app modelo view\n'
    problems = _problems(body)
    assert any("must be the last frame" in problem for problem in problems)


def test_result_without_expect_is_refused() -> None:
    body = "@result aeat app modelo verify\n"
    problems = _problems(body)
    assert any("at least one" in problem and "@expect" in problem for problem in problems)


def test_unresolved_placeholder_is_refused() -> None:
    body = (
        "aeat app modelo calculate {work_unit_id}\n"
        "@result aeat app modelo verify\n"
        '@expect result.status == "verified_complete"\n'
    )
    problems = _problems(body)
    assert any("does not resolve to an earlier @capture" in problem for problem in problems)


def test_placeholder_cannot_reference_its_own_frame_capture() -> None:
    # The capture is produced by frame 1's output, so it is not available to
    # frame 1's own argv -- only to strictly-later frames.
    body = (
        "aeat app modelo calculate {work_unit_id}\n"
        "@capture work_unit_id result.work_unit_id\n"
        "@result aeat app modelo verify\n"
        '@expect result.status == "verified_complete"\n'
    )
    problems = _problems(body)
    assert any("does not resolve to an earlier @capture" in problem for problem in problems)


def test_nested_fence_is_refused() -> None:
    body = (
        "aeat app modelo create 303\n"
        "```bash\n"
        "@result aeat app modelo verify\n"
        '@expect result.status == "verified_complete"\n'
    )
    problems = _problems(body)
    assert any("nested code fences" in problem for problem in problems)


def test_plain_non_aeat_line_is_unrecognised() -> None:
    body = 'ls -la\n@result aeat app modelo verify\n@expect result.status == "verified_complete"\n'
    problems = _problems(body)
    assert any("unrecognised line" in problem for problem in problems)


def test_sigil_frame_must_invoke_aeat() -> None:
    body = "@result ls -la\n"
    problems = _problems(body)
    assert any("must invoke 'aeat'" in problem for problem in problems)


def test_capture_before_any_frame_is_refused() -> None:
    body = (
        "@capture work_unit_id result.work_unit_id\n"
        "@result aeat app modelo verify\n"
        '@expect result.status == "verified_complete"\n'
    )
    problems = _problems(body)
    assert any("@capture must follow a command frame" in problem for problem in problems)


def test_malformed_expect_without_operator_is_refused() -> None:
    body = "@result aeat app modelo verify\n@expect result.status verified\n"
    problems = _problems(body)
    assert any("@expect must be '@expect <json-path> == <literal>'" in problem for problem in problems)


def test_unquoted_expect_string_literal_is_refused() -> None:
    body = "@result aeat app modelo verify\n@expect result.status == verified_complete\n"
    problems = _problems(body)
    assert any("must be a JSON literal" in problem for problem in problems)


def test_duplicate_capture_name_is_refused() -> None:
    body = (
        "aeat app modelo create 303\n"
        "@capture work_unit_id result.work_unit_id\n"
        "aeat app modelo calculate {work_unit_id}\n"
        "@capture work_unit_id result.work_unit_id\n"
        "@result aeat app modelo verify {work_unit_id}\n"
        '@expect result.status == "verified_complete"\n'
    )
    problems = _problems(body)
    assert any("duplicate @capture name" in problem for problem in problems)


def test_unknown_sigil_is_refused() -> None:
    body = (
        "@teardown aeat app modelo delete\n"
        "@result aeat app modelo verify\n"
        '@expect result.status == "verified_complete"\n'
    )
    problems = _problems(body)
    assert any("unknown sigil" in problem for problem in problems)


def test_invalid_placeholder_shape_is_refused() -> None:
    body = (
        "aeat app modelo calculate {1bad}\n"
        "@result aeat app modelo verify\n"
        '@expect result.status == "verified_complete"\n'
    )
    problems = _problems(body)
    assert any("invalid placeholder" in problem for problem in problems)


def test_independent_faults_accumulate_in_one_pass() -> None:
    # A nested fence AND a missing @result AND a bad @expect literal -- all three
    # surface together, proving the parser does not abort on the first fault.
    body = (
        "aeat app modelo create 303\n"
        "```\n"
        "@capture work_unit_id result.work_unit_id\n"
        "aeat app modelo calculate {work_unit_id}\n"
        "@expect result.status == open\n"
    )
    problems = _problems(body)
    assert any("nested code fences" in problem for problem in problems)
    assert any("exactly one @result frame; found none" in problem for problem in problems)
    assert any("must be a JSON literal" in problem for problem in problems)
    assert len(problems) >= 3
