"""Encrypted, content-addressed cache of a document's deterministic extraction.

Memoises the text a document yields so re-classifying or re-drafting need not
re-run extraction. Nothing between raw bytes and a persisted record is stored
today, which is why every operation currently re-does everything -- and why
batch and resume verbs would be expensive as well as, until the idempotency key
landed, corrupting.

**Why this is core-side and encrypted.** The cached value is the extracted text
of an invoice, which *is* the invoice in a shape a grep can read. On disk in the
clear it would be a new plaintext store of taxpayer financial data that does not
exist in this tree today. The operator ruling exempts IN-MEMORY reading,
rasterising and inference from encryption; it does not reach persistence, and
the rule it clarifies names "on-disk caches" explicitly among what it does not
reach. So the cache is written through the core's encrypted bucket-scoped
repository, and the inference subpackage -- which holds no storage handle --
cannot write it at all.

**Deliberately not called a normalization cache.** That name presupposes the
normalize-then-extract pipeline separation the governing ADR leaves open for
want of a measurement that was never run. What is cached here is the
deterministic extraction of a document's text, which exists under either
pipeline shape, so the name asserts nothing the record says is undecided.

Keyed by the document's content address, so the same bytes hit the same entry
regardless of which evidence record or attachment referenced them, and a
re-ingest of an identical document reuses the extraction rather than repeating
it.
"""

from __future__ import annotations

from typing import override

from pydantic import BaseModel, Field

from ...adapters.persistence.storage import (
    LEDGER_EXTRACTED_DOCUMENT_CACHE_NAMESPACE,
    SecureBoundRepository,
    secure_object_repository_for_bucket,
)
from ...core import STRICT_FROZEN_CONFIG
from ...core.config import Settings
from ...core.time import UtcInstant, now

__all__ = [
    "ExtractedDocumentCacheDocument",
    "ExtractedDocumentCacheRepository",
    "ExtractedDocumentEntry",
    "load_extracted_document_cache",
    "read_cached_extraction",
    "write_cached_extraction",
]


class ExtractedDocumentEntry(BaseModel):
    """One document's extraction, keyed by the content address of its bytes.

    Attributes:
        content_sha256: Content address of the source document bytes. The cache
            key, so identical bytes reached through different evidence records
            or attachments resolve to one entry.
        extracted_text: The deterministic extraction. FINANCIAL: this is the
            invoice's contents in readable form.
        extractor: Which reader produced it, so an entry written by a superseded
            extractor is identifiable rather than silently trusted.
        cached_at: When the entry was written.
    """

    model_config = STRICT_FROZEN_CONFIG

    content_sha256: str = Field(min_length=64, max_length=64)
    extracted_text: str
    extractor: str = Field(min_length=1)
    cached_at: UtcInstant


class ExtractedDocumentCacheDocument(BaseModel):
    """One bucket's encrypted extraction cache."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: str = Field(min_length=1)
    entries: tuple[ExtractedDocumentEntry, ...] = ()


class ExtractedDocumentCacheRepository(SecureBoundRepository[ExtractedDocumentCacheDocument]):
    """Encrypted store for one bucket's extraction cache.

    Namespace, sensitivity and schema version come from the registry
    definition; the base wraps every document in an ``Envelope`` before it
    reaches disk, which is what makes "no cache byte lands in the clear" a
    property of the substrate rather than of this module's care.
    """

    namespace = LEDGER_EXTRACTED_DOCUMENT_CACHE_NAMESPACE.namespace
    sensitivity = LEDGER_EXTRACTED_DOCUMENT_CACHE_NAMESPACE.sensitivity
    schema_version = LEDGER_EXTRACTED_DOCUMENT_CACHE_NAMESPACE.schema_version
    payload_type = ExtractedDocumentCacheDocument

    @override
    def extract_identifier(self, payload: ExtractedDocumentCacheDocument) -> str:
        return payload.bucket_id


def _repository(bucket_id: str, settings: Settings) -> ExtractedDocumentCacheRepository:
    return ExtractedDocumentCacheRepository(objects=secure_object_repository_for_bucket(bucket_id, settings))


def load_extracted_document_cache(bucket_id: str, settings: Settings) -> ExtractedDocumentCacheDocument:
    """Load a bucket's extraction cache, or an empty one when none exists yet."""
    document = _repository(bucket_id, settings).load(bucket_id)
    return document if document is not None else ExtractedDocumentCacheDocument(bucket_id=bucket_id)


def read_cached_extraction(
    *,
    bucket_id: str,
    content_sha256: str,
    settings: Settings,
) -> str | None:
    """Return the cached extraction for these bytes, or ``None`` on a miss.

    A miss is not an error: the caller re-extracts and writes through. The cache
    is an optimisation over a deterministic function, so a cold cache and a warm
    one must produce identical results -- which is what makes it safe to drop
    entirely.
    """
    cache = load_extracted_document_cache(bucket_id, settings)
    entry = next((row for row in cache.entries if row.content_sha256 == content_sha256), None)
    return entry.extracted_text if entry is not None else None


def write_cached_extraction(
    *,
    bucket_id: str,
    content_sha256: str,
    extracted_text: str,
    extractor: str,
    settings: Settings,
) -> ExtractedDocumentCacheDocument:
    """Write an extraction through the core's encrypted repository.

    Replaces any prior entry for the same content address rather than appending
    a second: the key is the bytes, and two extractions of one document are the
    same fact re-derived, not two facts.
    """
    cache = load_extracted_document_cache(bucket_id, settings)
    retained = tuple(row for row in cache.entries if row.content_sha256 != content_sha256)
    updated = ExtractedDocumentCacheDocument(
        bucket_id=bucket_id,
        entries=(
            *retained,
            ExtractedDocumentEntry(
                content_sha256=content_sha256,
                extracted_text=extracted_text,
                extractor=extractor,
                cached_at=now(),
            ),
        ),
    )
    _repository(bucket_id, settings).save(updated)
    return updated
