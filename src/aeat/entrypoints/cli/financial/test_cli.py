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


def test_financial_ingest_json_stream_for_n26_pdf() -> None:
    """`aeat financial ingest --output-json` should auto-detect N26 PDFs."""
    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "ingest",
            str(_FIXTURES / "n26" / "n26-savings-2025-01.pdf"),
            "--provider",
            "auto",
            "--output-json",
        ],
    )
    assert result.exit_code == 0, result.output
    payloads = [json.loads(line) for line in result.stdout.splitlines() if line.strip().startswith("{")]
    assert len(payloads) == 4
    assert payloads[0]["provenance"]["source_format"] == "pdf"


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


# ── #216 Kent-moment integration tests ───────────────────────────────


def test_financial_ingest_persist_kent_moment(tmp_path: Path) -> None:
    """The Kent moment: aeat financial ingest --persist persists to the catalogue."""

    from ....adapters.persistence.storage import (
        EncryptedBlobStore,
        EphemeralMasterKeyProvider,
        SecretStore,
        override_master_key_provider,
        override_secret_store,
    )

    provider = EphemeralMasterKeyProvider()
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs",
        master_key_provider=provider,
    )
    secret_store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_master_key_provider(provider)
    override_secret_store(secret_store)
    catalogue_dir = tmp_path / "catalogue"
    try:
        result = _RUNNER.invoke(
            root_app,
            [
                "financial",
                "ingest",
                str(_FIXTURES / "synthetic-transactions.csv"),
                "--provider",
                "auto",
                "--persist",
                "--catalogue-dir",
                str(catalogue_dir),
            ],
        )
        assert result.exit_code == 0, result.output
        # The envelope file landed under the catalogue directory at
        # FINANCIAL classification.
        envelope_path = catalogue_dir / "transactions.envelope.json"
        assert envelope_path.exists()
        envelope_text = envelope_path.read_text(encoding="utf-8")
        assert '"classification":"financial"' in envelope_text
        assert "imported=2" in result.output
        assert "skipped=0" in result.output

        # Re-import the same file: idempotency yields imported=0,
        # skipped=2 against the existing catalogue.
        result_b = _RUNNER.invoke(
            root_app,
            [
                "financial",
                "ingest",
                str(_FIXTURES / "synthetic-transactions.csv"),
                "--provider",
                "auto",
                "--persist",
                "--catalogue-dir",
                str(catalogue_dir),
            ],
        )
        assert result_b.exit_code == 0, result_b.output
        assert "imported=0" in result_b.output
        assert "skipped=2" in result_b.output
    finally:
        override_master_key_provider(None)
        override_secret_store(None)


def test_financial_ingest_no_persist_preserves_pipe_workflow(tmp_path: Path) -> None:
    """``--no-persist`` keeps the legacy stdout-only behaviour intact."""
    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "ingest",
            str(_FIXTURES / "synthetic-transactions.csv"),
            "--provider",
            "auto",
            "--output-json",
            "--no-persist",
        ],
    )
    assert result.exit_code == 0, result.output
    payloads = [json.loads(line) for line in result.stdout.splitlines() if line.strip().startswith("{")]
    assert len(payloads) == 2
    # No 'persisted' / 'imported=' summary line on stdout when --no-persist.
    assert "imported=" not in result.output
