"""CLI smoke tests for ``aeat financial invoices`` and ``aeat invoices``."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from ....entrypoints.cli import app as root_app
from .. import RawProvenance, SourceFormat
from ..providers import RawTransaction
from ..transactions import (
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ..transactions._repository import TransactionCatalogueRepository
from ._enums import InvoiceKind, IvaRate, PaymentStatus
from ._models import Invoice, InvoiceCatalogue, InvoiceLine
from ._repository import InvoiceCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]

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


def _seed_environment(tmp_path: Path) -> tuple[InvoiceCatalogue, TransactionCatalogue, dict[str, str]]:
    invoices_dir = tmp_path / "invoices"
    transactions_dir = tmp_path / "transactions"
    invoices_dir.mkdir()
    transactions_dir.mkdir()
    invoice_catalogue = InvoiceCatalogue.from_invoices(
        [
            _make_invoice(invoice_number="INV-001"),
            _make_invoice(invoice_number="INV-002", kind=InvoiceKind.RECEIVED),
        ]
    )
    transaction_catalogue = TransactionCatalogue.from_transactions([_make_transaction()])
    InvoiceCatalogueRepository(store_dir=invoices_dir).save(invoice_catalogue)
    TransactionCatalogueRepository(store_dir=transactions_dir).save(transaction_catalogue)
    env = {
        "AEAT_INVOICES_DIR": str(invoices_dir),
        "AEAT_FINANCIAL_TXS_DIR": str(transactions_dir),
    }
    return invoice_catalogue, transaction_catalogue, env


def test_financial_invoices_list_emits_full_catalogue(tmp_path: Path) -> None:
    """`aeat financial invoices list` must print every stored invoice."""
    invoices, _, env = _seed_environment(tmp_path)
    result = _RUNNER.invoke(root_app, ["financial", "invoices", "list"], env=env)
    assert result.exit_code == 0, result.output
    for invoice in invoices.values():
        assert invoice.invoice_id in result.output


def test_financial_invoices_list_filters_by_kind(tmp_path: Path) -> None:
    """`--kind issued` filters to ISSUED invoices only."""
    invoices, _, env = _seed_environment(tmp_path)
    result = _RUNNER.invoke(root_app, ["financial", "invoices", "list", "--kind", "ISSUED"], env=env)
    assert result.exit_code == 0, result.output
    issued_ids = [invoice.invoice_id for invoice in invoices.values() if invoice.kind is InvoiceKind.ISSUED]
    received_ids = [invoice.invoice_id for invoice in invoices.values() if invoice.kind is InvoiceKind.RECEIVED]
    for invoice_id in issued_ids:
        assert invoice_id in result.output
    for invoice_id in received_ids:
        assert invoice_id not in result.output


def test_financial_invoices_show_emits_json(tmp_path: Path) -> None:
    """`aeat financial invoices show <id>` must emit the stored invoice JSON."""
    invoices, _, env = _seed_environment(tmp_path)
    invoice = next(invoices.values())
    result = _RUNNER.invoke(root_app, ["financial", "invoices", "show", invoice.invoice_id], env=env)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["invoice_id"] == invoice.invoice_id


def test_financial_invoices_show_missing_id_exits_two(tmp_path: Path) -> None:
    """Missing invoice ID must exit code 2."""
    _, _, env = _seed_environment(tmp_path)
    result = _RUNNER.invoke(root_app, ["financial", "invoices", "show", "missing"], env=env)
    assert result.exit_code == 2


def test_financial_invoices_link_updates_both_files(tmp_path: Path) -> None:
    """`aeat financial invoices link` must update both catalogues on disk."""
    invoices, transactions, env = _seed_environment(tmp_path)
    invoice = next(invoices.values())
    transaction = next(transactions.values())

    result = _RUNNER.invoke(
        root_app,
        ["financial", "invoices", "link", invoice.invoice_id, transaction.transaction_id],
        env=env,
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert transaction.transaction_id in payload["linked_transaction_ids"]

    updated_invoices = InvoiceCatalogueRepository(store_dir=tmp_path / "invoices").load()
    updated_invoice = updated_invoices.get(invoice.invoice_id)
    assert updated_invoice is not None
    assert transaction.transaction_id in updated_invoice.linked_transaction_ids


def test_financial_invoices_reconcile_prints_suggestions(tmp_path: Path) -> None:
    """`aeat financial invoices reconcile` prints the suggestion table."""
    _, transactions, env = _seed_environment(tmp_path)
    transaction = next(transactions.values())

    result = _RUNNER.invoke(root_app, ["financial", "invoices", "reconcile"], env=env)
    assert result.exit_code == 0, result.output
    assert transaction.transaction_id in result.output


def test_financial_invoices_reconcile_apply_persists_links(tmp_path: Path) -> None:
    """`reconcile --apply` performs the bidirectional link on each match."""
    _, transactions, env = _seed_environment(tmp_path)
    transaction = next(transactions.values())

    result = _RUNNER.invoke(root_app, ["financial", "invoices", "reconcile", "--apply"], env=env)
    assert result.exit_code == 0, result.output

    updated = InvoiceCatalogueRepository(store_dir=tmp_path / "invoices").load()
    assert any(transaction.transaction_id in invoice.linked_transaction_ids for invoice in updated.values())


def test_financial_invoices_verify_exits_zero_when_consistent(tmp_path: Path) -> None:
    """`aeat financial invoices verify` exits 0 when no drift exists."""
    _, _, env = _seed_environment(tmp_path)
    result = _RUNNER.invoke(root_app, ["financial", "invoices", "verify"], env=env)
    assert result.exit_code == 0, result.output


def test_financial_invoices_verify_exits_two_when_drifted(tmp_path: Path) -> None:
    """`verify` must exit code 2 when the two catalogues disagree."""
    env_initial = _seed_environment(tmp_path)
    _, transactions, env = env_initial
    transaction = next(transactions.values())

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
    InvoiceCatalogueRepository(store_dir=tmp_path / "invoices").save(
        InvoiceCatalogue.from_invoices([drifted]),
    )

    result = _RUNNER.invoke(root_app, ["financial", "invoices", "verify"], env=env)
    assert result.exit_code == 2, result.output


def test_financial_invoices_unmatched_lists_unlinked_invoices(tmp_path: Path) -> None:
    """`aeat financial invoices unmatched` prints invoices without transactions."""
    invoices, _, env = _seed_environment(tmp_path)
    result = _RUNNER.invoke(root_app, ["financial", "invoices", "unmatched"], env=env)
    assert result.exit_code == 0, result.output
    for invoice in invoices.values():
        assert invoice.invoice_id in result.output


def test_top_level_invoices_alias_works(tmp_path: Path) -> None:
    """`aeat invoices list` (top-level alias) must match the nested command."""
    invoices, _, env = _seed_environment(tmp_path)
    invoice = next(invoices.values())
    result = _RUNNER.invoke(root_app, ["invoices", "show", invoice.invoice_id], env=env)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["invoice_id"] == invoice.invoice_id
