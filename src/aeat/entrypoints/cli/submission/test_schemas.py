"""Tests for ``aeat submission schemas`` (EPIC #305)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_runner = CliRunner()


def _unwrap_result(output: str):
    return json.loads(output)["result"]


class TestSchemasCommand:
    def test_schemas_lists_all_four_registered_modelos(self) -> None:
        result = _runner.invoke(app, ["schemas"])
        assert result.exit_code == 0, result.stdout
        # Registry ships 130 2024, 130 2025, 303 2024, 303 2025.
        assert "130" in result.stdout
        assert "303" in result.stdout
        assert "2024" in result.stdout
        assert "2025" in result.stdout
        # Registered-count banner.
        assert "4 schema(s) registered" in result.stdout

    def test_schemas_json_shape(self) -> None:
        result = _runner.invoke(app, ["schemas", "--json"])
        assert result.exit_code == 0, result.stdout
        rows = _unwrap_result(result.stdout)
        assert isinstance(rows, list)
        assert len(rows) == 4
        by_key = {(r["modelo"], r["ejercicio"]): r for r in rows}
        # Modelo 130 is a single-record schema; 878 + 0 envelope-extras.
        assert by_key[("130", "2024")]["kind"] == "record"
        assert by_key[("130", "2024")]["bytes"] == 878
        assert by_key[("130", "2024")]["encoding"] == "cp1252"
        # Modelo 303 is an 8-segment envelope totalling 7994 bytes.
        assert by_key[("303", "2024")]["kind"] == "envelope"
        assert by_key[("303", "2024")]["bytes"] == 7994
        assert by_key[("303", "2024")]["encoding"] == "iso-8859-1"
        # Required-header counts are modelo-specific — just confirm non-zero.
        assert by_key[("130", "2024")]["required_header_fields"] >= 6
        assert by_key[("303", "2024")]["required_header_fields"] >= 11

    def test_schemas_json_is_sorted_deterministically(self) -> None:
        """JSON output must be stable across runs (no dict-insert-order surprises)."""
        first = _unwrap_result(_runner.invoke(app, ["schemas", "--json"]).stdout)
        second = _unwrap_result(_runner.invoke(app, ["schemas", "--json"]).stdout)
        assert first == second

    def test_schemas_130_and_303_clone_parity(self) -> None:
        """2024 and 2025 clones must carry identical bytes + encoding + kind."""
        rows = _unwrap_result(_runner.invoke(app, ["schemas", "--json"]).stdout)
        by_key = {(r["modelo"], r["ejercicio"]): r for r in rows}
        for modelo in ("130", "303"):
            a, b = by_key[(modelo, "2024")], by_key[(modelo, "2025")]
            assert a["kind"] == b["kind"]
            assert a["bytes"] == b["bytes"]
            assert a["encoding"] == b["encoding"]
