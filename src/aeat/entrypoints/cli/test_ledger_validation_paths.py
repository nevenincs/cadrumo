"""Real-CLI tests: ledger verb validation-error paths (S13).

Each verb that wraps command construction in a try/except ValidationError
must surface the pydantic field message through ``_ledger_validation_bad``
rather than letting the generic boundary swallow it as an opaque
"config repair" hint.  One test per verb; each drives a combination of
flags that trips a model_validator rule and asserts the field name or
message fragment appears in stderr/output.

Verbs covered: add, update, allocate, split, classify.
ledger_list and ledger_view do not construct pydantic models from operator
flags and therefore have no ValidationError path to exercise here.
# TODO(S05): add list/view surface assertions once S05 lands.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.entrypoints.cli import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _create_profile_and_import(tmp_path: Path) -> str:
    """Provision a profile with one imported transaction; return transaction_id."""
    created = _RUNNER.invoke(
        app,
        [
            "config", "profile", "create", "tester", "--quiet",
            "--tax-id", "00000001R", "--activity", "freelance",
        ],
    )
    assert created.exit_code == 0, created.output

    statement = tmp_path / "statement.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,-50.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    imported = _RUNNER.invoke(
        app, ["app", "ledger", "import", str(statement), "--provider", "csv"]
    )
    assert imported.exit_code == 0, imported.output

    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    rows = payload if isinstance(payload, list) else payload.get(
        "transactions", payload.get("rows", [])
    )
    assert rows, listed.output
    return rows[0]["transaction_id"]


# ---------------------------------------------------------------------------
# S13.1  ledger add — business_pct set without MIXED classification
# ---------------------------------------------------------------------------


def test_ledger_add_rejects_business_pct_on_non_mixed_classification(tmp_path: Path) -> None:
    """``ledger add`` must surface the field validator message when
    ``--business-pct`` is supplied alongside a non-MIXED classification.

    The ``ManualLedgerTransactionCommand._validate_business_percentage``
    validator raises "business_pct must be None unless classification is
    MIXED".  ``_ledger_validation_bad`` must route this through the CLI
    refusal rather than letting it bubble to the generic boundary."""

    _RUNNER.invoke(
        app,
        [
            "config", "profile", "create", "tester", "--quiet",
            "--tax-id", "00000001R", "--activity", "freelance",
        ],
    )

    result = _RUNNER.invoke(
        app,
        [
            "app", "ledger", "add",
            "--date", "2026-04-15",
            "--amount", "-50.00",
            "--direction", "OUTGOING",
            "--description", "office supplies",
            "--classification", "BUSINESS",
            "--business-pct", "0.75",
        ],
    )

    # CLI boundary converts the ValidationError; exit code must not be 0.
    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "business_pct" in combined or "MIXED" in combined, combined


# ---------------------------------------------------------------------------
# S13.2  ledger update — patch with no fields (empty-patch validator)
# ---------------------------------------------------------------------------


def test_ledger_update_rejects_empty_patch(tmp_path: Path) -> None:
    """``ledger update`` called with only ``--id`` and no mutable options must
    surface the patch validator message "manual ledger patch must carry at
    least one field".

    The ``ManualLedgerTransactionPatch._require_change`` validator fires when
    no option besides the id is supplied.  The CLI must not crash silently."""

    txn_id = _create_profile_and_import(tmp_path)

    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "update", "--id", txn_id],
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "at least one field" in combined or "patch" in combined, combined


# ---------------------------------------------------------------------------
# S13.3  ledger allocate — business_pct out of range for MIXED
# ---------------------------------------------------------------------------


def test_ledger_allocate_rejects_out_of_range_business_pct(tmp_path: Path) -> None:
    """``ledger allocate`` with ``--business-pct 1.5`` exceeds the 0..1 bound.

    The ``ManualLedgerTransactionCommand._validate_business_percentage``
    validator raises "business_pct must be within 0..1 when classification is
    MIXED".  ``_ledger_validation_bad`` must extract and surface this."""

    txn_id = _create_profile_and_import(tmp_path)

    result = _RUNNER.invoke(
        app,
        [
            "app", "ledger", "allocate",
            "--id", txn_id,
            "--business-pct", "1.5",
        ],
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "business_pct" in combined or "0..1" in combined or "within" in combined, combined


# ---------------------------------------------------------------------------
# S13.4  ledger split — blank description on a child slice
# ---------------------------------------------------------------------------


def test_ledger_split_rejects_blank_child_description(tmp_path: Path) -> None:
    """``ledger split`` with a blank ``--child-description`` must surface the
    ``SplitChildCommand`` field validator message.

    The ``SplitChildCommand._trim_description`` validator raises
    "description must not be blank".  ``_ledger_validation_bad`` wraps it
    via the pydantic ``ValidationError`` caught in the split handler."""

    txn_id = _create_profile_and_import(tmp_path)

    result = _RUNNER.invoke(
        app,
        [
            "app", "ledger", "split",
            "--id", txn_id,
            "--yes",
            "--child-amount", "-25.00",
            "--child-description", "   ",          # blank after strip
            "--child-amount", "-25.00",
            "--child-description", "valid slice",
        ],
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "description" in combined or "blank" in combined, combined


# ---------------------------------------------------------------------------
# S13.5  ledger classify — business_pct requires MIXED (pre-pydantic guard)
# ---------------------------------------------------------------------------


def test_ledger_classify_rejects_business_pct_without_mixed_classification(
    tmp_path: Path,
) -> None:
    """``ledger classify`` refuses ``--business-pct`` when classification is
    not MIXED.

    The CLI handler applies an explicit pre-pydantic guard (lines 514-518 of
    ``_ledger.py``) that raises ``_bad(tr(...))`` before constructing the
    patch model.  The refusal must be user-facing prose, not a pydantic
    traceback, and must mention MIXED or business_pct."""

    txn_id = _create_profile_and_import(tmp_path)

    result = _RUNNER.invoke(
        app,
        [
            "app", "ledger", "classify",
            "--id", txn_id,
            "--classification", "BUSINESS",
            "--business-pct", "0.5",
        ],
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    # The guard surfaces a tr() refusal key; the English text contains
    # either "business_pct" or "MIXED".
    assert "business_pct" in combined or "MIXED" in combined or "mixed" in combined, combined
