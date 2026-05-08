"""Thin-wrapper CLI tests for ``aeat financial invoices``."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceKind,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
)
from aeat.domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)
from aeat.entrypoints.cli.financial import app as financial_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    previous_db = os.environ.get("AEAT_DATABASE_URL")
    os.environ["AEAT_DATABASE_URL"] = f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}"
    dispose_engine()

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    blob_store = EncryptedBlobStore(root_dir=tmp_path / "blobs", master_key_provider=provider)
    secret_store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_secret_store(secret_store)
    try:
        yield
    finally:
        override_master_key_provider(None)
        override_secret_store(None)
        dispose_engine()
        if previous_db is None:
            os.environ.pop("AEAT_DATABASE_URL", None)
        else:
            os.environ["AEAT_DATABASE_URL"] = previous_db


def test_financial_invoices_list_renders_backend_rows() -> None:
    invoice = _invoice()
    InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices([invoice]))

    result = _RUNNER.invoke(financial_app, ["invoices", "list"])

    assert result.exit_code == 0, result.output
    assert invoice.invoice_id in result.output
    assert invoice.counterparty_name in result.output


def test_financial_invoices_show_missing_id_exits_two() -> None:
    result = _RUNNER.invoke(financial_app, ["invoices", "show", "missing"])

    assert result.exit_code == 2
    assert "Factura no encontrada" in result.output


def test_financial_invoices_link_renders_backend_result_json() -> None:
    invoice = _invoice()
    transaction = _transaction()
    InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices([invoice]))
    TransactionCatalogueRepository().save(TransactionCatalogue.from_transactions([transaction]))

    result = _RUNNER.invoke(financial_app, ["invoices", "link", invoice.invoice_id, transaction.transaction_id])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["invoice_id"] == invoice.invoice_id
    assert payload["linked_transaction_ids"] == [transaction.transaction_id]


def test_financial_invoices_reconcile_renders_backend_suggestions() -> None:
    invoice = _invoice()
    transaction = _transaction()
    InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices([invoice]))
    TransactionCatalogueRepository().save(TransactionCatalogue.from_transactions([transaction]))

    result = _RUNNER.invoke(financial_app, ["invoices", "reconcile"])

    assert result.exit_code == 0, result.output
    assert invoice.invoice_id in result.output
    assert transaction.transaction_id in result.output


def _invoice() -> Invoice:
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-CLI-001",
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
                        "description": "Service",
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
            provider_name="csv",
        ),
        raw_fields={"Concepto": "payment"},
    )
    return Transaction.model_validate({"raw": raw, "direction": TransactionDirection.INCOMING})
