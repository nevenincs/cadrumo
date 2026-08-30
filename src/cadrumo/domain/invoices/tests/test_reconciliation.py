"""Unit tests for the reconciliation heuristic and bidirectional linking."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ....application.invoices import link_invoice_transaction_repositories
from ....core import LinkInconsistencyDirection
from ...iva.classification import InvoiceKind
from ...transactions.enums import TransactionDirection
from ...transactions.models import Transaction, TransactionCatalogue
from ...transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..enums import IvaRate, PaymentStatus
from ..models import Invoice, InvoiceCatalogue, InvoiceLine
from ..service import (
    suggest_reconciliations,
    verify_link_consistency,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_ID = "18181818-1818-4181-8181-181818181818"


_active_bucket_runtime = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=True, name="_active_bucket_runtime")


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
        },
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
        },
    )


def _transaction(
    *,
    provider_id: str,
    amount: Decimal,
    counterparty: str | None = "Cliente SL",
    invoice_id: str | None = None,
    direction: TransactionDirection = TransactionDirection.INCOMING,
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
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
        "direction": direction,
        "source_jurisdiction": "ES",
        "group_label": None,
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


def test_received_invoice_matches_outgoing_transaction() -> None:
    """RECEIVED invoices should match OUTGOING transactions by magnitude."""
    invoice = _invoice(kind=InvoiceKind.RECEIVED, counterparty_name="Proveedor SL")
    transaction = _transaction(
        provider_id="row-1",
        amount=Decimal("121.00"),
        counterparty="Proveedor SL",
        direction=TransactionDirection.OUTGOING,
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
    assert {LinkInconsistencyDirection.INVOICE_ONLY, LinkInconsistencyDirection.TRANSACTION_ONLY} <= directions
    assert any(item.transaction_id == hex_a for item in inconsistencies)
    assert any(item.transaction_id == transaction.transaction_id for item in inconsistencies)


def test_link_bidirectional_updates_both_catalogues() -> None:
    """The happy path writes both catalogues with the link in place."""
    invoice = _invoice()
    transaction = _transaction(
        provider_id="row-1",
        amount=Decimal("121.00"),
        counterparty="Cliente SL",
    )
    InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices([invoice]))
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID).save(TransactionCatalogue.from_transactions([transaction]))

    result = link_invoice_transaction_repositories(
        bucket_id=_BUCKET_ID,
        invoice_id=invoice.invoice_id,
        transaction_id=transaction.transaction_id,
    )
    updated_invoices = result.invoices
    updated_transactions = result.transactions

    updated_invoice = updated_invoices.get(invoice.invoice_id)
    updated_transaction = updated_transactions.get(transaction.transaction_id)
    assert updated_invoice is not None
    assert updated_transaction is not None
    assert transaction.transaction_id in updated_invoice.linked_transaction_ids
    assert updated_transaction.invoice_id == invoice.invoice_id

    # Catalogues persisted in the secure backend agree with the returned values.
    reloaded = TransactionCatalogueRepository(bucket_id=_BUCKET_ID).load()
    assert reloaded.get(transaction.transaction_id) == updated_transaction
