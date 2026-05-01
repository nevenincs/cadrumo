"""Unit tests for attachment model validation and invariants."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from . import Attachment, AttachmentKind, AttachmentSource

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _digest_for(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sample_payload(
    *,
    data: bytes = b"invoice-bytes",
    linked_transaction_ids: tuple[str, ...] = (),
    linked_invoice_ids: tuple[str, ...] = (),
    metadata: dict[str, str] | None = None,
) -> dict[str, object]:
    digest = _digest_for(data)
    return {
        "attachment_id": digest,
        "kind": AttachmentKind.INVOICE_PDF,
        "source": AttachmentSource.LOCAL_FILE,
        "source_reference": "/var/invoices/2026-04-17.pdf",
        "sha256": digest,
        "mime_type": "application/pdf",
        "bytes_size": len(data),
        "captured_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        "linked_transaction_ids": linked_transaction_ids,
        "linked_invoice_ids": linked_invoice_ids,
        "metadata": metadata or {},
        "notes": "",
    }


def test_attachment_round_trips_through_json() -> None:
    """Attachment must survive a JSON round-trip with tuple ordering intact."""
    payload = _sample_payload(
        linked_transaction_ids=("tx-a", "tx-b"),
        linked_invoice_ids=("inv-1",),
        metadata={"gmail_message_id": "abc123"},
    )
    original = Attachment.model_validate(payload)
    restored = Attachment.model_validate_json(original.model_dump_json())
    assert restored == original
    assert restored.linked_transaction_ids == ("tx-a", "tx-b")
    assert restored.linked_invoice_ids == ("inv-1",)
    assert dict(restored.metadata) == {"gmail_message_id": "abc123"}


def test_attachment_rejects_hash_mismatch_between_id_and_sha256() -> None:
    """attachment_id must equal sha256; otherwise validation fails."""
    payload = _sample_payload()
    payload["attachment_id"] = "f" * 64
    with pytest.raises(ValidationError):
        Attachment.model_validate(payload)


def test_attachment_rejects_invalid_sha256_shape() -> None:
    """Non-hex or wrong-length digests must be rejected."""
    payload = _sample_payload()
    payload["sha256"] = "zz" + "0" * 62
    payload["attachment_id"] = payload["sha256"]
    with pytest.raises(ValidationError):
        Attachment.model_validate(payload)


def test_attachment_rejects_naive_captured_at() -> None:
    """Naive capture timestamps must be rejected to preserve audit integrity."""
    payload = _sample_payload()
    payload["captured_at"] = datetime(2026, 4, 17, 12, 0)
    with pytest.raises(ValidationError):
        Attachment.model_validate(payload)


def test_attachment_linked_ids_are_deduplicated_preserving_first_seen_order() -> None:
    """Duplicate linked IDs collapse; first-seen order is preserved."""
    payload = _sample_payload(
        linked_transaction_ids=("tx-a", "tx-b", "tx-a"),
        linked_invoice_ids=("inv-2", "inv-1", "inv-2"),
    )
    attachment = Attachment.model_validate(payload)
    assert attachment.linked_transaction_ids == ("tx-a", "tx-b")
    assert attachment.linked_invoice_ids == ("inv-2", "inv-1")


def test_attachment_rejects_blank_linked_identifier() -> None:
    """Blank linked IDs must fail validation rather than be silently dropped."""
    payload = _sample_payload(linked_transaction_ids=("tx-a", "  "))
    with pytest.raises(ValidationError):
        Attachment.model_validate(payload)


def test_attachment_rejects_scalar_linked_ids() -> None:
    """A bare string for linked_transaction_ids must be rejected."""
    payload = _sample_payload()
    payload["linked_transaction_ids"] = "tx-a"
    with pytest.raises(ValidationError):
        Attachment.model_validate(payload)


def test_attachment_metadata_rejects_empty_keys() -> None:
    """Metadata keys must be non-blank strings."""
    payload = _sample_payload(metadata={"   ": "value"})
    with pytest.raises(ValidationError):
        Attachment.model_validate(payload)


def test_attachment_metadata_rejects_non_string_values() -> None:
    """Metadata values must be strings; the escape hatch is string-only."""
    payload = _sample_payload()
    payload["metadata"] = {"drive_revision": 12}
    with pytest.raises(ValidationError):
        Attachment.model_validate(payload)


def test_attachment_trims_required_text_and_notes() -> None:
    """source_reference, mime_type, and notes are trimmed on validation."""
    payload = _sample_payload()
    payload["source_reference"] = "  source://x.pdf  "
    payload["mime_type"] = "  application/pdf  "
    payload["notes"] = "  hand-scanned  "
    attachment = Attachment.model_validate(payload)
    assert attachment.source_reference == "source://x.pdf"
    assert attachment.mime_type == "application/pdf"
    assert attachment.notes == "hand-scanned"
