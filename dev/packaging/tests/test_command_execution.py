"""Real-subprocess contracts for the canonical packaging command boundary."""

from __future__ import annotations

import os
import subprocess
import sys
from contextlib import suppress
from datetime import UTC
from pathlib import Path

import pytest

from .._command import run_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: Reads whatever the parent said it inherited. The token is a descriptor
#: number on POSIX and a HANDLE on Windows, because that is the difference
#: between the two inheritance mechanisms rather than a detail of this test.
_READ_WHAT_WAS_INHERITED = """
import os, sys

token = int(sys.argv[1])
if sys.platform == "win32":
    import msvcrt

    token = msvcrt.open_osfhandle(token, os.O_RDONLY | os.O_BINARY)
sys.stdout.write(os.read(token, 64).decode())
"""


def _inheritance_token(descriptor: int) -> str:
    if sys.platform == "win32":
        import msvcrt

        return str(msvcrt.get_osfhandle(descriptor))
    return str(descriptor)


def test_run_command_retains_real_streams_and_timestamps(tmp_path: Path) -> None:
    """A successful real process retains the exact facts later evidence consumes."""
    execution = run_command(
        (sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr)"),
        cwd=tmp_path,
    )
    assert execution.returncode == 0
    assert execution.stdout == "out\n"
    assert execution.stderr == "err\n"
    assert execution.cwd == str(tmp_path)
    assert execution.started_at.tzinfo is UTC
    assert execution.completed_at >= execution.started_at
    assert execution.duration_seconds >= 0


def test_run_command_returns_nonzero_result_without_synthesising_a_success(tmp_path: Path) -> None:
    """The domain layer, not the runner, decides how a real nonzero exit fails."""
    execution = run_command(
        (sys.executable, "-c", "import sys; print('refusal', file=sys.stderr); raise SystemExit(7)"),
        cwd=tmp_path,
    )

    assert execution.returncode == 7
    assert execution.stdout == ""
    assert execution.stderr == "refusal\n"


def test_run_command_propagates_a_real_timeout_without_inventing_an_exit_status(tmp_path: Path) -> None:
    """A process that did not exit cannot truthfully become a command transcript."""
    with pytest.raises(subprocess.TimeoutExpired):
        run_command((sys.executable, "-c", "import time; time.sleep(1)"), cwd=tmp_path, timeout_seconds=0.01)


@pytest.mark.parametrize("argv", ((), ("",)))
def test_run_command_refuses_an_empty_command(argv: tuple[str, ...]) -> None:
    """The common runner never creates a result for an invalid command identity."""
    with pytest.raises(ValueError, match="non-empty"):
        run_command(argv, cwd=Path.cwd())


def test_run_command_delivers_a_named_descriptor_to_the_child(tmp_path: Path) -> None:
    """A child that must read a bounded secret channel has to actually receive it."""
    read_descriptor, write_descriptor = os.pipe()
    try:
        os.write(write_descriptor, b"inherited")
        execution = run_command(
            (sys.executable, "-c", _READ_WHAT_WAS_INHERITED, _inheritance_token(read_descriptor)),
            cwd=tmp_path,
            inherited_descriptors=(read_descriptor,),
        )
    finally:
        for descriptor in (read_descriptor, write_descriptor):
            with suppress(OSError):
                os.close(descriptor)

    assert execution.returncode == 0, execution.stderr
    assert execution.stdout == "inherited"


def test_run_command_withholds_a_descriptor_it_was_not_told_to_pass(tmp_path: Path) -> None:
    """Inheritance is the explicit allowlist, not a side effect of spawning."""
    read_descriptor, write_descriptor = os.pipe()
    try:
        os.write(write_descriptor, b"inherited")
        execution = run_command(
            (sys.executable, "-c", _READ_WHAT_WAS_INHERITED, _inheritance_token(read_descriptor)),
            cwd=tmp_path,
        )
    finally:
        for descriptor in (read_descriptor, write_descriptor):
            with suppress(OSError):
                os.close(descriptor)

    assert execution.stdout != "inherited"
