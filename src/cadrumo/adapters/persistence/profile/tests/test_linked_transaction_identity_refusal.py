"""Encrypted persistence proof for refused linked transaction identity edits."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from .....application.ledger.actions_manual import (
    create_manual_transaction,
    link_manual_transaction_invoice,
    update_manual_transaction_fields,
)
from .....application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from .....application.ledger.persistence_ports import LedgerPersistenceConflictError
from .....domain.buckets.event import BucketEventHistoryCatalogue
from .....domain.invoices.tests.catalogue_support import build_invoice_catalogue
from .....domain.transactions.enums import TransactionDirection
from .....domain.transactions.errors import TransactionValidationError
from ...storage.sql.secure_objects import SecureObjectRepository
from ..buckets import BucketEventHistoryRepository
from ..invoices import InvoiceCatalogueRepository
from ..transactions import TransactionCatalogueRepository
from .ledger_action_create_support import ledger_ports_for_test
from .ledger_action_persistence_support import (
    BUCKET_ID as _BUCKET_ID,
)
from .ledger_action_persistence_support import (
    purchase_invoice,
)
from .ledger_action_persistence_support import (
    repositories as _repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]


def _persist_linked_transaction(secure_objects: SecureObjectRepository) -> tuple[str, str]:
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice = purchase_invoice()
    invoice_repository.save(build_invoice_catalogue((invoice,)))
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
    ) as ports:
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 2),
                amount=Decimal("59.29"),
                direction=TransactionDirection.OUTGOING,
                description="CARGO SUSCRIPCION NUBE SOFTWARE",
                idempotency_key="linked-identity-refusal",
            ),
            ports=ports,
            occurred_at=datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
        )
        link_manual_transaction_invoice(
            bucket_id=_BUCKET_ID,
            transaction_id=created.ref.transaction_id,
            invoice_id=invoice.invoice_id,
            actor="operator",
            ports=ports,
            occurred_at=datetime(2026, 5, 2, 9, 1, tzinfo=UTC),
        )
    return created.ref.transaction_id, invoice.invoice_id


def test_linked_identity_change_refusal_leaves_encrypted_reciprocal_records_unchanged(
    secure_objects: SecureObjectRepository,
) -> None:
    """Changing a linked row's derived id cannot write either encrypted side."""
    transaction_id, invoice_id = _persist_linked_transaction(secure_objects)
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    before_transactions = transaction_repository.load()
    before_invoices = invoice_repository.load()
    before_events: BucketEventHistoryCatalogue = event_repository.load()
    before_transaction_revision = transaction_repository.load_revision()
    before_invoice_revision = invoice_repository.load_revision()

    with (
        ledger_ports_for_test(
            bucket_id=_BUCKET_ID,
            objects=secure_objects,
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            invoice_repository=invoice_repository,
        ) as ports,
        pytest.raises(
            TransactionValidationError,
            match="linked transaction identity cannot change without updating its invoice link",
        ),
    ):
        update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=transaction_id,
            patch=ManualLedgerTransactionPatch(amount=Decimal("60.00")),
            actor="operator",
            source_command="tui.ledger.transaction.update",
            ports=ports,
            occurred_at=datetime(2026, 5, 2, 9, 2, tzinfo=UTC),
        )

    reopened_transactions = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    reopened_invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    reopened_events = BucketEventHistoryRepository(objects=secure_objects)
    assert reopened_transactions.load() == before_transactions
    assert reopened_invoices.load() == before_invoices
    assert reopened_events.load() == before_events
    assert reopened_transactions.load_revision() == before_transaction_revision
    assert reopened_invoices.load_revision() == before_invoice_revision
    assert (reopened_transaction := reopened_transactions.load().get(transaction_id)) is not None
    assert reopened_transaction.invoice_id == invoice_id
    assert (reopened_invoice := reopened_invoices.load().get(invoice_id)) is not None
    assert reopened_invoice.linked_transaction_ids == (transaction_id,)


def test_stale_opened_linked_detail_cannot_overwrite_the_concurrent_writer(
    secure_objects: SecureObjectRepository,
) -> None:
    """The real guarded write rejects after an opened snapshot becomes stale."""
    transaction_id, invoice_id = _persist_linked_transaction(secure_objects)
    opened_transactions, _opened_events = _repositories(secure_objects)
    opened_catalogue = opened_transactions.load()
    opened = opened_catalogue.get(transaction_id)
    assert opened is not None

    concurrent_transactions, concurrent_events = _repositories(secure_objects)
    concurrent_invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=concurrent_transactions,
        bucket_event_repository=concurrent_events,
        invoice_repository=concurrent_invoices,
    ) as ports:
        concurrent = update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=transaction_id,
            patch=ManualLedgerTransactionPatch(notes="concurrent operator correction"),
            actor="concurrent-operator",
            source_command="tui.ledger.transaction.update",
            ports=ports,
            occurred_at=datetime(2026, 5, 2, 9, 2, tzinfo=UTC),
        )
    assert concurrent.ref.transaction_id == transaction_id

    committed_transactions = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    committed_invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    committed_events = BucketEventHistoryRepository(objects=secure_objects)
    transactions_after_concurrent = committed_transactions.load()
    invoices_after_concurrent = committed_invoices.load()
    events_after_concurrent: BucketEventHistoryCatalogue = committed_events.load()
    transaction_revision_after_concurrent = committed_transactions.load_revision()
    invoice_revision_after_concurrent = committed_invoices.load_revision()
    _events_after_concurrent, event_revision_after_concurrent = committed_events.load_revisioned()

    stale_transactions, stale_events = _repositories(secure_objects)
    stale_invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    with (
        ledger_ports_for_test(
            bucket_id=_BUCKET_ID,
            objects=secure_objects,
            transaction_repository=stale_transactions,
            bucket_event_repository=stale_events,
            invoice_repository=stale_invoices,
        ) as ports,
        pytest.raises(LedgerPersistenceConflictError, match="transaction changed since it was opened"),
    ):
        update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=transaction_id,
            patch=ManualLedgerTransactionPatch(notes="stale operator correction"),
            actor="stale-operator",
            source_command="tui.ledger.transaction.update",
            ports=ports,
            catalogue=opened_catalogue,
            expected_current=opened,
            occurred_at=datetime(2026, 5, 2, 9, 3, tzinfo=UTC),
        )

    reopened_transactions = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    reopened_invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    reopened_events = BucketEventHistoryRepository(objects=secure_objects)
    assert reopened_transactions.load() == transactions_after_concurrent
    assert reopened_invoices.load() == invoices_after_concurrent
    assert reopened_events.load() == events_after_concurrent
    assert reopened_transactions.load_revision() == transaction_revision_after_concurrent
    assert reopened_invoices.load_revision() == invoice_revision_after_concurrent
    assert reopened_events.load_revisioned()[1] == event_revision_after_concurrent
    assert (reopened_transaction := reopened_transactions.load().get(transaction_id)) is not None
    assert reopened_transaction.notes == "concurrent operator correction"
    assert reopened_transaction.invoice_id == invoice_id
    assert (reopened_invoice := reopened_invoices.load().get(invoice_id)) is not None
    assert reopened_invoice.linked_transaction_ids == (transaction_id,)
