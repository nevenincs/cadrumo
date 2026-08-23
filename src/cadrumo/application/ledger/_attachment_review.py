"""Read-side projection for encrypted attachments awaiting invoice review."""

from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import BaseModel

from ...adapters.outbound.google import parse_drive_file_id
from ...core import STRICT_FROZEN_CONFIG
from ...domain.attachments import Attachment, AttachmentSource, AttachmentStoreProtocol

__all__ = ["AttachmentReviewItem", "get_attachment_review_item", "list_attachment_review_queue"]


class AttachmentReviewItem(BaseModel):
    """Non-secret manifest facts exposed to an invoice-review operator."""

    model_config = STRICT_FROZEN_CONFIG

    attachment_id: str
    sha256: str
    mime_type: str
    bytes_size: int
    source: AttachmentSource
    provider_locator: str
    captured_at: str
    linked_invoice_ids: tuple[str, ...]
    pending_review: bool


def _project(attachment: Attachment) -> AttachmentReviewItem:
    provider_locator = "not-exposed"
    if attachment.source is AttachmentSource.GOOGLE_DRIVE:
        provider_locator = _drive_provider_locator(attachment.source_reference)
    return AttachmentReviewItem(
        attachment_id=attachment.attachment_id,
        sha256=attachment.sha256,
        mime_type=attachment.mime_type,
        bytes_size=attachment.bytes_size,
        source=attachment.source,
        provider_locator=provider_locator,
        captured_at=attachment.captured_at.isoformat(),
        linked_invoice_ids=attachment.linked_invoice_ids,
        pending_review=not attachment.linked_invoice_ids,
    )


def _drive_provider_locator(reference: str) -> str:
    """Return an id only from the canonical secret-free Drive file URL."""
    try:
        parsed = urlsplit(reference)
        if parsed.scheme != "https" or parsed.netloc != "drive.google.com":
            return "not-exposed"
        if parsed.username is not None or parsed.password is not None:
            return "not-exposed"
        if parsed.query or parsed.fragment:
            return "not-exposed"
        parts = parsed.path.split("/")
        if len(parts) != 4 or parts[:3] != ["", "file", "d"]:
            return "not-exposed"
        file_id = parts[3]
        if not file_id or parse_drive_file_id(file_id) != file_id:
            return "not-exposed"
        return file_id
    except ValueError:
        return "not-exposed"


def get_attachment_review_item(store: AttachmentStoreProtocol, attachment_id: str) -> AttachmentReviewItem:
    """Load one manifest and expose only review-safe provenance fields."""
    store.verify_blob(attachment_id)
    return _project(store.load_manifest(attachment_id))


def list_attachment_review_queue(store: AttachmentStoreProtocol) -> tuple[AttachmentReviewItem, ...]:
    """List unconfirmed Drive attachments from authoritative secure manifests."""
    return tuple(
        _project(attachment)
        for attachment in store.iter_manifests()
        if attachment.source is AttachmentSource.GOOGLE_DRIVE and not attachment.linked_invoice_ids
    )
