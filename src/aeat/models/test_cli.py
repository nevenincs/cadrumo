"""CLI smoke tests for the ``aeat modelos`` Typer sub-app."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from ._cli import app

pytestmark = pytest.mark.unit

_runner = CliRunner()


def test_list_text() -> None:
    """``aeat modelos list`` returns exit 0 and mentions modelo 303."""
    result = _runner.invoke(app, ["list"])
    assert result.exit_code == 0, result.output
    assert "303" in result.output


def test_list_json_contains_codes() -> None:
    """``aeat modelos list --json`` emits a JSON array of all entries."""
    result = _runner.invoke(app, ["list", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    codes = {entry["code"] for entry in payload}
    assert "303" in codes
    assert "390" in codes
    assert len(codes) == 20


def test_list_category_filter_iva() -> None:
    """``--category iva --json`` returns only IVA entries."""
    result = _runner.invoke(app, ["list", "--category", "iva", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert all(entry["category"] == "iva" for entry in payload)
    assert any(entry["code"] == "303" for entry in payload)


def test_show_round_trip_via_model_validate_json() -> None:
    """``aeat modelos show 303 --json`` round-trips through ``model_validate_json``."""
    from ._metadata import ModeloMetadata

    result = _runner.invoke(app, ["show", "303", "--json"])
    assert result.exit_code == 0, result.output
    # Strict pydantic v2 models reject list->frozenset coercion in
    # ``model_validate``; the JSON-native entrypoint handles the shape
    # conversions dictated by the JSON schema.
    record = ModeloMetadata.model_validate_json(result.output)
    assert record.code.value == "303"


def test_show_unknown_exits_non_zero() -> None:
    """``aeat modelos show 999`` exits non-zero via Typer BadParameter."""
    result = _runner.invoke(app, ["show", "999"])
    assert result.exit_code != 0


def test_applicable_to_autonomo_ed_solo_contains_303() -> None:
    """``applicable-to autonomo_ed_solo --json`` contains 303."""
    result = _runner.invoke(app, ["applicable-to", "autonomo_ed_solo", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    codes = {entry["code"] for entry in payload}
    assert "303" in codes


def test_year_plan_autonomo_ed_solo_has_obligations() -> None:
    """``year-plan`` for a GENERAL IVA profile prints at least one obligation."""
    result = _runner.invoke(
        app,
        [
            "year-plan",
            "2026",
            "--tax-id",
            "X1234567L",
            "--iva-regime",
            "GENERAL",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert isinstance(payload, list)
    assert len(payload) > 0
