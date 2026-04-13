"""Unit tests for the `aeat financial` CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.cli import app as root_app

_RUNNER = CliRunner()
_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "financial"


@pytest.mark.unit
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


@pytest.mark.unit
def test_financial_ingest_rejects_invalid_source(tmp_path: Path) -> None:
    """The CLI should abort before ingest when validation fails."""
    source = tmp_path / "invalid.csv"
    source.write_text("foo,bar\n1,2\n", encoding="utf-8")
    result = _RUNNER.invoke(root_app, ["financial", "ingest", str(source)])
    assert result.exit_code == 2
    assert "validation error" in result.output.lower()
