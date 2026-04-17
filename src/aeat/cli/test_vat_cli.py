"""Unit tests for the ``aeat vat`` CLI sub-app."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from . import app


@pytest.mark.unit
def test_vat_categories_list() -> None:
    """`aeat vat categories list` prints every category with exit 0."""
    runner = CliRunner()
    result = runner.invoke(app, ["vat", "categories", "list"])
    assert result.exit_code == 0, result.output
    assert "domestic_general_21" in result.output
    assert "intra_community_supply" in result.output
    assert "17 category(ies)" in result.output


@pytest.mark.unit
def test_vat_rates_list_filtered_by_spain() -> None:
    """`aeat vat rates list --member-state es` shows the ES rates."""
    runner = CliRunner()
    result = runner.invoke(app, ["vat", "rates", "list", "--member-state", "es"])
    assert result.exit_code == 0, result.output
    assert "21" in result.output
    assert "es" in result.output


@pytest.mark.unit
def test_vat_show_domestic_general_21() -> None:
    """`aeat vat show` surfaces the DOMESTIC_GENERAL_21 regulation."""
    runner = CliRunner()
    result = runner.invoke(app, ["vat", "show", "domestic_general_21"])
    assert result.exit_code == 0, result.output
    assert "Art. 90.Uno" in result.output
    assert "Operación interior" in result.output or "domestic_general_21" in result.output


@pytest.mark.unit
def test_vat_rule_includes_canonical_citation() -> None:
    """`aeat vat rule` appends the `cite()` canonical citation line."""
    runner = CliRunner()
    result = runner.invoke(app, ["vat", "rule", "domestic_general_21"])
    assert result.exit_code == 0, result.output
    assert "canonical citation:" in result.output
    assert "Ley 37/1992" in result.output


@pytest.mark.unit
def test_vat_verify_exits_zero_on_shipped_catalogue() -> None:
    """`aeat vat verify` reports a clean shipped catalogue."""
    runner = CliRunner()
    result = runner.invoke(app, ["vat", "verify"])
    assert result.exit_code == 0, result.output
    assert "verify clean" in result.output


@pytest.mark.unit
def test_vat_show_unknown_category_exits_nonzero() -> None:
    """`aeat vat show` rejects an unknown category."""
    runner = CliRunner()
    result = runner.invoke(app, ["vat", "show", "not_a_category"])
    assert result.exit_code != 0
