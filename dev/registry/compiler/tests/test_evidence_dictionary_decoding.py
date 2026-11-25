"""Citation evidence uses the dictionary parser's encoding contract and a fresh cache identity."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from cadrumo.core.hashing import sha256_hex
from cadrumo.domain.calculations.registry.schema_base import RegistrySourceKind, SourceCitation
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from .. import validate_evidence

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_QUOTE = "Resultado de la declaración – Ingreso o devolución"


def _source(
    root: Path,
    body: bytes,
    *,
    kind: RegistrySourceKind = RegistrySourceKind.DICTIONARY,
    suffix: str = ".properties",
) -> SourceReference:
    corpus_path = f"corpus/aeat_official/dictionary{suffix}"
    path = root / corpus_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return SourceReference(
        id="fixture-dictionary",
        evidence_tier="layout_authority",
        authority="aeat",
        kind=kind,
        corpus_path=corpus_path,
        sha256=sha256_hex(body),
        bytes=len(body),
        retrieved_at=date(filing_year_envelope().horizon, 11, 2),
        source_url=f"https://sede.agenciatributaria.gob.es/dictionary{suffix}",
        review_status="pending_review",
    )


def _validate(root: Path, source: SourceReference, quote: str = _QUOTE) -> list[str]:
    evidence = validate_evidence.EvidenceValidator(legal_refs={}, source_refs={source.id: source}, source_root=root)
    return evidence.validate_source_citations(
        "fixture",
        "result",
        (source.id,),
        (SourceCitation(source_ref=source.id, required_text=(quote,)),),
        "layout_authority",
    )


@pytest.mark.parametrize("encoding", ("cp1252", "utf-8"))
def test_dictionary_citations_preserve_published_accents_and_punctuation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, encoding: str
) -> None:
    monkeypatch.setattr(validate_evidence, "corpus_text_cache_dir", lambda: tmp_path / "cache")
    source = _source(tmp_path, f"RESINGDEV=[/IngresoDevolucionRes/RESINGDEV][IMP][0670][{_QUOTE}]".encode(encoding))
    assert _validate(tmp_path, source) == []
    assert _validate(tmp_path, source, "Resultado de la resolución") != []


def test_dictionary_extraction_does_not_reuse_the_old_lossy_text_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setattr(validate_evidence, "corpus_text_cache_dir", lambda: cache)
    source = _source(tmp_path, _QUOTE.encode("cp1252"))
    path = tmp_path / source.corpus_path
    new_key = validate_evidence.source_text_cache_key(source, path, tmp_path, path.stat())
    legacy_key = (str(source.kind), *new_key[1:])
    legacy_cache = cache / f"corpus_text_{sha256_hex(json.dumps(legacy_key).encode())}.txt"
    cache.mkdir()
    legacy_cache.write_text("Resultado de la declaraci�n", encoding="utf-8")

    assert _validate(tmp_path, source) == []
    assert legacy_cache.read_text(encoding="utf-8") == "Resultado de la declaraci�n"


def test_invalid_dictionary_bytes_are_reported_as_unreadable_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validate_evidence, "corpus_text_cache_dir", lambda: tmp_path / "cache")
    source = _source(tmp_path, b"Result=\x81")
    failures = _validate(tmp_path, source)
    assert len(failures) == 1
    assert "cannot be read" in failures[0]
    assert "neither UTF-8 nor CP1252" in failures[0]


@pytest.mark.parametrize("suffix", (".properties", ".txt"))
def test_other_utf8_evidence_retains_its_text_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    monkeypatch.setattr(validate_evidence, "corpus_text_cache_dir", lambda: tmp_path / "cache")
    source = _source(tmp_path, _QUOTE.encode("utf-8"), kind=RegistrySourceKind.INSTRUCTIONS, suffix=suffix)
    assert _validate(tmp_path, source) == []
