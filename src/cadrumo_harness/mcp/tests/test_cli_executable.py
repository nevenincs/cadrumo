"""Shared executable authority for both harness CLI process ports."""

from __future__ import annotations

import pytest

from .. import _cli_executable as executable_module

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_explicit_cli_binding_precedes_ambient_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """An attested oracle binding cannot be displaced by ambient PATH state."""
    monkeypatch.setenv("CADRUMO_CLI_EXECUTABLE", "bound-aeat")
    monkeypatch.setattr(executable_module.shutil, "which", lambda _: "ambient-aeat")

    assert executable_module.installed_cli_executable(purpose="test") == "bound-aeat"


def test_ambient_cli_remains_the_unbound_operator_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ordinary harness sessions can still resolve their installed PATH command."""
    monkeypatch.delenv("CADRUMO_CLI_EXECUTABLE", raising=False)
    monkeypatch.setattr(executable_module.shutil, "which", lambda _: "ambient-aeat")

    assert executable_module.installed_cli_executable(purpose="test") == "ambient-aeat"
