"""The transcription cache roundtrips through real encrypted storage, or refuses.

A persistence boundary needs a strict save-load-equality roundtrip against the
REAL adapter -- real key provider, real SQLite engine, real serializer -- plus
an anti-tautology proof that mutating the stored payload makes the load fail.
Without the second, every roundtrip in the suite could be passing on a boundary
that silently re-defaults whatever it dropped.

Every defaultable field is populated NON-default on purpose. A fixture built on
defaults cannot detect a save-drops-field / load-re-defaults-field regression:
the field never differed, so nothing notices when it stops surviving.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.provenance_stamp import LOCAL_TRANSPORT_LABEL
from ....core.field_origin import FieldOrigin
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ..document_transcription import DocumentTranscription, TranscriberIdentity
from ..extracted_document_cache import (
    ExtractedDocumentCacheDocument,
    load_extracted_document_cache,
    read_cached_transcription,
    write_cached_transcription,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_DIGEST = "b" * 64
_OTHER_DIGEST = "c" * 64

_TEXT_LAYER = TranscriberIdentity(
    transport=LOCAL_TRANSPORT_LABEL,
    origin=FieldOrigin.TEXT_LAYER,
    name="pdfplumber-text-layer",
    revision="0.11.4",
)
_VISION = TranscriberIdentity(
    transport=LOCAL_TRANSPORT_LABEL,
    origin=FieldOrigin.VISION,
    name="qwen2.5-vl-7b-instruct",
    revision="q4_k_m/prompt-r3",
)


def _transcription(
    *,
    text: str = "Factura Acme SL\nBase imponible 2.420,00",
    digest: str = _DIGEST,
    transcriber: TranscriberIdentity = _TEXT_LAYER,
    page_count: int = 2,
) -> DocumentTranscription:
    return DocumentTranscription(
        text=text,
        page_count=page_count,
        source_content_sha256=digest,
        transcriber=transcriber,
    )


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """A real isolated runtime profile -- real key provider, real SQLite engine.

    The roundtrip must cross the production adapter, not a stand-in: a stub that
    returns what the test expects is the canonical false positive for a
    persistence boundary.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as resolved:
        yield resolved


def test_the_cache_roundtrips_through_the_real_encrypted_repository(profile: TestRuntimeProfile) -> None:
    """Save, load, assert strict equality -- through the real adapter, not a stub.

    A mock that returns what the test expects is the canonical false positive
    for a persistence boundary, which is why this drives the real secure-object
    repository the production path uses.
    """
    original = _transcription()

    written = write_cached_transcription(
        bucket_id=profile.bucket_id,
        transcription=original,
        settings=profile.settings,
    )
    reloaded = load_extracted_document_cache(profile.bucket_id, profile.settings)

    assert reloaded == written, "the boundary must return exactly what crossed it"
    recovered = read_cached_transcription(
        bucket_id=profile.bucket_id,
        source_content_sha256=_DIGEST,
        transcriber_cache_key=_TEXT_LAYER.cache_key,
        settings=profile.settings,
    )
    assert recovered == original, "the record that comes back must equal the one that went in"


def test_the_printed_forms_survive_the_encrypted_boundary(profile: TestRuntimeProfile) -> None:
    """`2.420,00` crosses real encryption and comes back byte-identical.

    Asserted against the source literal rather than against the record's own
    output: an equality check alone would still hold if the write and the read
    normalised in the same direction.
    """
    text = "Base imponible 2.420,00\nRetencion 15% 363,00\nTotal 2.057,00"
    write_cached_transcription(
        bucket_id=profile.bucket_id,
        transcription=_transcription(text=text),
        settings=profile.settings,
    )

    recovered = read_cached_transcription(
        bucket_id=profile.bucket_id,
        source_content_sha256=_DIGEST,
        transcriber_cache_key=_TEXT_LAYER.cache_key,
        settings=profile.settings,
    )

    assert recovered is not None
    assert recovered.text == text
    assert "2.420,00" in recovered.text


def test_a_second_reading_by_the_same_transcriber_replaces_rather_than_appends(
    profile: TestRuntimeProfile,
) -> None:
    """One reader re-reading one document is the same fact re-derived.

    Appending would grow the cache without bound on every re-read and leave two
    answers for one question, with nothing saying which is current.
    """
    write_cached_transcription(
        bucket_id=profile.bucket_id,
        transcription=_transcription(text="first pass"),
        settings=profile.settings,
    )
    write_cached_transcription(
        bucket_id=profile.bucket_id,
        transcription=_transcription(text="second pass"),
        settings=profile.settings,
    )
    write_cached_transcription(
        bucket_id=profile.bucket_id,
        transcription=_transcription(text="a different document", digest=_OTHER_DIGEST),
        settings=profile.settings,
    )

    cache = load_extracted_document_cache(profile.bucket_id, profile.settings)

    assert len(cache.entries) == 2, "one entry per (content address, transcriber)"
    recovered = read_cached_transcription(
        bucket_id=profile.bucket_id,
        source_content_sha256=_DIGEST,
        transcriber_cache_key=_TEXT_LAYER.cache_key,
        settings=profile.settings,
    )
    assert recovered is not None
    assert recovered.text == "second pass"


def test_a_different_transcriber_keeps_its_own_entry(profile: TestRuntimeProfile) -> None:
    """The transcriber is half the key, so two readers of one document coexist.

    This is the property the old address-only key did not have. A vision read
    and a deterministic text-layer read of the same bytes are different facts,
    and letting whichever ran last answer for both would silently substitute a
    probabilistic reading for an exact one.
    """
    write_cached_transcription(
        bucket_id=profile.bucket_id,
        transcription=_transcription(text="deterministic reading", transcriber=_TEXT_LAYER),
        settings=profile.settings,
    )
    write_cached_transcription(
        bucket_id=profile.bucket_id,
        transcription=_transcription(text="vision reading", transcriber=_VISION),
        settings=profile.settings,
    )

    cache = load_extracted_document_cache(profile.bucket_id, profile.settings)
    assert len(cache.entries) == 2, "same bytes, two readers, two entries"

    def _read(identity: TranscriberIdentity) -> DocumentTranscription | None:
        return read_cached_transcription(
            bucket_id=profile.bucket_id,
            source_content_sha256=_DIGEST,
            transcriber_cache_key=identity.cache_key,
            settings=profile.settings,
        )

    deterministic = _read(_TEXT_LAYER)
    vision = _read(_VISION)
    assert deterministic is not None and deterministic.text == "deterministic reading"
    assert vision is not None and vision.text == "vision reading"


def test_a_revision_change_is_a_miss_rather_than_a_stale_hit(profile: TestRuntimeProfile) -> None:
    """A reading under one prompt revision does not answer for another.

    The revision is in the key because a transcription produced under one prompt
    revision is not interchangeable with one produced under the next; serving the
    old text for the new revision would make an improvement invisible.
    """
    write_cached_transcription(
        bucket_id=profile.bucket_id,
        transcription=_transcription(transcriber=_VISION),
        settings=profile.settings,
    )
    newer = TranscriberIdentity(
        transport=LOCAL_TRANSPORT_LABEL, origin=FieldOrigin.VISION, name=_VISION.name, revision="q4_k_m/prompt-r4"
    )

    assert (
        read_cached_transcription(
            bucket_id=profile.bucket_id,
            source_content_sha256=_DIGEST,
            transcriber_cache_key=newer.cache_key,
            settings=profile.settings,
        )
        is None
    )


def test_a_miss_returns_none_rather_than_raising(profile: TestRuntimeProfile) -> None:
    """A cold cache is the normal case, not an error.

    The cache memoises a read whose result is a fact about the document, so a
    miss must be indistinguishable in outcome from a hit: the caller re-reads.
    That is what makes the whole store safe to drop.
    """
    assert (
        read_cached_transcription(
            bucket_id=profile.bucket_id,
            source_content_sha256=_DIGEST,
            transcriber_cache_key=_TEXT_LAYER.cache_key,
            settings=profile.settings,
        )
        is None
    )


def test_deleting_a_persisted_field_makes_the_load_refuse(profile: TestRuntimeProfile) -> None:
    """Anti-tautology: corrupt the stored payload, prove the load notices.

    If this ever passes while the boundary is broken, every roundtrip above is
    tautological. The strict model must REFUSE a payload missing a field rather
    than silently re-defaulting it, because a silent re-default is exactly how a
    dropped field escapes a roundtrip test.
    """
    payload = ExtractedDocumentCacheDocument(
        bucket_id=profile.bucket_id,
        entries=(_transcription().to_cache_entry(cached_at=datetime(2024, 11, 15, 9, 0, tzinfo=UTC)),),
    )
    stored = payload.model_dump_json()

    assert ExtractedDocumentCacheDocument.model_validate_json(stored) == payload, (
        "positive control: the intact payload must load through this exact route, "
        "or every refusal below passes for the wrong reason"
    )

    for deleted in ("text", "page_count", "source_content_sha256", "cached_at"):
        corrupted = json.loads(stored)
        del corrupted["entries"][0][deleted]
        with pytest.raises(ValidationError):
            ExtractedDocumentCacheDocument.model_validate_json(json.dumps(corrupted))

    corrupted = json.loads(stored)
    del corrupted["entries"][0]["transcriber"]["revision"]
    with pytest.raises(ValidationError):
        ExtractedDocumentCacheDocument.model_validate_json(json.dumps(corrupted))


def test_an_unexpected_stored_key_is_refused_rather_than_ignored() -> None:
    """A strict model rejects a field it does not declare.

    Guards the other direction from the deletion proof: a boundary that ignores
    unknown keys accepts a payload written by a shape it does not understand and
    silently discards whatever that shape carried.
    """
    assert ExtractedDocumentCacheDocument.model_validate_json('{"bucket_id": "b", "entries": []}') is not None, (
        "positive control: the same route must accept the payload without the extra key"
    )

    with pytest.raises(ValidationError):
        ExtractedDocumentCacheDocument.model_validate_json(
            '{"bucket_id": "b", "entries": [], "unexpected_key": "smuggled"}',
        )


def test_the_cache_document_is_the_only_route_a_transcription_can_be_written(
    profile: TestRuntimeProfile,
) -> None:
    """The cached document persists; the in-memory record still refuses.

    The pairing is the custody guarantee. If a later change made
    ``DocumentTranscription`` serialize directly, the encrypted repository would
    stop being the only way a transcription becomes durable and this assertion
    is what fails.
    """
    written = write_cached_transcription(
        bucket_id=profile.bucket_id,
        transcription=_transcription(),
        settings=profile.settings,
    )

    assert written.model_dump(mode="json")["entries"], "the persistable mirror serializes"

    with pytest.raises(NotImplementedError, match=r"(?i)serial|dump|persist|refus"):
        _transcription().model_dump()
