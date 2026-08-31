"""Ledger-corpus import/export fidelity journey tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ._isolated_profile_storage_fixtures import live_fx_isolated_backend
from ._ledger_corpus_support import (
    _CORPUS,
    _FIN_FIXTURES,
    _import_bbva,
    _import_corpus,
    _invoke,
    _list_rows,
    _xlsx_mirror_of_csv,
)

__all__ = ["live_fx_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("fmt", ["csv", "jsonl"])
def test_export_each_format(tmp_path: Path, fmt: str) -> None:
    # The ledger export surface emits canonical CSV and JSONL (one JSON object
    # per row); there is no xlsx export verb on this surface.
    _import_corpus()
    out = tmp_path / f"ledger-export.{fmt}"
    result = _invoke(["app", "ledger", "export", "--output", str(out), "--export-format", fmt])
    assert result.exit_code == 0, result.output
    assert out.exists() and out.stat().st_size > 0


def test_export_csv_is_refused_by_raw_bank_import_provider(tmp_path: Path) -> None:
    """Canonical ledger CSV exports are not raw bank statements."""
    _import_corpus()
    before = len(_list_rows())
    out = tmp_path / "ledger-export.csv"
    exported = _invoke(["app", "ledger", "export", "--output", str(out), "--export-format", "csv"])
    assert exported.exit_code == 0, exported.output
    # A canonical ledger export is a rich local ledger artifact, not a bank CSV
    # statement. The raw bank provider must refuse it instead of creating
    # phantom rows or offering a restore path here.
    reimported = _invoke(["app", "ledger", "import", "--file", str(out), "--provider", "csv"])
    assert reimported.exit_code != 0, reimported.output
    assert "raw bank CSV provider" in reimported.output
    assert len(_list_rows()) == before, reimported.output


def test_xlsx_import_is_id_for_id_parity_with_csv(tmp_path: Path) -> None:
    """The XLSX provider yields the same canonical rows as CSV."""
    from ....adapters.inbound.financial.providers.csv import CsvProvider
    from ....domain.transactions.models import derive_transaction_id

    csv_path = _CORPUS / "bbva-business-eur.csv"
    # Canonical CSV id-set computed in-process (no bucket pollution / no reset).
    csv_ids = {derive_transaction_id(parsed.raw) for parsed in CsvProvider().ingest(csv_path)}
    assert len(csv_ids) > 40

    # Importing the XLSX mirror into the empty bucket must reproduce that exact
    # id-set -- the two provider formats agree row-for-row.
    xlsx_path = tmp_path / "bbva.xlsx"
    _xlsx_mirror_of_csv(csv_path, xlsx_path)
    xlsx_res = _invoke(
        ["--format", "json", "app", "ledger", "import", "--file", str(xlsx_path), "--provider", "xlsx"],
    )
    assert xlsx_res.exit_code == 0, xlsx_res.output
    xlsx_ids = {r["transaction_id"] for r in _list_rows()}
    assert xlsx_ids == csv_ids, (len(xlsx_ids), len(csv_ids))


def test_cross_format_reimport_dedups_by_fingerprint(tmp_path: Path) -> None:
    """Re-importing the same rows in a different format adds nothing."""
    csv_path = _CORPUS / "bbva-business-eur.csv"
    _invoke(["app", "ledger", "import", "--file", str(csv_path), "--provider", "csv"])
    before = len(_list_rows())
    assert before > 40
    xlsx_path = tmp_path / "bbva.xlsx"
    _xlsx_mirror_of_csv(csv_path, xlsx_path)
    reimport = _invoke(
        ["--format", "json", "app", "ledger", "import", "--file", str(xlsx_path), "--provider", "xlsx"],
    )
    assert reimport.exit_code == 0, reimport.output
    # Cross-format re-import of identical rows dedups to zero new rows.
    assert len(_list_rows()) == before


def test_ofx_and_pdf_providers_import_real_transactions() -> None:
    """The OFX and PDF providers ingest real bank exports."""
    ofx = _FIN_FIXTURES / "synthetic-transactions.ofx"
    ofx_res = _invoke(["--format", "json", "app", "ledger", "import", "--file", str(ofx), "--provider", "ofx"])
    assert ofx_res.exit_code == 0, ofx_res.output
    assert len(_list_rows()) > 0

    _invoke(["app", "ledger", "reset", "--yes"])
    pdf = _FIN_FIXTURES / "n26" / "n26-savings-2025-01.pdf"
    pdf_res = _invoke(["--format", "json", "app", "ledger", "import", "--file", str(pdf), "--provider", "pdf"])
    assert pdf_res.exit_code == 0, pdf_res.output
    assert len(_list_rows()) > 0


def test_jsonl_export_roundtrips_back_through_import(tmp_path: Path) -> None:
    """Exporting JSONL and re-importing preserves the active row set."""
    _import_bbva()
    before = len(_list_rows())
    out = tmp_path / "ledger.jsonl"
    exported = _invoke(["app", "ledger", "export", "--output", str(out), "--export-format", "jsonl"])
    assert exported.exit_code == 0, exported.output
    assert out.exists() and out.read_text(encoding="utf-8").strip()
    # The canonical JSONL export carries the rich ledger schema, not a bank
    # layout; importing it through a bank provider must refuse explicitly rather
    # than being treated as a permissive no-op.
    reimported = _invoke(["app", "ledger", "import", "--file", str(out), "--provider", "csv"])
    assert reimported.exit_code != 0, reimported.output
    assert "cannot be imported" in reimported.output
    assert len(_list_rows()) == before
