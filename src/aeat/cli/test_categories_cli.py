"""CLI tests for the AEAT categories command group."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from . import app

runner = CliRunner()


@pytest.mark.unit
def test_categories_list_prints_known_category() -> None:
    """The list subcommand must emit category metadata."""

    result = runner.invoke(app, ["categories", "list"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert any(item["category"] == "cuotas_autonomos_ss" for item in payload)
    assert any(item["proportionality_kind"] == "full_deductible" for item in payload)


@pytest.mark.unit
def test_categories_show_prints_citations_and_mappings() -> None:
    """The show subcommand must render the explainable profile payload."""

    result = runner.invoke(app, ["categories", "show", "cuotas_autonomos_ss"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["category"] == "cuotas_autonomos_ss"
    assert payload["profile"]["casilla_mappings"][0]["casilla_code"] == "01"
    assert payload["profile"]["proportionality"]["citations"]


@pytest.mark.unit
def test_categories_casillas_filters_by_modelo() -> None:
    """The casillas subcommand must only show mappings for the requested modelo."""

    result = runner.invoke(app, ["categories", "casillas", "MODELO_130"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload
    assert all(mapping["modelo"] == "MODELO_130" for item in payload for mapping in item["mappings"])
