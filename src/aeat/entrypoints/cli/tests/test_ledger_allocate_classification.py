"""Real-behavior test: `ledger allocate` derives the classification
from the business proportion.

A 100% allocation is BUSINESS, a 0% allocation is PERSONAL, and a
strictly-partial allocation is MIXED. The verb previously hard-coded
MIXED, silently mislabelling a fully-business expense (CLI testimonial
finding, persona Nuria).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RUNNER = CliRunner()


def _imported_transaction_id(tmp_path: Path) -> str:
    """Create a profile, import one CSV transaction, return its id."""

    created = _RUNNER.invoke(
        app,
        [
            "config",
            "profile",
            "create",
            "tester",
            "--quiet",
            "--tax-id",
            "00000001R",
            "--activity",
            "freelance",
        ],
    )
    assert created.exit_code == 0, created.output

    statement = tmp_path / "statement.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    imported = _RUNNER.invoke(app, ["app", "ledger", "import", str(statement), "--provider", "csv"])
    assert imported.exit_code == 0, imported.output

    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    rows = payload.get("result", payload).get("rows", [])
    assert rows, listed.output
    return rows[0]["transaction_id"]


def _allocate(transaction_id: str, business_pct: str) -> dict[str, Any]:
    result = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "allocate",
            transaction_id,
            "--business-pct",
            business_pct,
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["result"]["transaction"]


def test_allocate_full_business_pct_yields_business(tmp_path: Path) -> None:
    txn = _imported_transaction_id(tmp_path)
    assert _allocate(txn, "1.0")["business_classification"] == "BUSINESS"


def test_allocate_partial_business_pct_yields_mixed(tmp_path: Path) -> None:
    txn = _imported_transaction_id(tmp_path)
    allocated = _allocate(txn, "0.5")
    assert allocated["business_classification"] == "MIXED"
    assert allocated["business_pct"] == "0.5"


def test_allocate_zero_business_pct_yields_personal(tmp_path: Path) -> None:
    txn = _imported_transaction_id(tmp_path)
    assert _allocate(txn, "0")["business_classification"] == "PERSONAL"


def _allocate_raw(transaction_id: str, business_pct: str):
    return _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "allocate",
            transaction_id,
            "--business-pct",
            business_pct,
        ],
        env={"AEAT_OUTPUT_LANGUAGE": "en"},
    )


def test_allocate_out_of_range_pct_shows_value_and_percent(tmp_path: Path) -> None:
    """An operator who types ``50`` (meaning 50 %) or ``1.5`` sees the
    offending value WITH its percent context, not a bare 'invalid'."""
    txn = _imported_transaction_id(tmp_path)
    result = _allocate_raw(txn, "1.5")
    assert result.exit_code != 0, result.output
    # The offending value and its percent translation both appear.
    assert "1.5" in result.output
    assert "150%" in result.output
    # And the convention is shown so the operator can self-correct.
    assert "0.5 for 50" in result.output


def test_allocate_whole_number_pct_shows_percent_context(tmp_path: Path) -> None:
    """``--business-pct 50`` (a percent typed as a whole number) is out of
    the 0..1 range and is refused with the 5000% context, steering the
    operator to the 0..1 share convention."""
    txn = _imported_transaction_id(tmp_path)
    result = _allocate_raw(txn, "50")
    assert result.exit_code != 0, result.output
    assert "50" in result.output
    assert "5000%" in result.output
