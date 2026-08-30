"""Encrypted store for pre-confirm extraction drafts.

An :class:`~application.ledger.evidence_draft.InvoiceDraft` is derived financial data: supplier
tax id, invoice number, taxable base, per-rate cuota. Persisting one is STORAGE
rather than processing, so it routes through the core's encrypted bucket-scoped
repository and never through the inference subpackage, which holds no storage
handle by contract.

Its pre-confirm, operator-correctable lifecycle changes when a draft may be
discarded; it does not change its sensitivity. A leaked draft would disclose
exactly what the confirmed invoice would, so it is stored at the same
``FINANCIAL`` classification rather than a softer one.

**A draft is not an invoice and this store must never become a second writer of
one.** It holds what a reader proposed, pending the operator's confirm; the sole
sanctioned :class:`~domain.invoices.Invoice` writer stays where it is. Keeping
the draft here is what lets an operator leave a review half-finished and return
to it without the extraction being re-run -- which is also why the store is keyed
by the evidence reference the draft came from rather than by the draft's own
content: correcting a field must update the review in place, not fork a second
one.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.config import Settings
from ...core.identity import BucketId
from ...core.time import UtcInstant, now
from .evidence_draft import InvoiceDraft

__all__ = [
    "ExtractionDraftDocument",
    "ExtractionDraftRepositoryFactory",
    "ExtractionDraftRepositoryProtocol",
    "StoredExtractionDraft",
    "bind_extraction_draft_repository_factory",
    "discard_extraction_draft",
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
    """

    model_config = STRICT_FROZEN_CONFIG

    evidence_reference: str = Field(min_length=1)
    draft: InvoiceDraft
    extractor: str = Field(min_length=1)
    read_transports: tuple[str, ...] = ()
    drafted_at: UtcInstant


class ExtractionDraftDocument(BaseModel):
    """One bucket's pending extraction drafts."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    drafts: tuple[StoredExtractionDraft, ...] = ()


def extraction_draft_object_key(document: ExtractionDraftDocument) -> str:
    """Return the canonical natural object key for one draft document."""
    return document.bucket_id


class ExtractionDraftRepositoryProtocol(Protocol):
    """Persistence operations required by extraction-draft application policy."""

    def load(self, identifier: str) -> ExtractionDraftDocument | None:
        """Load the document stored under ``identifier``, when present."""
        ...

    def save(self, payload: ExtractionDraftDocument) -> None:
        """Persist one complete extraction-draft document."""
        ...


class ExtractionDraftRepositoryFactory(Protocol):
    """Construct a repository port for one bucket and storage configuration."""

    def __call__(self, *, bucket_id: str, settings: Settings) -> ExtractionDraftRepositoryProtocol:
        """Return the encrypted repository for ``bucket_id``."""
        ...


_BOUND_EXTRACTION_DRAFT_REPOSITORY_FACTORY: ContextVar[ExtractionDraftRepositoryFactory] = ContextVar(
    "cadrumo_extraction_draft_repository_factory"
)


@contextmanager
def bind_extraction_draft_repository_factory(
    factory: ExtractionDraftRepositoryFactory,
) -> Generator[ExtractionDraftRepositoryFactory]:
    """Bind one outward-composed repository factory for the host context."""
    token = _BOUND_EXTRACTION_DRAFT_REPOSITORY_FACTORY.set(factory)
    try:
        yield factory
    finally:
        _BOUND_EXTRACTION_DRAFT_REPOSITORY_FACTORY.reset(token)


def _repository(bucket_id: str, settings: Settings) -> ExtractionDraftRepositoryProtocol:
    try:
        factory = _BOUND_EXTRACTION_DRAFT_REPOSITORY_FACTORY.get()
    except LookupError as error:
        raise RuntimeError("extraction-draft persistence has not been composed") from error
    return factory(bucket_id=bucket_id, settings=settings)


def load_extraction_drafts(bucket_id: str, settings: Settings) -> ExtractionDraftDocument:
    """Load a bucket's pending drafts, or an empty document when none exist."""
    document = _repository(bucket_id, settings).load(bucket_id)
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
    """
    document = load_extraction_drafts(bucket_id, settings)
    retained = tuple(row for row in document.drafts if row.evidence_reference != evidence_reference)
    updated = ExtractionDraftDocument(
        bucket_id=bucket_id,
        drafts=(
            *retained,
            StoredExtractionDraft(
                evidence_reference=evidence_reference,
                draft=draft,
                extractor=extractor,
                read_transports=read_transports,
                drafted_at=now(),
            ),
        ),
    )
    _repository(bucket_id, settings).save(updated)
    return updated


def discard_extraction_draft(
    *,
    bucket_id: str,
    evidence_reference: str,
    settings: Settings,
) -> ExtractionDraftDocument:
    """Drop a pending draft once it has been confirmed or abandoned.

    A draft outlives its usefulness the moment the invoice is minted, and a
    confirmed document that still shows a pending review invites a second
    confirm of the same evidence.
    """
    document = load_extraction_drafts(bucket_id, settings)
    updated = ExtractionDraftDocument(
        bucket_id=bucket_id,
        drafts=tuple(row for row in document.drafts if row.evidence_reference != evidence_reference),
    )
    _repository(bucket_id, settings).save(updated)
    return updated
