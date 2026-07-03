"""Real-behaviour tests for the ``python -m dev.registry.matrix`` CLI surface."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from ..cli import app

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_cli_report_prints_human_table() -> None:
    """The matrix CLI's sole command prints the fixed-width table with known modelos and a summary.

    Typer collapses a single-command app onto its root verb, so the report
    command is invoked directly rather than via an explicit ``report`` argument.
    """
    result = CliRunner().invoke(app, [])

    assert result.exit_code == 0, result.stdout
    assert "130" in result.stdout
    assert "303" in result.stdout
    assert "modelos:" in result.stdout


def test_cli_report_json_emits_parseable_rows_for_known_modelos() -> None:
    """``--json`` emits a JSON array with real per-modelo capability rows."""
    result = CliRunner().invoke(app, ["--json"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert payload, "expected at least one modelo row"

    by_id = {row["modelo_id"]: row for row in payload}
    assert by_id["130"]["has_fixed_width_export"] is True
    assert by_id["303"]["has_fixed_width_export"] is True
    assert by_id["100"]["has_xml_dictionary_export"] is True
    assert by_id["100"]["has_fixed_width_export"] is False
