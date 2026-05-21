"""Real-behavior regressions for the ledger-UX defect cluster.

Each test reproduces one operator-facing failure surfaced by the
persona testimonials and pins the corrected behaviour:

- a discoverable, validated ``--category-id`` catalogue;
- a discoverable ``--provider`` value list;
- an explained zero-import result;
- a specific cause behind the previously opaque
  "command input failed validation" refusal on ``ledger add`` and
  ``ledger review --id``.

The tests drive the real Typer app end to end against an isolated
``AEAT_LOCAL_STORAGE_ROOT`` — no mocks, no patched validators.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.domain.categories import SpendingCategory
from aeat.entrypoints.cli import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()

_N26_HEADER = "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"


def _create_profile() -> None:
    created = _RUNNER.invoke(
        app,
        [
            "config", "profile", "create", "tester", "--quiet",
            "--tax-id", "00000001R", "--activity", "freelance",
        ],
    )
    assert created.exit_code == 0, created.output


def _imported_transaction_id(tmp_path: Path) -> str:
    statement = tmp_path / "statement.csv"
    statement.write_text(
        _N26_HEADER + "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
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


# --- M9: discoverable + validated --category-id -----------------------------


def test_categories_command_lists_the_canonical_spending_taxonomy(
    tmp_path: Path,
) -> None:
    """`ledger categories` enumerates every SpendingCategory id."""
    _create_profile()
    result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "categories"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    listed = set(payload["category_ids"])
    expected = {category.value for category in SpendingCategory}
    assert listed == expected
    # Every listed id must belong to a family group, never float free.
    grouped = {
        category_id
        for family in payload["families"]
        for category_id in family["category_ids"]
    }
    assert grouped == expected


def test_classify_rejects_an_invented_category_id(tmp_path: Path) -> None:
    """An id outside the closed taxonomy is refused, not silently kept."""
    _create_profile()
    txn = _imported_transaction_id(tmp_path)
    result = _RUNNER.invoke(
        app,
        [
            "app", "ledger", "classify", "--id", txn,
            "--classification", "BUSINESS", "--category-id", "ventas_actividad",
        ],
    )
    assert result.exit_code != 0
    assert "ventas_actividad" in result.output
    assert "ledger categories" in result.output


def test_classify_accepts_a_canonical_category_id(tmp_path: Path) -> None:
    """A real SpendingCategory id still classifies successfully."""
    _create_profile()
    txn = _imported_transaction_id(tmp_path)
    result = _RUNNER.invoke(
        app,
        [
            "--format", "json", "app", "ledger", "classify", "--id", txn,
            "--classification", "BUSINESS",
            "--category-id", SpendingCategory.MATERIAL_OFICINA.value,
        ],
    )
    assert result.exit_code == 0, result.output
    transaction = json.loads(result.output)["transaction"]
    assert transaction["category_id"] == SpendingCategory.MATERIAL_OFICINA.value


# --- M11: discoverable --provider list --------------------------------------


def test_import_help_lists_recognised_providers() -> None:
    """`import --help` enumerates the accepted --provider values."""
    result = _RUNNER.invoke(app, ["app", "ledger", "import", "--help"])
    assert result.exit_code == 0, result.output
    haystack = " ".join(result.output.split())
    for provider in ("csv", "ofx", "xlsx", "n26"):
        assert provider in haystack


def test_unknown_provider_error_enumerates_known_providers(tmp_path: Path) -> None:
    """An unknown --provider is refused with the recognised set inline."""
    _create_profile()
    statement = tmp_path / "statement.csv"
    statement.write_text(
        _N26_HEADER + "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    result = _RUNNER.invoke(
        app, ["app", "ledger", "import", str(statement), "--provider", "quickbooks"]
    )
    assert result.exit_code != 0
    assert "quickbooks" in result.output
    for provider in ("csv", "ofx", "xlsx", "n26"):
        assert provider in result.output


# --- M12: explained zero-import ---------------------------------------------


def test_import_of_a_headers_only_csv_explains_zero_rows(tmp_path: Path) -> None:
    """A parsed-but-empty CSV explains the zero result, never silently.

    A header-only N26 CSV fails provider validation outright with a
    specific "no data rows" reason. The operator must see that reason
    rather than a bare "imported 0" success line — the silent-success
    path is the defect.
    """
    _create_profile()
    statement = tmp_path / "empty.csv"
    statement.write_text(_N26_HEADER, encoding="utf-8")
    result = _RUNNER.invoke(
        app, ["app", "ledger", "import", str(statement), "--provider", "csv"]
    )
    assert result.exit_code != 0
    assert "no data rows" in result.output.lower()


def test_import_of_a_blank_data_row_csv_emits_a_notice(tmp_path: Path) -> None:
    """A CSV that validates but yields no rows carries an explicit notice.

    A recognised header followed only by an all-whitespace data row
    passes provider validation, parses to zero rows, and previously
    reported a bare "imported 0" with exit 0 — indistinguishable from
    success. The notice line is the fix.
    """
    _create_profile()
    statement = tmp_path / "blank.csv"
    statement.write_text(_N26_HEADER + " , , , , , \n", encoding="utf-8")
    result = _RUNNER.invoke(
        app, ["--format", "json", "app", "ledger", "import", str(statement),
              "--provider", "csv"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["imported"] == 0
    assert "empty_import_notice" in payload
    assert "no data rows" in payload["empty_import_notice"].lower()


def test_reimport_of_existing_rows_explains_the_zero_import(tmp_path: Path) -> None:
    """Re-importing only-duplicate rows reports why nothing was added."""
    _create_profile()
    statement = tmp_path / "statement.csv"
    statement.write_text(
        _N26_HEADER + "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    first = _RUNNER.invoke(
        app, ["app", "ledger", "import", str(statement), "--provider", "csv"]
    )
    assert first.exit_code == 0, first.output
    second = _RUNNER.invoke(
        app, ["--format", "json", "app", "ledger", "import", str(statement),
              "--provider", "csv"],
    )
    assert second.exit_code == 0, second.output
    payload = json.loads(second.output)
    assert payload["imported"] == 0
    assert payload["skipped"] == 1
    assert "empty_import_notice" in payload
    assert "duplicate" in payload["empty_import_notice"].lower()


# --- M8: specific cause behind the opaque add refusal -----------------------


def test_add_with_business_pct_on_a_business_row_surfaces_the_real_cause(
    tmp_path: Path,
) -> None:
    """The illegal --business-pct/--classification pair names the field.

    A non-MIXED classification forbids --business-pct. The refusal must
    name that exact rule rather than the misleading "run config repair".
    """
    _create_profile()
    result = _RUNNER.invoke(
        app,
        [
            "app", "ledger", "add",
            "--date", "2026-04-15", "--amount", "-121.00",
            "--direction", "OUTGOING", "--description", "Office chair",
            "--classification", "BUSINESS", "--business-pct", "1.0",
            "--taxable-base", "100.00", "--iva-rate", "0.21",
            "--iva-amount", "21.00",
        ],
    )
    assert result.exit_code != 0
    assert "business_pct" in result.output
    assert "MIXED" in result.output
    assert "config repair" not in result.output


def test_add_business_row_without_business_pct_succeeds(tmp_path: Path) -> None:
    """The same row minus --business-pct is legal and still works."""
    _create_profile()
    result = _RUNNER.invoke(
        app,
        [
            "--format", "json", "app", "ledger", "add",
            "--date", "2026-04-15", "--amount", "-121.00",
            "--direction", "OUTGOING", "--description", "Office chair",
            "--classification", "BUSINESS",
            "--taxable-base", "100.00", "--iva-rate", "0.21",
            "--iva-amount", "21.00",
        ],
    )
    assert result.exit_code == 0, result.output
    transaction = json.loads(result.output)["transaction"]
    assert transaction["business_classification"] == "BUSINESS"


# --- M10: review --id resolves a short prefix -------------------------------


def test_review_by_short_id_prefix_resolves_the_transaction(
    tmp_path: Path,
) -> None:
    """`review --id <prefix>` resolves the prefix instead of refusing."""
    _create_profile()
    txn = _imported_transaction_id(tmp_path)
    result = _RUNNER.invoke(
        app, ["--format", "json", "app", "ledger", "review", "--id", txn[:8]]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["id"] == txn
    assert "config repair" not in result.output


def test_review_by_full_id_still_resolves_the_transaction(
    tmp_path: Path,
) -> None:
    """`review --id <full>` keeps working after the prefix-resolution fix."""
    _create_profile()
    txn = _imported_transaction_id(tmp_path)
    result = _RUNNER.invoke(
        app, ["--format", "json", "app", "ledger", "review", "--id", txn]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["id"] == txn


# --- ledger view shows the full stored field set ----------------------------


def test_ledger_view_shows_iva_counterparty_and_notes_detail(
    tmp_path: Path,
) -> None:
    """`ledger view` must confirm every stored field, not just id / date /
    amount / description / review-state.

    An operator who entered IVA fields, a counterparty, and notes had no
    way to verify those persisted: the old view rendered five fields and
    dropped the rest. The full stored field set is now shown.
    """
    _create_profile()
    added = _RUNNER.invoke(
        app,
        [
            "--format", "json", "app", "ledger", "add",
            "--date", "2026-04-15", "--amount", "-121.00",
            "--direction", "OUTGOING", "--description", "Office chair",
            "--counterparty", "Muebles SL",
            "--classification", "BUSINESS",
            "--taxable-base", "100.00", "--iva-rate", "0.21",
            "--iva-amount", "21.00", "--notes", "Q2 furniture",
        ],
    )
    assert added.exit_code == 0, added.output
    txn = json.loads(added.output)["transaction_id"]

    viewed = _RUNNER.invoke(app, ["app", "ledger", "view", txn[:8]])
    assert viewed.exit_code == 0, viewed.output
    output = viewed.output
    # The IVA triple the operator entered is visible for confirmation.
    # Decimal values are rendered in their normalized form.
    assert "Taxable base\t100" in output
    assert "IVA rate\t0.21" in output
    assert "IVA amount\t21" in output
    # Counterparty, classification, and notes are visible too.
    assert "Muebles SL" in output
    assert "BUSINESS" in output
    assert "Q2 furniture" in output


def test_ledger_view_json_carries_the_full_transaction(tmp_path: Path) -> None:
    """The JSON payload exposes the typed transaction with every field,
    so the text view and the JSON contract agree."""
    _create_profile()
    added = _RUNNER.invoke(
        app,
        [
            "--format", "json", "app", "ledger", "add",
            "--date", "2026-04-15", "--amount", "-242.00",
            "--direction", "OUTGOING", "--description", "Laptop",
            "--counterparty", "PC Shop SL",
            "--taxable-base", "200.00", "--iva-rate", "0.21",
            "--iva-amount", "42.00",
        ],
    )
    assert added.exit_code == 0, added.output
    txn = json.loads(added.output)["transaction_id"]

    viewed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "view", txn])
    assert viewed.exit_code == 0, viewed.output
    transaction = json.loads(viewed.output)["transaction"]
    assert transaction["counterparty"] == "PC Shop SL"
    # Decimal fields are carried in their normalized display form.
    assert transaction["taxable_base"] == "200"
    assert transaction["iva_rate"] == "0.21"
    assert transaction["iva_amount"] == "42"
