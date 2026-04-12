"""Smoke tests for ``aeat filing`` CLI commands.

These tests use Typer's :class:`CliRunner` against the root
``aeat`` Typer app and a temporary drafts directory configured
via ``AEAT_DRAFTS_DIR``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.cli import app

runner = CliRunner()


def _write_inputs(tmp_path: Path) -> Path:
    """Write a JSON inputs file with a clean Modelo 130 draft."""
    payload = {
        "01": 12500,
        "02": 3500,
        "05": 400,
        "06": 0,
    }
    target = tmp_path / "inputs.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


@pytest.fixture
def drafts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``AEAT_DRAFTS_DIR`` at a clean per-test directory."""
    target = tmp_path / "drafts"
    target.mkdir()
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(target))
    return target


@pytest.mark.unit
class TestFilingCLI:
    def test_build_writes_draft_to_disk(self, tmp_path: Path, drafts_dir: Path) -> None:
        inputs = _write_inputs(tmp_path)
        result = runner.invoke(
            app,
            [
                "filing",
                "build",
                "--modelo",
                "130",
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
            ],
        )
        assert result.exit_code == 0, result.output
        produced = sorted(drafts_dir.glob("130_2026Q1_*.json"))
        assert len(produced) == 1

    def test_show_and_validate_round_trip(self, tmp_path: Path, drafts_dir: Path) -> None:
        inputs = _write_inputs(tmp_path)
        build_result = runner.invoke(
            app,
            [
                "filing",
                "build",
                "--modelo",
                "130",
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
            ],
        )
        assert build_result.exit_code == 0
        produced = next(drafts_dir.glob("130_2026Q1_*.json"))

        show_result = runner.invoke(app, ["filing", "show", str(produced)])
        assert show_result.exit_code == 0

        validate_result = runner.invoke(app, ["filing", "validate", str(produced)])
        assert validate_result.exit_code == 0

    def test_list_filters_by_modelo(self, tmp_path: Path, drafts_dir: Path) -> None:
        inputs = _write_inputs(tmp_path)
        runner.invoke(
            app,
            [
                "filing",
                "build",
                "--modelo",
                "130",
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
            ],
        )
        result = runner.invoke(app, ["filing", "list", "--modelo", "130"])
        assert result.exit_code == 0
