"""Tests for the ``aeat submission check-nif`` Typer command.

Exercises the AEAT check-letter validation paths (DNI, NIE, malformed
input) plus the JSON output contract emitted via
:func:`aeat.entrypoints.cli._schemas.emit_json_success`.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_runner = CliRunner()


def _unwrap_result(output: str):
    """Return the ``result`` payload from a CLI JSON-success envelope."""
    return json.loads(output)["result"]


class TestCheckNifCommand:
    """Behavioural tests for :func:`aeat.entrypoints.cli.submission.check_nif.check_nif_cmd`."""

    def test_valid_nie_passes(self) -> None:
        result = _runner.invoke(app, ["check-nif", "X1234567L"])
        assert result.exit_code == 0, result.stdout
        assert "check-nif OK" in result.stdout
        assert "NIE" in result.stdout

    def test_valid_dni_passes(self) -> None:
        result = _runner.invoke(app, ["check-nif", "12345678Z"])
        assert result.exit_code == 0, result.stdout
        assert "NIF" in result.stdout

    def test_invalid_check_letter_exits_2(self) -> None:
        result = _runner.invoke(app, ["check-nif", "X1234567Z"])
        assert result.exit_code == 2
        assert "INVALID" in result.stdout

    def test_malformed_exits_2(self) -> None:
        result = _runner.invoke(app, ["check-nif", "not-a-nif"])
        assert result.exit_code == 2
        assert "INVALID" in result.stdout

    def test_json_valid(self) -> None:
        result = _runner.invoke(app, ["check-nif", "X1234567L", "--json"])
        assert result.exit_code == 0, result.stdout
        doc = _unwrap_result(result.stdout)
        assert doc["status"] == "valid"
        assert doc["canonical"] == "X1234567L"
        assert doc["kind"] == "NIE"

    def test_json_invalid(self) -> None:
        result = _runner.invoke(app, ["check-nif", "X1234567Z", "--json"])
        assert result.exit_code == 2
        payload = json.loads(result.stderr)
        assert result.stdout == ""
        assert payload["error"]["category"] == "REFUSED"

    def test_normalises_lowercase_input(self) -> None:
        """The validator uppercases input; the canonical form reflects that."""
        result = _runner.invoke(app, ["check-nif", "x1234567l"])
        assert result.exit_code == 0, result.stdout
        assert "X1234567L" in result.stdout
