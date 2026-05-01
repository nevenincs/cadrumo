"""End-to-end tests for the cross-source review-queue aggregator."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...core.config import Settings
from ...core.i18n import Translatable
from ...adapters.inbound.financial import RawProvenance, RawTransaction, SourceFormat
from ...domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceKind,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
)
from ...domain.invoices._repository import InvoiceCatalogueRepository
from ...domain.transactions import (
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ...domain.transactions._repository import TransactionCatalogueRepository
from ..filing import (
    FilingDraft,
    FilingDraftStatus,
    FilingFindingSeverity,
    FilingValidationFinding,
    FilingValue,
    FilingValueKind,
)
from ..sync import (
    CasillaRemoved,
    DivergenceClassification,
    DivergenceRecord,
    JsonFileDivergenceRepository,
    ModeloIdentifier,
)
from . import (
    ReviewItemKind,
    ReviewQueue,
    ReviewSeverity,
    ReviewState,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _summary(text: str = "demo") -> Translatable:
    return {"es": text, "en": text, "hu": text}


def _build_settings(tmp_path: Path) -> Settings:
    return Settings(
        aeat_financial_txs_dir=tmp_path / "transactions",
        aeat_invoices_dir=tmp_path / "invoices",
        aeat_attachments_dir=tmp_path / "attachments",
        aeat_sync_divergence_file_dir=tmp_path / "divergences",
        aeat_inbox_dir=tmp_path / "inbox",
        aeat_inbox_pdf_dir=tmp_path / "inbox-pdfs",
        aeat_drafts_dir=tmp_path / "drafts",
    )


def _seed_all_sources(tmp_path: Path) -> Settings:
    """Materialise one pending item in every source under tmp_path."""
    settings = _build_settings(tmp_path)

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
    catalogue = TransactionCatalogue.from_transactions((transaction,))
    TransactionCatalogueRepository(store_dir=settings.aeat_financial_txs_dir).save(catalogue)

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
    InvoiceCatalogueRepository(store_dir=settings.aeat_invoices_dir).save(InvoiceCatalogue.from_invoices((invoice,)))

    modelo = ModeloIdentifier("130")
    repo = JsonFileDivergenceRepository(settings.aeat_sync_divergence_file_dir)
    repo.save(
        DivergenceRecord(
            record_id=uuid.uuid4().hex,
            detected_at=datetime(2026, 4, 12, tzinfo=UTC),
            modelo=modelo,
            classification=DivergenceClassification.BREAKING,
            payload=CasillaRemoved(modelo=modelo, casilla_id="C9"),
        )
    )

    settings.aeat_drafts_dir.mkdir(parents=True, exist_ok=True)
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
    from ..filing._repository import FilingDraftRepository

    FilingDraftRepository(store_dir=settings.aeat_drafts_dir).save(draft)

    return settings


def test_collect_returns_one_item_per_source(tmp_path: Path) -> None:
    settings = _seed_all_sources(tmp_path)
    items = ReviewQueue.collect(settings)
    kinds = {item.kind for item in items}
    assert kinds == {
        ReviewItemKind.TRANSACTION,
        ReviewItemKind.INVOICE,
        ReviewItemKind.DIVERGENCE,
        ReviewItemKind.FINDING,
    }
    assert len(items) == 4


def test_collect_sorts_critical_before_normal(tmp_path: Path) -> None:
    settings = _seed_all_sources(tmp_path)
    items = ReviewQueue.collect(settings)
    severities = [item.severity for item in items]
    # CRITICAL comes first; NORMAL last; the seeded items are CRITICAL x2, HIGH x1, NORMAL x1.
    assert severities[0] is ReviewSeverity.CRITICAL
    assert severities[-1] is ReviewSeverity.NORMAL


def test_collect_filters_by_kind(tmp_path: Path) -> None:
    settings = _seed_all_sources(tmp_path)
    items = ReviewQueue.collect(
        settings,
        kinds=frozenset({ReviewItemKind.DIVERGENCE, ReviewItemKind.FINDING}),
    )
    kinds = {item.kind for item in items}
    assert kinds == {ReviewItemKind.DIVERGENCE, ReviewItemKind.FINDING}
    assert len(items) == 2


def test_collect_filters_by_modelo(tmp_path: Path) -> None:
    settings = _seed_all_sources(tmp_path)
    items = ReviewQueue.collect(settings, modelo="130")
    # Transaction and invoice carry no modelo so they are excluded.
    # Only divergence + draft finding (both modelo=130) survive.
    assert {item.kind for item in items} == {ReviewItemKind.DIVERGENCE, ReviewItemKind.FINDING}


def test_collect_state_all_matches_pending_today(tmp_path: Path) -> None:
    settings = _seed_all_sources(tmp_path)
    pending = ReviewQueue.collect(settings, state=ReviewState.PENDING)
    every = ReviewQueue.collect(settings, state=ReviewState.ALL)
    assert pending == every


def test_collect_returns_empty_tuple_when_no_sources_present(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    assert ReviewQueue.collect(settings) == ()
