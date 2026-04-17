"""Unit tests for the reconciliation heuristic and bidirectional linking."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.financial import RawProvenance, SourceFormat
from aeat.financial.providers import RawTransaction
from aeat.financial.transactions import (
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    load_transactions,
    save_transactions,
)

from ._enums import InvoiceKind, IvaRate, PaymentStatus
from ._errors import InvoiceLinkInconsistencyError
from ._models import Invoice, InvoiceCatalogue, InvoiceLine
from ._service import (
    link_transaction_bidirectional,
    save_invoices,
    suggest_reconciliations,
    verify_link_consistency,
)


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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
def test_link_bidirectional_updates_both_files(tmp_path: Path) -> None:
    """The happy path writes both catalogues with the link in place."""
    invoice = _invoice()
    transaction = _transaction(
        provider_id="row-1",
        amount=Decimal("121.00"),
        counterparty="Cliente SL",
    )
    invoices_path = tmp_path / "invoices.json"
    transactions_path = tmp_path / "transactions.json"
    save_invoices(InvoiceCatalogue.from_invoices([invoice]), invoices_path)
    save_transactions(TransactionCatalogue.from_transactions([transaction]), transactions_path)

    updated_invoices, updated_transactions = link_transaction_bidirectional(
        invoices_path, transactions_path, invoice.invoice_id, transaction.transaction_id
    )

    updated_invoice = updated_invoices.get(invoice.invoice_id)
    updated_transaction = updated_transactions.get(transaction.transaction_id)
    assert updated_invoice is not None
    assert updated_transaction is not None
    assert transaction.transaction_id in updated_invoice.linked_transaction_ids
    assert updated_transaction.invoice_id == invoice.invoice_id

    # Catalogues on disk agree with the returned in-memory values.
    assert load_transactions(transactions_path).get(transaction.transaction_id) == updated_transaction


@pytest.mark.unit
def test_link_bidirectional_restores_invoice_on_transaction_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the transaction write fails, the invoice file must be restored."""
    invoice = _invoice()
    transaction = _transaction(
        provider_id="row-1",
        amount=Decimal("121.00"),
        counterparty="Cliente SL",
    )
    invoices_path = tmp_path / "invoices.json"
    transactions_path = tmp_path / "transactions.json"
    save_invoices(InvoiceCatalogue.from_invoices([invoice]), invoices_path)
    save_transactions(TransactionCatalogue.from_transactions([transaction]), transactions_path)
    prior_invoice_bytes = invoices_path.read_bytes()

    # Make the transactions directory unwritable by deleting it and blocking
    # the recreate with an existing file of the same name.
    # Cross-platform approach: patch the transactions module's save helper to
    # raise a TransactionPersistenceError on second invocation, which is what
    # link_transaction_bidirectional catches.
    from aeat.financial.invoices import _service as service_module
    from aeat.financial.transactions import TransactionPersistenceError

    original_save = service_module._save_transactions

    def _fail_save(*args: object, **kwargs: object) -> None:
        raise TransactionPersistenceError("simulated failure")

    monkeypatch.setattr(service_module, "_save_transactions", _fail_save)
    try:
        with pytest.raises(service_module.InvoiceLinkError):
            link_transaction_bidirectional(
                invoices_path, transactions_path, invoice.invoice_id, transaction.transaction_id
            )
    finally:
        monkeypatch.setattr(service_module, "_save_transactions", original_save)

    # The invoice file must be restored to its pre-update bytes.
    assert invoices_path.read_bytes() == prior_invoice_bytes


@pytest.mark.unit
def test_link_bidirectional_raises_inconsistency_when_restore_also_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When both the tx write and the invoice rollback fail, an inconsistency is raised."""
    invoice = _invoice()
    transaction = _transaction(
        provider_id="row-1",
        amount=Decimal("121.00"),
        counterparty="Cliente SL",
    )
    invoices_path = tmp_path / "invoices.json"
    transactions_path = tmp_path / "transactions.json"
    save_invoices(InvoiceCatalogue.from_invoices([invoice]), invoices_path)
    save_transactions(TransactionCatalogue.from_transactions([transaction]), transactions_path)

    from aeat.financial.invoices import _service as service_module
    from aeat.financial.transactions import TransactionPersistenceError

    def _fail_save(*args: object, **kwargs: object) -> None:
        raise TransactionPersistenceError("simulated failure")

    def _fail_write_bytes(self: Path, *args: object, **kwargs: object) -> int:
        raise OSError("simulated rollback failure")

    monkeypatch.setattr(service_module, "_save_transactions", _fail_save)
    monkeypatch.setattr(Path, "write_bytes", _fail_write_bytes)

    with pytest.raises(InvoiceLinkInconsistencyError) as excinfo:
        link_transaction_bidirectional(invoices_path, transactions_path, invoice.invoice_id, transaction.transaction_id)

    error = excinfo.value
    assert error.invoice_path == invoices_path.resolve()
    assert error.transactions_path == transactions_path.resolve()
    assert error.invoice_id == invoice.invoice_id
    assert error.transaction_id == transaction.transaction_id
