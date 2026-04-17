"""Unit tests for the `aeat financial` CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from .. import app as root_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]

_RUNNER = CliRunner()
_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "financial"


def test_financial_ingest_json_stream() -> None:
    """`aeat financial ingest --output-json` should emit JSON lines."""
    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "ingest",
            str(_FIXTURES / "synthetic-transactions.csv"),
            "--provider",
            "auto",
            "--output-json",
        ],
    )
    assert result.exit_code == 0, result.output
    payloads = [json.loads(line) for line in result.stdout.splitlines() if line.strip().startswith("{")]
    assert len(payloads) == 2
    assert payloads[0]["provenance"]["source_format"] == "csv"


def test_financial_ingest_rejects_invalid_source(tmp_path: Path) -> None:
    """The CLI should abort before ingest when validation fails."""
    source = tmp_path / "invalid.csv"
    source.write_text("foo,bar\n1,2\n", encoding="utf-8")
    result = _RUNNER.invoke(root_app, ["financial", "ingest", str(source)])
    assert result.exit_code == 2
    assert "validation error" in result.output.lower()


def test_financial_ingest_reports_ingest_errors(tmp_path: Path) -> None:
    """The CLI should convert ingest-time provider failures into a clean exit."""
    source = tmp_path / "malformed.csv"
    source.write_text(
        "Fecha operación,Importe,Concepto\nNOT-A-DATE,-12.34,Subscription\n",
        encoding="utf-8",
    )
    result = _RUNNER.invoke(root_app, ["financial", "ingest", str(source)])
    assert result.exit_code == 2
    assert "ingest error" in result.output.lower()
