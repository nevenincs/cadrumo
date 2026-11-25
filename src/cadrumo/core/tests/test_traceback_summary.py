"""A traceback summary admits only strict identifiers and holds only a bounded number of frames."""

from __future__ import annotations

import pytest

from ..traceback_summary import SUMMARY_FRAMES, TracebackReader, TracebackSummary

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_NAME = "Lucía Fernández Ortega"


def _read(*lines: str) -> TracebackSummary:
    reader = TracebackReader()
    for line in lines:
        if (summary := reader.read(line)) is not None:
            return summary
    return reader.unfinished()


def test_the_exception_line_ends_the_body_with_its_type_and_frames_innermost_first() -> None:
    summary = _read(
        '  File "/srv/app/outer.py", line 10, in start',
        "    inner()",
        '  File "C:\\work\\inner.py", line 7, in Clock.inner',
        f"    raise ClockUnavailableError('{_NAME}')",
        f"errors.ClockUnavailableError: {_NAME} IBAN ES9121000418450200051332",
        '  File "after.py", line 1, in ignored',
    )
    assert summary == TracebackSummary(
        error_type="errors.ClockUnavailableError",
        frames=("inner.py:7:Clock.inner", "outer.py:10:start"),
        innermost_admitted=True,
    )
    assert summary.origin == "inner.py:7:Clock.inner"


@pytest.mark.parametrize(
    "crafted",
    [
        f'  File "C:\\Users\\{_NAME}\\{_NAME}.py", line 4, in <module>',
        f'  File "clock.py", line 4, in {_NAME}',
        '  File "clock.py", line 4, in password=hunter2',
        '  File "12345678Z.py", line 4, in <module>',
        '  File "clock.py", line 4, in ES9121000418450200051332',
        '  File "clock.py", line 99999999, in start',
        '  File "clock.py", line 4, in call_600123456',
    ],
)
def test_a_frame_with_a_token_that_is_not_a_strict_identifier_is_dropped_and_names_no_origin(crafted: str) -> None:
    summary = _read('  File "boot.py", line 2, in <module>', crafted, "LookupError: x")
    assert summary == TracebackSummary(
        error_type="LookupError", frames=("boot.py:2:<module>",), innermost_admitted=False
    )
    assert summary.origin is None


@pytest.mark.parametrize("type_line", [f"{_NAME}: x", "LuciaFernandez: x", "ES9121000418450200051332Error: x"])
def test_an_exception_line_that_names_no_exception_type_names_no_type(type_line: str) -> None:
    assert _read('  File "boot.py", line 2, in <module>', type_line).error_type is None


def test_a_body_holds_only_its_innermost_frames() -> None:
    reader = TracebackReader()
    for line in range(1, 5000):
        assert reader.read(f'  File "deep.py", line {line}, in step_{line}') is None
        assert reader.read("    step()") is None
    summary = reader.read("RecursionError: depth")
    assert summary is not None
    assert len(summary.frames) == SUMMARY_FRAMES
    assert summary.frames[0] == "deep.py:4999:step_4999"
    assert summary.frames[-1] == f"deep.py:{5000 - SUMMARY_FRAMES}:step_{5000 - SUMMARY_FRAMES}"


def test_a_body_that_never_reaches_its_exception_line_is_unfinished_with_no_type() -> None:
    summary = _read('  File "boot.py", line 2, in <module>')
    assert summary == TracebackSummary(error_type=None, frames=("boot.py:2:<module>",), innermost_admitted=True)
