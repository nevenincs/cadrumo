"""A worker exit account names only an exception type and frame identifiers, never output text."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from ..worker_exit_reason import WORKER_ERROR_FRAMES, WORKER_STANDARD_ERROR_BYTES, worker_exit_fields

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_NAME = "Lucía Fernández Ortega"

_CHAINED = (
    "Traceback (most recent call last):\n"
    '  File "C:\\work\\first.py", line 3, in <module>\n'
    "    first()\n"
    "KeyError: 'missing'\n"
    "\n"
    "During handling of the above exception, another exception occurred:\n"
    "\n"
    "Traceback (most recent call last):\n"
    '  File "/srv/app/outer.py", line 10, in start\n'
    "    inner()\n"
    '  File "/srv/app/inner.py", line 7, in Clock.inner\n'
    f"    raise errors.ClockUnavailableError('{_NAME}')\n"
    f"errors.ClockUnavailableError: {_NAME} IBAN ES9121000418450200051332\n"
)


def _text(fields: Mapping[str, object]) -> str:
    return " ".join(str(value) for value in fields.values())


def test_the_last_traceback_names_its_type_and_frames_innermost_first_without_any_message() -> None:
    fields = worker_exit_fields(exit_code=1, standard_error=_CHAINED.encode())
    assert fields == {
        "exit_code": 1,
        "worker_error_type": "errors.ClockUnavailableError",
        "worker_error_origin": "inner.py:7:Clock.inner",
        "worker_error_frames": "inner.py:7:Clock.inner <- outer.py:10:start",
    }
    for private in (_NAME, "Lucía", "ES9121000418450200051332", "/srv/app", "missing"):
        assert private not in _text(fields)


@pytest.mark.parametrize(
    "crafted",
    [
        f'  File "C:\\Users\\{_NAME}\\{_NAME}.py", line 4, in <module>',
        f'  File "clock.py", line 4, in {_NAME}',
        '  File "clock.py", line 4, in password=hunter2',
        '  File "clock.py", line 4, in 12345678Z',
        '  File "12345678Z.py", line 4, in <module>',
        '  File "clock.py", line 4, in ES9121000418450200051332',
        '  File "clock.py", line 99999999, in start',
        '  File "clock.py", line 4, in <Lucia>',
        '  File "clock.py", line 4, in call_600123456',
    ],
)
def test_a_frame_whose_tokens_are_not_strict_identifiers_is_dropped(crafted: str) -> None:
    standard_error = (
        f'Traceback (most recent call last):\n  File "boot.py", line 2, in <module>\n{crafted}\nLookupError: x\n'
    )
    fields = worker_exit_fields(exit_code=1, standard_error=standard_error.encode())
    # The innermost frame was refused, so no origin is named; the admitted outer frame remains.
    assert fields == {"exit_code": 1, "worker_error_type": "LookupError", "worker_error_frames": "boot.py:2:<module>"}


@pytest.mark.parametrize("type_line", [f"{_NAME}: x", "LuciaFernandez: x", "ES9121000418450200051332Error: x"])
def test_an_exception_line_that_does_not_name_an_exception_type_names_no_type(type_line: str) -> None:
    standard_error = f'Traceback (most recent call last):\n  File "boot.py", line 2, in <module>\n{type_line}\n'
    fields = worker_exit_fields(exit_code=1, standard_error=standard_error.encode())
    assert "worker_error_type" not in fields
    assert fields["worker_error_origin"] == "boot.py:2:<module>"


def test_output_without_a_traceback_reports_only_the_exit_status() -> None:
    fields = worker_exit_fields(exit_code=3, standard_error=f"fatal: cannot open store for {_NAME}\n".encode())
    assert fields == {"exit_code": 3}


def test_an_uncaptured_stream_reports_only_the_exit_status() -> None:
    assert worker_exit_fields(exit_code=None, standard_error=None) == {"exit_code": None}


def test_a_traceback_longer_than_the_held_bytes_still_names_its_innermost_frames_within_the_bound() -> None:
    frames = "".join(f'  File "deep.py", line {line}, in step_{line}\n    step()\n' for line in range(1, 400))
    held = f"Traceback (most recent call last):\n{frames}RecursionError: depth\n".encode()
    fields = worker_exit_fields(exit_code=1, standard_error=held[-WORKER_STANDARD_ERROR_BYTES:])
    assert fields["worker_error_type"] == "RecursionError"
    assert fields["worker_error_origin"] == "deep.py:399:step_399"
    named = str(fields["worker_error_frames"]).split(" <- ")
    assert len(named) == WORKER_ERROR_FRAMES
    assert named[-1] == f"deep.py:{400 - WORKER_ERROR_FRAMES}:step_{400 - WORKER_ERROR_FRAMES}"
