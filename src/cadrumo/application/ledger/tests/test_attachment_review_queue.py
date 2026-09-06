"""Direct coverage for the two public attachment-review read operations.

The sibling locator suite proves the redaction rule by calling ``_project``
directly, which leaves the operations an operator actually reaches -- the queue
listing and the single-item read -- asserted nowhere. Both back installed
Ledger surfaces: the queue is read on every visit to the evidence area, and a
row that should not be there is a disclosure, not a cosmetic defect.

The store is supplied as an in-memory implementation of the declared
``AttachmentStoreProtocol`` rather than the encrypted adapter. That is the
boundary these functions take, and it keeps the assertions on the filtering and
projection semantics they own; the adapter's own manifest iteration is proven
by its suite under ``adapters/persistence/storage``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import override

import pytest

from ....domain.attachments.enums import AttachmentKind, AttachmentSource
from ....domain.attachments.models import Attachment
from ..attachment_review import get_attachment_review_item, list_attachment_review_queue

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FILE_ID = "1AbcDEfgHIjkLMnoPQRstuVWxyz12345"


def _attachment(
    digest: str,
    *,
    source: AttachmentSource = AttachmentSource.GOOGLE_DRIVE,
    linked_invoice_ids: tuple[str, ...] = (),
) -> Attachment:
    return Attachment(
        attachment_id=digest,
        sha256=digest,
        kind=AttachmentKind.DRIVE_DOCUMENT,
        source=source,
        source_reference=f"https://drive.google.com/file/d/{_FILE_ID}",
        mime_type="application/pdf",
        bytes_size=42,
        captured_at=datetime(2026, 8, 23, tzinfo=UTC),
        linked_invoice_ids=linked_invoice_ids,
    )


class _InMemoryAttachmentStore:
    """The declared store boundary over a fixed manifest list."""

    def __init__(self, *attachments: Attachment) -> None:
        self._attachments = attachments
        self.verified: list[str] = []

    def iter_manifests(self) -> Iterator[Attachment]:
        return iter(self._attachments)

    def load_manifest(self, attachment_id: str) -> Attachment:
        return next(item for item in self._attachments if item.attachment_id == attachment_id)

    def verify_blob(self, attachment_id: str) -> None:
        self.verified.append(attachment_id)

    def put_bytes(self, data: bytes) -> str:  # pragma: no cover - unused by the read path
        raise NotImplementedError

    def put_file(self, source: Path) -> tuple[str, int]:  # pragma: no cover - unused by the read path
        raise NotImplementedError

    def read_bytes(self, sha256: str) -> bytes:  # pragma: no cover - unused by the read path
        raise NotImplementedError

    def write_manifest(self, attachment: Attachment) -> None:  # pragma: no cover - unused by the read path
        raise NotImplementedError


def test_the_queue_holds_only_unreviewed_drive_evidence() -> None:
    """Both filters are load-bearing, so each exclusion is asserted separately."""
    unreviewed = _attachment("a" * 64)
    already_linked = _attachment("b" * 64, linked_invoice_ids=("inv-1",))
    other_channel = _attachment("c" * 64, source=AttachmentSource.LOCAL_FILE)

    rows = list_attachment_review_queue(_InMemoryAttachmentStore(unreviewed, already_linked, other_channel))

    assert [row.attachment_id for row in rows] == [unreviewed.attachment_id]


def test_every_queued_row_reports_itself_as_pending_review() -> None:
    """The queue and the flag must not be able to disagree."""
    rows = list_attachment_review_queue(_InMemoryAttachmentStore(_attachment("a" * 64), _attachment("d" * 64)))

    assert len(rows) == 2
    assert all(row.pending_review for row in rows)


def test_the_queue_preserves_the_store_order() -> None:
    """An operator works the queue top-down, so order is part of the contract."""
    store = _InMemoryAttachmentStore(_attachment("d" * 64), _attachment("a" * 64), _attachment("c" * 64))

    assert [row.attachment_id for row in list_attachment_review_queue(store)] == ["d" * 64, "a" * 64, "c" * 64]


def test_an_empty_queue_is_an_empty_tuple_not_an_absent_read() -> None:
    """Nothing outstanding and never read are different states downstream.

    The installed evidence area treats an empty tuple as "read, nothing to do"
    and ``None`` as an absent door, so returning the wrong one would either
    hide a working surface or claim a reading that never happened.
    """
    assert list_attachment_review_queue(_InMemoryAttachmentStore()) == ()


def test_a_single_item_read_verifies_the_blob_before_exposing_the_manifest() -> None:
    """Integrity is checked first, so tampered bytes cannot be described as sound."""
    attachment = _attachment("a" * 64)
    store = _InMemoryAttachmentStore(attachment)

    item = get_attachment_review_item(store, attachment.attachment_id)

    assert store.verified == [attachment.attachment_id]
    assert item.attachment_id == attachment.attachment_id
    assert item.provider_locator == _FILE_ID
    assert item.pending_review is True


def test_a_single_item_read_refuses_when_the_blob_fails_verification() -> None:
    """A failed integrity check must abort, never fall through to a projection."""

    class _TamperedStore(_InMemoryAttachmentStore):
        @override
        def verify_blob(self, attachment_id: str) -> None:
            raise ValueError("stored blob digest does not match")

    with pytest.raises(ValueError, match="digest does not match"):
        get_attachment_review_item(_TamperedStore(_attachment("a" * 64)), "a" * 64)
