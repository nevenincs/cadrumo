"""Real-behavior test: `ledger allocate` derives the classification
from the business proportion.

A 100% allocation is BUSINESS, a 0% allocation is PERSONAL, and a
strictly-partial allocation is MIXED. The verb previously hard-coded
MIXED, silently mislabelling a fully-business expense (CLI testimonial
finding, persona Nuria).
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from ....adapters.persistence.storage.tests.seeded_isolated_backend_fixture import seeded_isolated_backend_fixture
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: Sequence[str], *, env: dict[str, str] | None = None) -> Result:
    return invoke_cached_cli(args, env=env)


def _import_one_transaction() -> None:
    """Import the single CSV row every case allocates."""
    with tempfile.TemporaryDirectory(prefix="allocate-statement-") as directory:
        statement = Path(directory) / "statement.csv"
        statement.write_text(
            "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
            "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
            encoding="utf-8",
        )
        imported = _invoke(["app", "ledger", "import", "--file", str(statement), "--provider", "csv"])
    assert imported.exit_code == 0, imported.output


#: Every case allocates the same imported row of the same profile, and each one
#: rewrites that row's classification, so the world is seeded once and every
#: test gets its own filesystem copy of it rather than a shared one.
_seeded_origin, _isolated_storage = seeded_isolated_backend_fixture(
    seed=_import_one_transaction,
    display_name="tester",
    profile_overrides={
        "identity.tax_id": "00000001R",
        "activities.description": "freelance",
        "taxpayer_type.entity_type": "natural_person",
        "identity.name": "Tester",
        "identity.surnames": "Allocation",
    },
    settings_overrides={"cadrumo_output_language": "en"},
    name="_isolated_storage",
    origin_name="_seeded_origin",
)
__all__ = ["_isolated_storage", "_seeded_origin"]


def _imported_transaction_id() -> str:
    """Return the id of the transaction this test's copy of the world holds."""
    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    assert isinstance(payload, dict), listed.output
    result = payload.get("result", payload)
    assert isinstance(result, dict), listed.output
    rows = result.get("rows", [])
    assert isinstance(rows, list) and rows, listed.output
    first = rows[0]
    assert isinstance(first, dict), listed.output
    transaction_id = first.get("transaction_id")
    assert isinstance(transaction_id, str), listed.output
    return transaction_id


def _allocate(transaction_id: str, business_pct: str) -> dict[str, Any]:
    result = _invoke(
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


def test_allocate_full_business_pct_yields_business() -> None:
    txn = _imported_transaction_id()
    assert _allocate(txn, "1.0")["business_classification"] == "BUSINESS"


def test_allocate_partial_business_pct_yields_mixed() -> None:
    txn = _imported_transaction_id()
    allocated = _allocate(txn, "0.5")
    assert allocated["business_classification"] == "MIXED"
    assert allocated["business_pct"] == "0.5"


def test_allocate_zero_business_pct_yields_personal() -> None:
    txn = _imported_transaction_id()
    assert _allocate(txn, "0")["business_classification"] == "PERSONAL"


def _allocate_raw(transaction_id: str, business_pct: str) -> Result:
    return _invoke(
        [
            "app",
            "ledger",
            "allocate",
            transaction_id,
            "--business-pct",
            business_pct,
        ],
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
    )


def test_allocate_out_of_range_pct_shows_value_and_percent() -> None:
    """An operator who types ``50`` (meaning 50 %) or ``1.5`` sees the
    offending value WITH its percent context, not a bare 'invalid'."""
    txn = _imported_transaction_id()
    result = _allocate_raw(txn, "1.5")
    assert result.exit_code != 0, result.output
    # The offending value and its percent translation both appear.
    assert "1.5" in result.output
    assert "150%" in result.output
    # And the convention is shown so the operator can self-correct.
    assert "0.5 for 50" in result.output


def test_allocate_whole_number_pct_shows_percent_context() -> None:
    """``--business-pct 50`` (a percent typed as a whole number) is out of
    the 0..1 range and is refused with the 5000% context, steering the
    operator to the 0..1 share convention."""
    txn = _imported_transaction_id()
    result = _allocate_raw(txn, "50")
    assert result.exit_code != 0, result.output
    assert "50" in result.output
    assert "5000%" in result.output
