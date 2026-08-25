"""Encrypted, content-addressed cache of a document's stage-S1 transcription.

Memoises the faithful text a document yields so re-extracting, re-classifying or
re-drafting need not re-read it. Re-reading is the expensive half of ingestion --
a vision transcription costs a model pass over every page -- and the pipeline
deliberately re-runs the cheap semantic stages when a model or prompt improves,
which is only affordable if the transcription itself is kept.

**Why this is application-owned and encrypted.** The cached value is the transcription of
an invoice, which *is* the invoice in a shape a grep can read. On disk in the
clear it would be a new plaintext store of taxpayer financial data that does not
exist in this tree today. The operator ruling exempts IN-MEMORY reading,
rasterising and inference from encryption; it does not reach persistence, and the
rule it clarifies names "on-disk caches" explicitly among what it does not reach.
So the cache is written through the bound encrypted bucket-scoped repository,
and the inference subpackage -- which holds no storage handle -- cannot write it
at all.

**Keyed by source content address plus transcriber identity.** The bytes address
the document, so the same bytes hit the same entry regardless of which evidence
record or attachment referenced them, and a re-ingest of an identical document
reuses the reading rather than repeating it. The transcriber -- reader name and
revision, per :class:`TranscriberIdentity` -- distinguishes the readings of those
bytes, because a text-layer extraction and a vision read of one document are two
different facts and neither supersedes the other. Keying on the address alone
would let whichever ran last silently answer for both.

The value is stored as a :class:`TranscriptionCacheEntry`, the persistable mirror
of the tripwired in-memory :class:`DocumentTranscription`; see
:mod:`cadrumo.application.ledger.document_transcription` for why the record
itself cannot be serialized.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG
from ...core.config import Settings
from ...core.identity import BucketId
from .document_transcription import DocumentTranscription, TranscriptionCacheEntry

__all__ = [
    "ExtractedDocumentCacheDocument",
    "ExtractedDocumentCacheRepositoryFactory",
    "ExtractedDocumentCacheRepositoryProtocol",
    "bind_extracted_document_cache_repository_factory",
    "extracted_document_cache_object_key",
    "load_extracted_document_cache",
    "read_cached_transcription",
    "write_cached_transcription",
]


class ExtractedDocumentCacheDocument(BaseModel):
    """One bucket's encrypted transcription cache."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    entries: tuple[TranscriptionCacheEntry, ...] = ()


def extracted_document_cache_object_key(document: ExtractedDocumentCacheDocument) -> str:
    """Return the bucket-scoped natural key for one cache document."""
    return document.bucket_id


class ExtractedDocumentCacheRepositoryProtocol(Protocol):
    """Persistence operations required by transcription-cache policy."""

    def load(self, identifier: str) -> ExtractedDocumentCacheDocument | None:
        """Load the cache document stored under ``identifier``, when present."""
        ...

    def save(self, payload: ExtractedDocumentCacheDocument) -> None:
        """Persist one complete cache document through encrypted storage."""
        ...


class ExtractedDocumentCacheRepositoryFactory(Protocol):
    """Construct a cache repository for one bucket and storage configuration."""

    def __call__(self, *, bucket_id: str, settings: Settings) -> ExtractedDocumentCacheRepositoryProtocol:
        """Return the encrypted repository bound to ``bucket_id``."""
        ...


_BOUND_EXTRACTED_DOCUMENT_CACHE_REPOSITORY_FACTORY: ContextVar[ExtractedDocumentCacheRepositoryFactory] = ContextVar(
    "cadrumo_extracted_document_cache_repository_factory"
)


@contextmanager
def bind_extracted_document_cache_repository_factory(
    factory: ExtractedDocumentCacheRepositoryFactory,
) -> Generator[ExtractedDocumentCacheRepositoryFactory]:
    """Bind one outward-composed cache repository factory for the host context."""
    token = _BOUND_EXTRACTED_DOCUMENT_CACHE_REPOSITORY_FACTORY.set(factory)
    try:
        yield factory
    finally:
        _BOUND_EXTRACTED_DOCUMENT_CACHE_REPOSITORY_FACTORY.reset(token)


def _repository(bucket_id: str, settings: Settings) -> ExtractedDocumentCacheRepositoryProtocol:
    try:
        factory = _BOUND_EXTRACTED_DOCUMENT_CACHE_REPOSITORY_FACTORY.get()
    except LookupError as error:
        raise RuntimeError("extracted-document-cache persistence has not been composed") from error
    return factory(bucket_id=bucket_id, settings=settings)


def load_extracted_document_cache(bucket_id: str, settings: Settings) -> ExtractedDocumentCacheDocument:
    """Load a bucket's transcription cache, or an empty one when none exists yet."""
    document = _repository(bucket_id, settings).load(bucket_id)
    return document if document is not None else ExtractedDocumentCacheDocument(bucket_id=bucket_id)


def read_cached_transcription(
    *,
    bucket_id: str,
    source_content_sha256: str,
    transcriber_cache_key: str,
    settings: Settings,
) -> DocumentTranscription | None:
    """Return the cached transcription for these bytes and reader, or ``None``.

    A miss is not an error: the caller re-reads and writes through. The cache
    memoises a read whose result is a fact about the document, so a cold cache
    and a warm one must produce the same downstream answers -- which is what
    makes the whole store safe to drop.

    Args:
        bucket_id: The secure-storage bucket to read from.
        source_content_sha256: Content address of the source document bytes.
        transcriber_cache_key: :attr:`TranscriberIdentity.cache_key` of the
            reader whose transcription is wanted. A different reader or a
            different revision is a different entry, never a substitute.
        settings: Deployment settings resolving the storage route.
    """
    cache = load_extracted_document_cache(bucket_id, settings)
    key = (source_content_sha256, transcriber_cache_key)
    entry = next((row for row in cache.entries if row.cache_key == key), None)
    return entry.to_transcription() if entry is not None else None


def write_cached_transcription(
    *,
    bucket_id: str,
    transcription: DocumentTranscription,
    settings: Settings,
) -> ExtractedDocumentCacheDocument:
    """Write a transcription through the bound encrypted repository.

    Replaces any prior entry sharing the same key rather than appending a
    second: one reader re-reading one document produces the same fact
    re-derived, not two facts. A *different* reader keeps its own entry, so the
    replacement never crosses transcriber identities.
    """
    cache = load_extracted_document_cache(bucket_id, settings)
    entry = transcription.to_cache_entry()
    retained = tuple(row for row in cache.entries if row.cache_key != entry.cache_key)
    updated = ExtractedDocumentCacheDocument(bucket_id=bucket_id, entries=(*retained, entry))
    _repository(bucket_id, settings).save(updated)
    return updated
