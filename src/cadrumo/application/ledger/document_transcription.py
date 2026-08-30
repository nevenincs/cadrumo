"""The faithful text representation a document ingestion produces at stage S1.

The acquisition stage of the ingestion pipeline turns a document's bytes into
one typed record: reading-order text with the document's own **printed forms
preserved**, the page count, the content address of the bytes it was read from,
and the identity of whatever transcribed it. Everything downstream -- semantic
extraction, anchor grounding, classification -- reads this record rather than
the bytes, so it is the seam the whole pipeline is anchored to.

**One record, not a union.** A text-layer read and a vision read differ in their
:class:`TranscriberIdentity`, never in their type. A tagged union would push a
branch into every consumer for a distinction only provenance cares about, and
would let a consumer forget the branch that matters.

**Printed forms are preserved literally.** ``2.420,00`` stays ``2.420,00``; it is
never normalised to ``2420.00`` on the way in. The grounding stage verifies a
candidate value by finding its verbatim anchor in this text, so normalising here
would delete the evidence the anchor check runs against -- and the corpus scores
against printed form. Nothing in this module transforms :attr:`
DocumentTranscription.text`.

CRITICAL (``sensitive-financial-data-secure-storage-only``): the transcription of
an invoice *is* the invoice, in a shape a grep can read. This record holds it in
process memory ONLY and carries the same serialization tripwires as
:class:`~cadrumo.application.ledger.evidence_input.EvidenceInput` -- ``model_dump``,
``model_dump_json``, iteration and pickling all raise, so a stray persistence
call fails loudly rather than writing taxpayer financial data out in the clear.
The one sanctioned durable route is :meth:`DocumentTranscription.to_cache_entry`,
whose result persists only through the core's encrypted bucket-scoped repository
(see :mod:`cadrumo.application.ledger.extracted_document_cache`). That route is
a named method rather than a serializer flag precisely so it is greppable: every
place a transcription becomes durable names it.
"""

from __future__ import annotations

from typing import Never, Self, SupportsIndex, override

from pydantic import BaseModel, Field, model_serializer, model_validator

from ...core import FieldOrigin
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.identity import ContentDigest
from ...core.time import UtcInstant, now

__all__ = [
    "ACQUISITION_ORIGINS",
    "DocumentTranscription",
    "TranscriberIdentity",
    "TranscriptionCacheEntry",
]


_REFUSAL_MESSAGE = (
    "DocumentTranscription must never be serialized, iterated, or persisted directly; it holds a "
    "document's FINANCIAL contents in memory only. Persist it through to_cache_entry() and the "
    "encrypted transcription cache (sensitive-financial-data-secure-storage-only)."
)

ACQUISITION_ORIGINS = frozenset({FieldOrigin.TEXT_LAYER, FieldOrigin.VISION})
"""The origins stage S1 can actually produce.

Derived from the closed core taxonomy rather than restated as strings, so a new
:class:`~cadrumo.core.FieldOrigin` member cannot silently become an acquisition
origin. ``EXACT_STRUCTURED`` values come from a machine-readable record that
needs no transcription at all, ``TABULAR_MAPPED`` from a column-role mapping,
and ``OPERATOR`` from a human at the confirm boundary -- none of the three
transcribes a document, so none may stamp a transcription.
"""


class TranscriberIdentity(BaseModel):
    """Who produced a transcription, at what revision.

    Every axis is required for both origins, and none has a default. A
    provenance stamp that can be constructed without naming its producer is a
    stamp that will eventually be constructed wrong: a hardcoded default would
    let a transcription claim a reader it did not come from, which is exactly
    the class of lie a provenance record exists to make impossible. The
    transport is required for the same reason and it is the sharper case -- a
    defaulted transport would let an off-host read claim it never left the
    machine, and that claim is the one a consent withdrawal rests on.

    The revision is load-bearing rather than decorative. A transcription
    produced by one model under one prompt revision is NOT interchangeable with
    one produced by the same model under another -- so the revision is part of
    the cache key, and a re-read under a new revision is a new fact rather than
    a replacement of the old one.

    Attributes:
        origin: Which acquisition path read the document -- ``TEXT_LAYER`` for
            the deterministic extraction, ``VISION`` for a local vision model in
            transcription role. Constrained to :data:`ACQUISITION_ORIGINS`.
        name: The concrete reader, e.g. a deterministic extractor's name or a
            vision model's identifier. Never a coarse label like ``local``: the
            point is to know which reader's output is being trusted.
        transport: Where the read ran, as the one canonical transport token
            (:func:`~core.provenance_transport_label`). A transcription is a
            durable artefact derived from the document, so one produced
            off-host is an artefact a consent withdrawal must enumerate -- and
            a model identifier reveals its vendor only to a reader who already
            knows the catalogue.

            Its own axis rather than folded into ``name``, which is where it
            started: ``name`` is contracted to say WHICH reader produced the
            text and explicitly not to carry a coarse label, so smuggling the
            transport through it broke that contract and created a third
            provenance grammar nothing could parse. Recorded as data, nothing
            has to parse it at all.
        revision: The reader's version -- an extractor release, or a model's
            weights-plus-prompt revision.
    """

    model_config = STRICT_FROZEN_CONFIG

    origin: FieldOrigin
    name: str = Field(min_length=1)
    transport: str = Field(min_length=1)
    revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def _reject_non_acquisition_origin(self) -> Self:
        """Refuse an origin that names something other than a document read."""
        if self.origin not in ACQUISITION_ORIGINS:
            accepted = ", ".join(sorted(member.value for member in ACQUISITION_ORIGINS))
            raise ValueError(
                f"TranscriberIdentity.origin must be an acquisition origin ({accepted}); got {self.origin.value!r}",
            )
        return self

    @property
    def cache_key(self) -> str:
        """Return the stable transcriber half of the transcription cache key.

        Folds every axis that makes two transcriptions non-interchangeable, so
        a vision re-read and a text-layer read of the same bytes occupy separate
        cache entries rather than overwriting one another.

        The transport is one of those axes, and it was already folded in before
        it had its own field -- it rode inside ``name``. Keeping it here is
        therefore preservation rather than a new decision, and the reason it
        earns the place is that serving the same model off-host is a different
        trust context, not merely a different route.
        """
        return f"{self.origin.value}:{self.transport}-{self.name}@{self.revision}"


class DocumentTranscription(BaseModel):
    """A document's faithful reading-order text plus the provenance to cite it.

    In-memory only; see the module docstring for the custody contract and the
    single sanctioned durable route.

    Attributes:
        text: The document's reading-order text with printed forms preserved
            verbatim. FINANCIAL: this is the document's contents in readable
            form, so it is excluded from ``repr``.
        page_count: How many pages were read. At least one -- a transcription of
            no pages is a failed read, not an empty success.
        source_content_sha256: 64-character lowercase hex SHA-256 content address
            of the source bytes. Identical bytes reached through different
            evidence records or attachments resolve to one transcription.
        transcriber: Which reader produced this text, at which revision.
    """

    model_config = STRICT_FROZEN_CONFIG

    text: str = Field(min_length=1, repr=False)
    page_count: int = Field(ge=1)
    source_content_sha256: ContentDigest
    transcriber: TranscriberIdentity

    @property
    def cache_key(self) -> tuple[str, str]:
        """Return the full cache key: source content address plus transcriber.

        Deliberately not the evidence id and not a path. The same bytes reached
        through two evidence records are one document, and a path is not
        identity at all -- so the bytes address the entry and the transcriber
        distinguishes the readings of it.
        """
        return (self.source_content_sha256, self.transcriber.cache_key)

    def to_cache_entry(self, *, cached_at: UtcInstant | None = None) -> TranscriptionCacheEntry:
        """Return the persistable mirror of this transcription.

        The ONE sanctioned route out of memory. The returned entry is an
        ordinary strict model that serializes normally, because it is written
        exclusively through the core's encrypted repository; this record keeps
        its tripwires so that every other route still fails loudly.

        Args:
            cached_at: When the entry was written. Defaults to now.
        """
        return TranscriptionCacheEntry(
            text=self.text,
            page_count=self.page_count,
            source_content_sha256=self.source_content_sha256,
            transcriber=self.transcriber,
            cached_at=cached_at if cached_at is not None else now(),
        )

    @model_serializer
    def _refuse_model_serialization(self) -> dict[str, object]:
        """Refuse pydantic serialization on every route, including nested dumps.

        Registered as the model serializer so a parent model that embeds a
        transcription and calls ``model_dump`` also raises here rather than
        serializing the text through the field schema. This is what makes the
        cache entry's separate existence load-bearing: a document holding a
        transcription cannot be persisted by accident, only by conversion.
        """
        raise NotImplementedError(_REFUSAL_MESSAGE)

    @override
    def model_dump(self, *args: object, **kwargs: object) -> Never:  # reason: deliberate persistence tripwire
        """Refuse serialization -- a document's readable contents must not leak."""
        raise NotImplementedError(_REFUSAL_MESSAGE)

    @override
    def model_dump_json(self, *args: object, **kwargs: object) -> Never:  # reason: deliberate persistence tripwire
        """Refuse JSON serialization -- a document's readable contents must not leak."""
        raise NotImplementedError(_REFUSAL_MESSAGE)

    @override
    def __iter__(self) -> Never:  # reason: deliberate persistence tripwire
        """Refuse iteration / ``dict()`` -- it would expose the transcribed text."""
        raise NotImplementedError(_REFUSAL_MESSAGE)

    @override
    def __reduce_ex__(self, protocol: SupportsIndex) -> Never:
        """Refuse pickling -- it would embed the transcribed text."""
        raise NotImplementedError(_REFUSAL_MESSAGE)


class TranscriptionCacheEntry(BaseModel):
    """One cached transcription, as it is written to encrypted storage.

    The persistable mirror of :class:`DocumentTranscription`. It carries the same
    facts plus the write time, and it serializes normally -- deliberately, because
    its only writer is the encrypted bucket-scoped repository. The pair is what
    keeps "no transcription lands in the clear" a structural property: the
    in-memory record cannot serialize at all, and the shape that can is only ever
    handed to the encrypted substrate.

    Attributes:
        text: The transcribed text, printed forms preserved. FINANCIAL.
        page_count: Pages read.
        source_content_sha256: Content address of the source bytes.
        transcriber: Which reader produced the text, at which revision.
        cached_at: When the entry was written.
    """

    model_config = STRICT_FROZEN_CONFIG

    text: str = Field(min_length=1, repr=False)
    page_count: int = Field(ge=1)
    source_content_sha256: ContentDigest
    transcriber: TranscriberIdentity
    cached_at: UtcInstant

    @property
    def cache_key(self) -> tuple[str, str]:
        """Return the entry's key: source content address plus transcriber."""
        return (self.source_content_sha256, self.transcriber.cache_key)

    def to_transcription(self) -> DocumentTranscription:
        """Return the in-memory transcription this entry mirrors.

        The read half of the sanctioned route. A loaded entry becomes a
        tripwired record again immediately, so a cache hit and a fresh read are
        indistinguishable to every consumer -- including in what they refuse.
        """
        return DocumentTranscription(
            text=self.text,
            page_count=self.page_count,
            source_content_sha256=self.source_content_sha256,
            transcriber=self.transcriber,
        )
