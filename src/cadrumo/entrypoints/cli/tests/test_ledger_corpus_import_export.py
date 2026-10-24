"""Ledger-corpus import/export fidelity journey tests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from ...tests.ledger_corpus_support import (
    FINANCIAL_FIXTURE_ROOT,
    LEDGER_CORPUS_ROOT,
    import_bbva_corpus_account,
    import_ledger_corpus,
    invoke_corpus_cli,
    write_corpus_xlsx_mirror,
)
from .ledger_cli import list_ledger_rows_via_cli as _list_rows
from .profile_world_fixtures import recorded_fx_isolated_backend

__all__ = ["recorded_fx_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("fmt", ["csv", "jsonl"])
def test_export_each_format(tmp_path: Path, fmt: str, invoke_cli: Callable[..., Result]) -> None:
    # The ledger export surface emits canonical CSV and JSONL (one JSON object
    # per row); there is no xlsx export verb on this surface.
    import_ledger_corpus(invoke_cli=invoke_cli)
    out = tmp_path / f"ledger-export.{fmt}"
    result = invoke_corpus_cli(
        ["app", "ledger", "export", "--output", str(out), "--export-format", fmt], invoke_cli=invoke_cli
    )
    assert result.exit_code == 0, result.output
    assert out.exists() and out.stat().st_size > 0


def test_export_csv_is_refused_by_raw_bank_import_provider(tmp_path: Path, invoke_cli: Callable[..., Result]) -> None:
    """Canonical ledger CSV exports are not raw bank statements."""
    import_ledger_corpus(invoke_cli=invoke_cli)
    before = len(_list_rows())
    out = tmp_path / "ledger-export.csv"
    exported = invoke_corpus_cli(
        ["app", "ledger", "export", "--output", str(out), "--export-format", "csv"], invoke_cli=invoke_cli
    )
    assert exported.exit_code == 0, exported.output
    # A canonical ledger export is a rich local ledger artifact, not a bank CSV
    # statement. The raw bank provider must refuse it instead of creating
    # phantom rows or offering a restore path here.
    reimported = invoke_corpus_cli(
        ["--format", "json", "app", "ledger", "import", "--file", str(out), "--provider", "csv"], invoke_cli=invoke_cli
    )
    assert reimported.exit_code != 0, reimported.output
    assert json.loads(reimported.output)["error"]["code"] == "ERROR_TRANSACTION_VALIDATION", reimported.output
    assert len(_list_rows()) == before, reimported.output


def test_xlsx_import_is_id_for_id_parity_with_csv(tmp_path: Path, invoke_cli: Callable[..., Result]) -> None:
    """The XLSX provider yields the same canonical rows as CSV."""
    from ....adapters.inbound.financial.providers.csv import CsvProvider
    from ....domain.transactions.models import derive_transaction_id

    csv_path = LEDGER_CORPUS_ROOT / "bbva-business-eur.csv"
    # Canonical CSV id-set computed in-process (no bucket pollution / no reset).
    csv_ids = {derive_transaction_id(parsed.raw) for parsed in CsvProvider().ingest(csv_path)}
    assert len(csv_ids) > 40

    # Importing the XLSX mirror into the empty bucket must reproduce that exact
    # id-set -- the two provider formats agree row-for-row.
    xlsx_path = tmp_path / "bbva.xlsx"
    write_corpus_xlsx_mirror(csv_path, xlsx_path)
    xlsx_res = invoke_corpus_cli(
        ["--format", "json", "app", "ledger", "import", "--file", str(xlsx_path), "--provider", "xlsx"],
        invoke_cli=invoke_cli,
    )
    assert xlsx_res.exit_code == 0, xlsx_res.output
    xlsx_ids = {r["transaction_id"] for r in _list_rows()}
    assert xlsx_ids == csv_ids, (len(xlsx_ids), len(csv_ids))


def test_cross_format_reimport_dedups_by_fingerprint(tmp_path: Path, invoke_cli: Callable[..., Result]) -> None:
    """Re-importing the same rows in a different format adds nothing."""
    csv_path = LEDGER_CORPUS_ROOT / "bbva-business-eur.csv"
    invoke_corpus_cli(["app", "ledger", "import", "--file", str(csv_path), "--provider", "csv"], invoke_cli=invoke_cli)
    before = len(_list_rows())
    assert before > 40
    xlsx_path = tmp_path / "bbva.xlsx"
    write_corpus_xlsx_mirror(csv_path, xlsx_path)
    reimport = invoke_corpus_cli(
        ["--format", "json", "app", "ledger", "import", "--file", str(xlsx_path), "--provider", "xlsx"],
        invoke_cli=invoke_cli,
    )
    assert reimport.exit_code == 0, reimport.output
    # Cross-format re-import of identical rows dedups to zero new rows.
    assert len(_list_rows()) == before


def test_ofx_provider_imports_real_transactions(invoke_cli: Callable[..., Result]) -> None:
    """The OFX provider ingests a real bank export."""
    ofx = FINANCIAL_FIXTURE_ROOT / "synthetic-transactions.ofx"
    ofx_res = invoke_corpus_cli(
        ["--format", "json", "app", "ledger", "import", "--file", str(ofx), "--provider", "ofx"],
        invoke_cli=invoke_cli,
    )
    assert ofx_res.exit_code == 0, ofx_res.output
    assert len(_list_rows()) > 0


def test_the_retired_bank_named_pdf_token_is_refused(invoke_cli: Callable[..., Result]) -> None:
    """No provider token names a bank; the former bank-named PDF token imports nothing."""
    pdf = FINANCIAL_FIXTURE_ROOT / "n26" / "n26-savings-2025-01.pdf"
    refused = invoke_corpus_cli(
        ["--format", "json", "app", "ledger", "import", "--file", str(pdf), "--provider", "pdf-n26"],
        invoke_cli=invoke_cli,
    )
    assert refused.exit_code != 0
    assert len(_list_rows()) == 0


def test_jsonl_export_roundtrips_back_through_import(tmp_path: Path, invoke_cli: Callable[..., Result]) -> None:
    """Exporting JSONL and re-importing preserves the active row set."""
    import_bbva_corpus_account(invoke_cli=invoke_cli)
    before = len(_list_rows())
    out = tmp_path / "ledger.jsonl"
    exported = invoke_corpus_cli(
        ["app", "ledger", "export", "--output", str(out), "--export-format", "jsonl"], invoke_cli=invoke_cli
    )
    assert exported.exit_code == 0, exported.output
    assert out.exists() and out.read_text(encoding="utf-8").strip()
    # The canonical JSONL export carries the rich ledger schema, not a bank
    # layout; importing it through a bank provider must refuse explicitly rather
    # than being treated as a permissive no-op.
    reimported = invoke_corpus_cli(
        ["--format", "json", "app", "ledger", "import", "--file", str(out), "--provider", "csv"], invoke_cli=invoke_cli
    )
    assert reimported.exit_code != 0, reimported.output
    assert json.loads(reimported.output)["error"]["code"] == "ERROR_TRANSACTION_VALIDATION", reimported.output
    assert len(_list_rows()) == before


def test_jsonl_export_rows_match_ledger_readback_and_digest(tmp_path: Path, invoke_cli: Callable[..., Result]) -> None:
    """The exported bytes retain the canonical ledger meaning and row identity."""
    import_bbva_corpus_account(invoke_cli=invoke_cli)
    readback = {str(row["transaction_id"]): row for row in _list_rows()}
    assert len(readback) > 40

    out = tmp_path / "canonical-ledger.jsonl"
    result = invoke_corpus_cli(
        ["--format", "json", "app", "ledger", "export", "--output", str(out), "--export-format", "jsonl"],
        invoke_cli=invoke_cli,
    )
    assert result.exit_code == 0, result.output
    document = json.loads(result.output)
    metadata = document.get("result", document)
    payload = out.read_bytes()
    exported_rows = [json.loads(line) for line in payload.decode("utf-8").splitlines()]

    assert metadata["row_count"] == len(exported_rows) == len(readback)
    assert metadata["sha256"] == hashlib.sha256(payload).hexdigest()
    assert {row["transaction_id"] for row in exported_rows} == set(readback)
    for exported in exported_rows:
        source = readback[exported["transaction_id"]]
        assert exported["bucket_id"]
        assert exported["booked_date"] == source["booked_date"]
        assert exported["effective_date"] == source["date"]
        assert Decimal(exported["amount"]) == Decimal(source["amount"])
        assert exported["currency"] == source["currency"]
        assert exported["direction"] == source["direction"]
        assert exported["invoice_id"] == (source["invoice_id"] or "")
        assert exported["description"] == source["description"]
        assert exported["business_classification"] == source["business_classification"]
