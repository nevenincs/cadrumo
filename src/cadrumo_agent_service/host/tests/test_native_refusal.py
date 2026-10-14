"""Only the native host's own last standard-error line is read, as a closed code and a plain name."""

from __future__ import annotations

import json

import pytest

from ..native_refusal import (
    STANDARD_ERROR_TAIL_BYTES,
    NativeLaunchRefusal,
    NativeLaunchRefusalCode,
    native_launch_refusal_from,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ABSENT = NativeLaunchRefusal(code=None, subject=None)


def _line(code: str, subject: str) -> bytes:
    return json.dumps({"native_refusal": code, "subject": subject}).encode() + b"\n"


@pytest.mark.parametrize(
    ("code", "subject", "expected"),
    [
        ("launch_value_missing", "SLOT_ONE", NativeLaunchRefusalCode.LAUNCH_VALUE_MISSING),
        ("launch_value_malformed", "SLOT_TWO", NativeLaunchRefusalCode.LAUNCH_VALUE_MALFORMED),
        ("invocation_undeclared", "-m other.module", NativeLaunchRefusalCode.INVOCATION_UNDECLARED),
    ],
)
def test_each_closed_code_is_read_with_the_name_it_concerns(
    code: str, subject: str, expected: NativeLaunchRefusalCode
) -> None:
    assert native_launch_refusal_from(_line(code, subject)) == NativeLaunchRefusal(code=expected, subject=subject)


def test_the_last_line_decides_and_earlier_output_is_never_read() -> None:
    tail = b"warning: something\n" + _line("launch_value_missing", "EARLIER") + _line("launch_value_malformed", "LAST")
    assert native_launch_refusal_from(tail) == NativeLaunchRefusal(
        code=NativeLaunchRefusalCode.LAUNCH_VALUE_MALFORMED, subject="LAST"
    )
    assert native_launch_refusal_from(_line("launch_value_missing", "EARLIER") + b"trailing noise\n") == _ABSENT


def test_line_endings_blank_trailing_lines_and_a_cut_start_are_tolerated() -> None:
    line = _line("launch_value_missing", "SLOT")
    expected = NativeLaunchRefusal(code=NativeLaunchRefusalCode.LAUNCH_VALUE_MISSING, subject="SLOT")
    assert native_launch_refusal_from(line.replace(b"\n", b"\r\n") + b"\r\n\r\n") == expected
    assert native_launch_refusal_from(b"x" * STANDARD_ERROR_TAIL_BYTES + b"\n" + line + b"\n  \n") == expected
    assert native_launch_refusal_from(b"ult}\n" + line) == expected


@pytest.mark.parametrize(
    "tail",
    [
        pytest.param(b"", id="empty"),
        pytest.param(b"   \n\n", id="blank"),
        pytest.param(b"not json at all\n", id="not-json"),
        pytest.param(b"\xff\xfe{\n", id="not-utf8"),
        pytest.param(b'["launch_value_missing", "SLOT"]\n', id="not-an-object"),
        pytest.param(b'{"native_refusal": "launch_value_missing"}\n', id="subject-absent"),
        pytest.param(b'{"subject": "SLOT"}\n', id="code-absent"),
        pytest.param(b'{"native_refusal": 125, "subject": "SLOT"}\n', id="code-not-a-string"),
        pytest.param(b'{"native_refusal": "launch_value_missing", "subject": 7}\n', id="subject-not-a-string"),
        pytest.param(
            b'{"native_refusal": "launch_value_missing", "subject": "SLOT", "value": "PLANTED-VALUE"}\n',
            id="extra-key-carrying-a-value",
        ),
        pytest.param(b'{"native_refusal": "Launch Value", "subject": "SLOT"}\n', id="code-not-a-token"),
        pytest.param(_line("launch_value_missing", "A" * 600), id="subject-far-too-long"),
    ],
)
def test_anything_that_is_not_exactly_the_hosts_line_reads_as_absent(tail: bytes) -> None:
    assert native_launch_refusal_from(tail) == _ABSENT


def test_a_code_outside_the_closed_set_is_dropped_but_a_plain_name_is_kept() -> None:
    assert native_launch_refusal_from(_line("launch_value_unheard_of", "SLOT")) == NativeLaunchRefusal(
        code=None, subject="SLOT"
    )


@pytest.mark.parametrize(
    "subject",
    [
        pytest.param("C:\\Users\\someone\\secret.txt", id="windows-path"),
        pytest.param("/home/someone/secret", id="posix-path"),
        pytest.param("NAME=VALUE", id="assignment"),
        pytest.param("A" * 129, id="over-128-characters"),
        pytest.param("tab\there", id="control-character"),
        pytest.param('quoted "value"', id="quote"),
        pytest.param("", id="empty"),
    ],
)
def test_a_subject_that_is_not_a_plain_name_is_dropped_but_the_code_is_kept(subject: str) -> None:
    assert native_launch_refusal_from(_line("launch_value_malformed", subject)) == NativeLaunchRefusal(
        code=NativeLaunchRefusalCode.LAUNCH_VALUE_MALFORMED, subject=None
    )
