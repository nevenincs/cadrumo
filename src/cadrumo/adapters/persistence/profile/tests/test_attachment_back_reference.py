"""Attaching evidence records the link on both sides of the provenance pair.

``attach_manual_transaction_evidence`` persists the attachment id into
``Transaction.attachment_ids``, but its verification helper only loaded and
validated the manifest -- it never appended the transaction id to
``Attachment.linked_transaction_ids``. The attachment domain's
``iter_manifests`` filtered by ``linked_to`` therefore could not discover an
attachment that the transaction itself cited, even though the manifest models
the link and the evidence workflow documents the provenance as bidirectional.
Invoice linkage had a dedicated manifest updater; ledger linkage now shares
that same canonical mutation path.

Real encrypted attachment store, real ledger repositories, real bucket-event
history -- no mocks or stubs.
"""

from __future__ import annotations

import pytest

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.manual_update import attach_manual_transaction_evidence
from cadrumo.domain.attachments.service import (
    link_attachment_transaction,
)

from .ledger_action_create_support import ledger_ports_for_test
from .ledger_action_persistence_support import (
    BUCKET_ID as _BUCKET_ID,
)
from .ledger_action_persistence_support import (
    repositories as _repositories,
)
from .ledger_attachment_support import attachment_store, seed_attachment, seed_manual_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PDF_BYTES = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\nledger-attachment-back-reference\n%%EOF\n"


def _seed_attachment(secure_objects: SecureObjectRepository, *, marker: bytes) -> str:
    return seed_attachment(secure_objects, pdf_bytes=_PDF_BYTES, marker=marker)


def _attach(
    secure_objects: SecureObjectRepository,
    *,
    transaction_id: str,
    attachment_id: str,
) -> str:
    transaction_repository, event_repository = _repositories(secure_objects)
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        attachment_store=attachment_store(secure_objects),
    ) as ports:
        result = attach_manual_transaction_evidence(
            bucket_id=_BUCKET_ID,
            transaction_id=transaction_id,
            actor="operator",
            attachment_ids=(attachment_id,),
            ports=ports,
        )
    return result.transaction.transaction_id


def test_attaching_records_the_link_on_both_sides(secure_objects: SecureObjectRepository) -> None:
    attachment_id = _seed_attachment(secure_objects, marker=b"a")
    transaction_id = seed_manual_transaction(secure_objects, idempotency_key="back-ref-1")

    resulting_id = _attach(secure_objects, transaction_id=transaction_id, attachment_id=attachment_id)

    transaction_repository, _ = _repositories(secure_objects)
    reloaded = transaction_repository.load().get(resulting_id)
    assert reloaded is not None
    assert attachment_id in reloaded.attachment_ids

    manifest = attachment_store(secure_objects).load_manifest(attachment_id)
    assert resulting_id in manifest.linked_transaction_ids


def test_the_filtered_list_discovers_an_attachment_the_transaction_cites(
    secure_objects: SecureObjectRepository,
) -> None:
    """``iter_manifests`` filtered by ``linked_to`` is the discovery surface that was blind."""
    attachment_id = _seed_attachment(secure_objects, marker=b"b")
    transaction_id = seed_manual_transaction(secure_objects, idempotency_key="back-ref-2")

    resulting_id = _attach(secure_objects, transaction_id=transaction_id, attachment_id=attachment_id)

    found = tuple(
        item
        for item in attachment_store(secure_objects).iter_manifests()
        if resulting_id in item.linked_transaction_ids + item.linked_invoice_ids
    )
    assert tuple(item.attachment_id for item in found) == (attachment_id,)


def test_an_unlinked_attachment_is_not_discovered(secure_objects: SecureObjectRepository) -> None:
    """The filter must stay a filter: linking one attachment must not surface another."""
    linked_id = _seed_attachment(secure_objects, marker=b"c")
    unlinked_id = _seed_attachment(secure_objects, marker=b"d")
    transaction_id = seed_manual_transaction(secure_objects, idempotency_key="back-ref-3")

    resulting_id = _attach(secure_objects, transaction_id=transaction_id, attachment_id=linked_id)

    found = {
        item.attachment_id
        for item in attachment_store(secure_objects).iter_manifests()
        if resulting_id in item.linked_transaction_ids + item.linked_invoice_ids
    }
    assert linked_id in found
    assert unlinked_id not in found
    assert attachment_store(secure_objects).load_manifest(unlinked_id).linked_transaction_ids == ()


def test_repeated_linking_does_not_grow_the_reverse_link(secure_objects: SecureObjectRepository) -> None:
    """The reverse write is idempotent, so a re-link re-converges rather than duplicating.

    Driven through the canonical mutator directly because the ledger action
    refuses a second identical attach as a no-op update, so the action cannot
    reach the repeat case the mutator must survive.
    """
    attachment_id = _seed_attachment(secure_objects, marker=b"e")
    transaction_id = seed_manual_transaction(secure_objects, idempotency_key="back-ref-4")
    resulting_id = _attach(secure_objects, transaction_id=transaction_id, attachment_id=attachment_id)

    link_attachment_transaction(
        attachment_store(secure_objects),
        attachment_id=attachment_id,
        transaction_id=resulting_id,
    )

    manifest = attachment_store(secure_objects).load_manifest(attachment_id)
    assert manifest.linked_transaction_ids.count(resulting_id) == 1
    assert len(manifest.linked_transaction_ids) == len(set(manifest.linked_transaction_ids))


def test_a_transaction_with_no_attachments_writes_no_manifest_link(
    secure_objects: SecureObjectRepository,
) -> None:
    """Creating an attachment-free transaction must not touch any manifest."""
    attachment_id = _seed_attachment(secure_objects, marker=b"f")
    seed_manual_transaction(secure_objects, idempotency_key="back-ref-5")

    assert attachment_store(secure_objects).load_manifest(attachment_id).linked_transaction_ids == ()
