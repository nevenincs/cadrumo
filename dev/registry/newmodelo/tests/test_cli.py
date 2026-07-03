"""Real-behaviour tests for the ``python -m dev.registry.newmodelo`` CLI surface."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from .. import cli as cli_module
from ..cli import app
from ..manager import NewModeloScaffoldManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_THROWAWAY_MODELO_ID = "986"
_THROWAWAY_REVISION_ID = "2026-y-siguientes"


def _redirect_default_manager(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point the CLI's default manager factory at a real, isolated tmp_path tree."""
    monkeypatch.setattr(
        cli_module,
        "_default_manager",
        lambda: NewModeloScaffoldManager(registry_modelos_root=tmp_path),
    )


def test_cli_scaffold_writes_tree_and_prints_checklist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``newmodelo scaffold`` writes the skeleton and prints the 12-item checklist."""
    _redirect_default_manager(monkeypatch, tmp_path)

    result = CliRunner().invoke(app, ["scaffold", _THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID])

    assert result.exit_code == 0, result.stdout
    assert "written" in result.stdout
    assert "Contributor checklist for a new modelo revision (12 items):" in result.stdout
    assert (tmp_path / _THROWAWAY_MODELO_ID / "manifest.toml").is_file()


def test_cli_scaffold_check_exits_nonzero_when_tree_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``newmodelo scaffold --check`` exits 1 and lists missing files when nothing is scaffolded."""
    _redirect_default_manager(monkeypatch, tmp_path)

    result = CliRunner().invoke(
        app,
        ["scaffold", _THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID, "--check"],
    )

    assert result.exit_code == 1
    assert "missing" in result.stdout
    assert not (tmp_path / _THROWAWAY_MODELO_ID).exists()


def test_cli_scaffold_check_exits_zero_after_real_scaffold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``newmodelo scaffold --check`` is conformant immediately after a real scaffold run."""
    _redirect_default_manager(monkeypatch, tmp_path)

    first = CliRunner().invoke(app, ["scaffold", _THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID])
    assert first.exit_code == 0

    second = CliRunner().invoke(
        app,
        ["scaffold", _THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID, "--check"],
    )

    assert second.exit_code == 0
    assert "conformant" in second.stdout


def test_cli_checklist_command_prints_all_items() -> None:
    """``newmodelo checklist`` prints the checklist without touching the filesystem."""
    result = CliRunner().invoke(app, ["checklist"])

    assert result.exit_code == 0
    assert "Contributor checklist for a new modelo revision (12 items):" in result.stdout


def test_cli_scaffold_rejects_malformed_modelo_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A malformed modelo id exits non-zero with an instructive error, not a traceback."""
    _redirect_default_manager(monkeypatch, tmp_path)

    result = CliRunner().invoke(app, ["scaffold", "AB", _THROWAWAY_REVISION_ID])

    assert result.exit_code == 1
    assert "error:" in result.stdout.lower() or "error:" in (result.stderr or "").lower()
