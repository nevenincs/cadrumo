"""Real-behaviour tests for the ``python -m dev.registry.newmodelo`` CLI surface."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from dev._paths import REPO_ROOT

from ..checklist import CHECKLIST
from ..cli import _default_manager, app

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_THROWAWAY_MODELO_ID = "986"
_THROWAWAY_REVISION_ID = "2026-y-siguientes"


def test_default_manager_targets_the_live_cadrumo_registry_tree() -> None:
    """The no-override CLI path resolves the bundled Cadrumo registry."""
    manager = _default_manager()

    assert manager.registry_modelos_root.is_dir()
    assert manager.registry_modelos_root == (REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos")


def _scaffold_args(tmp_path: Path, *extra: str) -> list[str]:
    return [
        "scaffold",
        _THROWAWAY_MODELO_ID,
        _THROWAWAY_REVISION_ID,
        "--registry-modelos-root",
        str(tmp_path),
        "--valid-from",
        "2026-01-01",
        "--year-from",
        "2026",
        "--period",
        "0A",
        *extra,
    ]


def test_cli_scaffold_writes_tree_and_prints_checklist(tmp_path: Path) -> None:
    """``newmodelo scaffold`` writes the skeleton and prints the whole checklist."""
    result = CliRunner().invoke(app, _scaffold_args(tmp_path))

    assert result.exit_code == 0, result.stdout
    assert result.stderr == "", "the scaffold report is the command's sole stdout contract, never a diagnostic stream"
    assert "written" in result.stdout
    assert f"Contributor checklist for a new modelo revision ({len(CHECKLIST)} items):" in result.stdout
    assert (tmp_path / _THROWAWAY_MODELO_ID / "manifest.toml").is_file()


def test_cli_requires_real_applicability_coordinates(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        ["scaffold", _THROWAWAY_MODELO_ID, _THROWAWAY_REVISION_ID, "--registry-modelos-root", str(tmp_path)],
    )

    assert result.exit_code != 0
    assert "--valid-from" in result.stderr


def test_cli_checklist_command_prints_all_items() -> None:
    """``newmodelo checklist`` prints the checklist without touching the filesystem."""
    result = CliRunner().invoke(app, ["checklist"])

    assert result.exit_code == 0
    assert result.stderr == "", "the checklist report is the command's sole stdout contract, never a diagnostic stream"
    assert f"Contributor checklist for a new modelo revision ({len(CHECKLIST)} items):" in result.stdout


def test_cli_scaffold_rejects_malformed_modelo_id(tmp_path: Path) -> None:
    """A malformed modelo id exits non-zero with an instructive error, not a traceback."""
    result = CliRunner().invoke(
        app,
        _scaffold_args(tmp_path)[:1] + ["AB"] + _scaffold_args(tmp_path)[2:],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "error:" in result.stderr.lower()
