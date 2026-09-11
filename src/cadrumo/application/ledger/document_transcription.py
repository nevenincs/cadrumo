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
"""

from __future__ import annotations

from typing import Never, Self, SupportsIndex, override

from pydantic import BaseModel, Field, model_serializer, model_validator

from ...core.field_origin import FieldOrigin
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG

__all__ = [
    "ACQUISITION_ORIGINS",
    "DocumentTranscription",
    "TranscriberIdentity",
]


_REFUSAL_MESSAGE = (
    "DocumentTranscription must never be serialized, iterated, or persisted directly; it holds a "
    "document's FINANCIAL contents in memory only "
    "(sensitive-financial-data-secure-storage-only)."
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
    produced by one model under one prompt revision is not interchangeable with
    one produced by the same model under another.

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


class DocumentTranscription(BaseModel):
    """A document's faithful reading-order text plus the provenance to cite it.

    In-memory only; see the module docstring for the custody contract.

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

    @model_serializer
    def _refuse_model_serialization(self) -> dict[str, object]:
        """Refuse pydantic serialization on every route, including nested dumps.

        Registered as the model serializer so a parent model that embeds a
        transcription and calls ``model_dump`` also raises here rather than
        serializing the text through the field schema.
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
