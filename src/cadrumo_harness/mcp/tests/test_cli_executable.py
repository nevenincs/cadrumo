"""Shared executable authority for both harness CLI process ports."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from .. import _cli_executable as executable_module

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_explicit_cli_binding_precedes_sibling_and_ambient_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """An attested oracle binding cannot be displaced by the environment's own CLI or PATH."""
    monkeypatch.setenv("CADRUMO_CLI_EXECUTABLE", "bound-aeat")
    monkeypatch.setattr(executable_module.shutil, "which", lambda _: "ambient-aeat")

    assert executable_module.installed_cli_executable(purpose="test") == "bound-aeat"


def test_the_sibling_cli_precedes_an_ambient_path_entry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Another release or a checkout ahead on PATH cannot answer for this installation."""
    sibling = tmp_path / "aeat"
    sibling.write_text("", encoding="utf-8")
    monkeypatch.delenv("CADRUMO_CLI_EXECUTABLE", raising=False)
    monkeypatch.setattr(executable_module, "sibling_cli_executable", lambda: sibling)
    monkeypatch.setattr(executable_module.shutil, "which", lambda _: "ambient-aeat")

    assert executable_module.installed_cli_executable(purpose="test") == str(sibling)


def test_ambient_path_serves_only_an_environment_without_its_own_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A harness whose environment carries no CLI can still resolve the one on PATH."""
    monkeypatch.delenv("CADRUMO_CLI_EXECUTABLE", raising=False)
    monkeypatch.setattr(executable_module, "sibling_cli_executable", lambda: tmp_path / "absent-aeat")
    monkeypatch.setattr(executable_module.shutil, "which", lambda _: "ambient-aeat")

    assert executable_module.installed_cli_executable(purpose="test") == "ambient-aeat"


def test_no_cli_anywhere_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CADRUMO_CLI_EXECUTABLE", raising=False)
    monkeypatch.setattr(executable_module, "sibling_cli_executable", lambda: tmp_path / "absent-aeat")
    monkeypatch.setattr(executable_module.shutil, "which", lambda _: None)

    with pytest.raises(RuntimeError, match="the installed aeat executable is required for test"):
        executable_module.installed_cli_executable(purpose="test")


def test_this_environment_resolves_its_own_cli_over_a_foreign_one_on_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The real lookup: a foreign ``aeat`` placed first on PATH is passed over."""
    own = executable_module.sibling_cli_executable()
    if not own.is_file():
        pytest.fail(f"the environment running these tests has no CLI of its own at {own}")
    foreign_dir = tmp_path / "foreign-bin"
    foreign_dir.mkdir()
    foreign = foreign_dir / own.name
    shutil.copy2(own, foreign)
    monkeypatch.delenv("CADRUMO_CLI_EXECUTABLE", raising=False)
    monkeypatch.setenv("PATH", os.pathsep.join((str(foreign_dir), os.environ.get("PATH", ""))))
    assert Path(shutil.which(own.stem if sys.platform == "win32" else own.name) or "") == foreign

    assert executable_module.installed_cli_executable(purpose="test") == str(own)
