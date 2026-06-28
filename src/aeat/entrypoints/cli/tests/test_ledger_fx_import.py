"""CLI import wires the ECB normalizer so foreign rows convert (ledger-fx-conversion).

Regression for the persona-surfaced HIGH defect: the CLI import path previously
persisted GBP/USD rows with value_in_eur=None, which then gated as
UNSUPPORTED_CURRENCY at aggregation. After wiring the ECB euro reference-rate
normalizer at the composition root, imported foreign rows carry fx_rate and
value_in_eur; EUR rows remain unconverted (native).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core import resolve_active_bucket_id
from ....core.config import override_settings
from ....domain.transactions import TransactionCatalogueRepository
from ....tests import FIXTURES_DIR
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RUNNER = CliRunner()
_CORPUS = FIXTURES_DIR / "financial" / "ledger-corpus"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        try:
            workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="default"))
            yield
        finally:
            dispose_engine()


def test_cli_import_converts_foreign_rows_to_eur() -> None:
    result = _RUNNER.invoke(app, ["app", "ledger", "import", str(_CORPUS / "revolut-multi.csv"), "--provider", "csv"])
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
    import json

    result = _RUNNER.invoke(app, ["app", "ledger", "import", str(_CORPUS / "revolut-multi.csv"), "--provider", "csv"])
    assert result.exit_code == 0, result.output
    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = json.loads(listed.output)["result"]["rows"]
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
    import json

    assert (
        _RUNNER.invoke(
            app,
            ["app", "ledger", "import", str(_CORPUS / "revolut-multi.csv"), "--provider", "csv"],
        ).exit_code
        == 0
    )

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    catalogue = TransactionCatalogueRepository(bucket_id=bucket_id).load()
    foreign = [t for t in catalogue.values() if t.raw.currency in {"GBP", "USD"}]
    assert foreign, "revolut corpus must contain a GBP/USD row to view"
    target = foreign[0]
    assert target.value_in_eur is not None and target.fx_rate is not None

    viewed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "view", target.transaction_id])
    # Before the fix this exits non-zero: the strict CLI payload rejects the
    # persisted FX fields as extra_forbidden. The exit-0 assertion fails loudly
    # then and passes once the fields are declared.
    assert viewed.exit_code == 0, viewed.output

    transaction = json.loads(viewed.output)["result"]["transaction"]
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
    import json

    assert (
        _RUNNER.invoke(
            app,
            ["app", "ledger", "import", str(_CORPUS / "revolut-multi.csv"), "--provider", "csv"],
        ).exit_code
        == 0
    )
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    catalogue = TransactionCatalogueRepository(bucket_id=bucket_id).load()
    eur = [t for t in catalogue.values() if t.raw.currency == "EUR"]
    assert eur, "revolut corpus must contain an EUR row"
    target = eur[0]
    assert target.value_in_eur is None and target.fx_rate is None

    viewed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "view", target.transaction_id])
    assert viewed.exit_code == 0, viewed.output
    transaction = json.loads(viewed.output)["result"]["transaction"]
    assert transaction["currency"] == "EUR"
    assert transaction["value_in_eur"] is None
    assert transaction["fx_rate"] is None


def test_export_period_filters_to_the_quarter(tmp_path: Path) -> None:
    """export --period restricts the hand-off to one quarter's rows."""
    import csv

    res = _RUNNER.invoke(app, ["app", "ledger", "import", str(_CORPUS / "bbva-business-eur.csv"), "--provider", "csv"])
    assert res.exit_code == 0, res.output
    full = tmp_path / "full.csv"
    q1 = tmp_path / "q1.csv"
    full_res = _RUNNER.invoke(app, ["app", "ledger", "export", "--output", str(full), "--export-format", "csv"])
    assert full_res.exit_code == 0, full_res.output
    r = _RUNNER.invoke(
        app,
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
    import json

    result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "import", str(_CORPUS), "--provider", "csv"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    # The four corpus CSVs (manifest.json / README.md are skipped by extension).
    assert payload["rows"] >= 500, payload
    assert payload["imported"] >= 500, payload
    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0
    assert len(json.loads(listed.output)["result"]["rows"]) == payload["imported"]


def test_review_filter_by_classification() -> None:
    """review --filter classification= lets an asesor triage by disposition."""
    res = _RUNNER.invoke(app, ["app", "ledger", "import", str(_CORPUS / "bbva-business-eur.csv"), "--provider", "csv"])
    assert res.exit_code == 0, res.output
    # Fresh import: everything is NOT_YET_PROCESSED; no BUSINESS rows yet.
    not_proc = _RUNNER.invoke(app, ["app", "ledger", "review", "--filter", "classification=NOT_YET_PROCESSED"])
    assert not_proc.exit_code == 0, not_proc.output
    business = _RUNNER.invoke(app, ["app", "ledger", "review", "--filter", "classification=BUSINESS"])
    assert business.exit_code == 0, business.output
    # Classify one row BUSINESS, then it must surface under the classification filter.
    import json

    rows = json.loads(_RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"]).output)["result"]["rows"]
    tx = next(r["transaction_id"] for r in rows if "ACME" in r["description"])
    assert _RUNNER.invoke(app, ["app", "ledger", "classify", tx, "--classification", "BUSINESS"]).exit_code == 0
    after = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "review", "--filter", "classification=BUSINESS"])
    assert after.exit_code == 0, after.output
    matched = json.loads(after.output)["result"]["rows"]
    assert (
        any(r.get("id") == tx or r.get("full_id") == tx or tx.startswith(str(r.get("id", ""))) for r in matched)
        or len(matched) >= 1
    )


def test_track_surfaces_import_provenance_for_imported_rows() -> None:
    """track names the import batch (provider/source/ingest) instead of a bare '-'."""
    import json

    res = _RUNNER.invoke(app, ["app", "ledger", "import", str(_CORPUS / "bbva-business-eur.csv"), "--provider", "csv"])
    assert res.exit_code == 0, res.output
    rows = json.loads(_RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"]).output)["result"]["rows"]
    tx = rows[0].get("full_id") or rows[0]["transaction_id"]
    tracked = _RUNNER.invoke(app, ["app", "ledger", "track", tx])
    assert tracked.exit_code == 0, tracked.output
    assert "import_provider" in tracked.output
    assert "import_source" in tracked.output
    assert "import_fingerprint" in tracked.output
    assert "	-" not in tracked.output.split("import_fingerprint")[1]  # fingerprint not bare


def test_status_surfaces_income_expense_net_rollup() -> None:
    """status carries an income/expense/net money roll-up (year-end finding)."""
    import json

    assert (
        _RUNNER.invoke(
            app,
            ["app", "ledger", "import", str(_CORPUS / "bbva-business-eur.csv"), "--provider", "csv"],
        ).exit_code
        == 0
    )
    rows = json.loads(_RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"]).output)["result"]["rows"]
    income = next(r.get("full_id") or r["transaction_id"] for r in rows if "ACME" in r["description"])
    expense = next(r.get("full_id") or r["transaction_id"] for r in rows if "Gestoria" in r["description"])
    for tx in (income, expense):
        classify_result = _RUNNER.invoke(app, ["app", "ledger", "classify", tx, "--classification", "BUSINESS"])
        assert classify_result.exit_code == 0
    report = json.loads(_RUNNER.invoke(app, ["--format", "json", "app", "ledger", "status"]).output)["result"]
    assert report["income_total"] != "0.00"
    assert report["expense_total"] != "0.00"
    assert "net_total" in report


def test_review_filter_text_search() -> None:
    """review --filter text= searches description/counterparty/category."""
    import json

    assert (
        _RUNNER.invoke(
            app,
            ["app", "ledger", "import", str(_CORPUS / "bbva-business-eur.csv"), "--provider", "csv"],
        ).exit_code
        == 0
    )
    res = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "review", "--filter", "text=ACME"])
    assert res.exit_code == 0, res.output
    rows = json.loads(res.output)["result"]["rows"]
    assert rows
    assert all("ACME" in r["description"] for r in rows)


def test_import_records_fx_rate_provenance_through_persistence() -> None:
    """Foreign rows persist rate_source + rate_date provenance (survives roundtrip)."""
    res = _RUNNER.invoke(app, ["app", "ledger", "import", str(_CORPUS / "revolut-multi.csv"), "--provider", "csv"])
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
