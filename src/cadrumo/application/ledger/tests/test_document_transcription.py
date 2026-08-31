"""The transcription record keeps its text faithful and refuses to be persisted.

Three properties are load-bearing here and each is gated separately:

* the record cannot serialize by any ordinary route, exactly like
  :class:`~cadrumo.application.ledger.evidence_input.EvidenceInput` -- a transcription of an
  invoice is the invoice in readable form, and the secure-storage rule names
  "on-disk caches" among what the in-memory processing exemption does not reach;
* the ONE sanctioned durable route roundtrips with strict equality, so the
  tripwires cost the pipeline nothing they were not meant to cost;
* the text survives that roundtrip **byte for byte**, printed forms included.
  The grounding stage verifies a candidate by finding its verbatim anchor in
  this text, so a normalisation anywhere on this path deletes the evidence the
  anchor check runs against.

Every defaultable field is populated NON-default on purpose: a fixture built on
defaults cannot detect a drops-field / re-defaults-field regression, because the
field never differed.
"""

from __future__ import annotations

import json
import pickle
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from pydantic_core import PydanticSerializationError

from ....core.field_origin import FieldOrigin
from ....core.provenance_stamp import LOCAL_TRANSPORT_LABEL
from ..document_transcription import (
    ACQUISITION_ORIGINS,
    DocumentTranscription,
    TranscriberIdentity,
    TranscriptionCacheEntry,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DIGEST = "a" * 64

#: A printed form that a naive normaliser would rewrite. Spanish invoices print
#: thousands with a dot and the decimal with a comma, so `2.420,00` round-tripped
#: as `2420.00` is the exact corruption this record exists to prevent.
_PRINTED_TEXT = "FACTURA A-2024/117\nBase imponible 2.420,00 EUR\nIVA 21% 508,20 EUR\nTotal 2.928,20 EUR"


def _transcription(**overrides: object) -> DocumentTranscription:
    fields: dict[str, object] = {
        "text": _PRINTED_TEXT,
        "page_count": 3,
        "source_content_sha256": _DIGEST,
        "transcriber": TranscriberIdentity(
            transport=LOCAL_TRANSPORT_LABEL,
            origin=FieldOrigin.VISION,
            name="qwen2.5-vl-7b-instruct",
            revision="q4_k_m/prompt-r3",
        ),
    }
    fields.update(overrides)
    return DocumentTranscription(**fields)  # type: ignore[arg-type]


def test_the_record_refuses_every_ordinary_serialization_route() -> None:
    """Dump, JSON dump, iteration and pickling all raise.

    Four routes rather than one because each is a separate way a document's
    readable contents reach a durable artefact, and closing three of four is
    the same as closing none.
    """
    transcription = _transcription()

    with pytest.raises(NotImplementedError, match=r"(?i)serial|dump|persist|refus"):
        transcription.model_dump()

    with pytest.raises(NotImplementedError, match=r"(?i)serial|dump|persist|refus"):
        transcription.model_dump_json()

    with pytest.raises(NotImplementedError, match=r"(?i)serial|dump|persist|refus"):
        dict(transcription)  # type: ignore[call-overload]

    with pytest.raises(NotImplementedError, match=r"(?i)serial|dump|persist|refus"):
        pickle.dumps(transcription)


def test_a_parent_model_embedding_a_transcription_also_refuses() -> None:
    """The tripwire survives nesting, which is how it would otherwise be lost.

    A record that refuses its own dump but serializes cleanly as a field is
    protected only against the mistake nobody makes. Registering the refusal as
    the model serializer is what makes the nested route raise too.
    """
    from pydantic import BaseModel

    class Holder(BaseModel):
        transcription: DocumentTranscription

    holder = Holder(transcription=_transcription())

    with pytest.raises(PydanticSerializationError, match=r"(?i)serial|dump|persist|refus"):
        holder.model_dump()

    with pytest.raises(PydanticSerializationError, match=r"(?i)serial|dump|persist|refus"):
        holder.model_dump_json()


def test_the_text_is_excluded_from_repr() -> None:
    """A repr is a log line waiting to happen, so the contents stay out of it."""
    rendered = repr(_transcription())

    assert "2.420,00" not in rendered
    assert "FACTURA" not in rendered
    assert _DIGEST in rendered, "provenance stays visible; only the contents are withheld"


def test_the_sanctioned_cache_route_roundtrips_with_strict_equality() -> None:
    """Record to entry to JSON to entry to record, asserting model equality.

    The tripwires must not cost the pipeline the ability to cache. This drives
    the exact conversion the encrypted cache uses, through a real serialization
    cycle, and asserts the record that comes back equals the one that went in --
    not a field-by-field subset, which is how a dropped field survives a
    roundtrip test.
    """
    original = _transcription()
    stamped = datetime(2024, 11, 15, 9, 30, tzinfo=UTC)

    entry = original.to_cache_entry(cached_at=stamped)
    reloaded_entry = TranscriptionCacheEntry.model_validate_json(entry.model_dump_json())

    assert reloaded_entry == entry, "the serialization cycle must return exactly what crossed it"
    assert reloaded_entry.to_transcription() == original
    assert reloaded_entry.cached_at == stamped


def test_the_printed_forms_survive_the_cache_route_byte_for_byte() -> None:
    """`2.420,00` stays `2.420,00`. Nothing on this path may normalise it.

    Separate from the equality roundtrip on purpose: equality would still hold
    if BOTH sides normalised identically, so this asserts the literal printed
    form against the source string rather than against the record's own output.
    """
    recovered = _transcription().to_cache_entry().to_transcription().text

    assert recovered == _PRINTED_TEXT
    assert "2.420,00" in recovered
    assert "2420.00" not in recovered


def test_the_transcriber_identity_is_part_of_the_cache_key() -> None:
    """Two readers of one document key differently, and so does one reader's revision.

    A cache keyed on the bytes alone lets whichever reader ran last answer for
    every reader, which silently substitutes a probabilistic vision read for a
    deterministic text-layer one.
    """
    vision = _transcription()
    text_layer = _transcription(
        transcriber=TranscriberIdentity(
            transport=LOCAL_TRANSPORT_LABEL,
            origin=FieldOrigin.TEXT_LAYER,
            name="pdfplumber-text-layer",
            revision="0.11.4",
        ),
    )
    newer_revision = _transcription(
        transcriber=TranscriberIdentity(
            transport=LOCAL_TRANSPORT_LABEL,
            origin=FieldOrigin.VISION,
            name="qwen2.5-vl-7b-instruct",
            revision="q4_k_m/prompt-r4",
        ),
    )

    assert vision.cache_key[0] == text_layer.cache_key[0] == newer_revision.cache_key[0]
    assert len({vision.cache_key, text_layer.cache_key, newer_revision.cache_key}) == 3


@pytest.mark.parametrize(
    "origin",
    [member for member in FieldOrigin if member not in ACQUISITION_ORIGINS],
)
def test_a_non_acquisition_origin_is_refused(origin: FieldOrigin) -> None:
    """Only a reader that actually transcribes a document may stamp one.

    Parametrised over the closed enum's complement rather than over a hand-listed
    set, so a new ``FieldOrigin`` member is covered the moment it lands instead
    of quietly defaulting to accepted.
    """
    with pytest.raises(ValidationError):
        TranscriberIdentity(transport=LOCAL_TRANSPORT_LABEL, origin=origin, name="reader", revision="1")


def test_a_transcriber_identity_cannot_be_built_without_naming_its_reader() -> None:
    """No default fills in the producer, and neither half may be blank.

    The failure this forecloses is a real one seen in this codebase: a provenance
    stamp that hardcoded `local` would have claimed a cloud read was on-host.
    A required field with no default cannot lie by omission.
    """
    assert TranscriberIdentity.model_validate_json(
        '{"origin": "vision", "name": "model", "transport": "local", "revision": "r1"}',
    ), "positive control: the complete payload must build, or the refusals below prove nothing"

    with pytest.raises(ValidationError):
        TranscriberIdentity.model_validate_json('{"origin": "vision"}')

    # The transport is the sharper case of the same rule. A defaulted one would
    # let an off-host read claim it never left the machine, and that claim is
    # what a consent withdrawal rests on -- so its absence must refuse rather
    # than resolve to the reassuring answer.
    with pytest.raises(ValidationError):
        TranscriberIdentity.model_validate_json(
            '{"origin": "vision", "name": "model", "revision": "r1"}',
        )

    with pytest.raises(ValidationError):
        TranscriberIdentity(transport=LOCAL_TRANSPORT_LABEL, origin=FieldOrigin.VISION, name="", revision="r1")

    with pytest.raises(ValidationError):
        TranscriberIdentity(transport=LOCAL_TRANSPORT_LABEL, origin=FieldOrigin.VISION, name="model", revision="")


def test_an_empty_or_pageless_transcription_is_refused() -> None:
    """A read that produced nothing is a failure, not an empty success.

    A zero-page or empty-text record would cache as a legitimate hit and answer
    for the document forever, so the failure has to be refused at construction
    rather than stored.
    """
    with pytest.raises(ValidationError):
        _transcription(text="")

    with pytest.raises(ValidationError):
        _transcription(page_count=0)


def test_the_persisted_entry_refuses_an_unexpected_key() -> None:
    """Strict on the way in: a payload written by a shape we do not know is refused.

    The complement of the cache's deletion proof. A boundary that ignores
    unknown keys accepts a foreign payload and silently discards what it carried.
    """
    entry = json.loads(_transcription().to_cache_entry().model_dump_json())

    assert TranscriptionCacheEntry.model_validate_json(json.dumps(entry)) is not None, (
        "positive control: the unmutated payload must load, or the refusal below proves nothing"
    )

    entry["unexpected_key"] = "smuggled"
    with pytest.raises(ValidationError):
        TranscriptionCacheEntry.model_validate_json(json.dumps(entry))
