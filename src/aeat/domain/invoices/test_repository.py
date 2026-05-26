"""Round-trip persistence tests for the invoice and transaction catalogues.

These tests exercise the actual encrypted SQL backend end-to-end
(``save`` ÔåÆ fresh repository instance ÔåÆ ``load``) rather than asserting
against the on-disk envelope shape. They are the regression net that
catches signature drift between the production repository classes and
their callers ÔÇö a class of drift that type checkers will flag in tests
but only a real round-trip can flag in production.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from aeat.adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_secret_store,
)
from aeat.adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from aeat.core.config import Settings
from aeat.domain.invoices._enums import InvoiceKind, IvaRate, PaymentStatus
from aeat.domain.invoices._models import Invoice, InvoiceCatalogue, InvoiceLine
from aeat.domain.invoices._repository import InvoiceCatalogueRepository
from aeat.domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from aeat.domain.transactions._repository import TransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@pytest.fixture
def secure_engine(tmp_path: Path) -> Iterator[Engine]:
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
        )
        blob_store = EncryptedBlobStore(
            root_dir=tmp_path / "blobs",
            master_key_provider=provider,
        )
        secret_store = SecretStore(
            store_dir=tmp_path / "secrets",
            blob_store=blob_store,
            master_key_provider=provider,
        )
        override_secret_store(secret_store)
        try:
            yield engine
        finally:
            override_secret_store(None)
            engine.dispose()


@pytest.fixture
def secure_objects(secure_engine: Engine) -> SecureObjectRepository:
    return SecureObjectRepository(engine=secure_engine)


def _invoice_repo(objects: SecureObjectRepository) -> InvoiceCatalogueRepository:
    return InvoiceCatalogueRepository(objects=objects)


def _transaction_repo(
    objects: SecureObjectRepository,
    *,
    bucket_id: str = "test",
) -> TransactionCatalogueRepository:
    return TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects)


def _invoice(invoice_number: str = "INV-001") -> Invoice:
    line = InvoiceLine.model_validate(
        {
            "description": "ConsultorÝa",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.00"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("21.00"),
        }
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
        }
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
        {"raw": raw, "direction": TransactionDirection.INCOMING},
    )


class TestInvoiceCatalogueRoundTrip:
    """Save ÔåÆ fresh repository ÔåÆ load must yield a value-equal catalogue."""

    def test_empty_catalogue_loads_when_nothing_persisted(self, secure_objects: SecureObjectRepository) -> None:
        catalogue = _invoice_repo(secure_objects).load()
        assert len(catalogue) == 0

    def test_exists_is_false_when_nothing_persisted(self, secure_objects: SecureObjectRepository) -> None:
        assert _invoice_repo(secure_objects).exists() is False

    def test_single_invoice_round_trip_preserves_model(self, secure_objects: SecureObjectRepository) -> None:
        invoice = _invoice()
        original = InvoiceCatalogue.from_invoices([invoice])
        _invoice_repo(secure_objects).save(original)

        reloaded = _invoice_repo(secure_objects).load()
        assert reloaded == original

    def test_multi_invoice_round_trip_preserves_order_and_values(self, secure_objects: SecureObjectRepository) -> None:
        invoices = [
            _invoice(invoice_number="INV-001"),
            _invoice(invoice_number="INV-002"),
            _invoice(invoice_number="INV-003"),
        ]
        original = InvoiceCatalogue.from_invoices(invoices)
        _invoice_repo(secure_objects).save(original)

        reloaded = _invoice_repo(secure_objects).load()
        assert reloaded == original
        assert tuple(reloaded.values()) == tuple(original.values())

    def test_resave_overwrites_atomically(self, secure_objects: SecureObjectRepository) -> None:
        first = InvoiceCatalogue.from_invoices([_invoice("INV-A")])
        second = InvoiceCatalogue.from_invoices([_invoice("INV-B")])
        repo = _invoice_repo(secure_objects)
        repo.save(first)
        repo.save(second)

        reloaded = _invoice_repo(secure_objects).load()
        invoice_numbers = {invoice.invoice_number for invoice in reloaded.values()}
        assert invoice_numbers == {"INV-B"}


class TestTransactionCatalogueRoundTrip:
    """Save ÔåÆ fresh repository ÔåÆ load must yield a value-equal catalogue."""

    def test_empty_catalogue_loads_when_nothing_persisted(self, secure_objects: SecureObjectRepository) -> None:
        catalogue = _transaction_repo(secure_objects).load()
        assert len(catalogue) == 0

    def test_single_transaction_round_trip_preserves_model(self, secure_objects: SecureObjectRepository) -> None:
        transaction = _transaction()
        original = TransactionCatalogue.from_transactions([transaction])
        _transaction_repo(secure_objects).save(original)

        reloaded = _transaction_repo(secure_objects).load()
        assert reloaded == original

    def test_multi_transaction_round_trip_preserves_values(self, secure_objects: SecureObjectRepository) -> None:
        transactions = [_transaction(provider_id=f"row-{i}") for i in range(3)]
        original = TransactionCatalogue.from_transactions(transactions)
        _transaction_repo(secure_objects).save(original)

        reloaded = _transaction_repo(secure_objects).load()
        assert reloaded == original
