"""Service helpers orchestrating the attachment store and manifest model."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from aeat.logging import get_logger

from ._enums import AttachmentKind, AttachmentSource
from ._errors import AttachmentNotFoundError, AttachmentValidationError
from ._models import Attachment
from ._store import AttachmentStore

_LOGGER = get_logger(__name__)


def add_attachment(
    store: AttachmentStore,
    *,
    path: Path,
    kind: AttachmentKind,
    source: AttachmentSource,
    source_reference: str,
    mime_type: str,
    captured_at: datetime,
    link_transaction_ids: Iterable[str] = (),
    link_invoice_ids: Iterable[str] = (),
    metadata: Mapping[str, str] | None = None,
    notes: str = "",
) -> Attachment:
    """Ingest ``path`` into the store, merging links on re-ingest.

    Hashing is performed once over the file's bytes. The hex digest becomes
    both the byte-store key and the ``attachment_id`` of the resulting
    manifest. If a manifest already exists for that digest, the caller's
    supplied link tuples are merged into the existing ones so re-ingesting
    the same file with fresh links is additive rather than destructive.

    Args:
        store: Destination attachment store.
        path: Filesystem path to the source bytes.
        kind: Document-kind classification.
        source: Source-channel classification.
        source_reference: Stable provenance pointer (path / Gmail ID / URL).
        mime_type: MIME type of the stored bytes.
        captured_at: Timezone-aware capture timestamp.
        link_transaction_ids: Transaction identifiers to link to.
        link_invoice_ids: Invoice identifiers to link to.
        metadata: Free-form provider metadata; string values only.
        notes: Optional human-readable notes.

    Returns:
        The persisted ``Attachment`` manifest.

    Raises:
        AttachmentPersistenceError: When the source cannot be read or the
            store cannot be written.
        AttachmentValidationError: When the supplied payload fails domain
            validation.
    """
    digest, bytes_size = store.put_file(path)
    existing_transactions: tuple[str, ...] = ()
    existing_invoices: tuple[str, ...] = ()
    try:
        existing = store.load_manifest(digest)
    except AttachmentNotFoundError:
        existing = None
    if existing is not None:
        existing_transactions = existing.linked_transaction_ids
        existing_invoices = existing.linked_invoice_ids
    merged_transactions = tuple(existing_transactions) + tuple(link_transaction_ids)
    merged_invoices = tuple(existing_invoices) + tuple(link_invoice_ids)
    try:
        attachment = Attachment.model_validate(
            {
                "attachment_id": digest,
                "kind": kind,
                "source": source,
                "source_reference": source_reference,
                "sha256": digest,
                "mime_type": mime_type,
                "bytes_size": bytes_size,
                "captured_at": captured_at,
                "linked_transaction_ids": merged_transactions,
                "linked_invoice_ids": merged_invoices,
                "metadata": metadata or {},
                "notes": notes,
            }
        )
    except ValidationError as exc:
        raise AttachmentValidationError(f"invalid attachment payload for source: {path}") from exc
    store.write_manifest(attachment)
    _LOGGER.info("added attachment %s from %s (%d bytes)", digest, path, bytes_size)
    return attachment


def load_attachment(store: AttachmentStore, attachment_id: str) -> Attachment:
    """Return the manifest for ``attachment_id`` or raise typed errors.

    Args:
        store: Attachment store to query.
        attachment_id: Stable attachment identifier.

    Returns:
        The validated attachment manifest.

    Raises:
        AttachmentNotFoundError: When no manifest exists.
        AttachmentPersistenceError: When the manifest cannot be read.
        AttachmentValidationError: When the manifest fails validation.
    """
    return store.load_manifest(attachment_id)


def list_attachments(
    store: AttachmentStore,
    *,
    linked_to: str | None = None,
    kind: AttachmentKind | None = None,
) -> tuple[Attachment, ...]:
    """Return every manifest in the store, optionally filtered by linkage.

    Args:
        store: Attachment store to iterate.
        linked_to: When provided, only include attachments whose
            ``linked_transaction_ids`` or ``linked_invoice_ids`` contain the
            supplied identifier.
        kind: When provided, only include attachments whose ``kind`` matches.

    Returns:
        A tuple of matching attachments in deterministic sorted order.
    """
    matches: list[Attachment] = []
    for attachment in store.iter_manifests():
        if kind is not None and attachment.kind != kind:
            continue
        if linked_to is not None and (
            linked_to not in attachment.linked_transaction_ids and linked_to not in attachment.linked_invoice_ids
        ):
            continue
        matches.append(attachment)
    return tuple(matches)
