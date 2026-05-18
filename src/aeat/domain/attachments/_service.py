"""Service-layer helpers over :class:`AttachmentStoreProtocol`.

Thin orchestration on top of the storage primitives in
:mod:`aeat.domain.attachments._repository`: ingest a file from disk,
build the corresponding :class:`~aeat.domain.attachments._models.Attachment`
manifest, persist it, and expose simple read paths for callers that
do not need the full repository API.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from ...core.logging import get_logger
from ._enums import AttachmentKind, AttachmentSource
from ._models import Attachment
from ._repository import AttachmentStoreProtocol

_logger = get_logger(__name__)


def add_attachment(
    store: AttachmentStoreProtocol,
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
    """Store attachment bytes and persist the corresponding manifest.

    The stored bytes' SHA-256 doubles as the attachment id so equal
    files deduplicate naturally.

    Args:
        store: Backing :class:`AttachmentStoreProtocol` for blob storage and
            manifest persistence.
        path: Local filesystem path to the bytes being ingested.
        kind: Logical
            :class:`~aeat.domain.attachments._enums.AttachmentKind`
            for the attachment.
        source: Originating
            :class:`~aeat.domain.attachments._enums.AttachmentSource`
            channel.
        source_reference: Caller-supplied opaque reference into the
            originating system (e.g. invoice number, e-mail UID).
        mime_type: MIME type of the attachment bytes.
        captured_at: Wall-clock timestamp when the bytes were
            captured upstream.
        link_transaction_ids: Optional tuple of transaction ids the
            attachment evidences.
        link_invoice_ids: Optional tuple of invoice ids the
            attachment evidences.
        metadata: Optional free-form key/value metadata.
        notes: Free-form operator notes; defaults to empty.

    Returns:
        The persisted
        :class:`~aeat.domain.attachments._models.Attachment` manifest.
    """
    _logger.debug("ingesting attachment from %s kind=%s source=%s", path, kind.value, source.value)
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
    _logger.info("added attachment kind=%s source=%s bytes=%d", kind.value, source.value, bytes_size)
    return attachment


def load_attachment(store: AttachmentStoreProtocol, attachment_id: str) -> Attachment:
    """Load one attachment manifest from the store.

    Args:
        store: Backing :class:`AttachmentStoreProtocol`.
        attachment_id: SHA-256 of the attachment bytes.

    Returns:
        The :class:`~aeat.domain.attachments._models.Attachment`
        manifest for ``attachment_id``.
    """
    return store.load_manifest(attachment_id)


def list_attachments(
    store: AttachmentStoreProtocol,
    *,
    linked_to: str | None = None,
    kind: AttachmentKind | None = None,
) -> tuple[Attachment, ...]:
    """List attachment manifests, optionally filtered by link or kind.

    Args:
        store: Backing :class:`AttachmentStoreProtocol`.
        linked_to: When provided, return only attachments whose
            ``linked_transaction_ids`` or ``linked_invoice_ids``
            tuple contains this id.
        kind: When provided, return only attachments of this
            :class:`~aeat.domain.attachments._enums.AttachmentKind`.

    Returns:
        Filtered tuple of attachment manifests in store iteration
        order.
    """
    out: list[Attachment] = []
    for attachment in store.iter_manifests():
        if kind is not None and attachment.kind is not kind:
            continue
        if linked_to is not None and linked_to not in attachment.linked_transaction_ids + attachment.linked_invoice_ids:
            continue
        out.append(attachment)
    return tuple(out)
