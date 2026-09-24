"""An edit to a linked ledger row keeps the row's half of the invoice link.

The edit path rebuilds the transaction from a command that carries no invoice
reference, so reclassifying a linked row once stored it unlinked while the
invoice catalogue still named it: the one-sided state link verification
reports, produced by an ordinary classify.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from .....application.ledger.actions_manual import create_manual_transaction, update_manual_transaction_fields
from .....application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from .....domain.transactions.enums import BusinessClassification, TransactionDirection
from .....domain.transactions.errors import TransactionValidationError
from .....domain.transactions.service import link_invoice
from ...storage.sql.secure_objects import SecureObjectRepository
from .ledger_action_create_support import ledger_ports_for_test
from .ledger_action_persistence_support import (
    BUCKET_ID as _BUCKET_ID,
    repositories as _repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_INVOICE_ID = "a" * 64


def _linked_row(secure_objects: SecureObjectRepository) -> str:
    transaction_repository, event_repository = _repositories(secure_objects)
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 1, 8),
                amount=Decimal("59.29"),
                direction=TransactionDirection.OUTGOING,
                description="CARGO SUSCRIPCION NUBE SOFTWARE",
                idempotency_key="linked-row",
            ),
            ports=ports,
            occurred_at=datetime(2026, 1, 8, 9, 0, tzinfo=UTC),
        )
    transaction_id = created.ref.transaction_id
    transaction_repository.save(link_invoice(transaction_repository.load(), transaction_id, _INVOICE_ID))
    return transaction_id


def _classify(secure_objects: SecureObjectRepository, transaction_id: str) -> tuple[str, int]:
    transaction_repository, event_repository = _repositories(secure_objects)
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        result = update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=transaction_id,
            patch=ManualLedgerTransactionPatch(business_classification=BusinessClassification.PERSONAL),
            actor="test",
            source_command="aeat app ledger classify",
            ports=ports,
            occurred_at=datetime(2026, 1, 9, 9, 0, tzinfo=UTC),
        )
    return result.ref.transaction_id, len(result.bucket_event_ids)


def test_classifying_a_linked_row_keeps_its_invoice_link(secure_objects: SecureObjectRepository) -> None:
    """DISCRIMINATING: the stored row still names its invoice after a classify."""
    transaction_id = _linked_row(secure_objects)

    classified_id, _ = _classify(secure_objects, transaction_id)

    transaction_repository, _ = _repositories(secure_objects)
    stored = transaction_repository.load().transactions[classified_id]
    assert stored.business_classification is BusinessClassification.PERSONAL
    assert stored.invoice_id == _INVOICE_ID


def test_repeating_the_classify_stays_a_no_op(secure_objects: SecureObjectRepository) -> None:
    """ANTI-VACUITY: carrying the link forward does not turn a repeat into a write."""
    transaction_id = _linked_row(secure_objects)
    classified_id, first_events = _classify(secure_objects, transaction_id)

    _, repeat_events = _classify(secure_objects, classified_id)

    assert first_events > 0
    assert repeat_events == 0


def test_changing_a_linked_rows_identity_refuses_without_replacing_it(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_id = _linked_row(secure_objects)
    transaction_repository, event_repository = _repositories(secure_objects)
    before = transaction_repository.load()

    with (
        ledger_ports_for_test(
            bucket_id=_BUCKET_ID,
            objects=secure_objects,
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        ) as ports,
        pytest.raises(TransactionValidationError, match="invoice link"),
    ):
        update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=transaction_id,
            patch=ManualLedgerTransactionPatch(amount=Decimal("60.00")),
            actor="test",
            source_command="aeat app ledger update",
            ports=ports,
            occurred_at=datetime(2026, 1, 10, 9, 0, tzinfo=UTC),
        )

    assert transaction_repository.load() == before
