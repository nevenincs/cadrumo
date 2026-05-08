"""CLI smoke tests for ``aeat financial invoices``."""

from __future__ import annotations

import json
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
from aeat.entrypoints.cli.financial import app as financial_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_RUNNER = CliRunner()


@pytest.fixture(autouse=True)
def _patch_master_key(tmp_path: Path) -> Iterator[None]:
    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
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
        yield
    finally:
        override_master_key_provider(None)
        override_secret_store(None)


def _make_invoice(
    *,
    kind: InvoiceKind = InvoiceKind.ISSUED,
    invoice_number: str = "INV-001",
    counterparty_name: str = "Cliente SL",
    linked_transaction_ids: tuple[str, ...] = (),
) -> Invoice:
    line = InvoiceLine.model_validate(
        {
            "description": "Service",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.00"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("21.00"),
        }
    )
    return Invoice.model_validate(
        {
            "kind": kind,
            "invoice_number": invoice_number,
            "issued_at": date(2026, 4, 1),
            "counterparty_name": counterparty_name,
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": linked_transaction_ids,
        }
    )


def _make_transaction(
    *,
    provider_id: str = "row-1",
    amount: Decimal = Decimal("121.00"),
    counterparty: str | None = "Cliente SL",
) -> Transaction:
    raw = RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2026, 4, 5),
        value_date=date(2026, 4, 5),
        amount=amount,
        currency="EUR",
        counterparty=counterparty,
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
    direction = TransactionDirection.INCOMING if amount > 0 else TransactionDirection.OUTGOING
    return Transaction.model_validate({"raw": raw, "direction": direction})


def _seed_catalogues() -> tuple[InvoiceCatalogue, TransactionCatalogue]:
    invoice_catalogue = InvoiceCatalogue.from_invoices(
        [
            _make_invoice(invoice_number="INV-001"),
            _make_invoice(invoice_number="INV-002", kind=InvoiceKind.RECEIVED),
        ]
    )
    transaction_catalogue = TransactionCatalogue.from_transactions([_make_transaction()])
    InvoiceCatalogueRepository().save(invoice_catalogue)
    TransactionCatalogueRepository().save(transaction_catalogue)
    return invoice_catalogue, transaction_catalogue


def test_financial_invoices_list_emits_full_catalogue() -> None:
    """`aeat financial invoices list` must print every stored invoice."""
    invoices, _ = _seed_catalogues()
    result = _RUNNER.invoke(financial_app, ["invoices", "list"])
    assert result.exit_code == 0, result.output
    for invoice in invoices.values():
        assert invoice.invoice_id in result.output


def test_financial_invoices_list_filters_by_kind() -> None:
    """`--kind issued` filters to ISSUED invoices only."""
    invoices, _ = _seed_catalogues()
    result = _RUNNER.invoke(financial_app, ["invoices", "list", "--kind", "ISSUED"])
    assert result.exit_code == 0, result.output
    issued_ids = [invoice.invoice_id for invoice in invoices.values() if invoice.kind is InvoiceKind.ISSUED]
    received_ids = [invoice.invoice_id for invoice in invoices.values() if invoice.kind is InvoiceKind.RECEIVED]
    for invoice_id in issued_ids:
        assert invoice_id in result.output
    for invoice_id in received_ids:
        assert invoice_id not in result.output


def test_financial_invoices_show_emits_json() -> None:
    """`aeat financial invoices show <id>` must emit the stored invoice JSON."""
    invoices, _ = _seed_catalogues()
    invoice = next(iter(invoices.values()))
    result = _RUNNER.invoke(financial_app, ["invoices", "show", invoice.invoice_id])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["invoice_id"] == invoice.invoice_id


def test_financial_invoices_show_missing_id_exits_two() -> None:
    """Missing invoice ID must exit code 2."""
    _seed_catalogues()
    result = _RUNNER.invoke(financial_app, ["invoices", "show", "missing"])
    assert result.exit_code == 2


def test_financial_invoices_link_updates_both_files() -> None:
    """`aeat financial invoices link` must update both catalogues on disk."""
    invoices, transactions = _seed_catalogues()
    invoice = next(iter(invoices.values()))
    transaction = next(iter(transactions.values()))

    result = _RUNNER.invoke(
        financial_app,
        ["invoices", "link", invoice.invoice_id, transaction.transaction_id],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert transaction.transaction_id in payload["linked_transaction_ids"]

    updated_invoices = InvoiceCatalogueRepository().load()
    updated_invoice = updated_invoices.get(invoice.invoice_id)
    assert updated_invoice is not None
    assert transaction.transaction_id in updated_invoice.linked_transaction_ids


def test_financial_invoices_reconcile_prints_suggestions() -> None:
    """`aeat financial invoices reconcile` prints the suggestion table."""
    _, transactions = _seed_catalogues()
    transaction = next(iter(transactions.values()))

    result = _RUNNER.invoke(financial_app, ["invoices", "reconcile"])
    assert result.exit_code == 0, result.output
    assert transaction.transaction_id in result.output


def test_financial_invoices_reconcile_apply_persists_links() -> None:
    """`reconcile --apply` performs the bidirectional link on each match."""
    _, transactions = _seed_catalogues()
    transaction = next(iter(transactions.values()))

    result = _RUNNER.invoke(financial_app, ["invoices", "reconcile", "--apply"])
    assert result.exit_code == 0, result.output

    updated = InvoiceCatalogueRepository().load()
    assert any(transaction.transaction_id in invoice.linked_transaction_ids for invoice in updated.values())


def test_financial_invoices_verify_exits_zero_when_consistent() -> None:
    """`aeat financial invoices verify` exits 0 when no drift exists."""
    _seed_catalogues()
    result = _RUNNER.invoke(financial_app, ["invoices", "verify"])
    assert result.exit_code == 0, result.output


def test_financial_invoices_verify_exits_two_when_drifted() -> None:
    """`verify` must exit code 2 when the two catalogues disagree."""
    _, transactions = _seed_catalogues()
    transaction = next(iter(transactions.values()))

    # Build a drifted invoice that cites the transaction; transaction side does not.
    drifted_line = InvoiceLine.model_validate(
        {
            "description": "Drift",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.00"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("21.00"),
        }
    )
    drifted = Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-004",
            "issued_at": date(2026, 4, 1),
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (drifted_line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": (transaction.transaction_id,),
        }
    )
    InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices([drifted]))

    result = _RUNNER.invoke(financial_app, ["invoices", "verify"])
    assert result.exit_code == 2, result.output


def test_financial_invoices_unmatched_lists_unlinked_invoices() -> None:
    """`aeat financial invoices unmatched` prints invoices without transactions."""
    invoices, _ = _seed_catalogues()
    result = _RUNNER.invoke(financial_app, ["invoices", "unmatched"])
    assert result.exit_code == 0, result.output
    for invoice in invoices.values():
        assert invoice.invoice_id in result.output
