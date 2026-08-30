"""Runtime-created secure-storage enrollment tests for financial repositories."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...adapters.persistence.storage.bucket import bucket_paths
from ...tests.secure_sql import isolated_runtime_profile
from ..invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
)
from ..iva import InvoiceKind
from ..transactions.enums import TransactionDirection
from ..transactions.models import Transaction, TransactionCatalogue
from ..transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NOW = datetime(2026, 5, 26, 10, 0, tzinfo=UTC)


def _transaction(source_path: Path) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="runtime-row-1",
        booked_date=date(2026, 4, 5),
        value_date=date(2026, 4, 5),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description="runtime storage enrollment transaction",
        provenance=RawProvenance(
            source_path=source_path,
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=_NOW,
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": "runtime storage enrollment transaction"},
    )
    return Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
    )


def _invoice(bucket_id: str) -> Invoice:
    line = InvoiceLine(
        description="Runtime enrollment service",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
    )
    return Invoice.model_validate(
        {
            "bucket_id": bucket_id,
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": "RUNTIME-001",
            "issued_at": date(2026, 4, 1),
            "counterparty_name": "Proveedor SL",
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


def test_transaction_repository_default_uses_runtime_created_bucket_store(tmp_path: Path) -> None:
    # A canonical profile identity: the test capsule publisher now requires one,
    # so a readable slug no longer stands in for a bucket id.
    bucket_id = "73737373-7373-4373-8373-737373737311"

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        original = TransactionCatalogue.from_transactions((_transaction(Path(__file__)),))
        TransactionCatalogueRepository(bucket_id=bucket_id).save(original)

        loaded = TransactionCatalogueRepository(bucket_id=bucket_id).load()

    assert loaded == original
    assert bucket_paths(tmp_path / "cadrumo-storage", bucket_id).database_file.is_file()


def test_invoice_repository_default_uses_runtime_created_bucket_store(tmp_path: Path) -> None:
    bucket_id = "73737373-7373-4373-8373-737373737312"

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        invoice = _invoice(bucket_id)
        original = InvoiceCatalogue.from_invoices((invoice,))
        InvoiceCatalogueRepository(bucket_id=bucket_id).save(original)

        loaded = InvoiceCatalogueRepository(bucket_id=bucket_id).load()

    assert loaded == original
    assert loaded.get(invoice.invoice_id) is not None
    assert bucket_paths(tmp_path / "cadrumo-storage", bucket_id).database_file.is_file()
