"""Tests for registry source and legal catalogue verification."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest

from ._errors import RegistryValidationError
from ._legal import verify_legal_catalogue
from ._schema import LegalReference, SourceReference
from ._sources import verify_source_catalogue, verify_source_file

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _legal_reference(
    *,
    ref_id: str = "ley-37-1992:art-90",
    article: str = "90",
    notes: str | None = "IVA general",
) -> LegalReference:
    return LegalReference(
        id=ref_id,
        authority="boe",
        kind="ley",
        corpus_ref="corpus/normatives/ley-37-1992.json#art-90",
        document_id="BOE-A-1992-28740",
        article=article,
        permalink=f"https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a{article}",
        effective_from=date(1992, 12, 29),
        review_status="reviewed",
        notes=notes,
    )


def _source_reference(path: str, payload: bytes) -> SourceReference:
    return SourceReference(
        id="aeat-source",
        authority="aeat",
        kind="record_design",
        corpus_path=path,
        sha256=hashlib.sha256(payload).hexdigest(),
        bytes=len(payload),
        retrieved_at=date(2026, 5, 3),
        source_url="https://sede.agenciatributaria.gob.es/source.xlsx",
        review_status="reviewed",
    )


def test_verify_source_file_checks_hash_and_size(tmp_path: Path) -> None:
    payload = b"official"
    source_path = tmp_path / "corpus" / "source.xlsx"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(payload)

    verify_source_file(tmp_path, _source_reference("corpus/source.xlsx", payload))


def test_verify_source_file_rejects_hash_mismatch(tmp_path: Path) -> None:
    source_path = tmp_path / "corpus" / "source.xlsx"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"changed")

    with pytest.raises(RegistryValidationError, match=r"byte count mismatch|sha256 mismatch"):
        verify_source_file(tmp_path, _source_reference("corpus/source.xlsx", b"official"))


def test_verify_source_file_rejects_path_escape(tmp_path: Path) -> None:
    source = SourceReference.model_construct(
        id="escape",
        authority="aeat",
        kind="record_design",
        corpus_path="../outside.xlsx",
        sha256=hashlib.sha256(b"x").hexdigest(),
        bytes=1,
        retrieved_at=date(2026, 5, 3),
        source_url="https://sede.agenciatributaria.gob.es/source.xlsx",
        review_status="reviewed",
    )

    with pytest.raises(RegistryValidationError, match="escapes repository root"):
        verify_source_file(tmp_path, source)


def test_verify_source_catalogue_checks_every_entry(tmp_path: Path) -> None:
    payload = b"official"
    source_path = tmp_path / "corpus" / "source.xlsx"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(payload)

    verify_source_catalogue(tmp_path, {"aeat-source": _source_reference("corpus/source.xlsx", payload)})


def test_verify_legal_catalogue_rejects_known_bad_citation_role() -> None:
    reference = _legal_reference(
        ref_id="ley-35-2006:art-103",
        article="103",
        notes="cuota diferencial",
    )

    with pytest.raises(RegistryValidationError, match="known-bad citation"):
        verify_legal_catalogue({reference.id: reference})


def test_verify_legal_catalogue_rejects_key_mismatch() -> None:
    reference = _legal_reference()

    with pytest.raises(RegistryValidationError, match="does not match reference id"):
        verify_legal_catalogue({"other-id": reference})


def test_verify_legal_catalogue_accepts_reviewed_reference() -> None:
    reference = _legal_reference()

    verify_legal_catalogue({reference.id: reference})
