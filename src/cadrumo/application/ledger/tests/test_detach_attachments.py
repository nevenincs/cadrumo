"""``ledger detach`` is the inverse of ``ledger attach`` for supplementary evidence.

Real secure storage, real repositories, real bucket-event history throughout: the
attachments are genuine content-addressed secure objects, because the transaction
boundary refuses an ``attachment_id`` that is not a 64-character digest naming a
stored manifest and blob. A test that invented ids would prove nothing about the
door it is exercising.

Detaching removes one transaction's REFERENCE to an attachment; it never deletes
the attachment's bytes, which are content-addressed and may be referenced by
other transactions and by finalized revisions.
"""

from __future__ import annotations

import pytest

from ....adapters.persistence.storage import AttachmentStore
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.attachments.enums import AttachmentKind, AttachmentSource
from ....domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment, load_attachment
from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    Decimal,
    ManualLedgerTransactionCommand,
    TransactionDirection,
    TransactionValidationError,
    _repositories,
    attach_manual_transaction_evidence,
    create_manual_transaction,
    date,
    datetime,
    detach_manual_transaction_attachments,
)
from ._action_test_support import (
    secure_objects as secure_objects,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PDF_BYTES = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\nledger-detach\n%%EOF\n"


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


def _attach(secure_objects: SecureObjectRepository, *, transaction_id: str, attachment_ids: tuple[str, ...]):
    transaction_repository, event_repository = _repositories(secure_objects)
    return attach_manual_transaction_evidence(
        bucket_id=_BUCKET_ID,
        transaction_id=transaction_id,
        actor="operator",
        attachment_ids=attachment_ids,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        attachment_store=_store(secure_objects),
    )


def _detach(secure_objects: SecureObjectRepository, *, transaction_id: str, attachment_ids: tuple[str, ...]):
    transaction_repository, event_repository = _repositories(secure_objects)
    return detach_manual_transaction_attachments(
        bucket_id=_BUCKET_ID,
        transaction_id=transaction_id,
        actor="operator",
        attachment_ids=attachment_ids,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        attachment_store=_store(secure_objects),
    )


def test_detach_removes_only_the_named_attachment(secure_objects: SecureObjectRepository) -> None:
    """A detach that cleared the whole tuple would drop evidence nobody named."""
    transaction_id = _seed_transaction(secure_objects, idempotency_key="detach-one")
    first = _seed_attachment(secure_objects, marker=b"one")
    second = _seed_attachment(secure_objects, marker=b"two")
    attached = _attach(secure_objects, transaction_id=transaction_id, attachment_ids=(first, second))
    assert set(attached.transaction.attachment_ids) == {first, second}

    detached = _detach(secure_objects, transaction_id=transaction_id, attachment_ids=(first,))

    assert detached.transaction.attachment_ids == (second,)
    assert detached.bucket_event_ids, "detaching must emit its own lifecycle event"


def test_detach_leaves_the_attachment_bytes_in_the_store(secure_objects: SecureObjectRepository) -> None:
    """Detaching drops a REFERENCE, never the content-addressed object itself.

    Other transactions and finalized revisions may reference the same digest, so
    removing the bytes on a detach would destroy evidence beyond this caller's
    subject.
    """
    transaction_id = _seed_transaction(secure_objects, idempotency_key="detach-keeps-bytes")
    attachment_id = _seed_attachment(secure_objects, marker=b"kept")
    _attach(secure_objects, transaction_id=transaction_id, attachment_ids=(attachment_id,))

    _detach(secure_objects, transaction_id=transaction_id, attachment_ids=(attachment_id,))

    assert load_attachment(_store(secure_objects), attachment_id=attachment_id) is not None


def test_detach_can_clear_the_last_attachment(secure_objects: SecureObjectRepository) -> None:
    """An empty remainder is a real clear, not a silently-skipped no-op.

    ``ManualLedgerTransactionPatch`` separates set from unset by
    ``model_fields_set``, so an explicitly-set empty tuple applies. Without that
    the last attachment could never come off, which is exactly the case an
    operator correcting a mistake reaches.
    """
    transaction_id = _seed_transaction(secure_objects, idempotency_key="detach-last")
    attachment_id = _seed_attachment(secure_objects, marker=b"last")
    _attach(secure_objects, transaction_id=transaction_id, attachment_ids=(attachment_id,))

    detached = _detach(secure_objects, transaction_id=transaction_id, attachment_ids=(attachment_id,))

    assert detached.transaction.attachment_ids == ()


def test_detach_refuses_an_attachment_the_transaction_does_not_carry(
    secure_objects: SecureObjectRepository,
) -> None:
    """The control: a silent no-op would let a typo read as a successful detach."""
    transaction_id = _seed_transaction(secure_objects, idempotency_key="detach-unknown")
    attached_id = _seed_attachment(secure_objects, marker=b"attached")
    stranger_id = _seed_attachment(secure_objects, marker=b"stranger")
    _attach(secure_objects, transaction_id=transaction_id, attachment_ids=(attached_id,))

    with pytest.raises(TransactionValidationError, match="does not carry attachment"):
        _detach(secure_objects, transaction_id=transaction_id, attachment_ids=(stranger_id,))


def test_detach_requires_at_least_one_attachment_id(secure_objects: SecureObjectRepository) -> None:
    """An empty request is a caller error, never an instruction to clear everything."""
    transaction_id = _seed_transaction(secure_objects, idempotency_key="detach-empty")
    attachment_id = _seed_attachment(secure_objects, marker=b"present")
    _attach(secure_objects, transaction_id=transaction_id, attachment_ids=(attachment_id,))

    with pytest.raises(TransactionValidationError, match="at least one attachment id"):
        _detach(secure_objects, transaction_id=transaction_id, attachment_ids=())
