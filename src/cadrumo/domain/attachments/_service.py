"""Service-layer helpers over :class:`AttachmentStoreProtocol`.

Thin orchestration on top of :class:`AttachmentStoreProtocol` primitives:
ingest a file from disk, build the corresponding :class:`Attachment`
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
    captured_by: str | None,
    source_command: str | None,
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
            "captured_by": captured_by,
            "source_command": source_command,
            "linked_transaction_ids": link_transaction_ids,
            "linked_invoice_ids": link_invoice_ids,
            "bucket_id": bucket_id,
            "metadata": metadata or {},
            "notes": notes,
        },
    )


def _persist_attachment(
    store: AttachmentStoreProtocol,
    *,
    sha256: str,
    kind: AttachmentKind,
    source: AttachmentSource,
    source_reference: str,
    mime_type: str,
    bytes_size: int,
    captured_at: datetime,
    bucket_id: str | None,
    captured_by: str | None,
    source_command: str | None,
    link_transaction_ids: tuple[str, ...],
    link_invoice_ids: tuple[str, ...],
    metadata: Mapping[str, str] | None,
    notes: str,
) -> Attachment:
    """Build the :class:`Attachment` manifest for already-stored bytes and persist it.

    The shared write core of :func:`add_attachment` and
    :func:`add_attachment_bytes`: both first hand the bytes to the store (from a
    file path or from memory) and receive the content ``sha256`` and byte count,
    then call this to validate the manifest and commit it through the single
    ``write_manifest`` write path. It introduces no temporary materialisation and
    re-sequences nothing — the bytes never leave secure storage.
    """
    attachment = _build_attachment_manifest(
        sha256=sha256,
        kind=kind,
        source=source,
        source_reference=source_reference,
        mime_type=mime_type,
        bytes_size=bytes_size,
        captured_at=captured_at,
        bucket_id=bucket_id,
        captured_by=captured_by,
        source_command=source_command,
        link_transaction_ids=link_transaction_ids,
        link_invoice_ids=link_invoice_ids,
        metadata=metadata,
        notes=notes,
    )
    store.write_manifest(attachment)
    return attachment


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
    captured_by: str | None = None,
    source_command: str | None = None,
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
            :class:`AttachmentKind`
            for the attachment.
        source: Originating
            :class:`AttachmentSource`
            channel.
        source_reference: Caller-supplied opaque reference into the
            originating system (e.g. invoice number, e-mail UID).
        mime_type: MIME type of the attachment bytes.
        captured_at: Wall-clock timestamp when the bytes were
            captured upstream.
        bucket_id: Optional owning profile bucket for the evidence record.
        captured_by: Actor that captured or imported the evidence when known.
        source_command: Operator command or backend that captured the evidence.
        link_transaction_ids: Optional tuple of transaction ids the
            attachment evidences.
        link_invoice_ids: Optional tuple of invoice ids the
            attachment evidences.
        metadata: Optional free-form key/value metadata.
        notes: Free-form operator notes; defaults to empty.

    Returns:
        The persisted
        :class:`Attachment` manifest.
    """
    _logger.debug("ingesting attachment from %s kind=%s source=%s", path, kind.value, source.value)
    sha256, bytes_size = store.put_file(path)
    attachment = _persist_attachment(
        store,
        sha256=sha256,
        kind=kind,
        source=source,
        source_reference=source_reference,
        mime_type=mime_type,
        bytes_size=bytes_size,
        captured_at=captured_at,
        bucket_id=bucket_id,
        captured_by=captured_by,
        source_command=source_command,
        link_transaction_ids=link_transaction_ids,
        link_invoice_ids=link_invoice_ids,
        metadata=metadata,
        notes=notes,
    )
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
    captured_by: str | None = None,
    source_command: str | None = None,
    link_transaction_ids: tuple[str, ...] = (),
    link_invoice_ids: tuple[str, ...] = (),
    metadata: Mapping[str, str] | None = None,
    notes: str = "",
) -> Attachment:
    """Store in-memory attachment bytes and persist the corresponding manifest.

    The byte-bearing companion to :func:`add_attachment`: it accepts the
    already-fetched document ``data`` (e.g. a Drive download resolved via
    :func:`adapters.outbound.google.resolve_document_link`) instead of a
    filesystem path, stores the encrypted blob through the same
    ``put_bytes`` / ``write_manifest`` path, and records the *real* SHA-256
    and supplied ``mime_type``. The stored bytes' SHA-256 is the attachment id,
    so equal documents deduplicate naturally. There is deliberately no
    link-only path: an evidence record always carries the document's encrypted
    bytes.

    Args:
        store: Backing :class:`AttachmentStoreProtocol`.
        data: The already-fetched document bytes to encrypt and store.
        kind: Logical :class:`AttachmentKind`.
        source: Originating :class:`AttachmentSource`.
        source_reference: The original link / reference recorded as provenance.
        mime_type: MIME type of the fetched bytes.
        captured_at: Wall-clock timestamp when the bytes were captured.
        bucket_id: Optional owning profile bucket for the evidence record.
        captured_by: Actor that captured or imported the evidence when known.
        source_command: Operator command or backend that captured the evidence.
        link_transaction_ids: Optional transaction ids the attachment evidences.
        link_invoice_ids: Optional invoice ids the attachment evidences.
        metadata: Optional free-form key/value metadata.
        notes: Free-form operator notes; defaults to empty.

    Returns:
        The persisted :class:`Attachment`
        manifest carrying the real ``sha256`` and ``mime_type``.
    """
    sha256 = store.put_bytes(data)
    attachment = _persist_attachment(
        store,
        sha256=sha256,
        kind=kind,
        source=source,
        source_reference=source_reference,
        mime_type=mime_type,
        bytes_size=len(data),
        captured_at=captured_at,
        bucket_id=bucket_id,
        captured_by=captured_by,
        source_command=source_command,
        link_transaction_ids=link_transaction_ids,
        link_invoice_ids=link_invoice_ids,
        metadata=metadata,
        notes=notes,
    )
    _logger.info("added attachment bytes kind=%s source=%s bytes=%d", kind.value, source.value, len(data))
    return attachment


def load_attachment(store: AttachmentStoreProtocol, attachment_id: str) -> Attachment:
    """Load one attachment manifest from the store.

    Args:
        store: Backing :class:`AttachmentStoreProtocol`.
        attachment_id: SHA-256 of the attachment bytes.

    Returns:
        The :class:`Attachment`
        manifest for ``attachment_id``.
    """
    return store.load_manifest(attachment_id)


def link_attachment_invoice(
    store: AttachmentStoreProtocol,
    *,
    attachment_id: str,
    invoice_id: str,
) -> Attachment:
    """Append ``invoice_id`` to an already-persisted attachment's ``linked_invoice_ids``.

    Closes the provenance loop the other direction from ``add_attachment(_bytes)``'s
    ``link_invoice_ids`` parameter: that parameter can only be populated for an
    invoice that already exists *before* the evidence is captured, but the
    evidence-confirmation flow mints the :class:`~cadrumo.domain.invoices.Invoice`
    *after* the attachment is already stored. This helper re-persists the same
    manifest (attachment id and bytes unchanged) through the same
    :meth:`AttachmentStoreProtocol.write_manifest` write path
    (``composition-service-no-parallel-write-path``), with ``invoice_id`` appended.

    Idempotent by construction: :class:`Attachment`'s
    ``linked_invoice_ids`` validator deduplicates and preserves first-seen
    order, so calling this twice with the same ``invoice_id`` is a no-op --
    the manifest's byte content after the second call is identical to after
    the first (a real re-confirm safely re-links without growing the tuple).

    Args:
        store: Backing :class:`AttachmentStoreProtocol`.
        attachment_id: SHA-256 of the attachment bytes to update.
        invoice_id: Stable :class:`~cadrumo.domain.invoices.Invoice` identifier
            to record as evidenced by this attachment.

    Returns:
        The re-persisted :class:`Attachment` manifest carrying ``invoice_id``
        in :attr:`Attachment.linked_invoice_ids`.
    """
    attachment = store.load_manifest(attachment_id)
    if invoice_id in attachment.linked_invoice_ids:
        return attachment
    updated = attachment.model_copy(update={"linked_invoice_ids": (*attachment.linked_invoice_ids, invoice_id)})
    store.write_manifest(updated)
    _logger.info("linked attachment %s to invoice %s", attachment_id, invoice_id)
    return updated


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
            :class:`AttachmentKind`.

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
