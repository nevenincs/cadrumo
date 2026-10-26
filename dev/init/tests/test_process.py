"""Steps run against the project environment, not the one `init` runs on."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from ..contract import Step
from ..process import run, step_environment

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _exits_zero_when(condition: str) -> tuple[str, ...]:
    """Return a real child process that succeeds only when ``condition`` holds in it."""
    return (sys.executable, "-c", f"import os, sys; sys.exit(0 if {condition} else 3)")


def test_step_environment_drops_the_active_environment_marker(tmp_path: Path) -> None:
    """The ephemeral interpreter's activation marker is the one variable withheld."""
    environment = step_environment({"VIRTUAL_ENV": str(tmp_path / "ephemeral"), "PATH": "/usr/bin", "KEPT": "value"})

    assert "VIRTUAL_ENV" not in environment
    assert environment == {"PATH": "/usr/bin", "KEPT": "value"}


def test_step_environment_leaves_an_environment_without_the_marker_unchanged() -> None:
    """No marker to drop is not an error, and the source mapping is not mutated."""
    source = {"PATH": "/usr/bin"}

    environment = step_environment(source)

    assert environment == source
    assert environment is not source


def test_a_step_does_not_inherit_the_active_environment_marker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A nested `uv` would warn about a foreign VIRTUAL_ENV; the child must not see one."""
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "ephemeral"))
    step = Step(name="probe", argv=_exits_zero_when("'VIRTUAL_ENV' not in os.environ"), summary="probe")

    result, code = run(step, cwd=tmp_path, echo=False)

    assert (result.exit_code, code) == (0, 0)


def test_a_step_still_inherits_every_other_variable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Withholding the marker must not cut the step off from the rest of the environment."""
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "ephemeral"))
    monkeypatch.setenv("CADRUMO_INIT_STEP_PROBE", "present")
    step = Step(
        name="probe",
        argv=_exits_zero_when("os.environ.get('CADRUMO_INIT_STEP_PROBE') == 'present'"),
        summary="probe",
    )

    result, code = run(step, cwd=tmp_path, echo=False)

    assert (result.exit_code, code) == (0, 0)
