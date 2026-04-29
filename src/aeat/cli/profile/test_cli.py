"""CLI tests for ``aeat profile`` tax-residence commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...cli import SCHEMA_REGISTRY, app

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]

runner = CliRunner()


def _env(tmp_path: Path, *, language: str = "es") -> dict[str, str]:
    return {
        "AEAT_TAX_RESIDENCE_PROFILE_PATH": str(tmp_path / "tax-residence.json"),
        "AEAT_OUTPUT_LANGUAGE": language,
    }


def test_profile_show_without_profile(tmp_path: Path) -> None:
    result = runner.invoke(app, ["profile", "show"], env=_env(tmp_path))
    assert result.exit_code == 0, result.output
    assert "No hay residencia fiscal configurada" in result.output
    assert "aeat profile set tax-region <ccaa>" in result.output


def test_profile_help_explains_renta_tax_region_setup() -> None:
    result = runner.invoke(app, ["profile", "--help"])
    assert result.exit_code == 0, result.output
    assert "RENTA" in result.output
    assert "residencia fiscal" in result.output
    assert "set" in result.output
    assert "show" in result.output


def test_profile_tax_region_help_lists_values_and_foral_boundary() -> None:
    result = runner.invoke(app, ["profile", "set", "tax-region", "--help"])
    assert result.exit_code == 0, result.output
    assert "andalucia" in result.output
    assert "cataluna" in result.output
    assert "madrid" in result.output
    assert "Pais Vasco" in result.output
    assert "Navarra" in result.output
    assert "--since" in result.output


def test_profile_set_tax_region_persists(tmp_path: Path) -> None:
    env = _env(tmp_path)
    result = runner.invoke(app, ["profile", "set", "tax-region", "andalucia"], env=env)
    assert result.exit_code == 0, result.output
    assert "Andalucía" in result.output
    show = runner.invoke(app, ["profile", "show", "--json"], env=env)
    assert show.exit_code == 0, show.output
    payload = json.loads(show.output)
    assert payload["result"]["ccaa"] == "andalucia"


def test_profile_foral_region_refused(tmp_path: Path) -> None:
    result = runner.invoke(app, ["profile", "set", "tax-region", "pais-vasco"], env=_env(tmp_path))
    assert result.exit_code == 2
    assert "#424" in result.output


def test_profile_output_language_english(tmp_path: Path) -> None:
    env = _env(tmp_path, language="en")
    result = runner.invoke(app, ["profile", "set", "tax-region", "madrid"], env=env)
    assert result.exit_code == 0, result.output
    assert "Tax residence saved" in result.output


def test_profile_show_json_schema_registered_and_valid(tmp_path: Path) -> None:
    assert "profile show" in SCHEMA_REGISTRY
    env = _env(tmp_path)
    runner.invoke(app, ["profile", "set", "tax-region", "cataluna"], env=env)
    result = runner.invoke(app, ["profile", "show", "--json"], env=env)
    payload = json.loads(result.output)
    schema = SCHEMA_REGISTRY["profile show"]
    schema.model_validate(payload["result"])
