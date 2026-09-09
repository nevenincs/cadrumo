"""Read-side projection for encrypted attachments awaiting invoice review."""

from __future__ import annotations

import re
from typing import Final
from urllib.parse import SplitResult, urlsplit

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.attachments.enums import AttachmentSource
from ...domain.attachments.models import Attachment
from ...domain.attachments.protocols import AttachmentStoreProtocol

__all__ = ["AttachmentReviewItem", "get_attachment_review_item", "list_attachment_review_queue"]

_DRIVE_FILE_ID_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_-]{25,}")


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
    file_id = _drive_file_id(reference)
    return file_id if file_id is not None else "not-exposed"


def _drive_file_id(reference: str) -> str | None:
    """Extract a validated Drive ID, refusing malformed URL components."""
    try:
        parsed = urlsplit(reference)
        if not _is_secret_free_drive_url(parsed):
            return None
        parts = _drive_file_path_parts(parsed)
        if parts is None:
            return None
        file_id = parts[3]
        return file_id if _DRIVE_FILE_ID_RE.fullmatch(file_id) is not None else None
    except ValueError:
        return None


def _is_secret_free_drive_url(parsed: SplitResult) -> bool:
    """Return whether URL-level components match the safe Drive origin."""
    return (
        parsed.scheme == "https"
        and parsed.netloc == "drive.google.com"
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
    )


def _drive_file_path_parts(parsed: SplitResult) -> list[str] | None:
    """Return path components for exactly ``/file/d/<id>`` URLs."""
    parts = parsed.path.split("/")
    if len(parts) != 4 or parts[:3] != ["", "file", "d"]:
        return None
    return parts


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
