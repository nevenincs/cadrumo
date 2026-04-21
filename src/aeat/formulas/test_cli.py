"""Tests for the ``aeat formulas`` Typer subcommand surface."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from ._cli import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.unit
def test_list_subcommand(runner: CliRunner) -> None:
    """``aeat formulas list`` emits the registered rulesets as JSON.

    Wave 2 (#183) added two Modelo 303 rulesets alongside the
    Modelo 130 pair.
    """
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    ids = sorted(row["ruleset_id"] for row in payload)
    assert ids == [
        "modelo_100.summary.2025",
        "modelo_130.2024",
        "modelo_130.2025",
        "modelo_303.2024",
        "modelo_303.2025",
    ]


@pytest.mark.unit
def test_show_subcommand(runner: CliRunner) -> None:
    """``aeat formulas show`` emits the full ruleset JSON."""
    result = runner.invoke(app, ["show", "modelo_130.2024"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ruleset_id"] == "modelo_130.2024"
    assert len(payload["casillas"]) == 19


@pytest.mark.unit
def test_show_unknown_ruleset_errors(runner: CliRunner) -> None:
    """Unknown ruleset ids return a non-zero exit code."""
    result = runner.invoke(app, ["show", "does.not.exist"])
    assert result.exit_code != 0


@pytest.mark.unit
def test_compute_subcommand(runner: CliRunner) -> None:
    """``aeat formulas compute`` runs the forward engine."""
    result = runner.invoke(
        app,
        [
            "compute",
            "--modelo",
            "MODELO_130",
            "--period",
            "2024Q2",
            "-i",
            "01=12000",
            "-i",
            "02=3500",
            "-i",
            "06=500",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    entry_by_casilla = {row["casilla_id"]: row for row in payload["entries"]}
    assert entry_by_casilla["03"]["value"] == "8500.00"
    assert entry_by_casilla["04"]["value"] == "1700.00"


@pytest.mark.unit
def test_audit_subcommand_clean(runner: CliRunner) -> None:
    """``aeat formulas audit`` returns 0 when user values match."""
    result = runner.invoke(
        app,
        [
            "audit",
            "--modelo",
            "MODELO_130",
            "--period",
            "2024Q2",
            "-p",
            "01=12000",
            "-p",
            "02=3500",
            "-p",
            "03=8500.00",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["discrepancies"] == []


@pytest.mark.unit
def test_audit_subcommand_strict_exits_non_zero_on_discrepancy(runner: CliRunner) -> None:
    """``aeat formulas audit --strict`` exits 3 on discrepancy."""
    result = runner.invoke(
        app,
        [
            "audit",
            "--modelo",
            "MODELO_130",
            "--period",
            "2024Q2",
            "--strict",
            "-p",
            "01=12000",
            "-p",
            "02=3500",
            "-p",
            "03=1",
        ],
    )
    assert result.exit_code == 3


@pytest.mark.unit
def test_compute_invalid_modelo(runner: CliRunner) -> None:
    """Unknown modelo codes fail with a bad-parameter error."""
    result = runner.invoke(
        app,
        [
            "compute",
            "--modelo",
            "NOT_A_MODEL",
            "--period",
            "2024Q2",
        ],
    )
    assert result.exit_code != 0


@pytest.mark.unit
def test_compute_invalid_period(runner: CliRunner) -> None:
    """Malformed periods fail parsing."""
    result = runner.invoke(
        app,
        [
            "compute",
            "--modelo",
            "MODELO_130",
            "--period",
            "20xxQ2",
        ],
    )
    assert result.exit_code != 0
