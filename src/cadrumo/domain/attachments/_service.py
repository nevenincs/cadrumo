"""Service-layer helpers over :class:`AttachmentStoreProtocol`.

Thin orchestration on top of :class:`AttachmentStoreProtocol` primitives:
ingest a file from disk, build the corresponding :class:`Attachment`
manifest, persist it, and expose simple read paths for callers that
do not need the full repository API.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...core.identity import BucketId
from ...core.logging import get_logger
from ._enums import AttachmentKind, AttachmentSource
from ._models import Attachment
from ._protocols import AttachmentStoreProtocol

_logger = get_logger(__name__)


class AttachmentIngestionRequest(BaseModel):
    """Typed manifest facts for one attachment capture."""

    model_config = STRICT_FROZEN_CONFIG

    kind: AttachmentKind
    source: AttachmentSource
    source_reference: str
    mime_type: str
    captured_at: datetime
    bucket_id: BucketId | None = None
    captured_by: str | None = None
    source_command: str | None = None
    link_transaction_ids: tuple[str, ...] = ()
    link_invoice_ids: tuple[str, ...] = ()
    metadata: Mapping[str, str] = Field(default_factory=dict)
    notes: str = ""


class AttachmentFileContent(BaseModel):
    """One local file supplied to the attachment custody service."""

    model_config = STRICT_FROZEN_CONFIG

    path: Path


class AttachmentBytesContent(BaseModel):
    """One already-fetched byte payload supplied to the custody service."""

    model_config = STRICT_FROZEN_CONFIG

    data: bytes


@dataclass(frozen=True)
class _StoredAttachment:
    """Content-addressed storage result passed to the sole manifest writer."""

    sha256: str
    bytes_size: int


def _store_content(
    store: AttachmentStoreProtocol,
    content: AttachmentFileContent | AttachmentBytesContent,
) -> _StoredAttachment:
    """Store one typed content source and return its address and exact byte count."""
    if isinstance(content, AttachmentFileContent):
        sha256, bytes_size = store.put_file(content.path)
        return _StoredAttachment(sha256=sha256, bytes_size=bytes_size)
    sha256 = store.put_bytes(content.data)
    return _StoredAttachment(sha256=sha256, bytes_size=len(content.data))


def _persist_attachment(
    store: AttachmentStoreProtocol,
    *,
    stored: _StoredAttachment,
    request: AttachmentIngestionRequest,
) -> Attachment:
    """Build and persist the manifest through the sole attachment creation write path."""
    attachment = Attachment.model_validate(
        {
            "attachment_id": stored.sha256,
            "kind": request.kind,
            "source": request.source,
            "source_reference": request.source_reference,
            "sha256": stored.sha256,
            "mime_type": request.mime_type,
            "bytes_size": stored.bytes_size,
            "captured_at": request.captured_at,
            "captured_by": request.captured_by,
            "source_command": request.source_command,
            "linked_transaction_ids": request.link_transaction_ids,
            "linked_invoice_ids": request.link_invoice_ids,
            "bucket_id": request.bucket_id,
            "metadata": request.metadata,
            "notes": request.notes,
        },
    )
    store.write_manifest(attachment)
    return attachment


def add_attachment(
    store: AttachmentStoreProtocol,
    *,
    content: AttachmentFileContent | AttachmentBytesContent,
    request: AttachmentIngestionRequest,
) -> Attachment:
    """Store one typed file or byte payload and persist its attachment manifest."""
    _logger.debug("ingesting attachment kind=%s source=%s", request.kind.value, request.source.value)
    stored = _store_content(store, content)
    attachment = _persist_attachment(
        store,
        stored=stored,
        request=request,
    )
    _logger.info(
        "added attachment kind=%s source=%s bytes=%d",
        request.kind.value,
        request.source.value,
        stored.bytes_size,
    )
    return attachment


def _link_attachment(
    store: AttachmentStoreProtocol,
    *,
    attachment_id: str,
    related_id: str,
    field: Literal["linked_invoice_ids", "linked_transaction_ids"],
    related_kind: Literal["invoice", "transaction"],
) -> Attachment:
    """Append one typed relation to a manifest through the sole update write path."""
    attachment = store.load_manifest(attachment_id)
    related_ids = attachment.linked_invoice_ids if field == "linked_invoice_ids" else attachment.linked_transaction_ids
    if related_id in related_ids:
        return attachment
    updated = attachment.model_copy(update={field: (*related_ids, related_id)})
    store.write_manifest(updated)
    _logger.info("linked attachment %s to %s %s", attachment_id, related_kind, related_id)
    return updated


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

    Closes the provenance loop the other direction from ``add_attachment``'s
    ``link_invoice_ids`` parameter: that parameter can only be populated for an
    invoice that already exists *before* the evidence is captured, but the
    evidence-confirmation flow mints the :class:`~cadrumo.domain.invoices.Invoice`
    *after* the attachment is already stored. This helper re-persists the same
    manifest (attachment id and bytes unchanged) through the same
    :meth:`AttachmentStoreProtocol.write_manifest` write path
    (``aeat-architecture-boundaries``), with ``invoice_id`` appended.

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
    return _link_attachment(
        store,
        attachment_id=attachment_id,
        related_id=invoice_id,
        field="linked_invoice_ids",
        related_kind="invoice",
    )


def link_attachment_transaction(
    store: AttachmentStoreProtocol,
    *,
    attachment_id: str,
    transaction_id: str,
) -> Attachment:
    """Append ``transaction_id`` to a persisted attachment's ``linked_transaction_ids``.

    The transaction-side twin of :func:`link_attachment_invoice`, and for the
    same reason: ``add_attachment``'s ``link_transaction_ids``
    parameter can only be populated for a transaction that already exists
    *before* the evidence is captured, but the ledger evidence flow attaches an
    already-stored attachment to an existing transaction. Without this the link
    was recorded on the transaction only, so
    :func:`list_attachments` with ``linked_to=<transaction_id>`` could not
    discover an attachment the transaction itself cites -- even though the
    manifest models the link and the surrounding workflow documents the
    provenance as bidirectional.

    Re-persists the same manifest (attachment id and bytes unchanged) through
    the same :meth:`AttachmentStoreProtocol.write_manifest` write path
    (``aeat-architecture-boundaries``).

    Idempotent by construction: :class:`Attachment`'s
    ``linked_transaction_ids`` validator deduplicates and preserves first-seen
    order, so a repeated attach is a no-op rather than a growing tuple.

    Args:
        store: Backing :class:`AttachmentStoreProtocol`.
        attachment_id: SHA-256 of the attachment bytes to update.
        transaction_id: Stable ledger transaction identifier to record as
            supported by this attachment.

    Returns:
        The re-persisted :class:`Attachment` manifest carrying
        ``transaction_id`` in :attr:`Attachment.linked_transaction_ids`.
    """
    return _link_attachment(
        store,
        attachment_id=attachment_id,
        related_id=transaction_id,
        field="linked_transaction_ids",
        related_kind="transaction",
    )


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
