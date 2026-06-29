"""CLI integration tests for schema-localized casillas output."""

from __future__ import annotations

import json

import pytest

from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NO_FORCED_LANGUAGE_ENV: dict[str, str | None] = {"AEAT_OUTPUT_LANGUAGE": None}


def test_casillas_command_default_language_is_spanish() -> None:
    """Invoking casillas without overrides defaults to Spanish labels."""
    result = invoke_cached_cli(
        ["app", "modelo", "casillas", "130"],
        env=_NO_FORCED_LANGUAGE_ENV,
    )
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
    lang: str,
    expected_label_1: str,
    expected_label_2: str,
) -> None:
    """Invoking casillas with `--language` returns localized labels."""
    result = invoke_cached_cli(
        ["--language", lang, "app", "modelo", "casillas", "130"],
        env=_NO_FORCED_LANGUAGE_ENV,
    )
    assert result.exit_code == 0, result.output
    assert expected_label_1 in result.output
    assert expected_label_2 in result.output


def test_casillas_command_explain_option_displays_localized_help() -> None:
    """Invoking casillas with `--explain` includes the help/hint column with translations."""
    result = invoke_cached_cli(
        ["--language", "en", "app", "modelo", "casillas", "130", "--explain"],
        env=_NO_FORCED_LANGUAGE_ENV,
    )
    assert result.exit_code == 0, result.output
    assert "help" in result.output
    assert "Total cumulative business income for the tax year." in result.output
    assert "Total cumulative business expenses for the tax year." in result.output


def test_casillas_json_envelope_carries_localized_attributes() -> None:
    """JSON output for casillas carries raw translation dictionaries in the envelope."""
    result = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "casillas", "130"],
        env=_NO_FORCED_LANGUAGE_ENV,
    )
    assert result.exit_code == 0, result.output

    parsed = json.loads(result.output)
    assert parsed["command"] == "modelo.casillas"

    rows = parsed["result"]["rows"]
    row_01 = next(r for r in rows if r["casilla_id"] == "01")

    assert row_01["localized_labels"]["en"] == "Income"
    assert row_01["localized_labels"]["ca"] == "Ingressos"
    assert row_01["localized_labels"]["hu"] == "Bevételek"

    assert "Total cumulative business income for the tax year." in row_01["localized_help"]["en"]
