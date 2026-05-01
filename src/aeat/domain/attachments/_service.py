"""Attachment service helpers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from ._enums import AttachmentKind, AttachmentSource
from ._models import Attachment
from ._repository import AttachmentStore


def add_attachment(
    store: AttachmentStore,
    *,
    path: Path,
    kind: AttachmentKind,
    source: AttachmentSource,
    source_reference: str,
    mime_type: str,
    captured_at: datetime,
    link_transaction_ids: tuple[str, ...] = (),
    link_invoice_ids: tuple[str, ...] = (),
    metadata: Mapping[str, str] | None = None,
    notes: str = "",
) -> Attachment:
    """Store attachment bytes and persist the corresponding manifest."""
    sha256, bytes_size = store.put_file(path)
    attachment = Attachment.model_validate(
        {
            "attachment_id": sha256,
            "kind": kind,
            "source": source,
            "source_reference": source_reference,
            "sha256": sha256,
            "mime_type": mime_type,
            "bytes_size": bytes_size,
            "captured_at": captured_at,
            "linked_transaction_ids": link_transaction_ids,
            "linked_invoice_ids": link_invoice_ids,
            "metadata": metadata or {},
            "notes": notes,
        }
    )
    store.write_manifest(attachment)
    return attachment


def load_attachment(store: AttachmentStore, attachment_id: str) -> Attachment:
    """Load one attachment manifest from ``store``."""
    return store.load_manifest(attachment_id)


def list_attachments(
    store: AttachmentStore,
    *,
    linked_to: str | None = None,
    kind: AttachmentKind | None = None,
) -> tuple[Attachment, ...]:
    """List attachment manifests, optionally filtering by link or kind."""
    out: list[Attachment] = []
    for attachment in store.iter_manifests():
        if kind is not None and attachment.kind is not kind:
            continue
        if linked_to is not None and linked_to not in attachment.linked_transaction_ids + attachment.linked_invoice_ids:
            continue
        out.append(attachment)
    return tuple(out)
