"""Boundary proofs for the sole CLI-to-TUI launch seam."""

from __future__ import annotations

import sys

import pytest
import typer

from ....tests.audited_process import ensure_text_completed_process, run_audited_process
from ..tui_launcher import TUI_ROOT_MODULE, launch_tui, tui_root_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_the_tui_root_module_is_the_absolute_tui_package() -> None:
    """``python -m`` refuses relative module names, so the root must be spelled absolutely."""
    assert TUI_ROOT_MODULE == "cadrumo.entrypoints.tui"


def test_the_launched_command_resolves_the_tui_module() -> None:
    """The built command reaches the TUI module, which refuses an unknown argument itself.

    The refusal comes from the TUI's own argument check, so it proves the child
    interpreter found and ran the module without needing a terminal.
    """
    completed = ensure_text_completed_process(
        run_audited_process(
            [*tui_root_command(), "--help"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    )

    assert completed.returncode != 0
    assert "unrecognised TUI module arguments" in completed.stderr, completed.stderr


def test_the_launcher_builds_only_the_fixed_tui_root_module_command() -> None:
    """No subject, route, capability, or session result crosses this boundary."""
    assert tui_root_command("/usr/bin/python3") == ["/usr/bin/python3", "-m", TUI_ROOT_MODULE]


def test_the_launcher_propagates_the_child_exit_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """The launcher neither interprets nor converts the child's result."""
    observed: list[object] = []

    async def run(command: list[str]) -> int:
        observed.append(command)
        return 17

    monkeypatch.setattr("cadrumo.entrypoints.cli.tui_launcher._run_tui", run)

    with pytest.raises(typer.Exit) as raised:
        launch_tui()

    assert raised.value.exit_code == 17
    assert observed == [[sys.executable, "-m", TUI_ROOT_MODULE]]
