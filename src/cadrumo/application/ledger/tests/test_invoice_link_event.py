"""Audit-trace contract for the sole invoice-linkage writer.

Every neighbouring ledger mutation appends a :class:`BucketEvent`; invoice
linkage did not, so the one verb that binds a transaction to an invoice left
no trace an operator or auditor could later read. These tests pin the event
to the same unit of work as the two catalogue writes, using real adapters
throughout: a real
:class:`~cadrumo.tests.master_key.EphemeralMasterKeyProvider`, a real
SQLite-backed
:class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`, and the
production serializers. The failure injected below is the production
compare-and-swap revision guard, not a substituted component.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.errors import SecureObjectRevisionConflictError
from ....domain.buckets import BucketEventObjectType, BucketEventType
from ....domain.invoices import Invoice, InvoiceCatalogue, InvoiceLine, InvoiceLinkError, IvaRate, PaymentStatus
from ....domain.iva import InvoiceKind
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_runtime_profile
from ...invoices import link_invoice_transaction_catalogues, link_invoice_transaction_repositories
from ..actions_manual import link_manual_transaction_invoice

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "41414141-4141-4141-8141-414141414141"
_STALE_REVISION_ID = "0" * 64
_NOW = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)


def test_link_appends_exactly_one_invoice_linked_event(tmp_path: Path) -> None:
    """A successful link leaves one audit event naming the transaction.

    The event carries the invoice id, the operator's verb, and the mutation
    kind -- identifiers and outcome only, never invoice content.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        invoice, transaction = _seed(profile.bucket_id)
        events = BucketEventHistoryRepository(objects=profile.repository)
        # The profile capsule emits its own bucket-created lifecycle event, so
        # this asserts the DELTA this verb appends rather than an empty log.
        baseline = set(events.load().events)

        link_manual_transaction_invoice(
            bucket_id=profile.bucket_id,
            transaction_id=transaction.transaction_id,
            invoice_id=invoice.invoice_id,
            actor="operator",
            bucket_event_repository=events,
            occurred_at=_NOW,
        )

        appended = tuple(event for key, event in events.load().events.items() if key not in baseline)
        assert len(appended) == 1
        event = appended[0]
        assert event.event_type is BucketEventType.LEDGER_TRANSACTION_INVOICE_LINKED
        assert event.object_type is BucketEventObjectType.LEDGER_TRANSACTION
        assert event.object_id == transaction.transaction_id
        assert event.actor == "operator"
        assert event.payload["invoice_id"] == invoice.invoice_id
        assert event.payload["mutation_kind"] == "invoice_linkage"
        # Invoice content must not leak into the audit trail.
        # Both identifiers are optional on the invoice. If either were absent the
        # membership checks below would pass vacuously, so the leak test would
        # report success while checking nothing.
        assert invoice.counterparty_tax_id is not None
        assert invoice.counterparty_name is not None
        for value in event.payload.values():
            # Rendered rather than narrowed to str: a payload value that is not a
            # string can still carry the identifier inside it, and skipping those
            # would leave the leak this test exists to catch unchecked.
            rendered = value if isinstance(value, str) else repr(value)
            assert invoice.counterparty_tax_id not in rendered
            assert invoice.counterparty_name not in rendered


def test_refused_link_appends_no_event(tmp_path: Path) -> None:
    """A refused link leaves the event history untouched.

    Every rejection fires before the writer builds or commits anything, so a
    refusal cannot leave an audit entry for a link that never happened.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _invoice_unused, transaction = _seed(profile.bucket_id)
        events = BucketEventHistoryRepository(objects=profile.repository)
        baseline = set(events.load().events)

        with pytest.raises(InvoiceLinkError):
            link_manual_transaction_invoice(
                bucket_id=profile.bucket_id,
                transaction_id=transaction.transaction_id,
                invoice_id="no-such-invoice",
                actor="operator",
                bucket_event_repository=events,
                occurred_at=_NOW,
            )

        assert set(events.load().events) == baseline


def test_event_rolls_back_with_the_catalogues_on_a_mid_batch_failure(tmp_path: Path) -> None:
    """A failure inside the composed write leaves no event and no link.

    The event write rides the same batch as the two catalogues, so the
    production revision guard raised mid-batch must roll all three back
    together. Without this, a crash could record a linkage that never landed.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        invoice, transaction = _seed(profile.bucket_id)
        invoices_repo = InvoiceCatalogueRepository(bucket_id=profile.bucket_id)
        transactions_repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        events = BucketEventHistoryRepository(objects=profile.repository)
        baseline = set(events.load().events)
        events.save(events.load())  # give the history row a revision to stale against
        result = link_invoice_transaction_catalogues(
            invoices_repo.load(),
            transactions_repo.load(),
            invoice_id=invoice.invoice_id,
            transaction_id=transaction.transaction_id,
        )
        conflicting_event_write = events.to_secure_object_write(
            events.load(),
            expected_revision_id=_STALE_REVISION_ID,
        )

        with pytest.raises(SecureObjectRevisionConflictError):
            link_invoice_transaction_repositories(
                bucket_id=profile.bucket_id,
                invoice_id=invoice.invoice_id,
                transaction_id=transaction.transaction_id,
                invoice_repository=invoices_repo,
                transaction_repository=transactions_repo,
                extra_writes=(conflicting_event_write,),
            )

        assert result.invoices.get(invoice.invoice_id) is not None  # the link was computed
        stored_invoice = InvoiceCatalogueRepository(bucket_id=profile.bucket_id).load().get(invoice.invoice_id)
        stored_transaction = (
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).load().get(transaction.transaction_id)
        )
        assert stored_invoice is not None
        assert stored_transaction is not None
        assert stored_invoice.linked_transaction_ids == ()
        assert stored_transaction.invoice_id is None
        assert set(events.load().events) == baseline


def _seed(bucket_id: str) -> tuple[Invoice, Transaction]:
    """Persist one unlinked invoice and one unlinked transaction."""
    invoice = _invoice()
    transaction = _transaction()
    InvoiceCatalogueRepository(bucket_id=bucket_id).save(InvoiceCatalogue.from_invoices([invoice]))
    TransactionCatalogueRepository(bucket_id=bucket_id).save(TransactionCatalogue.from_transactions([transaction]))
    return invoice, transaction


def _invoice() -> Invoice:
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-EVENT-1",
            "issued_at": date(2026, 5, 1),
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
        provider_transaction_id="bank-row-event-1",
        booked_date=date(2026, 5, 2),
        value_date=date(2026, 5, 2),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Cliente SL",
        description="Cliente SL",
        provenance=RawProvenance(
            source_path=Path("statement.csv"),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 5, 2, tzinfo=UTC),
            provider_name="csv",
        ),
        raw_fields={"amount": "121.00"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
        },
    )
