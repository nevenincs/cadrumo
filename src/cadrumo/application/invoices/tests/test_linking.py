"""Invoice linking application service tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....domain.invoices import Invoice, InvoiceCatalogue, InvoiceLine, InvoiceLinkError, IvaRate, PaymentStatus
from ....domain.iva import InvoiceKind
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_runtime_profile
from .. import link_invoice_transaction_catalogues, link_invoice_transaction_repositories

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "21212121-2121-4212-8212-212121212121"


def test_link_invoice_transaction_catalogues_roundtrips_bidirectional_link() -> None:
    invoice = _invoice()
    transaction = _transaction()

    result = link_invoice_transaction_catalogues(
        InvoiceCatalogue.from_invoices([invoice]),
        TransactionCatalogue.from_transactions([transaction]),
        invoice_id=invoice.invoice_id,
        transaction_id=transaction.transaction_id.upper(),
    )

    linked_invoice = result.invoices.get(invoice.invoice_id)
    linked_transaction = result.transactions.get(transaction.transaction_id)
    assert result.invoice == linked_invoice
    assert result.transaction_id == transaction.transaction_id
    assert linked_invoice is not None
    assert linked_invoice.linked_transaction_ids == (transaction.transaction_id,)
    assert linked_transaction is not None
    assert linked_transaction.invoice_id == invoice.invoice_id


def test_link_invoice_transaction_catalogues_reports_missing_transaction_context() -> None:
    invoice = _invoice()

    with pytest.raises(InvoiceLinkError) as exc_info:
        link_invoice_transaction_catalogues(
            InvoiceCatalogue.from_invoices([invoice]),
            TransactionCatalogue(),
            invoice_id=invoice.invoice_id,
            transaction_id="missing-transaction",
        )

    assert exc_info.value.translated_message == "application.invoices.linking.errors.transaction_not_found"
    assert exc_info.value.context == {"transaction_id": "missing-transaction"}


def test_link_invoice_transaction_repositories_binds_both_catalogues_to_requested_bucket(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        invoice = _invoice()
        transaction = _transaction()
        invoices = InvoiceCatalogueRepository(bucket_id=profile.bucket_id)
        transactions = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        invoices.save(InvoiceCatalogue.from_invoices([invoice]))
        transactions.save(TransactionCatalogue.from_transactions([transaction]))

        result = link_invoice_transaction_repositories(
            bucket_id=profile.bucket_id,
            invoice_id=invoice.invoice_id,
            transaction_id=transaction.transaction_id.upper(),
        )

        reloaded_invoice = invoices.load().get(invoice.invoice_id)
        reloaded_transaction = transactions.load().get(transaction.transaction_id)
        assert result.transaction_id == transaction.transaction_id
        assert reloaded_invoice is not None
        assert reloaded_invoice.linked_transaction_ids == (transaction.transaction_id,)
        assert reloaded_transaction is not None
        assert reloaded_transaction.invoice_id == invoice.invoice_id


def _invoice() -> Invoice:
    return Invoice.model_validate(
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
            "payment_status": PaymentStatus.PAID,
            "lines": (
                InvoiceLine.model_validate(
                    {
                        "description": "Servicios",
                        "quantity": Decimal("1"),
                        "unit_price": Decimal("100.00"),
                        "subtotal": Decimal("100.00"),
                        "iva_rate": IvaRate.RATE_21,
                        "iva_amount": Decimal("21.00"),
                    },
                ),
            ),
        },
    )


def _transaction() -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="bank-row-1",
        booked_date=date(2026, 4, 2),
        value_date=date(2026, 4, 2),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Cliente SL",
        description="Cliente SL",
        provenance=RawProvenance(
            source_path=Path("statement.csv"),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 2, tzinfo=UTC),
            provider_name="csv",
        ),
        raw_fields={"amount": "121.00"},
    )
    return Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.INCOMING, "group_label": None, "source_jurisdiction": "ES"},
    )
