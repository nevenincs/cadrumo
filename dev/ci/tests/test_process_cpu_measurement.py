"""Timed children receive their stdin, and a spawning call is charged for its child.

Product commands read a profile passphrase only from an explicit stdin channel,
so a benchmark that times them has to deliver that payload through the same
call that owns the child's CPU accounting: the payload must arrive
byte-for-byte and be closed afterwards, and an empty payload is still an
explicit, immediately closed stream rather than an inherited one.

A call that hands its work to a child process is the other trap. Its own
``process_time`` stays near zero however expensive the child is, so a CPU gate
built on it passes whatever the call costs. The detector case runs a real child
that burns a known amount of CPU inside the measured block and requires the
measurement to see it.
"""

from __future__ import annotations

import sys
import time

import pytest

from ..perf_measurement import process_tree_cpu, timed_subprocess

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ECHO_REVERSED = "import sys; data = sys.stdin.read(); sys.stdout.write(data[::-1])"

#: CPU seconds the busy child spends before it exits; comfortably above timer
#: resolution on every platform and far above an interpreter start alone.
_CHILD_BUSY_CPU_S = 0.6
_BUSY_CHILD = (
    "import time\n"
    f"deadline = time.process_time() + {_CHILD_BUSY_CPU_S}\n"
    "while time.process_time() < deadline:\n"
    "    pass\n"
)


def test_input_text_is_the_childs_whole_stdin() -> None:
    payload = '{"profile_passphrase":"not-a-real-secret"}'

    timing = timed_subprocess((sys.executable, "-c", _ECHO_REVERSED), timeout_s=60.0, input_text=payload)

    assert timing.returncode == 0, timing.stderr
    assert timing.stdout == payload[::-1]
    assert timing.cpu_seconds > 0.0
    assert timing.wall_seconds > 0.0


def test_an_empty_input_text_is_a_closed_stream_not_an_inherited_one() -> None:
    timing = timed_subprocess(
        (sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))"),
        timeout_s=60.0,
        input_text="",
    )

    assert timing.returncode == 0, timing.stderr
    assert timing.stdout.strip() == "''"


def test_a_call_that_spawns_a_busy_child_is_charged_for_the_child() -> None:
    # The child runs under its own job on Windows, as a timed child does, so
    # this also proves a nested job still reports into the enclosing one.
    with process_tree_cpu() as measured:
        child = timed_subprocess((sys.executable, "-c", _BUSY_CHILD), timeout_s=60.0)

    assert child.returncode == 0, child.stderr

    assert measured.child_cpu_seconds >= _CHILD_BUSY_CPU_S * 0.9, measured
    assert measured.cpu_seconds >= measured.child_cpu_seconds
    # The parent only waited, which is exactly what process_time alone reports.
    assert measured.own_cpu_seconds < measured.child_cpu_seconds, measured
    assert measured.wall_seconds >= measured.child_cpu_seconds * 0.5, measured


def test_a_call_that_spawns_nothing_is_charged_only_for_itself() -> None:
    with process_tree_cpu() as measured:
        deadline = time.process_time() + 0.2
        while time.process_time() < deadline:
            pass

    assert measured.own_cpu_seconds >= 0.2
    assert measured.child_cpu_seconds < 0.1, measured
