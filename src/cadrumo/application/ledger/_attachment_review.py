"""Read-side projection for encrypted attachments awaiting invoice review."""

from __future__ import annotations

from pydantic import BaseModel

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
        marker = "/file/d/"
        if marker in attachment.source_reference:
            provider_locator = attachment.source_reference.split(marker, maxsplit=1)[1].split("/", maxsplit=1)[0]
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
