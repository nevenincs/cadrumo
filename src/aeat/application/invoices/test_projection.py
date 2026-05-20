"""Invoice review projection service tests."""

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
from ..review import InvoiceReviewFilterSpec, update_invoice_review
from ..workflow import WorkflowState
from . import (
    InvoiceMatchRow,
    apply_manual_invoice_match,
    project_invoice_payment_matches,
    project_invoice_reviews,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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


def test_review_projection_applies_review_rate_and_status() -> None:
    invoice = _invoice()
    catalogue = InvoiceCatalogue.from_invoices([invoice])
    state = update_invoice_review(
        WorkflowState(),
        invoice.invoice_id,
        fields={"base": "200.00", "iva.rate": "10"},
        action="edit",
        reason="reviewed base",
    )

    rows = project_invoice_reviews(catalogue, state, spec=InvoiceReviewFilterSpec())

    assert len(rows) == 1
    assert rows[0].base == "200"
    assert rows[0].iva == "20"
    assert rows[0].status == "reviewed"


def test_manual_match_projection_records_payment_and_matches_existing_transaction_id() -> None:
    invoice = _invoice()
    transaction = _transaction()
    transaction_id = transaction.transaction_id
    state = apply_manual_invoice_match(WorkflowState(), invoice.invoice_id, transaction_id)
    catalogue = InvoiceCatalogue.from_invoices([invoice])
    transactions = TransactionCatalogue.from_transactions([transaction])

    projection = project_invoice_payment_matches(
        period="2026Q1",
        catalogue=catalogue,
        transactions=transactions,
        state=state,
    )

    assert projection.matched == (
        InvoiceMatchRow(invoice=invoice.invoice_id, payment=transaction_id),
    )
    assert projection.unmatched == ()


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
