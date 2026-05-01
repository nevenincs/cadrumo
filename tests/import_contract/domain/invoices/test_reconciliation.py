"""Unit tests for the reconciliation heuristic and bidirectional linking."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from aeat.adapters.inbound.financial import RawProvenance, SourceFormat
from aeat.adapters.inbound.financial.providers import RawTransaction
from aeat.domain.transactions import (
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from aeat.domain.transactions import TransactionCatalogueRepository
from aeat.domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceKind,
    InvoiceLine,
    link_transaction_bidirectional,
    InvoiceLinkError,
    InvoiceLinkInconsistencyError,
    IvaRate,
    PaymentStatus,
    suggest_reconciliations,
    verify_link_consistency,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


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


def _invoice(
    *,
    kind: InvoiceKind = InvoiceKind.ISSUED,
    invoice_number: str = "INV-001",
    counterparty_name: str = "Cliente SL",
    counterparty_tax_id: str = "B12345674",
    counterparty_country: str = "ES",
    grand_total: Decimal = Decimal("121.00"),
    linked_transaction_ids: tuple[str, ...] = (),
) -> Invoice:
    subtotal = (grand_total / Decimal("1.21")).quantize(Decimal("0.01"))
    iva_amount = grand_total - subtotal
    line = InvoiceLine.model_validate(
        {
            "description": "Service",
            "quantity": Decimal("1"),
            "unit_price": subtotal,
            "subtotal": subtotal,
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": iva_amount,
        }
    )
    return Invoice.model_validate(
        {
            "kind": kind,
            "invoice_number": invoice_number,
            "issued_at": date(2026, 4, 1),
            "counterparty_name": counterparty_name,
            "counterparty_tax_id": counterparty_tax_id,
            "counterparty_country": counterparty_country,
            "base_total": subtotal,
            "iva_total": iva_amount,
            "grand_total": grand_total,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": linked_transaction_ids,
        }
    )


def _transaction(
    *,
    provider_id: str,
    amount: Decimal,
    counterparty: str | None = "Cliente SL",
    invoice_id: str | None = None,
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
    payload: dict[str, object] = {
        "raw": raw,
        "direction": (TransactionDirection.INCOMING if amount > 0 else TransactionDirection.OUTGOING),
    }
    if invoice_id is not None:
        payload["invoice_id"] = invoice_id
    return Transaction.model_validate(payload)


def test_issued_invoice_matches_positive_incoming_transaction() -> None:
    """ISSUED invoices should match positive transaction amounts."""
    invoice = _invoice(counterparty_name="Cliente SL")
    transaction = _transaction(
        provider_id="row-1",
        amount=Decimal("121.00"),
        counterparty="Cliente SL",
    )
    suggestions = suggest_reconciliations(
        InvoiceCatalogue.from_invoices([invoice]),
        TransactionCatalogue.from_transactions([transaction]),
    )
    assert len(suggestions) == 1
    assert suggestions[0].invoice_id == invoice.invoice_id
    assert suggestions[0].transaction_id == transaction.transaction_id
    assert suggestions[0].score == Decimal("1.0")


def test_received_invoice_matches_negative_outgoing_transaction() -> None:
    """RECEIVED invoices should match negative transaction amounts."""
    invoice = _invoice(kind=InvoiceKind.RECEIVED, counterparty_name="Proveedor SL")
    transaction = _transaction(
        provider_id="row-1",
        amount=Decimal("-121.00"),
        counterparty="Proveedor SL",
    )
    suggestions = suggest_reconciliations(
        InvoiceCatalogue.from_invoices([invoice]),
        TransactionCatalogue.from_transactions([transaction]),
    )
    assert len(suggestions) == 1
    assert suggestions[0].score == Decimal("1.0")


def test_amount_match_without_counterparty_scores_half() -> None:
    """A counterparty mismatch still emits a score-0.5 suggestion when amounts align."""
    invoice = _invoice(counterparty_name="Very Specific Customer Name")
    transaction = _transaction(
        provider_id="row-1",
        amount=Decimal("121.00"),
        counterparty="Some Other Name",
    )
    suggestions = suggest_reconciliations(
        InvoiceCatalogue.from_invoices([invoice]),
        TransactionCatalogue.from_transactions([transaction]),
    )
    assert len(suggestions) == 1
    assert suggestions[0].amount_match is True
    assert suggestions[0].counterparty_match is False
    assert suggestions[0].score == Decimal("0.5")


def test_none_counterparty_does_not_boost_score() -> None:
    """A transaction without a counterparty must not score a false-positive boost.

    Guards against the regression where an empty-string counterparty would
    make ``invoice_counterparty in tx_normalised`` evaluate ``True`` and
    grant an undeserved 0.5 score.
    """
    invoice = _invoice(counterparty_name="Cliente SL")
    transaction = _transaction(
        provider_id="row-none",
        amount=Decimal("121.00"),
        counterparty=None,
    )
    suggestions = suggest_reconciliations(
        InvoiceCatalogue.from_invoices([invoice]),
        TransactionCatalogue.from_transactions([transaction]),
    )
    assert len(suggestions) == 1
    assert suggestions[0].counterparty_match is False
    assert suggestions[0].score == Decimal("0.5")


def test_counterparty_only_match_emits_no_suggestion() -> None:
    """Counterparty-only matches are never emitted (would be too noisy)."""
    invoice = _invoice(counterparty_name="Cliente SL")
    transaction = _transaction(
        provider_id="row-1",
        amount=Decimal("999.00"),
        counterparty="Cliente SL",
    )
    assert (
        suggest_reconciliations(
            InvoiceCatalogue.from_invoices([invoice]),
            TransactionCatalogue.from_transactions([transaction]),
        )
        == ()
    )


def test_already_linked_items_are_excluded() -> None:
    """Linked invoices and transactions do not appear in suggestions."""
    hex_a = "a" * 64
    linked_invoice = _invoice(invoice_number="INV-001", linked_transaction_ids=(hex_a,))
    unlinked_invoice = _invoice(invoice_number="INV-002")
    linked_transaction = _transaction(
        provider_id="row-1",
        amount=Decimal("121.00"),
        counterparty="Cliente SL",
        invoice_id=linked_invoice.invoice_id,
    )
    unlinked_transaction = _transaction(
        provider_id="row-2",
        amount=Decimal("121.00"),
        counterparty="Cliente SL",
    )
    suggestions = suggest_reconciliations(
        InvoiceCatalogue.from_invoices([linked_invoice, unlinked_invoice]),
        TransactionCatalogue.from_transactions([linked_transaction, unlinked_transaction]),
    )
    assert all(s.invoice_id == unlinked_invoice.invoice_id for s in suggestions)
    assert all(s.transaction_id == unlinked_transaction.transaction_id for s in suggestions)


def test_suggestion_ordering_is_deterministic() -> None:
    """Suggestions must sort by (score desc, invoice_id asc, transaction_id asc)."""
    invoice_a = _invoice(invoice_number="INV-001", counterparty_name="Cliente SL")
    invoice_b = _invoice(invoice_number="INV-002", counterparty_name="Cliente SL")
    tx_a = _transaction(provider_id="row-a", amount=Decimal("121.00"), counterparty="Cliente SL")
    tx_b = _transaction(provider_id="row-b", amount=Decimal("121.00"), counterparty=None)
    suggestions = suggest_reconciliations(
        InvoiceCatalogue.from_invoices([invoice_b, invoice_a]),
        TransactionCatalogue.from_transactions([tx_b, tx_a]),
    )
    # high-score suggestions (score 1.0 with tx_a) come first
    assert suggestions[0].score == Decimal("1.0")
    # within equal scores, sorted ascending by invoice_id
    scores = [s.score for s in suggestions]
    assert scores == sorted(scores, reverse=True)


def test_verify_link_consistency_detects_one_sided_links() -> None:
    """verify_link_consistency must find invoice-only and transaction-only drifts."""
    hex_a = "a" * 64
    invoice = _invoice(invoice_number="INV-001", linked_transaction_ids=(hex_a,))
    # transaction B claims the invoice but the invoice does not carry it.
    transaction = _transaction(
        provider_id="row-b",
        amount=Decimal("121.00"),
        counterparty="Cliente SL",
        invoice_id=invoice.invoice_id,
    )
    inconsistencies = verify_link_consistency(
        InvoiceCatalogue.from_invoices([invoice]),
        TransactionCatalogue.from_transactions([transaction]),
    )
    directions = {item.direction for item in inconsistencies}
    assert {"invoice-only", "transaction-only"} <= directions
    assert any(item.transaction_id == hex_a for item in inconsistencies)
    assert any(item.transaction_id == transaction.transaction_id for item in inconsistencies)


def test_link_bidirectional_updates_both_files(tmp_path: Path) -> None:
    """The happy path writes both catalogues with the link in place."""
    invoice = _invoice()
    transaction = _transaction(
        provider_id="row-1",
        amount=Decimal("121.00"),
        counterparty="Cliente SL",
    )
    invoices_dir = tmp_path / "invoices"
    transactions_dir = tmp_path / "transactions"
    InvoiceCatalogueRepository(store_dir=invoices_dir).save(InvoiceCatalogue.from_invoices([invoice]))
    TransactionCatalogueRepository(store_dir=transactions_dir).save(
        TransactionCatalogue.from_transactions([transaction]),
    )

    updated_invoices, updated_transactions = link_transaction_bidirectional(
        invoices_dir, transactions_dir, invoice.invoice_id, transaction.transaction_id
    )

    updated_invoice = updated_invoices.get(invoice.invoice_id)
    updated_transaction = updated_transactions.get(transaction.transaction_id)
    assert updated_invoice is not None
    assert updated_transaction is not None
    assert transaction.transaction_id in updated_invoice.linked_transaction_ids
    assert updated_transaction.invoice_id == invoice.invoice_id

    # Catalogues on disk agree with the returned in-memory values.
    reloaded = TransactionCatalogueRepository(store_dir=transactions_dir).load()
    assert reloaded.get(transaction.transaction_id) == updated_transaction


def test_link_bidirectional_restores_invoice_on_transaction_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the transaction write fails, the invoice envelope must be restored."""
    invoice = _invoice()
    transaction = _transaction(
        provider_id="row-1",
        amount=Decimal("121.00"),
        counterparty="Cliente SL",
    )
    invoices_dir = tmp_path / "invoices"
    transactions_dir = tmp_path / "transactions"
    InvoiceCatalogueRepository(store_dir=invoices_dir).save(InvoiceCatalogue.from_invoices([invoice]))
    TransactionCatalogueRepository(store_dir=transactions_dir).save(
        TransactionCatalogue.from_transactions([transaction]),
    )
    invoices_envelope = InvoiceCatalogueRepository(store_dir=invoices_dir).envelope_path
    prior_invoice_bytes = invoices_envelope.read_bytes()

    from aeat.domain.transactions import TransactionPersistenceError

    def _fail_save(self: object, catalogue: object) -> None:
        del self, catalogue
        raise TransactionPersistenceError("simulated failure")

    monkeypatch.setattr(TransactionCatalogueRepository, "save", _fail_save)

    with pytest.raises(InvoiceLinkError):
        link_transaction_bidirectional(
            invoices_dir,
            transactions_dir,
            invoice.invoice_id,
            transaction.transaction_id,
        )

    # The invoice envelope must be restored to its pre-update bytes.
    assert invoices_envelope.read_bytes() == prior_invoice_bytes


def test_link_bidirectional_raises_inconsistency_when_restore_also_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both the tx write and the invoice rollback fail, an inconsistency is raised."""
    invoice = _invoice()
    transaction = _transaction(
        provider_id="row-1",
        amount=Decimal("121.00"),
        counterparty="Cliente SL",
    )
    invoices_dir = tmp_path / "invoices"
    transactions_dir = tmp_path / "transactions"
    InvoiceCatalogueRepository(store_dir=invoices_dir).save(InvoiceCatalogue.from_invoices([invoice]))
    TransactionCatalogueRepository(store_dir=transactions_dir).save(
        TransactionCatalogue.from_transactions([transaction]),
    )
    invoices_envelope = InvoiceCatalogueRepository(store_dir=invoices_dir).envelope_path
    transactions_envelope = TransactionCatalogueRepository(store_dir=transactions_dir).envelope_path

    from aeat.domain.transactions import TransactionPersistenceError

    def _fail_save(self: object, catalogue: object) -> None:
        del self, catalogue
        raise TransactionPersistenceError("simulated failure")

    monkeypatch.setattr(TransactionCatalogueRepository, "save", _fail_save)

    def _fail_write_bytes(path: Path, payload: bytes) -> None:
        del path, payload
        raise OSError("simulated rollback failure")

    with pytest.raises(InvoiceLinkInconsistencyError) as excinfo:
        link_transaction_bidirectional(
            invoices_dir,
            transactions_dir,
            invoice.invoice_id,
            transaction.transaction_id,
            rollback_temp_writer=_fail_write_bytes,
        )

    error = excinfo.value
    assert error.invoice_path == invoices_envelope
    assert error.transactions_path == transactions_envelope
    assert error.invoice_id == invoice.invoice_id
    assert error.transaction_id == transaction.transaction_id
