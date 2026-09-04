"""Real-behaviour tests for the ``cli-sequence`` frame-grammar parser.

There is no external numeric oracle for a parser, so these tests prove the
GRAMMAR and the STRUCTURAL CONTRACT: the worked example
parses into the expected typed frames with every capture, expect,
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
    StaticBlocker,
    parse_sequence,
    result_frame_asserts_result_payload,
)
from ..errors import SequenceParseError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


_VERIFY = "Verify the calculation before exporting."
# The worked example, minus its ``:seed:`` (seed inlining is exercised in
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


def test_bracket_quoted_object_key_path_parses() -> None:
    """@capture and @expect accept a bracket-quoted object key with dots and hyphens.

    M349's declarante casillas are flat string keys carrying a literal dot and
    hyphens (``decl.importe-operaciones`` / ``decl.numero-operadores``); the
    dotted grammar would split on the dot, so the bracket-quoted form is the only
    way to address them.
    """
    body = (
        "aeat --format json app modelo calculate x\n"
        '@capture importe result.casilla_values["decl.importe-operaciones"]\n'
        "@result aeat --format json app modelo verify x\n"
        '@expect result.casilla_values["decl.numero-operadores"] == "3"\n'
    )
    sequence = _parse(body)

    assert sequence.frames[0].captures == (
        CaptureBinding(name="importe", json_path='result.casilla_values["decl.importe-operaciones"]'),
    )
    assert sequence.result_frame.expects == (
        ExpectAssertion(json_path='result.casilla_values["decl.numero-operadores"]', expected="3"),
    )


@pytest.mark.parametrize(
    ("body", "expected_substring"),
    [
        pytest.param(
            '@result aeat app modelo verify\n@expect result.x["abc == 1\n',
            "is not a valid dotted path",
            id="unterminated_quoted_key_path",
        ),
        pytest.param(
            '@result aeat app modelo verify\n@expect result.x["a"b"] == 1\n',
            "is not a valid dotted path",
            id="embedded_double_quote_in_key_path",
        ),
        pytest.param(
            "aeat app modelo create 303 --year 2026 --period 1T\n",
            "exactly one @result frame; found none",
            id="zero_result_frames",
        ),
        pytest.param(
            "@result aeat app modelo verify\n"
            '@expect result.status == "verified_complete"\n'
            "@result aeat app modelo view\n"
            '@expect result.status == "verified_complete"\n',
            "exactly one @result frame; found 2",
            id="multiple_result_frames",
        ),
        pytest.param(
            '@result aeat app modelo verify\n@expect result.status == "verified_complete"\naeat app modelo view\n',
            "must be the last EXECUTED frame",
            id="non_terminal_result_frame",
        ),
        pytest.param(
            "aeat app modelo calculate {work_unit_id}\n"
            "@result aeat app modelo verify\n"
            '@expect result.status == "verified_complete"\n',
            "does not resolve to an earlier @capture",
            id="unresolved_placeholder",
        ),
        pytest.param(
            # The capture is produced by frame 1's output, so it is not available
            # to frame 1's own argv -- only to strictly-later frames.
            "aeat app modelo calculate {work_unit_id}\n"
            "@capture work_unit_id result.work_unit_id\n"
            "@result aeat app modelo verify\n"
            '@expect result.status == "verified_complete"\n',
            "does not resolve to an earlier @capture",
            id="placeholder_cannot_reference_its_own_frame_capture",
        ),
        pytest.param(
            "aeat app modelo create 303\n"
            "```bash\n"
            "@result aeat app modelo verify\n"
            '@expect result.status == "verified_complete"\n',
            "nested code fences",
            id="nested_fence",
        ),
        pytest.param(
            'ls -la\n@result aeat app modelo verify\n@expect result.status == "verified_complete"\n',
            "unrecognised line",
            id="plain_non_aeat_line_is_unrecognised",
        ),
        pytest.param(
            "@result ls -la\n",
            "must invoke 'aeat'",
            id="sigil_frame_must_invoke_aeat",
        ),
        pytest.param(
            "@capture work_unit_id result.work_unit_id\n"
            "@result aeat app modelo verify\n"
            '@expect result.status == "verified_complete"\n',
            "@capture must follow a command frame",
            id="capture_before_any_frame",
        ),
        pytest.param(
            "@result aeat app modelo verify\n@expect result.status verified\n",
            "@expect must be '@expect <json-path> == <literal>'",
            id="malformed_expect_without_operator",
        ),
        pytest.param(
            "@result aeat app modelo verify\n@expect result.status == verified_complete\n",
            "must be a JSON literal",
            id="unquoted_expect_string_literal",
        ),
        pytest.param(
            "aeat app modelo create 303\n"
            "@capture work_unit_id result.work_unit_id\n"
            "aeat app modelo calculate {work_unit_id}\n"
            "@capture work_unit_id result.work_unit_id\n"
            "@result aeat app modelo verify {work_unit_id}\n"
            '@expect result.status == "verified_complete"\n',
            "duplicate @capture name",
            id="duplicate_capture_name",
        ),
        pytest.param(
            "@teardown aeat app modelo delete\n"
            "@result aeat app modelo verify\n"
            '@expect result.status == "verified_complete"\n',
            "unknown sigil",
            id="unknown_sigil",
        ),
        pytest.param(
            "aeat app modelo calculate {1bad}\n"
            "@result aeat app modelo verify\n"
            '@expect result.status == "verified_complete"\n',
            "invalid placeholder",
            id="invalid_placeholder_shape",
        ),
        pytest.param(
            # M1: an unterminated ``{work_unit_id`` would otherwise survive as a
            # literal argv token with no problem raised.
            "aeat app modelo create 303\n"
            "@capture work_unit_id result.work_unit_id\n"
            "aeat app modelo calculate {work_unit_id\n"
            "@result aeat app modelo verify\n"
            '@expect result.status == "verified_complete"\n',
            "unbalanced placeholder brace",
            id="unbalanced_placeholder_brace",
        ),
        pytest.param(
            "aeat app modelo calculate value}\n"
            "@result aeat app modelo verify\n"
            '@expect result.status == "verified_complete"\n',
            "unbalanced placeholder brace",
            id="stray_closing_brace",
        ),
    ],
)
def test_refuses(body: str, expected_substring: str) -> None:
    problems = _problems(body)
    assert any(expected_substring in problem for problem in problems)


@pytest.mark.parametrize(
    ("body", "expected_substring_a", "expected_substring_b"),
    [
        pytest.param(
            "@result aeat app modelo verify\n",
            "at least one",
            "@expect",
            id="result_without_expect",
        ),
        pytest.param(
            # M3: exit_code is an integer exit status.
            '@result aeat app modelo verify\n@expect exit_code == "nope"\n',
            "exit_code",
            "integer literal",
            id="non_int_exit_code_expect",
        ),
        pytest.param(
            # A bool is an int subclass in Python but is not an exit code.
            "@result aeat app modelo verify\n@expect exit_code == true\n",
            "exit_code",
            "integer literal",
            id="bool_exit_code_expect",
        ),
        pytest.param(
            # L1: the diagnostic points at the offending @capture line (line 4),
            # not the frame's command line.
            "aeat app modelo create 303\n"
            "@capture work_unit_id result.work_unit_id\n"
            "aeat app modelo calculate {work_unit_id}\n"
            "@capture work_unit_id result.work_unit_id\n"
            "@result aeat app modelo verify {work_unit_id}\n"
            '@expect result.status == "verified_complete"\n',
            "line 4",
            "duplicate @capture name",
            id="duplicate_capture_diagnostic_locates_the_capture_line",
        ),
        pytest.param(
            "aeat app modelo create 303 --year 2026 --period 1T\n"
            "@result aeat app modelo verify\n"
            "@expect exit_code == 0\n"
            "@step This attaches to nothing.\n",
            "line 4",
            "trailing @step",
            id="trailing_step_with_no_following_frame",
        ),
        pytest.param(
            "@step\n"
            "aeat app modelo create 303 --year 2026 --period 1T\n"
            "@result aeat app modelo verify\n"
            "@expect exit_code == 0\n",
            "line 1",
            "@step requires one imperative sentence",
            id="empty_step_sentence",
        ),
        pytest.param(
            # '0abc' is neither an identifier nor an all-digit object key.
            "aeat app modelo create 303 --year 2026 --period 1T\n"
            "@result aeat app modelo verify\n@expect result.0abc == 1\n",
            "not a valid dotted path",
            "0abc",
            id="mixed_alnum_starting_with_digit_is_still_refused",
        ),
    ],
)
def test_refuses_with_two_substrings(
    body: str,
    expected_substring_a: str,
    expected_substring_b: str,
) -> None:
    problems = _problems(body)
    assert any(expected_substring_a in problem and expected_substring_b in problem for problem in problems)


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


@pytest.mark.parametrize(
    "body",
    (
        '@result aeat app modelo export\n@expect error.code == "REFUSED_MODELO_EXPORT_UNSUPPORTED"\n',
        "@result aeat config profile history --help\n@expect exit_code == 0\n",
    ),
)
def test_result_frame_semantic_contract_accepts_refusal_payload_and_terminal_help(body: str) -> None:
    assert result_frame_asserts_result_payload(_parse(body)) is True


def test_result_frame_semantic_contract_rejects_exit_only_structured_command() -> None:
    sequence = _parse("@result aeat app modelo work list\n@expect exit_code == 0\n")
    assert result_frame_asserts_result_payload(sequence) is False


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


# --- Review findings M1-M3, L1-L2 -------------------------------------------


def test_over_long_sequence_id_accumulates_not_raw_validation_error() -> None:
    # M2: a 121-char kebab id passes the pattern but exceeds SequenceId's cap;
    # it must surface as an accumulating SequenceParseError, not a raw pydantic
    # ValidationError, and co-accumulate with a second fault.
    long_id = "a" * 121
    with pytest.raises(SequenceParseError) as excinfo:
        parse_sequence(sequence_id=long_id, options={"verify": None}, body=_WORKED_EXAMPLE)
    problems = excinfo.value.problems
    assert any("sequence id" in problem and "characters" in problem for problem in problems)
    assert any(":verify: option is required" in problem for problem in problems)


def test_over_long_seed_name_is_refused(tmp_path) -> None:
    problems = _problems(_WORKED_EXAMPLE, seed="s" * 200)
    assert any(":seed: recipe name" in problem and "characters" in problem for problem in problems)


def test_over_long_verify_is_refused() -> None:
    problems = _problems(_WORKED_EXAMPLE, verify="V" * 241)
    assert any("at most 240 characters" in problem for problem in problems)


def test_int_exit_code_expect_is_accepted() -> None:
    body = "@result aeat app modelo verify\n@expect exit_code == 1\n"
    sequence = _parse(body)
    assert sequence.result_frame.expects[0].expected == 1


def test_parser_regexes_are_derived_from_the_schema_constraints() -> None:
    # L2: the parser must not duplicate the schema patterns; they are derived
    # from the single StringConstraints declaration and cannot drift.
    from typing import get_args

    from pydantic import StringConstraints

    from ..parser import _IDENTIFIER_RE, _JSON_PATH_RE, _SEQUENCE_ID_RE
    from ..schema import Identifier, JsonPath, SequenceId

    def _pattern(alias: object) -> str:
        pattern = next(meta for meta in get_args(alias) if isinstance(meta, StringConstraints)).pattern
        assert isinstance(pattern, str)
        return pattern

    assert _SEQUENCE_ID_RE.pattern == _pattern(SequenceId)
    assert _IDENTIFIER_RE.pattern == _pattern(Identifier)
    assert _JSON_PATH_RE.pattern == _pattern(JsonPath)


# --- @step frame descriptions ------------------------------------------------


def test_step_descriptions_attach_to_the_next_frame_of_any_kind() -> None:
    body = (
        "@step Prepare the quarter's ledger.\n"
        "@setup aeat app ledger import --file fixtures/q1.csv\n"
        "@step Create the Modelo 303 work unit.\n"
        "aeat app modelo create 303 --year 2026 --period 1T\n"
        "@capture work_unit_id result.work_unit_id\n"
        "aeat app modelo calculate {work_unit_id}\n"
        "@step Verify the calculation.\n"
        "@result aeat app modelo verify {work_unit_id}\n"
        '@expect result.status == "verified_complete"\n'
    )
    sequence = _parse(body)
    setup, create, calculate, result = sequence.frames
    assert setup.step_description == "Prepare the quarter's ledger."
    assert create.step_description == "Create the Modelo 303 work unit."
    assert calculate.step_description is None  # frames without @step stay bare
    assert result.step_description == "Verify the calculation."
    # The annotations beneath a described frame still attach normally.
    assert create.captures == (CaptureBinding(name="work_unit_id", json_path="result.work_unit_id"),)


def test_step_prose_is_not_placeholder_scanned() -> None:
    # Narration is free prose, never a command: braces in the sentence are
    # kept verbatim and raise no placeholder problem.
    body = (
        "@step Reuse the {work_unit_id} value from the create step.\n"
        "aeat app modelo create 303 --year 2026 --period 1T\n"
        "@result aeat app modelo verify\n"
        "@expect exit_code == 0\n"
    )
    sequence = _parse(body)
    assert sequence.frames[0].step_description == "Reuse the {work_unit_id} value from the create step."
    assert sequence.frames[0].placeholder_names == ()


def test_two_step_lines_for_one_frame_are_refused() -> None:
    body = (
        "@step First description.\n"
        "@step Second description for the same frame.\n"
        "aeat app modelo create 303 --year 2026 --period 1T\n"
        "@result aeat app modelo verify\n"
        "@expect exit_code == 0\n"
    )
    problems = _problems(body)
    assert any("line 2" in problem and "one @step description" in problem for problem in problems)
    assert any("line 1" in problem for problem in problems)  # the unattached earlier line is named


def test_over_long_step_sentence_is_refused() -> None:
    body = (
        f"@step {'x' * 300}\n"
        "aeat app modelo create 303 --year 2026 --period 1T\n"
        "@result aeat app modelo verify\n"
        "@expect exit_code == 0\n"
    )
    problems = _problems(body)
    assert any("line 1" in problem and "at most 240 characters" in problem for problem in problems)


# --- Numeric object keys in @expect / @capture json-paths --------------------


def test_numeric_object_key_segments_are_accepted() -> None:
    body = (
        "aeat --format json app modelo work calculate abc123\n"
        "@capture net_yield result.casilla_values.03\n"
        "@result aeat app modelo verify {net_yield}\n"
        '@expect result.casilla_values.01 == "1000.00"\n'
        "@expect exit_code == 0\n"
    )
    sequence = _parse(body)
    calculate, result = sequence.frames
    assert calculate.captures == (CaptureBinding(name="net_yield", json_path="result.casilla_values.03"),)
    assert result.expects[0] == ExpectAssertion(json_path="result.casilla_values.01", expected="1000.00")


# ---------------------------------------------------------------------------
# @static non-executed display frames
# ---------------------------------------------------------------------------


def test_static_frame_is_classified_and_excluded_from_executed_frames() -> None:
    """A @static frame parses to FrameKind.STATIC and is not in executed_frames."""
    sequence = _parse(
        "aeat app modelo create 303 --year 2026 --period 1T\n"
        "@result aeat app modelo verify wu\n"
        '@expect result.status == "ok"\n'
        "@step Upload the file at the portal yourself.\n"
        "@static aeat app live justificante pull\n"
        "@blocked live-aeat The pull verb fetches from the AEAT sede; the sandbox refuses it.",
    )
    kinds = [frame.kind for frame in sequence.frames]
    assert kinds == [FrameKind.COMMAND, FrameKind.RESULT, FrameKind.STATIC]
    # The static frame carries its @step header and its command, but is excluded
    # from the executed run.
    assert sequence.frames[-1].step_description == "Upload the file at the portal yourself."
    assert [frame.kind for frame in sequence.executed_frames] == [FrameKind.COMMAND, FrameKind.RESULT]


def test_static_frame_may_follow_the_result_frame() -> None:
    """A @static frame is allowed after the terminal @result (it is display-only)."""
    sequence = _parse(
        "@result aeat app modelo verify wu\n"
        "@expect exit_code == 0\n"
        "@static aeat app live justificante pull\n"
        "@blocked live-aeat The pull verb fetches from the AEAT sede; the sandbox refuses it.",
    )
    assert sequence.result_frame is not None
    assert sequence.frames[-1].kind is FrameKind.STATIC


def test_all_static_sequence_needs_no_result_or_verify() -> None:
    """An all-@static sequence parses with no @result and no :verify:."""
    sequence = _parse(
        "@step Authenticate with Google.\n"
        "@static aeat config google login\n"
        "@blocked external-service Needs a Google OAuth consent the sandbox cannot grant.\n"
        "@step Confirm the token was stored.\n"
        "@static aeat config google status\n"
        "@blocked external-service Needs a Google OAuth consent the sandbox cannot grant.",
        verify=None,
    )
    assert [frame.kind for frame in sequence.frames] == [FrameKind.STATIC, FrameKind.STATIC]
    assert sequence.executed_frames == ()
    assert sequence.result_frame is None
    assert sequence.verify is None


def test_verify_on_all_static_sequence_is_refused() -> None:
    """An all-@static sequence with a :verify: sentence is refused (it would overclaim)."""
    problems = _problems(
        "@static aeat config google login\n"
        "@blocked external-service Needs a Google OAuth consent the sandbox cannot grant.",
        verify=_VERIFY,
    )
    assert any("all-@static" in problem and ":verify:" in problem for problem in problems)


def test_expect_on_static_frame_is_refused() -> None:
    """@expect cannot annotate a @static frame (nothing runs to assert)."""
    problems = _problems(
        "@result aeat app modelo verify wu\n"
        "@expect exit_code == 0\n"
        "@static aeat app live justificante pull\n"
        "@expect exit_code == 0",
    )
    assert any("@expect cannot annotate a @static frame" in problem for problem in problems)


def test_capture_on_static_frame_is_refused() -> None:
    """@capture cannot annotate a @static frame (it produces no output to capture)."""
    problems = _problems(
        "@result aeat app modelo verify wu\n"
        "@expect exit_code == 0\n"
        "@static aeat app live justificante pull\n"
        "@capture ref result.reference",
    )
    assert any("@capture cannot annotate a @static frame" in problem for problem in problems)


# ---------------------------------------------------------------------------
# @blocked — the mandatory reason a @static frame does not execute
# ---------------------------------------------------------------------------


def test_static_frame_carries_its_blocked_reason() -> None:
    """A @static frame parses its @blocked code and detail onto the frame."""
    sequence = _parse(
        "@static aeat app live justificante pull\n"
        "@blocked live-aeat The pull verb fetches from the AEAT sede; the sandbox refuses it.",
        verify=None,
    )
    blocked = sequence.frames[0].blocked
    assert blocked is not None
    assert blocked.code is StaticBlocker.LIVE_AEAT
    assert blocked.detail == "The pull verb fetches from the AEAT sede; the sandbox refuses it."


def test_static_frame_without_a_blocked_reason_is_refused() -> None:
    """A bare @static marker is refused: the reason is what makes it auditable.

    This is the regression that let a documented dead end hide — an unexercised
    static frame and a deliberately-blocked one wore the same marker, so nobody
    could tell which was which.
    """
    problems = _problems("@static aeat config profile list", verify=None)
    assert any("must state why it is not executed" in problem and "@blocked" in problem for problem in problems)


def test_blocked_code_outside_the_closed_set_is_refused_with_its_options() -> None:
    """An unknown @blocked code names the accepted value set, never a bare refusal."""
    problems = _problems(
        "@static aeat config profile list\n@blocked someday A reason sentence that is long enough.",
        verify=None,
    )
    assert any("is not a known blocker" in problem and StaticBlocker.LIVE_AEAT.value in problem for problem in problems)


def test_blocked_detail_must_be_more_than_a_restated_code() -> None:
    """A token-length detail is refused: the code classifies, the detail must be checkable."""
    problems = _problems("@static aeat config profile list\n@blocked live-aeat live", verify=None)
    assert any("needs a specific reason of at least" in problem for problem in problems)


def test_blocked_on_an_executed_frame_is_refused() -> None:
    """@blocked cannot annotate an executed frame; a frame that runs has no blocker."""
    problems = _problems(
        "@result aeat app modelo verify wu\n"
        "@expect exit_code == 0\n"
        "@blocked live-aeat The pull verb fetches from the AEAT sede.",
    )
    assert any("@blocked cannot annotate a result frame" in problem for problem in problems)


def test_a_static_frame_takes_one_blocked_reason() -> None:
    """A second @blocked on the same @static frame is refused."""
    problems = _problems(
        "@static aeat config profile list\n"
        "@blocked live-aeat The pull verb fetches from the AEAT sede.\n"
        "@blocked interactive-tty Prompts on a terminal the runner does not have.",
        verify=None,
    )
    assert any("takes one @blocked reason" in problem for problem in problems)


def test_blocked_without_a_preceding_frame_is_refused() -> None:
    """A leading @blocked attaches to nothing and is refused."""
    problems = _problems(
        "@blocked live-aeat The pull verb fetches from the AEAT sede.\n@static aeat config profile list",
        verify=None,
    )
    assert any("@blocked must follow a @static frame" in problem for problem in problems)


def test_executed_frames_carry_no_blocked_reason() -> None:
    """An executed frame parses with ``blocked`` unset, so no stale reason can ride along."""
    sequence = _parse(_WORKED_EXAMPLE)
    assert all(frame.blocked is None for frame in sequence.executed_frames)


def test_executed_frame_after_result_is_refused() -> None:
    """An executed frame after the @result is refused; only @static may follow it."""
    problems = _problems(
        "@result aeat app modelo verify wu\n@expect exit_code == 0\naeat app modelo create 303 --year 2026 --period 1T",
    )
    assert any("must be the last EXECUTED frame" in problem for problem in problems)
