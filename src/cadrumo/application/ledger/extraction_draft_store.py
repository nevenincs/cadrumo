"""Encrypted store for pre-confirm extraction drafts.

An :class:`~application.ledger.invoice_draft_records.InvoiceDraft` is derived financial data: supplier
tax id, invoice number, taxable base, per-rate cuota. Persisting one is STORAGE
rather than processing, so it routes through the core's encrypted bucket-scoped
repository and never through the inference subpackage, which holds no storage
handle by contract.

Its pre-confirm, operator-correctable lifecycle does not change its sensitivity. A leaked draft would disclose
exactly what the confirmed invoice would, so it is stored at the same
``FINANCIAL`` classification rather than a softer one.

**A draft is not an invoice and this store must never become a second writer of
one.** It holds what a reader proposed, pending the operator's confirm; the sole
sanctioned :class:`~domain.invoices.models.Invoice` writer stays where it is. Keeping
the draft here is what lets an operator leave a review half-finished and return
to it without the extraction being re-run -- which is also why the store is keyed
by the evidence reference the draft came from rather than by the draft's own
content: correcting a field must update the review in place, not fork a second
one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core.identity.bucket import BucketId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.clock import now
from ...core.time.utc import UtcInstant
from . import extraction_draft_repository
from .invoice_draft_records import InvoiceDraft, LabelReadingFallback

if TYPE_CHECKING:
    from ...core.config import Settings

__all__ = [
    "ExtractionDraftDocument",
    "StoredExtractionDraft",
    "extraction_draft_object_key",
    "load_extraction_drafts",
    "read_extraction_draft",
    "write_extraction_draft",
]


class StoredExtractionDraft(BaseModel):
    """One pending extraction draft, keyed by the evidence it was read from.

    Attributes:
        evidence_reference: The evidence or attachment id the draft was read
            from. The key, so a correction updates the review in place rather
            than forking a second one for the same document.
        draft: The proposed fields, exactly as the reader produced them.
        extractor: Which reader produced it, so a draft from a superseded
            extractor is identifiable rather than silently trusted at confirm.
        read_transports: Every transport that carried this document's reading.
            Separate from ``extractor`` because they answer different questions
            at different granularities. WHICH reader produced a value is a
            per-field fact, already carried by the draft's own provenance
            envelopes, and a document-level claim about it would be exactly the
            laundering those envelopes exist to prevent. WHETHER any bytes left
            the host is legitimately document-level: if any field went off-host
            then the document did, so the fact is monotone over fields and
            loses nothing by being aggregated here.

            Empty means UNKNOWN, not on-host. A writer that cannot establish
            where the read ran says nothing rather than claiming the safe
            answer, and the consent withdrawal survey surfaces the uncertainty
            instead of resolving it optimistically.
        drafted_at: When the draft was written.
        label_reading_fallback: Why the draft's label reading stood without the
            model fill it asked for, when it did. Kept on the record because the
            draft's own payload describes only what the document says, so the
            reading-path fact would otherwise be lost the moment the draft is
            stored -- and a stored draft with empty fields would look exactly
            like a document that does not print them. Once stored, this field
            is the fact's only home; ``draft`` itself carries none.

            ``None`` means no degradation is recorded: the fill ran, was never
            needed, or the draft was stored before this fact was kept. It never
            claims the read was complete.
    """

    model_config = STRICT_FROZEN_CONFIG

    evidence_reference: str = Field(min_length=1)
    draft: InvoiceDraft
    extractor: str = Field(min_length=1)
    read_transports: tuple[str, ...] = ()
    drafted_at: UtcInstant
    label_reading_fallback: LabelReadingFallback | None = None


class ExtractionDraftDocument(BaseModel):
    """One bucket's pending extraction drafts."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    drafts: tuple[StoredExtractionDraft, ...] = ()


def extraction_draft_object_key(document: ExtractionDraftDocument) -> str:
    """Return the canonical natural object key for one draft document."""
    return document.bucket_id


def load_extraction_drafts(bucket_id: str, settings: Settings) -> ExtractionDraftDocument:
    """Load a bucket's pending drafts, or an empty document when none exist."""
    document = extraction_draft_repository.extraction_draft_repository(bucket_id, settings).load(bucket_id)
    return document if document is not None else ExtractionDraftDocument(bucket_id=bucket_id)


def read_extraction_draft(
    *,
    bucket_id: str,
    evidence_reference: str,
    settings: Settings,
) -> StoredExtractionDraft | None:
    """Return the pending draft for this evidence reference, or ``None``."""
    document = load_extraction_drafts(bucket_id, settings)
    return next((row for row in document.drafts if row.evidence_reference == evidence_reference), None)


def write_extraction_draft(
    *,
    bucket_id: str,
    evidence_reference: str,
    draft: InvoiceDraft,
    extractor: str,
    settings: Settings,
    read_transports: tuple[str, ...] = (),
) -> ExtractionDraftDocument:
    """Persist a draft through the core's encrypted repository.

    Replaces any pending draft for the same evidence reference. Two drafts for
    one document are a re-read or a correction, not two proposals, and leaving
    both would give the confirm boundary two answers with nothing saying which
    the operator meant.

    The draft's record of a label reading that stood without its model fill is
    moved onto the stored record here, at the one writer, so no caller has to
    remember to carry it. The record is then its only home: the stored draft
    keeps describing only what the document says, and a reload returns exactly
    what was written.
    """
    fallback = draft.label_reading_fallback
    document = load_extraction_drafts(bucket_id, settings)
    retained = tuple(row for row in document.drafts if row.evidence_reference != evidence_reference)
    updated = ExtractionDraftDocument(
        bucket_id=bucket_id,
        drafts=(
            *retained,
            StoredExtractionDraft(
                evidence_reference=evidence_reference,
                draft=draft if fallback is None else draft.with_label_reading_fallback(None),
                extractor=extractor,
                read_transports=read_transports,
                drafted_at=now(),
                label_reading_fallback=fallback,
            ),
        ),
    )
    extraction_draft_repository.extraction_draft_repository(bucket_id, settings).save(updated)
    return updated
