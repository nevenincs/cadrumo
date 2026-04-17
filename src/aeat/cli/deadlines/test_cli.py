"""Unit tests for the ``aeat deadlines`` CLI sub-app."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.cli.deadlines import app
from aeat.deadlines import AutonomoProfile, IVARegime

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


@pytest.fixture()
def profile_path(tmp_path: Path) -> Path:
    profile = AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=True,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    path = tmp_path / "profile.json"
    path.write_text(profile.model_dump_json(), encoding="utf-8")
    return path


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_list_renders_obligations(runner: CliRunner, profile_path: Path) -> None:
    result = runner.invoke(app, ["list", "--year", "2026", "--profile", str(profile_path)])
    assert result.exit_code == 0, result.output
    assert "303" in result.output
    assert "2026Q1" in result.output


def test_next_renders_an_obligation(runner: CliRunner, profile_path: Path) -> None:
    result = runner.invoke(app, ["next", "--year", "2026", "--profile", str(profile_path)])
    assert result.exit_code == 0, result.output
    assert any(token in result.output for token in ("303", "130", "115", "100"))


def test_explain_known_modelo(runner: CliRunner, profile_path: Path) -> None:
    result = runner.invoke(app, ["explain", "303", "--profile", str(profile_path)])
    assert result.exit_code == 0, result.output
    assert "303" in result.output
    assert "aplica" in result.output


def test_list_requires_profile_when_setting_unset(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEAT_DEFAULT_PROFILE_PATH", "")
    result = runner.invoke(app, ["list", "--year", "2026"])
    assert result.exit_code != 0
    assert "profile" in result.output.lower()


def test_next_uses_default_profile_path(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    profile_path: Path,
) -> None:
    monkeypatch.setenv("AEAT_DEFAULT_PROFILE_PATH", str(profile_path))
    result = runner.invoke(app, ["next", "--year", "2026"])
    assert result.exit_code == 0, result.output
