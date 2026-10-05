"""Run documentation delivery build commands with complete captured streams."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import CommandResult, run_command


def _repo_root() -> Path:
    """Return the repository root."""
    return REPO_ROOT


def _command_label(command: Sequence[str]) -> str:
    """Return a readable command without invoking a shell."""
    return subprocess.list2cmdline(list(command))


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Run one local command and stop on its real exit status."""
    print(f"+ {_command_label(command)}", flush=True)
    # Callers build fixed command vectors; externally supplied values are validated.
    completed = run_command(
        list(command),
        cwd=cwd,
        environment=env,
    )
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n", flush=True)
    if completed.stderr:
        print(completed.stderr, end="" if completed.stderr.endswith("\n") else "\n", file=sys.stderr, flush=True)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return completed
