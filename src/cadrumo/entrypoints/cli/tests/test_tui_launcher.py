"""Boundary proofs for the sole CLI-to-TUI launch seam."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
import typer

from ..tui_launcher import TUI_ROOT_MODULE, launch_tui, tui_root_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_the_launcher_builds_only_the_fixed_tui_root_module_command() -> None:
    """No subject, route, capability, or session result crosses this boundary."""
    assert tui_root_command("/usr/bin/python3") == ["/usr/bin/python3", "-m", TUI_ROOT_MODULE]


def test_the_launcher_propagates_the_child_exit_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """The launcher neither interprets nor converts the child's result."""
    observed: list[object] = []

    def run(command: list[str], *, check: bool) -> SimpleNamespace:
        observed.append((command, check))
        return SimpleNamespace(returncode=17)

    monkeypatch.setattr("cadrumo.entrypoints.cli.tui_launcher.subprocess.run", run)

    with pytest.raises(typer.Exit) as raised:
        launch_tui()

    assert raised.value.exit_code == 17
    assert observed == [([sys.executable, "-m", TUI_ROOT_MODULE], False)]
