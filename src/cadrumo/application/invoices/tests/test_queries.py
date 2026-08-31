"""Invoice query projection service tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core.invoice_link import LinkInconsistencyDirection
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.invoices.service import verify_link_consistency
from ....domain.iva.classification import InvoiceKind
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.transactions.service import link_invoice
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    link_invoice_transaction_catalogues,
    list_invoice_rows,
    list_unmatched_invoice_rows,
    verify_invoice_repository_links,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "22222222-2222-4222-8222-222222222222"


def test_invoice_rows_filter_and_sort_by_backend_projection() -> None:
    later = _invoice(invoice_number="INV-B", issued_at=date(2026, 4, 2))
    earlier = _invoice(invoice_number="INV-A", issued_at=date(2026, 4, 1))
    received = _invoice(invoice_number="INV-C", issued_at=date(2026, 4, 3), kind=InvoiceKind.RECEIVED)

    rows = list_invoice_rows(
        InvoiceCatalogue.from_invoices([later, received, earlier]),
        kind=InvoiceKind.ISSUED,
    )

    assert tuple(row.invoice_id for row in rows) == (earlier.invoice_id, later.invoice_id)
    assert all(row.kind is InvoiceKind.ISSUED for row in rows)
    assert rows[0].payment_status == PaymentStatus.PAID.value


def test_unmatched_rows_and_consistency_are_backend_queries() -> None:
    linked_invoice = _invoice(invoice_number="INV-LINKED")
    unlinked_invoice = _invoice(invoice_number="INV-OPEN")
    transaction = _transaction()
    linked = link_invoice_transaction_catalogues(
        InvoiceCatalogue.from_invoices([linked_invoice, unlinked_invoice]),
        TransactionCatalogue.from_transactions([transaction]),
        invoice_id=linked_invoice.invoice_id,
        transaction_id=transaction.transaction_id,
    )

    unmatched = list_unmatched_invoice_rows(linked.invoices)
    inconsistencies = verify_link_consistency(linked.invoices, linked.transactions)

    assert tuple(row.invoice_id for row in unmatched) == (unlinked_invoice.invoice_id,)
    assert inconsistencies == ()


def test_consistency_query_reports_one_sided_transaction_link() -> None:
    invoice = _invoice()
    transaction = _transaction()
    drifted_transactions = link_invoice(
        TransactionCatalogue.from_transactions([transaction]),
        transaction.transaction_id,
        invoice.invoice_id,
    )

    inconsistencies = verify_link_consistency(InvoiceCatalogue.from_invoices([invoice]), drifted_transactions)

    assert len(inconsistencies) == 1
    assert inconsistencies[0].invoice_id == invoice.invoice_id
    assert inconsistencies[0].transaction_id == transaction.transaction_id
    assert inconsistencies[0].direction is LinkInconsistencyDirection.TRANSACTION_ONLY


def test_repository_consistency_query_binds_both_catalogues_to_requested_bucket(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        invoice = _invoice()
        transaction = _transaction()
        linked = link_invoice_transaction_catalogues(
            InvoiceCatalogue.from_invoices([invoice]),
            TransactionCatalogue.from_transactions([transaction]),
            invoice_id=invoice.invoice_id,
            transaction_id=transaction.transaction_id,
        )
        InvoiceCatalogueRepository(bucket_id=profile.bucket_id).save(linked.invoices)
        TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(linked.transactions)

        assert verify_invoice_repository_links(bucket_id=profile.bucket_id) == ()


def _invoice(
    *,
    invoice_number: str = "INV-001",
    issued_at: date = date(2026, 4, 1),
    kind: InvoiceKind = InvoiceKind.ISSUED,
) -> Invoice:
    return Invoice.model_validate(
        {
            "kind": kind,
            "invoice_number": invoice_number,
            "issued_at": issued_at,
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
