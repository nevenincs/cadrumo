"""Attaching evidence records the link on both sides of the provenance pair.

``attach_manual_transaction_evidence`` persists the attachment id into
``Transaction.attachment_ids``, but its verification helper only loaded and
validated the manifest -- it never appended the transaction id to
``Attachment.linked_transaction_ids``. The attachment domain's
``list_attachments(linked_to=...)`` filter therefore could not discover an
attachment that the transaction itself cited, even though the manifest models
the link and the evidence workflow documents the provenance as bidirectional.
Invoice linkage had a dedicated manifest updater; ledger linkage now shares
that same canonical mutation path.

Real encrypted attachment store, real ledger repositories, real bucket-event
history -- no mocks or stubs.
"""

from __future__ import annotations

import pytest

from ....adapters.persistence.storage import AttachmentStore
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.attachments import (
    AttachmentBytesContent,
    AttachmentIngestionRequest,
    AttachmentKind,
    AttachmentSource,
    add_attachment,
    link_attachment_transaction,
    list_attachments,
    load_attachment,
)
from ....domain.transactions.service import find_transaction
from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    Decimal,
    ManualLedgerTransactionCommand,
    TransactionDirection,
    _repositories,
    attach_manual_transaction_evidence,
    create_manual_transaction,
    date,
    datetime,
)
from ._action_test_support import (
    secure_objects as secure_objects,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PDF_BYTES = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\nledger-attachment-back-reference\n%%EOF\n"


def _store(secure_objects: SecureObjectRepository) -> AttachmentStore:
    return AttachmentStore(objects=secure_objects)


def _seed_attachment(secure_objects: SecureObjectRepository, *, marker: bytes) -> str:
    attachment = add_attachment(
        _store(secure_objects),
        content=AttachmentBytesContent(data=_PDF_BYTES + marker),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.INVOICE_PDF,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="operator-evidence",
            mime_type="application/pdf",
            captured_at=datetime(2026, 8, 1, tzinfo=UTC),
            bucket_id=_BUCKET_ID,
        ),
    )
    return attachment.attachment_id


def _seed_transaction(secure_objects: SecureObjectRepository, *, idempotency_key: str) -> str:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            idempotency_key=idempotency_key,
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        attachment_store=_store(secure_objects),
    )
    return created.transaction.transaction_id


def _attach(
    secure_objects: SecureObjectRepository,
    *,
    transaction_id: str,
    attachment_id: str,
) -> str:
    transaction_repository, event_repository = _repositories(secure_objects)
    result = attach_manual_transaction_evidence(
        bucket_id=_BUCKET_ID,
        transaction_id=transaction_id,
        actor="operator",
        attachment_ids=(attachment_id,),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        attachment_store=_store(secure_objects),
    )
    return result.transaction.transaction_id


def test_attaching_records_the_link_on_both_sides(secure_objects: SecureObjectRepository) -> None:
    attachment_id = _seed_attachment(secure_objects, marker=b"a")
    transaction_id = _seed_transaction(secure_objects, idempotency_key="back-ref-1")

    resulting_id = _attach(secure_objects, transaction_id=transaction_id, attachment_id=attachment_id)

    transaction_repository, _ = _repositories(secure_objects)
    reloaded = find_transaction(transaction_repository.load(), resulting_id)
    assert reloaded is not None
    assert attachment_id in reloaded.attachment_ids

    manifest = load_attachment(_store(secure_objects), attachment_id)
    assert resulting_id in manifest.linked_transaction_ids


def test_the_filtered_list_discovers_an_attachment_the_transaction_cites(
    secure_objects: SecureObjectRepository,
) -> None:
    """``list_attachments(linked_to=...)`` is the discovery surface that was blind."""
    attachment_id = _seed_attachment(secure_objects, marker=b"b")
    transaction_id = _seed_transaction(secure_objects, idempotency_key="back-ref-2")

    resulting_id = _attach(secure_objects, transaction_id=transaction_id, attachment_id=attachment_id)

    found = list_attachments(_store(secure_objects), linked_to=resulting_id)
    assert tuple(item.attachment_id for item in found) == (attachment_id,)


def test_an_unlinked_attachment_is_not_discovered(secure_objects: SecureObjectRepository) -> None:
    """The filter must stay a filter: linking one attachment must not surface another."""
    linked_id = _seed_attachment(secure_objects, marker=b"c")
    unlinked_id = _seed_attachment(secure_objects, marker=b"d")
    transaction_id = _seed_transaction(secure_objects, idempotency_key="back-ref-3")

    resulting_id = _attach(secure_objects, transaction_id=transaction_id, attachment_id=linked_id)

    found = {item.attachment_id for item in list_attachments(_store(secure_objects), linked_to=resulting_id)}
    assert linked_id in found
    assert unlinked_id not in found
    assert load_attachment(_store(secure_objects), unlinked_id).linked_transaction_ids == ()


def test_repeated_linking_does_not_grow_the_reverse_link(secure_objects: SecureObjectRepository) -> None:
    """The reverse write is idempotent, so a re-link re-converges rather than duplicating.

    Driven through the canonical mutator directly because the ledger action
    refuses a second identical attach as a no-op update, so the action cannot
    reach the repeat case the mutator must survive.
    """
    attachment_id = _seed_attachment(secure_objects, marker=b"e")
    transaction_id = _seed_transaction(secure_objects, idempotency_key="back-ref-4")
    resulting_id = _attach(secure_objects, transaction_id=transaction_id, attachment_id=attachment_id)

    link_attachment_transaction(
        _store(secure_objects),
        attachment_id=attachment_id,
        transaction_id=resulting_id,
    )

    manifest = load_attachment(_store(secure_objects), attachment_id)
    assert manifest.linked_transaction_ids.count(resulting_id) == 1
    assert len(manifest.linked_transaction_ids) == len(set(manifest.linked_transaction_ids))


def test_a_transaction_with_no_attachments_writes_no_manifest_link(
    secure_objects: SecureObjectRepository,
) -> None:
    """Creating an attachment-free transaction must not touch any manifest."""
    attachment_id = _seed_attachment(secure_objects, marker=b"f")
    _seed_transaction(secure_objects, idempotency_key="back-ref-5")

    assert load_attachment(_store(secure_objects), attachment_id).linked_transaction_ids == ()
