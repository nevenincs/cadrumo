"""Invoice reconciliation application service tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....domain.invoices import Invoice, InvoiceCatalogue, InvoiceLine, IvaRate, PaymentStatus
from ....domain.iva import InvoiceKind
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_runtime_profile
from .. import reconcile_invoice_catalogues, reconcile_invoice_repositories

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "23232323-2323-4232-8232-232323232323"


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


def test_reconcile_invoice_repositories_binds_both_catalogues_to_requested_bucket(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        invoice = _invoice()
        transaction = _transaction()
        InvoiceCatalogueRepository(bucket_id=profile.bucket_id).save(InvoiceCatalogue.from_invoices([invoice]))
        TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(
            TransactionCatalogue.from_transactions([transaction]),
        )

        result = reconcile_invoice_repositories(bucket_id=profile.bucket_id, apply=True)

        reloaded_invoice = InvoiceCatalogueRepository(bucket_id=profile.bucket_id).load().get(invoice.invoice_id)
        reloaded_transaction = (
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).load().get(transaction.transaction_id)
        )
        assert result.applied == 1
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
