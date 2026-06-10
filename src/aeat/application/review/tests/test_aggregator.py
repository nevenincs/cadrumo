"""End-to-end tests for the cross-source review-queue aggregator."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....application.user_profile._orchestration import profile_create_storage_span, profile_storage_session
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import Settings
from ....core.errors import BaseSeverity
from ....core.i18n import Translatable as tr
from ....domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
)
from ....domain.invoices._repository import InvoiceCatalogueRepository
from ....domain.iva import InvoiceKind
from ....domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ....domain.transactions._repository import TransactionCatalogueRepository
from ...filing import (
    ModeloDraft,
    ModeloDraftStatus,
    ModeloValidationFinding,
    ModeloValue,
    ModeloValueKind,
)
from .. import (
    ReviewItemKind,
    ReviewQueue,
    ReviewSeverity,
    ReviewState,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _summary(text: str = "demo") -> tr:
    return tr("translation")


def _schema_version(modelo: str = "130") -> str:
    return f"test-schema-{modelo}"


def _build_settings(tmp_path: Path) -> Settings:
    return Settings(
        aeat_financial_txs_dir=tmp_path / "transactions",
        aeat_invoices_dir=tmp_path / "invoices",
        aeat_attachments_dir=tmp_path / "attachments",
        aeat_inbox_dir=tmp_path / "inbox",
        aeat_inbox_pdf_dir=tmp_path / "inbox-pdfs",
        aeat_drafts_dir=tmp_path / "drafts",
    )


def _seed_all_sources(tmp_path: Path) -> Settings:
    """Materialise one pending item in every source under tmp_path."""
    settings = _build_settings(tmp_path)
    with profile_create_storage_span("test"):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id="test",
                overrides={"identity.tax_id": "00000000T"},
            )
        )

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
        TransactionCatalogueRepository(bucket_id="test").save(catalogue)

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
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices((invoice,)))

        finding = ModeloValidationFinding(
            casilla_id="03",
            severity=BaseSeverity.ERROR,
            code="casilla-out-of-range",
            message=_summary("range"),
        )
        draft = ModeloDraft(
            draft_id="d1",
            modelo="130",
            period="2026Q1",
            profile_tax_id="00000000T",
            status=ModeloDraftStatus.BORRADOR,
            values=(
                ModeloValue(
                    casilla_id="03",
                    value=Decimal("0"),
                    kind=ModeloValueKind.LITERAL,
                    source="test",
                ),
            ),
            findings=(finding,),
            created_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
            updated_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
            schema_version=_schema_version(),
        )
        from ....domain.filing import ModeloDraftRepository

        ModeloDraftRepository().save(draft)

    return settings


def _collect(settings: Settings, **kwargs: Any) -> tuple:
    with profile_storage_session("test"):
        return ReviewQueue.collect(settings, bucket_id="test", **kwargs)


def test_collect_returns_one_item_per_source(tmp_path: Path) -> None:
    settings = _seed_all_sources(tmp_path)
    items = _collect(settings)
    kinds = {item.kind for item in items}
    assert kinds == {
        ReviewItemKind.TRANSACTION,
        ReviewItemKind.INVOICE,
        ReviewItemKind.FINDING,
    }
    assert len(items) == 3


def test_collect_sorts_critical_before_normal(tmp_path: Path) -> None:
    settings = _seed_all_sources(tmp_path)
    items = _collect(settings)
    severities = [item.severity for item in items]
    # CRITICAL comes first; NORMAL last; the seeded items are CRITICAL x1, HIGH x1, NORMAL x1.
    assert severities[0] is ReviewSeverity.CRITICAL
    assert severities[-1] is ReviewSeverity.NORMAL


def test_collect_filters_by_kind(tmp_path: Path) -> None:
    settings = _seed_all_sources(tmp_path)
    items = _collect(settings, kinds=frozenset({ReviewItemKind.FINDING}))
    kinds = {item.kind for item in items}
    assert kinds == {ReviewItemKind.FINDING}
    assert len(items) == 1


def test_collect_filters_by_modelo(tmp_path: Path) -> None:
    settings = _seed_all_sources(tmp_path)
    items = _collect(settings, modelo="130")
    # Transaction and invoice carry no modelo so they are excluded.
    assert {item.kind for item in items} == {ReviewItemKind.FINDING}


def test_collect_state_all_matches_pending_today(tmp_path: Path) -> None:
    settings = _seed_all_sources(tmp_path)
    pending = _collect(settings, state=ReviewState.PENDING)
    every = _collect(settings, state=ReviewState.ALL)
    assert pending == every


def test_collect_returns_empty_tuple_when_no_sources_present(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    with profile_create_storage_span("test"):
        assert ReviewQueue.collect(settings, bucket_id="test") == ()
