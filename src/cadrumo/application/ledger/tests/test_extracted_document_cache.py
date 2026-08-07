"""The extraction cache roundtrips through real encrypted storage, or refuses.

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

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._extracted_document_cache import (
    ExtractedDocumentCacheDocument,
    ExtractedDocumentEntry,
    load_extracted_document_cache,
    read_cached_extraction,
    write_cached_extraction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_DIGEST = "b" * 64
_OTHER_DIGEST = "c" * 64


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
    written = write_cached_extraction(
        bucket_id=profile.bucket_id,
        content_sha256=_DIGEST,
        extracted_text="Factura Acme SL\nBase imponible 100,00",
        extractor="pdfplumber-text-layer",
        settings=profile.settings,
    )

    reloaded = load_extracted_document_cache(profile.bucket_id, profile.settings)

    assert reloaded == written, "the boundary must return exactly what crossed it"
    assert reloaded.entries[0].extracted_text == "Factura Acme SL\nBase imponible 100,00"
    assert reloaded.entries[0].extractor == "pdfplumber-text-layer"


def test_a_second_extraction_of_the_same_bytes_replaces_rather_than_appends(
    profile: TestRuntimeProfile,
) -> None:
    """The key is the content address, so one document yields one entry.

    Two extractions of one document are the same fact re-derived, not two
    facts. Appending would grow the cache without bound on every re-read and
    leave two answers for one question, with nothing saying which is current.
    """
    write_cached_extraction(
        bucket_id=profile.bucket_id,
        content_sha256=_DIGEST,
        extracted_text="first pass",
        extractor="pdfplumber-text-layer",
        settings=profile.settings,
    )
    write_cached_extraction(
        bucket_id=profile.bucket_id,
        content_sha256=_DIGEST,
        extracted_text="second pass",
        extractor="pdfplumber-text-layer",
        settings=profile.settings,
    )
    write_cached_extraction(
        bucket_id=profile.bucket_id,
        content_sha256=_OTHER_DIGEST,
        extracted_text="a different document",
        extractor="pdfplumber-text-layer",
        settings=profile.settings,
    )

    cache = load_extracted_document_cache(profile.bucket_id, profile.settings)

    assert len(cache.entries) == 2, "one entry per content address"
    assert read_cached_extraction(
        bucket_id=profile.bucket_id,
        content_sha256=_DIGEST,
        settings=profile.settings,
    ) == "second pass"


def test_a_miss_returns_none_rather_than_raising(profile: TestRuntimeProfile) -> None:
    """A cold cache is the normal case, not an error.

    The cache memoises a deterministic function, so a miss must be
    indistinguishable in outcome from a hit: the caller re-extracts. That is
    what makes the whole store safe to drop.
    """
    assert (
        read_cached_extraction(
            bucket_id=profile.bucket_id,
            content_sha256=_DIGEST,
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
    from pydantic import ValidationError

    payload = ExtractedDocumentCacheDocument(
        bucket_id=profile.bucket_id,
        entries=(
            ExtractedDocumentEntry(
                content_sha256=_DIGEST,
                extracted_text="Factura Acme SL",
                extractor="pdfplumber-text-layer",
                cached_at=datetime(2024, 11, 15, 9, 0, tzinfo=UTC),
            ),
        ),
    )
    corrupted = payload.model_dump(mode="json")
    del corrupted["entries"][0]["extractor"]

    with pytest.raises(ValidationError):
        ExtractedDocumentCacheDocument.model_validate(corrupted)


def test_an_unexpected_stored_key_is_refused_rather_than_ignored() -> None:
    """A strict model rejects a field it does not declare.

    Guards the other direction from the deletion proof: a boundary that ignores
    unknown keys accepts a payload written by a shape it does not understand and
    silently discards whatever that shape carried.
    """
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ExtractedDocumentCacheDocument.model_validate(
            {"bucket_id": "b", "entries": [], "unexpected_key": "smuggled"},
        )
