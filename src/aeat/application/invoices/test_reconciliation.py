"""Invoice reconciliation application service tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...domain.invoices import Invoice, InvoiceCatalogue, InvoiceKind, InvoiceLine, IvaRate, PaymentStatus
from ...domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from . import reconcile_invoice_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_reconcile_invoice_catalogues_without_apply_reports_suggestions_without_mutation() -> None:
    invoice = _invoice()
    transaction = _transaction()
    invoices = InvoiceCatalogue.from_invoices([invoice])
    transactions = TransactionCatalogue.from_transactions([transaction])

    result = reconcile_invoice_catalogues(invoices, transactions)

    assert len(result.suggestions) == 1
    assert result.suggestions[0].invoice_id == invoice.invoice_id
    assert result.suggestions[0].transaction_id == transaction.transaction_id
    assert result.applied == 0
    assert result.skipped == ()
    unchanged_invoice = result.invoices.get(invoice.invoice_id)
    unchanged_transaction = result.transactions.get(transaction.transaction_id)
    assert unchanged_invoice is not None
    assert unchanged_invoice.linked_transaction_ids == ()
    assert unchanged_transaction is not None
    assert unchanged_transaction.invoice_id is None


def test_reconcile_invoice_catalogues_apply_roundtrips_bidirectional_links() -> None:
    invoice = _invoice()
    transaction = _transaction()

    first = reconcile_invoice_catalogues(
        InvoiceCatalogue.from_invoices([invoice]),
        TransactionCatalogue.from_transactions([transaction]),
        apply=True,
    )
    second = reconcile_invoice_catalogues(first.invoices, first.transactions, apply=True)

    linked_invoice = first.invoices.get(invoice.invoice_id)
    linked_transaction = first.transactions.get(transaction.transaction_id)
    assert first.applied == 1
    assert first.skipped == ()
    assert linked_invoice is not None
    assert linked_invoice.linked_transaction_ids == (transaction.transaction_id,)
    assert linked_transaction is not None
    assert linked_transaction.invoice_id == invoice.invoice_id
    assert second.suggestions == ()
    assert second.applied == 0
    assert second.invoices == first.invoices
    assert second.transactions == first.transactions


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
                    }
                ),
            ),
        }
    )


def _transaction() -> Transaction:
    raw = RawTransaction(
        transaction_id="bank-row-1",
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
    return Transaction.model_validate({"raw": raw, "direction": TransactionDirection.INCOMING})
