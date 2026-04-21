"""CLI tests for the ``aeat review queue`` sub-app."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl
from typer.testing import CliRunner

from ...filing import (
    FilingDraft,
    FilingDraftStatus,
    FilingFindingSeverity,
    FilingValidationFinding,
    FilingValue,
    FilingValueKind,
)
from ...financial import RawProvenance, RawTransaction, SourceFormat
from ...financial.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceKind,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
    save_invoices,
)
from ...financial.transactions import (
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    save_transactions,
)
from ...i18n import Translatable
from ...inbox import (
    Inbox,
    Notificacion,
    NotificacionKind,
    NotificacionPriority,
)
from ...sync import (
    CasillaRemoved,
    DivergenceClassification,
    DivergenceRecord,
    JsonFileDivergenceRepository,
    ModeloIdentifier,
)
from .. import app as root_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


def _summary(text: str) -> Translatable:
    return {"es": text, "en": text, "hu": text}


@pytest.fixture()
def isolated_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Point every disk-backed Settings field at tmp_path subdirectories."""
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "transactions"))
    monkeypatch.setenv("AEAT_INVOICES_DIR", str(tmp_path / "invoices"))
    monkeypatch.setenv("AEAT_ATTACHMENTS_DIR", str(tmp_path / "attachments"))
    monkeypatch.setenv("AEAT_SYNC_DIVERGENCE_FILE_DIR", str(tmp_path / "divergences"))
    monkeypatch.setenv("AEAT_INBOX_DIR", str(tmp_path / "inbox"))
    monkeypatch.setenv("AEAT_INBOX_PDF_DIR", str(tmp_path / "inbox-pdfs"))
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "drafts"))
    return tmp_path


def _seed_all(tmp_path: Path) -> None:
    raw = RawTransaction(
        transaction_id="prov-1",
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=Decimal("12.34"),
        currency="EUR",
        counterparty=None,
        description="Bank fee",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
            provider_name="csv",
        ),
        raw_fields={"Concepto": "Bank fee"},
    )
    transaction = Transaction.model_validate({"raw": raw, "direction": TransactionDirection.OUTGOING})
    save_transactions(
        TransactionCatalogue.from_transactions((transaction,)),
        tmp_path / "transactions" / "transactions.json",
    )

    line = InvoiceLine(
        description="Consultoría",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
    )
    invoice = Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-001",
            "issued_at": date(2026, 4, 1),
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PENDING,
            "linked_transaction_ids": (),
        }
    )
    save_invoices(InvoiceCatalogue.from_invoices((invoice,)), tmp_path / "invoices" / "invoices.json")

    modelo = ModeloIdentifier("130")
    repo = JsonFileDivergenceRepository(tmp_path / "divergences")
    repo.save(
        DivergenceRecord(
            record_id=uuid.uuid4().hex,
            detected_at=datetime(2026, 4, 12, tzinfo=UTC),
            modelo=modelo,
            classification=DivergenceClassification.BREAKING,
            payload=CasillaRemoved(modelo=modelo, casilla_id="C9"),
        )
    )

    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    finding = FilingValidationFinding(
        casilla_id="03",
        severity=FilingFindingSeverity.ERROR,
        code="casilla-out-of-range",
        message=_summary("range"),
    )
    draft = FilingDraft(
        draft_id="d1",
        modelo="130",
        period="2026Q1",
        profile_tax_id="00000000T",
        status=FilingDraftStatus.DRAFT,
        values=(
            FilingValue(
                casilla_id="03",
                value=Decimal("0"),
                kind=FilingValueKind.LITERAL,
                source="test",
            ),
        ),
        findings=(finding,),
        created_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
        schema_version="filing-schema-0.1.0",
    )
    (drafts_dir / "130_2026Q1_d1.json").write_text(
        draft.model_dump_json(indent=2),
        encoding="utf-8",
    )

    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    received = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)
    inbox = Inbox(
        entries={
            "AEAT-0001": Notificacion(
                notificacion_id="AEAT-0001",
                kind=NotificacionKind.REQUERIMIENTO,
                priority=NotificacionPriority.CRITICAL,
                subject=_summary("Requerimiento"),
                body_excerpt=_summary("Solicitamos"),
                received_at=received,
                effective_at=received,
                appeal_deadline=date(2026, 4, 20),
                source_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/notif/x"),
            )
        }
    )
    (inbox_dir / "inbox.json").write_text(inbox.model_dump_json(indent=2), encoding="utf-8")


def test_queue_empty_environment_prints_no_pending(isolated_settings: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(root_app, ["review", "queue"])
    assert result.exit_code == 0
    assert "No pending review items." in result.stdout


def test_queue_table_lists_every_kind(isolated_settings: Path) -> None:
    _seed_all(isolated_settings)
    runner = CliRunner()
    result = runner.invoke(root_app, ["review", "queue"])
    assert result.exit_code == 0
    # rich truncates long column values at narrow terminal widths in CliRunner;
    # use prefix matches that survive an 80-char terminal.
    for kind_prefix in ("transact", "invoice", "divergen", "finding", "inbox"):
        assert kind_prefix in result.stdout
    assert "5 item" in result.stdout
    assert "5 kind" in result.stdout


def test_queue_filter_by_single_kind(isolated_settings: Path) -> None:
    _seed_all(isolated_settings)
    runner = CliRunner()
    result = runner.invoke(root_app, ["review", "queue", "--kind", "divergence"])
    assert result.exit_code == 0
    assert "1 item" in result.stdout
    assert "divergen" in result.stdout
    # Other kind tokens must not appear in the table at all.
    assert "transact" not in result.stdout
    assert "invoice" not in result.stdout
    assert "inbox" not in result.stdout


def test_queue_filter_by_multiple_kinds(isolated_settings: Path) -> None:
    _seed_all(isolated_settings)
    runner = CliRunner()
    result = runner.invoke(
        root_app,
        ["review", "queue", "--kind", "transaction", "--kind", "invoice"],
    )
    assert result.exit_code == 0
    assert "2 item" in result.stdout


def test_queue_filter_by_modelo(isolated_settings: Path) -> None:
    _seed_all(isolated_settings)
    runner = CliRunner()
    result = runner.invoke(root_app, ["review", "queue", "--modelo", "130"])
    assert result.exit_code == 0
    # Only divergence + finding carry modelo=130; transaction/invoice/inbox excluded.
    assert "2 item" in result.stdout


def test_queue_json_format_emits_valid_payload(isolated_settings: Path) -> None:
    _seed_all(isolated_settings)
    runner = CliRunner()
    result = runner.invoke(root_app, ["review", "queue", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert len(payload) == 5
    for entry in payload:
        assert {"kind", "item_id", "severity"}.issubset(entry.keys())


def test_queue_state_all_matches_pending(isolated_settings: Path) -> None:
    _seed_all(isolated_settings)
    runner = CliRunner()
    pending = runner.invoke(root_app, ["review", "queue", "--state", "pending", "--format", "json"])
    every = runner.invoke(root_app, ["review", "queue", "--state", "all", "--format", "json"])
    assert pending.exit_code == 0
    assert every.exit_code == 0
    assert json.loads(pending.stdout) == json.loads(every.stdout)


def test_queue_reserved_kind_classification_is_rejected(isolated_settings: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(root_app, ["review", "queue", "--kind", "classification"])
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr if result.stderr is not None else "")
    assert "reserved" in combined.lower() or "C4h" in combined


def test_queue_reserved_kind_approval_stale_is_rejected(isolated_settings: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(root_app, ["review", "queue", "--kind", "approval-stale"])
    assert result.exit_code == 2
    combined = result.stdout + (result.stderr if result.stderr is not None else "")
    assert "230" in combined


def test_queue_unknown_kind_returns_helpful_error(isolated_settings: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(root_app, ["review", "queue", "--kind", "not-a-kind"])
    assert result.exit_code == 2


def _seed_transactions_with_varied_confidence(tmp_path: Path) -> tuple[str, str, str]:
    """Seed three transactions with low, high, and None confidence. Return their IDs."""

    def _raw(pid: str, description: str) -> RawTransaction:
        return RawTransaction(
            transaction_id=pid,
            booked_date=date(2026, 4, 10),
            value_date=date(2026, 4, 10),
            amount=Decimal("-10.00"),
            currency="EUR",
            counterparty=None,
            description=description,
            provenance=RawProvenance(
                source_path=Path(__file__),
                source_sha256="c" * 64,
                source_row_index=1,
                source_format=SourceFormat.CSV,
                ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
                provider_name="csv",
            ),
            raw_fields={"Concepto": description},
        )

    low = Transaction.model_validate(
        {
            "raw": _raw("tx-low", "Low confidence"),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": "PROCESSED_UNCLASSIFIED",
            "classification_confidence": Decimal("0.4"),
        }
    )
    high = Transaction.model_validate(
        {
            "raw": _raw("tx-high", "High confidence"),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": "PROCESSED_UNCLASSIFIED",
            "classification_confidence": Decimal("0.9"),
        }
    )
    bare = Transaction.model_validate(
        {
            "raw": _raw("tx-bare", "No confidence"),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": "NOT_YET_PROCESSED",
        }
    )
    save_transactions(
        TransactionCatalogue.from_transactions((low, high, bare)),
        tmp_path / "transactions" / "transactions.json",
    )
    return low.transaction_id, high.transaction_id, bare.transaction_id


def test_queue_filters_by_confidence_below(isolated_settings: Path) -> None:
    """`aeat review queue --confidence-below 0.5` must surface only low-confidence transactions (#236)."""
    low_id, high_id, bare_id = _seed_transactions_with_varied_confidence(isolated_settings)
    runner = CliRunner()
    result = runner.invoke(
        root_app,
        ["review", "queue", "--confidence-below", "0.5", "--format", "json"],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    item_ids = {item["item_id"] for item in payload}
    assert low_id in item_ids
    assert high_id not in item_ids
    assert bare_id not in item_ids


def test_queue_confidence_filter_excludes_non_transaction_kinds(isolated_settings: Path) -> None:
    """Non-transaction review kinds must be dropped when `--confidence-below` is set (#236)."""
    _seed_all(isolated_settings)
    runner = CliRunner()
    result = runner.invoke(
        root_app,
        ["review", "queue", "--confidence-below", "0.99", "--format", "json"],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    kinds = {item["kind"] for item in payload}
    assert kinds <= {"transaction"}


def test_queue_rejects_out_of_range_confidence_below(isolated_settings: Path) -> None:
    """An out-of-range `--confidence-below` must exit with code 2."""
    runner = CliRunner()
    result = runner.invoke(
        root_app,
        ["review", "queue", "--confidence-below", "1.5"],
    )

    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "0..1 range" in combined


def test_queue_rejects_non_numeric_confidence_below(isolated_settings: Path) -> None:
    """A non-numeric `--confidence-below` must exit with code 2."""
    runner = CliRunner()
    result = runner.invoke(
        root_app,
        ["review", "queue", "--confidence-below", "abc"],
    )

    assert result.exit_code == 2
    combined = result.stdout + (result.stderr or "")
    assert "not a valid Decimal" in combined
