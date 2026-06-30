"""Round-trip persistence tests for the invoice and transaction catalogues.

These tests exercise the actual encrypted SQL backend end-to-end
(``save`` -> fresh repository instance -> ``load``) rather than asserting
against the on-disk envelope shape. They are the regression net that
catches signature drift between the production repository classes and
their callers, a class of drift that type checkers will flag in tests
but only a real round-trip can flag in production.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...iva import InvoiceKind
from ...transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ...transactions._repository import TransactionCatalogueRepository
from .._enums import IvaRate, PaymentStatus
from .._models import Invoice, InvoiceCatalogue, InvoiceLine
from .._repository import InvoiceCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_ID = "17171717-1717-4171-8171-171717171717"


@pytest.fixture(autouse=True)
def _runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile


def _invoice(invoice_number: str = "INV-001") -> Invoice:
    line = InvoiceLine.model_validate(
        {
            "description": "ConsultorÝa",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.00"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("21.00"),
        },
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": invoice_number,
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
        },
    )


def _transaction(provider_id: str = "row-1") -> Transaction:
    raw = RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2026, 4, 5),
        value_date=date(2026, 4, 5),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Cliente SL",
        description="payment",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": "payment"},
    )
    return Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.INCOMING, "group_label": None, "source_jurisdiction": "ES"},
    )


class TestInvoiceCatalogueRoundTrip:
    """Save ÔåÆ fresh repository ÔåÆ load must yield a value-equal catalogue."""

    def test_empty_catalogue_loads_when_nothing_persisted(self) -> None:
        catalogue = InvoiceCatalogueRepository().load()
        assert len(catalogue) == 0

    def test_exists_is_false_when_nothing_persisted(self) -> None:
        assert InvoiceCatalogueRepository().exists() is False

    def test_single_invoice_round_trip_preserves_model(self) -> None:
        invoice = _invoice()
        original = InvoiceCatalogue.from_invoices([invoice])
        InvoiceCatalogueRepository().save(original)

        reloaded = InvoiceCatalogueRepository().load()
        assert reloaded == original

    def test_multi_invoice_round_trip_preserves_order_and_values(self) -> None:
        invoices = [
            _invoice(invoice_number="INV-001"),
            _invoice(invoice_number="INV-002"),
            _invoice(invoice_number="INV-003"),
        ]
        original = InvoiceCatalogue.from_invoices(invoices)
        InvoiceCatalogueRepository().save(original)

        reloaded = InvoiceCatalogueRepository().load()
        assert reloaded == original
        assert tuple(reloaded.values()) == tuple(original.values())

    def test_resave_overwrites_atomically(self) -> None:
        first = InvoiceCatalogue.from_invoices([_invoice("INV-A")])
        second = InvoiceCatalogue.from_invoices([_invoice("INV-B")])
        repo = InvoiceCatalogueRepository()
        repo.save(first)
        repo.save(second)

        reloaded = InvoiceCatalogueRepository().load()
        invoice_numbers = {invoice.invoice_number for invoice in reloaded.values()}
        assert invoice_numbers == {"INV-B"}


class TestTransactionCatalogueRoundTrip:
    """Save ÔåÆ fresh repository ÔåÆ load must yield a value-equal catalogue."""

    def test_empty_catalogue_loads_when_nothing_persisted(self) -> None:
        catalogue = TransactionCatalogueRepository(bucket_id=_BUCKET_ID).load()
        assert len(catalogue) == 0

    def test_single_transaction_round_trip_preserves_model(self) -> None:
        transaction = _transaction()
        original = TransactionCatalogue.from_transactions([transaction])
        TransactionCatalogueRepository(bucket_id=_BUCKET_ID).save(original)

        reloaded = TransactionCatalogueRepository(bucket_id=_BUCKET_ID).load()
        assert reloaded == original

    def test_multi_transaction_round_trip_preserves_values(self) -> None:
        transactions = [_transaction(provider_id=f"row-{i}") for i in range(3)]
        original = TransactionCatalogue.from_transactions(transactions)
        TransactionCatalogueRepository(bucket_id=_BUCKET_ID).save(original)

        reloaded = TransactionCatalogueRepository(bucket_id=_BUCKET_ID).load()
        assert reloaded == original
