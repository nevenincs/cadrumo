"""CLI tests for ``aeat profile`` tax-residence commands.

Exercises the Typer surface in :mod:`aeat.entrypoints.cli.profile`:
help text, set/show/clear round-trips, foral-region refusal and
JSON-schema registration.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from .. import SCHEMA_REGISTRY, app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

runner = CliRunner()

# Rich wraps styled CLI help text with ANSI escape codes. On narrow
# terminals (CI runners, ~80 cols) it can inject styling between the
# characters of a flag (e.g. ``--since`` becomes
# ``-\x1b[0m\x1b[1;36m-since``), so plain substring matches on the raw
# ``result.output`` miss flags that are visibly present.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Return ``text`` with ANSI styling codes stripped."""

    return _ANSI_RE.sub("", text)


def _env(tmp_path: Path, *, language: str = "es") -> dict[str, str]:
    """Build the env dict that pins the profile to ``tmp_path`` and a language."""
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
    plain = _strip_ansi(result.output)
    assert "RENTA" in plain
    assert "residencia fiscal" in plain
    assert "set" in plain
    assert "show" in plain


def test_profile_tax_region_help_lists_values_and_foral_boundary() -> None:
    result = runner.invoke(app, ["profile", "set", "tax-region", "--help"])
    assert result.exit_code == 0, result.output
    plain = _strip_ansi(result.output)
    assert "andalucia" in plain
    assert "cataluna" in plain
    assert "madrid" in plain
    assert "Pais Vasco" in plain
    assert "Navarra" in plain
    assert "--since" in plain


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
