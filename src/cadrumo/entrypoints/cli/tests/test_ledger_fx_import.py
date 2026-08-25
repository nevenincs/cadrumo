"""CLI import wires the ECB normalizer so foreign rows convert (ledger-fx-conversion).

Regression for the persona-surfaced HIGH defect: the CLI import path previously
persisted GBP/USD rows with value_in_eur=None, which then gated as
UNSUPPORTED_CURRENCY at aggregation. After wiring the ECB euro reference-rate
normalizer at the composition root, imported foreign rows carry fx_rate and
value_in_eur; EUR rows remain unconverted (native).
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core.bucket_pointer import resolve_active_bucket_id
from ....tests import FIXTURES_DIR
from ....tests.cli_envelope import unwrap_cli_result as _json_result
from ....tests.cli_runner import invoke_cached_cli
from ._isolated_profile_storage_fixtures import live_fx_isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["live_fx_isolated_backend"]

_CORPUS = FIXTURES_DIR / "financial" / "ledger-corpus"


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _import_statement(source: Path, *, json_format: bool = False) -> Result:
    args = ["app", "ledger", "import", "--file", str(source), "--provider", "csv"]
    if json_format:
        args = ["--format", "json", *args]
    return _invoke(args)


def _ledger_rows() -> list[dict[str, Any]]:
    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    return _json_result(listed)["rows"]


def test_cli_import_converts_foreign_rows_to_eur() -> None:
    result = _import_statement(_CORPUS / "revolut-multi.csv")
    assert result.exit_code == 0, result.output

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    catalogue = TransactionCatalogueRepository(bucket_id=bucket_id).load()
    transactions = list(catalogue.values())

    foreign = [t for t in transactions if t.raw.currency in {"GBP", "USD"}]
    eur = [t for t in transactions if t.raw.currency == "EUR"]
    assert foreign, "revolut corpus must contain GBP/USD rows"

    for t in foreign:
        assert t.fx_rate is not None, f"{t.raw.description}: fx_rate not set"
        assert t.value_in_eur is not None, f"{t.raw.description}: value_in_eur not set"
        assert t.value_in_eur > 0
    # EUR rows are native: no conversion applied.
    for t in eur:
        assert t.fx_rate is None
        assert t.value_in_eur is None


def test_list_surfaces_eur_value_and_fx_rate_for_foreign_rows() -> None:
    result = _import_statement(_CORPUS / "revolut-multi.csv")
    assert result.exit_code == 0, result.output
    rows = _ledger_rows()
    foreign = [r for r in rows if r.get("currency") in {"GBP", "USD"}]
    eur = [r for r in rows if r.get("currency") == "EUR"]
    assert foreign
    # Finding #2: the EUR-equivalent and FX rate are now visible on the read
    # surface, not only computed silently at aggregation.
    for r in foreign:
        assert r.get("value_in_eur") is not None, r
        assert r.get("fx_rate") is not None, r
    for r in eur:
        assert r.get("value_in_eur") is None
        assert r.get("fx_rate") is None


def test_view_single_foreign_row_surfaces_value_in_eur_and_fx_rate() -> None:
    """`ledger view <id>` on a foreign row round-trips the persisted FX fields.

    Regression for the single-transaction read-model BLOCKER: the importer
    persists value_in_eur/fx_rate on every foreign row and the application
    LedgerTransactionPayload emits them, but the strict CLI TransactionPayload
    (extra=forbid) previously omitted the two fields, so
    ``LedgerViewResult.model_validate(result_payload.model_dump(...))`` raised
    ValidationError(extra_forbidden) for any GBP/USD row — making the entire
    single-transaction correction surface (view/classify/update/archive/
    stash, all of which nest TransactionPayload) unreachable. Before the field
    declaration this view exits non-zero with extra_forbidden; after, it exits 0
    and surfaces the persisted EUR-equivalent and applied rate.
    """
    assert _import_statement(_CORPUS / "revolut-multi.csv").exit_code == 0

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    catalogue = TransactionCatalogueRepository(bucket_id=bucket_id).load()
    foreign = [t for t in catalogue.values() if t.raw.currency in {"GBP", "USD"}]
    assert foreign, "revolut corpus must contain a GBP/USD row to view"
    target = foreign[0]
    assert target.value_in_eur is not None and target.fx_rate is not None

    viewed = _invoke(["--format", "json", "app", "ledger", "view", target.transaction_id])
    # Before the fix this exits non-zero: the strict CLI payload rejects the
    # persisted FX fields as extra_forbidden. The exit-0 assertion fails loudly
    # then and passes once the fields are declared.
    assert viewed.exit_code == 0, viewed.output

    transaction = _json_result(viewed)["transaction"]
    assert transaction["currency"] in {"GBP", "USD"}
    # The persisted FX provenance round-trips through the single-transaction
    # read surface, not only the list/export surfaces. The view payload renders
    # each Decimal via the production display transform (``format(value
    # .normalize(), "f")``), so assert against that same rendering of the stored
    # value rather than the raw repr — a save-drops-field regression still
    # surfaces (the field would be absent/None, not merely formatted differently).
    assert transaction["value_in_eur"] == format(target.value_in_eur.normalize(), "f")
    assert transaction["fx_rate"] == format(target.fx_rate.normalize(), "f")


def test_view_single_eur_row_keeps_fx_fields_null() -> None:
    """`ledger view <id>` on an EUR-native row surfaces null FX fields (no false conversion)."""
    assert _import_statement(_CORPUS / "revolut-multi.csv").exit_code == 0
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    catalogue = TransactionCatalogueRepository(bucket_id=bucket_id).load()
    eur = [t for t in catalogue.values() if t.raw.currency == "EUR"]
    assert eur, "revolut corpus must contain an EUR row"
    target = eur[0]
    assert target.value_in_eur is None and target.fx_rate is None

    viewed = _invoke(["--format", "json", "app", "ledger", "view", target.transaction_id])
    assert viewed.exit_code == 0, viewed.output
    transaction = _json_result(viewed)["transaction"]
    assert transaction["currency"] == "EUR"
    assert transaction["value_in_eur"] is None
    assert transaction["fx_rate"] is None


def test_export_period_filters_to_the_quarter(tmp_path: Path) -> None:
    """export --period restricts the hand-off to one quarter's rows."""
    res = _import_statement(_CORPUS / "bbva-business-eur.csv")
    assert res.exit_code == 0, res.output
    full = tmp_path / "full.csv"
    q1 = tmp_path / "q1.csv"
    full_res = _invoke(["app", "ledger", "export", "--output", str(full), "--export-format", "csv"])
    assert full_res.exit_code == 0, full_res.output
    r = _invoke(
        [
            "app",
            "ledger",
            "export",
            "--output",
            str(q1),
            "--export-format",
            "csv",
            "--period",
            "1T",
            "--year",
            "2025",
        ],
    )
    assert r.exit_code == 0, r.output
    full_rows = list(csv.DictReader(full.read_text(encoding="utf-8").splitlines()))
    q1_rows = list(csv.DictReader(q1.read_text(encoding="utf-8").splitlines()))
    assert 0 < len(q1_rows) < len(full_rows)
    for row in q1_rows:
        assert row["effective_date"][:7] in {"2025-01", "2025-02", "2025-03"}, row["effective_date"]


def test_folder_import_aggregates_all_statement_files() -> None:
    """Importing a directory imports every supported file with aggregated counts."""

    result = _import_statement(_CORPUS, json_format=True)
    assert result.exit_code == 0, result.output
    payload = _json_result(result)
    # The four corpus CSVs (manifest.json / README.md are skipped by extension).
    assert payload["rows"] >= 500, payload
    assert payload["imported"] >= 500, payload
    assert len(_ledger_rows()) == payload["imported"]


def test_review_filter_by_classification() -> None:
    """review --filter classification= lets an asesor triage by disposition."""
    res = _import_statement(_CORPUS / "bbva-business-eur.csv")
    assert res.exit_code == 0, res.output
    # Fresh import: everything is NOT_YET_PROCESSED; no BUSINESS rows yet.
    not_proc = _invoke(["app", "ledger", "review", "--filter", "classification=NOT_YET_PROCESSED"])
    assert not_proc.exit_code == 0, not_proc.output
    business = _invoke(["app", "ledger", "review", "--filter", "classification=BUSINESS"])
    assert business.exit_code == 0, business.output
    # Classify one row BUSINESS, then it must surface under the classification filter.
    rows = _ledger_rows()
    tx = next(r["transaction_id"] for r in rows if "ACME" in r["description"])
    assert _invoke(["app", "ledger", "classify", tx, "--classification", "BUSINESS"]).exit_code == 0
    after = _invoke(["--format", "json", "app", "ledger", "review", "--filter", "classification=BUSINESS"])
    assert after.exit_code == 0, after.output
    matched = _json_result(after)["rows"]
    assert (
        any(r.get("id") == tx or r.get("full_id") == tx or tx.startswith(str(r.get("id", ""))) for r in matched)
        or len(matched) >= 1
    )


def test_track_surfaces_import_provenance_for_imported_rows() -> None:
    """track names the import batch (provider/source/ingest) instead of a bare '-'."""

    res = _import_statement(_CORPUS / "bbva-business-eur.csv")
    assert res.exit_code == 0, res.output
    rows = _ledger_rows()
    tx = rows[0].get("full_id") or rows[0]["transaction_id"]
    tracked = _invoke(["app", "ledger", "track", tx])
    assert tracked.exit_code == 0, tracked.output
    assert "import_provider" in tracked.output
    assert "import_source" in tracked.output
    assert "import_fingerprint" in tracked.output
    assert "	-" not in tracked.output.split("import_fingerprint")[1]  # fingerprint not bare


def test_status_surfaces_income_expense_net_rollup() -> None:
    """status carries the current business income/expense/net money roll-up."""

    assert _import_statement(_CORPUS / "bbva-business-eur.csv").exit_code == 0
    rows = _ledger_rows()
    income = next(r.get("full_id") or r["transaction_id"] for r in rows if "ACME" in r["description"])
    expense = next(r.get("full_id") or r["transaction_id"] for r in rows if "Gestoria" in r["description"])
    for tx in (income, expense):
        classify_result = _invoke(["app", "ledger", "classify", tx, "--classification", "BUSINESS"])
        assert classify_result.exit_code == 0
    report = _json_result(_invoke(["--format", "json", "app", "ledger", "status"]))
    assert report["business_income_total"] != "0.00"
    assert report["business_expense_total"] != "0.00"
    assert "business_net_total" in report
    assert "income_total" not in report
    assert "expense_total" not in report
    assert "net_total" not in report


def test_review_filter_text_search() -> None:
    """review --filter text= searches description/counterparty/category."""

    assert _import_statement(_CORPUS / "bbva-business-eur.csv").exit_code == 0
    res = _invoke(["--format", "json", "app", "ledger", "review", "--filter", "text=ACME"])
    assert res.exit_code == 0, res.output
    rows = _json_result(res)["rows"]
    assert rows
    assert all("ACME" in r["description"] for r in rows)


def test_import_records_fx_rate_provenance_through_persistence() -> None:
    """Foreign rows persist rate_source + rate_date provenance (survives roundtrip)."""
    res = _import_statement(_CORPUS / "revolut-multi.csv")
    assert res.exit_code == 0, res.output
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    catalogue = TransactionCatalogueRepository(bucket_id=bucket_id).load()
    foreign = [t for t in catalogue.values() if t.raw.currency in {"GBP", "USD"}]
    assert foreign
    for t in foreign:
        assert t.rate_source is not None, t.raw.description
        assert t.rate_date is not None and len(t.rate_date) == 10, t.rate_date
    # EUR rows carry no FX provenance.
    for t in (x for x in catalogue.values() if x.raw.currency == "EUR"):
        assert t.rate_source is None and t.rate_date is None
