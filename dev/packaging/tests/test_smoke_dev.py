"""Tests for the developer-venv packaging smoke lane's proof discipline.

`dev.quality.module_test_reach` listed `dev/packaging/smoke_dev.py` as unreached.
The lane builds a clean venv, installs the project non-editable, and proves the
developer toolchain starts in it. Each proof it records becomes a line in the
committed smoke manifest.

The manifest already refuses a DECLARED claim whose assertion never ran - that
is what ``ProofContractError`` is for. What it cannot see is an assertion that
ran over nothing: ``record_proof`` sat after a loop and fired whether or not the
loop had a single iteration, so an emptied command surface would have satisfied
the contract having started no command at all. The list is eleven entries today,
so this was latent rather than live; it is guarded because the whole point of
the proof ledger is that a claim cannot appear without its assertion.

The refusal is reachable without a venv because the guard runs first, and the
command list is now a parameter - so the empty case is driven by passing it
rather than by reaching into module state.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

from .._smoke_common import run_checked_marker
from ..smoke_dev import _DEV_COMMANDS, _assert_dev_commands

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_an_empty_command_surface_refuses(tmp_path: pathlib.Path) -> None:
    """The defect: this would have recorded a proof having started nothing.

    The guard runs before anything touches the venv, so no build is needed to
    reach it - which is also what makes it safe to keep.
    """
    with pytest.raises(SystemExit, match="would prove nothing"):
        _assert_dev_commands(tmp_path, tmp_path, commands=())


def test_the_declared_surface_is_not_empty() -> None:
    """The live list backs the lane's manifest claim, so it must carry entries."""
    assert _DEV_COMMANDS


def test_every_declared_command_is_a_probe_with_an_argument() -> None:
    """Each entry must start a tool and return, never do work.

    A bare executable with no argument would run the tool's default action
    inside the smoke venv - for pytest that is a full collection and run.
    """
    for command in _DEV_COMMANDS:
        assert len(command) >= 2, command
        executable, *args = command
        assert executable
        assert args[0].startswith("--"), command


def test_no_tool_is_probed_twice() -> None:
    """A duplicate costs a venv invocation and proves nothing new."""
    executables = [command[0] for command in _DEV_COMMANDS]

    assert len(executables) == len(set(executables))


def test_the_surface_covers_the_gates_the_repository_actually_runs() -> None:
    """These are the tools the quality gates invoke, so their absence breaks a lane.

    Named individually rather than counted: a count would pass while a tool was
    swapped for another, which is the substitution this check exists to notice.
    """
    executables = {command[0] for command in _DEV_COMMANDS}

    assert {"ruff", "pytest", "ty", "pyrefly", "lint-imports", "deptry"} <= executables


def test_a_child_that_skipped_its_tail_is_refused(tmp_path: pathlib.Path) -> None:
    """A completion marker printed into a void proves nothing.

    Five child programs across these lanes end with a print naming what they
    proved, and nothing asserted any of them: the parent read the exit code
    alone. A child that exits 0 having skipped its tail was indistinguishable
    from one that ran every assertion in it.
    """
    silent = [sys.executable, "-c", "raise SystemExit(0)"]

    with pytest.raises(SystemExit, match="without printing"):
        run_checked_marker(silent, cwd=tmp_path, marker="expected-marker")


def test_a_child_that_printed_its_marker_is_accepted(tmp_path: pathlib.Path) -> None:
    """The success path, so the requirement is not satisfied by refusing everything."""
    speaking = [sys.executable, "-c", "print('expected-marker')"]

    assert run_checked_marker(speaking, cwd=tmp_path, marker="expected-marker").returncode == 0


def test_a_failing_child_still_fails_on_its_exit_code(tmp_path: pathlib.Path) -> None:
    """The marker requirement is additional, never a replacement for the status."""
    failing = [sys.executable, "-c", "print('expected-marker'); raise SystemExit(3)"]

    with pytest.raises(SystemExit):
        run_checked_marker(failing, cwd=tmp_path, marker="expected-marker")
