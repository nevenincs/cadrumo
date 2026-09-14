"""Regression tests for content-addressed source-citation text caching."""

from __future__ import annotations

import hashlib
import os
from datetime import date
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_base import SourceCitation
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ..compiler.validate_evidence import EvidenceValidator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SOURCE_ID = "test-source-citation-cache"
_ORIGINAL_TEXT = "original cited phrase"
_REPLACEMENT_TEXT = "replaced cited phrase"


def _source_reference(payload: bytes) -> SourceReference:
    return SourceReference(
        id=_SOURCE_ID,
        evidence_tier="official_source_guidance",
        authority="aeat",
        kind="instructions",
        corpus_path="corpus/test/source.txt",
        sha256=hashlib.sha256(payload).hexdigest(),
        bytes=len(payload),
        retrieved_at=date(2026, 9, 14),
        source_url="https://sede.agenciatributaria.gob.es/test/source.txt",
        review_status="pending_review",
    )


def _validator(source: SourceReference, *, source_root: Path) -> EvidenceValidator:
    return EvidenceValidator(legal_refs={}, source_refs={source.id: source}, source_root=source_root)


def _citation(required_text: str) -> SourceCitation:
    return SourceCitation(source_ref=_SOURCE_ID, required_text=(required_text,))


def _citation_failures(
    validator: EvidenceValidator,
    *,
    required_text: str,
) -> list[str]:
    return validator.validate_source_citations(
        "test scope",
        "test owner",
        (_SOURCE_ID,),
        (_citation(required_text),),
        "official_source_guidance",
    )


def test_source_citation_cache_follows_declared_content_identity_after_metadata_preserving_replacement(
    tmp_path: Path,
) -> None:
    """A new source digest must prevent reuse of superseded citation text."""
    original_payload = _ORIGINAL_TEXT.encode()
    replacement_payload = _REPLACEMENT_TEXT.encode()
    assert len(replacement_payload) == len(original_payload)

    source_path = tmp_path / "corpus" / "test" / "source.txt"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(original_payload)
    original_source = _source_reference(original_payload)

    first_validator = _validator(original_source, source_root=tmp_path)
    assert _citation_failures(first_validator, required_text=_ORIGINAL_TEXT) == []

    original_stat = source_path.stat()
    source_path.write_bytes(replacement_payload)
    os.utime(source_path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    replacement_source = _source_reference(replacement_payload)

    assert source_path.stat().st_size == original_stat.st_size
    assert source_path.stat().st_mtime_ns == original_stat.st_mtime_ns
    assert replacement_source.sha256 != original_source.sha256

    second_validator = _validator(replacement_source, source_root=tmp_path)
    old_quote_failures = _citation_failures(second_validator, required_text=_ORIGINAL_TEXT)
    assert any("missing text" in failure and _ORIGINAL_TEXT in failure for failure in old_quote_failures)
    assert _citation_failures(second_validator, required_text=_REPLACEMENT_TEXT) == []
