"""Real-subprocess contracts for the canonical packaging command boundary."""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC
from pathlib import Path

import pytest

from dev.packaging._command import run_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


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
