"""Service-layer helpers over :class:`AttachmentStoreProtocol`.

Thin orchestration on top of the storage primitives in
:mod:`aeat.domain.attachments._protocols`: ingest a file from disk,
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
from ._protocols import AttachmentStoreProtocol

_logger = get_logger(__name__)


def _build_attachment_manifest(
    *,
    sha256: str,
    kind: AttachmentKind,
    source: AttachmentSource,
    source_reference: str,
    mime_type: str,
    bytes_size: int,
    captured_at: datetime,
    bucket_id: str | None,
    link_transaction_ids: tuple[str, ...],
    link_invoice_ids: tuple[str, ...],
    metadata: Mapping[str, str] | None,
    notes: str,
) -> Attachment:
    """Validate and return the :class:`Attachment` manifest for stored bytes."""
    return Attachment.model_validate(
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
            "bucket_id": bucket_id,
            "metadata": metadata or {},
            "notes": notes,
        },
    )


def add_attachment(
    store: AttachmentStoreProtocol,
    *,
    path: Path,
    kind: AttachmentKind,
    source: AttachmentSource,
    source_reference: str,
    mime_type: str,
    captured_at: datetime,
    bucket_id: str | None = None,
    link_transaction_ids: tuple[str, ...] = (),
    link_invoice_ids: tuple[str, ...] = (),
    metadata: Mapping[str, str] | None = None,
    notes: str = "",
) -> Attachment:
    """Store attachment bytes from a file and persist the corresponding manifest.

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
        bucket_id: Optional owning profile bucket for the evidence record.
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
    attachment = _build_attachment_manifest(
        sha256=sha256,
        kind=kind,
        source=source,
        source_reference=source_reference,
        mime_type=mime_type,
        bytes_size=bytes_size,
        captured_at=captured_at,
        bucket_id=bucket_id,
        link_transaction_ids=link_transaction_ids,
        link_invoice_ids=link_invoice_ids,
        metadata=metadata,
        notes=notes,
    )
    store.write_manifest(attachment)
    _logger.info("added attachment kind=%s source=%s bytes=%d", kind.value, source.value, bytes_size)
    return attachment


def add_attachment_bytes(
    store: AttachmentStoreProtocol,
    *,
    data: bytes,
    kind: AttachmentKind,
    source: AttachmentSource,
    source_reference: str,
    mime_type: str,
    captured_at: datetime,
    bucket_id: str | None = None,
    link_transaction_ids: tuple[str, ...] = (),
    link_invoice_ids: tuple[str, ...] = (),
    metadata: Mapping[str, str] | None = None,
    notes: str = "",
) -> Attachment:
    """Store in-memory attachment bytes and persist the corresponding manifest.

    The byte-bearing companion to :func:`add_attachment`: it accepts the
    already-fetched document ``data`` (e.g. a Drive download resolved via
    :func:`aeat.adapters.outbound.google.resolve_document_link`) instead of a
    filesystem path, stores the encrypted blob through the same
    ``put_bytes`` / ``write_manifest`` path, and records the *real* SHA-256
    and supplied ``mime_type``. The stored bytes' SHA-256 is the attachment id,
    so equal documents deduplicate naturally. There is deliberately no
    link-only / ``text/uri-list`` path: an evidence record always carries the
    document's encrypted bytes.

    Args:
        store: Backing :class:`AttachmentStoreProtocol`.
        data: The already-fetched document bytes to encrypt and store.
        kind: Logical :class:`~aeat.domain.attachments._enums.AttachmentKind`.
        source: Originating :class:`~aeat.domain.attachments._enums.AttachmentSource`.
        source_reference: The original link / reference recorded as provenance.
        mime_type: MIME type of the fetched bytes.
        captured_at: Wall-clock timestamp when the bytes were captured.
        bucket_id: Optional owning profile bucket for the evidence record.
        link_transaction_ids: Optional transaction ids the attachment evidences.
        link_invoice_ids: Optional invoice ids the attachment evidences.
        metadata: Optional free-form key/value metadata.
        notes: Free-form operator notes; defaults to empty.

    Returns:
        The persisted :class:`~aeat.domain.attachments._models.Attachment`
        manifest carrying the real ``sha256`` and ``mime_type``.
    """
    sha256 = store.put_bytes(data)
    attachment = _build_attachment_manifest(
        sha256=sha256,
        kind=kind,
        source=source,
        source_reference=source_reference,
        mime_type=mime_type,
        bytes_size=len(data),
        captured_at=captured_at,
        bucket_id=bucket_id,
        link_transaction_ids=link_transaction_ids,
        link_invoice_ids=link_invoice_ids,
        metadata=metadata,
        notes=notes,
    )
    store.write_manifest(attachment)
    _logger.info("added attachment bytes kind=%s source=%s bytes=%d", kind.value, source.value, len(data))
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
        Filtered tuple of :class:`Attachment` manifests in store iteration
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
