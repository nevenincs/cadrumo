"""CLI integration tests for schema-localized casillas output."""

from __future__ import annotations

import json
from typing import cast

import click
import pytest
from click.testing import CliRunner
from typer.main import get_command

from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _no_force_english(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop any test-suite-wide default env override to let flags control i18n."""
    monkeypatch.delenv("AEAT_OUTPUT_LANGUAGE", raising=False)


def test_casillas_command_default_language_is_spanish(cli_runner: CliRunner) -> None:
    """Invoking casillas without overrides defaults to Spanish labels."""
    cmd = cast(click.Command, get_command(app))
    result = cli_runner.invoke(cmd, ["app", "modelo", "casillas", "130"])
    assert result.exit_code == 0, result.output
    # Default Spanish labels from TOML registry
    assert "Ingresos" in result.output
    assert "Gastos" in result.output


@pytest.mark.parametrize(
    ("lang", "expected_label_1", "expected_label_2"),
    [
        ("en", "Income", "Expenses"),
        ("ca", "Ingressos", "Despeses"),
        ("hu", "Bevételek", "Kiadások"),
    ],
)
def test_casillas_command_respects_language_flag(
    cli_runner: CliRunner,
    lang: str,
    expected_label_1: str,
    expected_label_2: str,
) -> None:
    """Invoking casillas with `--language` returns localized labels."""
    cmd = cast(click.Command, get_command(app))
    result = cli_runner.invoke(cmd, ["--language", lang, "app", "modelo", "casillas", "130"])
    assert result.exit_code == 0, result.output
    assert expected_label_1 in result.output
    assert expected_label_2 in result.output


def test_casillas_command_explain_option_displays_localized_help(cli_runner: CliRunner) -> None:
    """Invoking casillas with `--explain` includes the help/hint column with translations."""
    cmd = cast(click.Command, get_command(app))
    result = cli_runner.invoke(cmd, ["--language", "en", "app", "modelo", "casillas", "130", "--explain"])
    assert result.exit_code == 0, result.output
    assert "help" in result.output
    assert "Total cumulative business income for the tax year." in result.output
    assert "Total cumulative business expenses for the tax year." in result.output


def test_casillas_json_envelope_carries_localized_attributes(cli_runner: CliRunner) -> None:
    """JSON output for casillas carries raw translation dictionaries in the envelope."""
    cmd = cast(click.Command, get_command(app))
    result = cli_runner.invoke(cmd, ["--format", "json", "app", "modelo", "casillas", "130"])
    assert result.exit_code == 0, result.output

    parsed = json.loads(result.output)
    assert parsed["command"] == "modelo.casillas"

    rows = parsed["result"]["rows"]
    row_01 = next(r for r in rows if r["casilla_id"] == "01")

    assert row_01["localized_labels"]["en"] == "Income"
    assert row_01["localized_labels"]["ca"] == "Ingressos"
    assert row_01["localized_labels"]["hu"] == "Bevételek"

    assert "Total cumulative business income for the tax year." in row_01["localized_help"]["en"]
