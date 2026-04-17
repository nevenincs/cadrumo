"""Unit tests for attachment catalogue construction and semantics."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aeat.financial.attachments import Attachment, AttachmentCatalogue, AttachmentKind, AttachmentSource


def _attachment(data: bytes) -> Attachment:
    digest = hashlib.sha256(data).hexdigest()
    return Attachment.model_validate(
        {
            "attachment_id": digest,
            "kind": AttachmentKind.METADATA_BLOB,
            "source": AttachmentSource.LOCAL_FILE,
            "source_reference": f"source://{digest}",
            "sha256": digest,
            "mime_type": "application/octet-stream",
            "bytes_size": len(data),
            "captured_at": datetime(2026, 4, 17, tzinfo=UTC),
        }
    )


@pytest.mark.unit
def test_catalogue_rejects_duplicate_attachment_ids_on_construction() -> None:
    """Duplicate attachment IDs must be rejected when building a catalogue."""
    attachment = _attachment(b"hello")
    with pytest.raises(ValidationError):
        AttachmentCatalogue.from_attachments([attachment, attachment])


@pytest.mark.unit
def test_catalogue_iteration_yields_attachments_not_mapping_entries() -> None:
    """AttachmentCatalogue iteration must expose attachments directly."""
    first = _attachment(b"first")
    second = _attachment(b"second")
    catalogue = AttachmentCatalogue.from_attachments([first, second])
    assert [attachment.attachment_id for attachment in catalogue] == [
        first.attachment_id,
        second.attachment_id,
    ]
    assert len(catalogue) == 2
    assert first in catalogue
    assert first.attachment_id in catalogue
    assert catalogue.get(second.attachment_id) == second
    assert catalogue.get("missing") is None


@pytest.mark.unit
def test_catalogue_round_trips_through_json() -> None:
    """Catalogue serialisation must survive a JSON round-trip unchanged."""
    first = _attachment(b"alpha")
    second = _attachment(b"beta")
    catalogue = AttachmentCatalogue.from_attachments([first, second])
    restored = AttachmentCatalogue.model_validate_json(catalogue.model_dump_json())
    assert restored == catalogue
