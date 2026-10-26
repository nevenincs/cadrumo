"""Semantic page annotations are catalogued against independent source identity."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ..corpus_catalogue import verify_manual_annotation_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _source() -> SourceReference:
    return SourceReference.model_validate(
        {
            "id": "official-manual",
            "evidence_tier": "official_source_guidance",
            "authority": "aeat",
            "kind": "manual_pdf",
            "corpus_path": "corpus/manuals/renta/2025/part1/source.pdf",
            "sha256": hashlib.sha256(b"official PDF").hexdigest(),
            "bytes": len(b"official PDF"),
            "retrieved_at": date(2026, 9, 14),
            "applies_from": date(2025, 1, 1),
            "applies_to": date(2025, 12, 31),
            "source_url": "https://sede.agenciatributaria.gob.es/manual.pdf",
            "review_status": "pending_review",
        }
    )


def _write_annotation(
    root: Path,
    *,
    target_declared: bool = True,
    anchor: str = "rule",
    pages: list[int] | None = None,
    extraction_sha256: str | None = None,
    extraction_units: list[dict[str, object]] | None = None,
) -> SourceReference:
    source = _source()
    directory = root / Path(*Path(source.corpus_path).parent.parts)
    directory.mkdir(parents=True)
    (directory / "source.pdf").write_bytes(b"official PDF")
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "content_length": source.bytes,
                "fetched_at": "2026-09-14T00:00:00Z",
                "relative_pdf_path": "source.pdf",
                "sha256": str(source.sha256),
                "source_pdf_url": source.source_url,
            }
        ),
        encoding="utf-8",
    )
    (directory / "source.pdf.annotation.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_sha256": str(source.sha256),
                "selections": [{"anchor": anchor, "pages": pages or [1]}],
            }
        ),
        encoding="utf-8",
    )
    (directory / "source.pdf.extracted.json").write_text(
        json.dumps(
            {
                "source_sha256": extraction_sha256 or str(source.sha256),
                "units": extraction_units or [{"title": "Pag. 1", "text": "Exact official rule."}],
            }
        ),
        encoding="utf-8",
    )
    return source if target_declared else source.model_copy(update={"corpus_path": "corpus/other.pdf"})


def test_manual_annotation_has_one_catalogued_semantic_role(tmp_path: Path) -> None:
    source = _write_annotation(tmp_path)

    verify_manual_annotation_catalogue(tmp_path, {source.id: source})


def test_manual_annotation_refuses_an_undeclared_target(tmp_path: Path) -> None:
    source = _write_annotation(tmp_path, target_declared=False)

    with pytest.raises(RegistryValidationError, match="no declared registry source target"):
        verify_manual_annotation_catalogue(tmp_path, {source.id: source})


def test_manual_annotation_refuses_extraction_bound_to_another_source(tmp_path: Path) -> None:
    source = _write_annotation(tmp_path, extraction_sha256="0" * 64)

    with pytest.raises(RegistryValidationError, match=r"cannot resolve anchor.*sibling extraction"):
        verify_manual_annotation_catalogue(tmp_path, {source.id: source})


def test_manual_annotation_refuses_source_bytes_outside_the_declared_identity(tmp_path: Path) -> None:
    source = _write_annotation(tmp_path)
    (tmp_path / Path(*Path(source.corpus_path).parts)).write_bytes(b"different PDF")

    with pytest.raises(RegistryValidationError, match="byte count mismatch"):
        verify_manual_annotation_catalogue(tmp_path, {source.id: source})


@pytest.mark.parametrize(
    ("units", "message"),
    [
        ([{"title": "Pag. 2", "text": "Another page."}], "page 1 is not unique"),
        (
            [
                {"title": "Pag. 1", "text": "First rendering."},
                {"title": "Pag. 1", "text": "Duplicate rendering."},
            ],
            "page 1 is not unique",
        ),
    ],
)
def test_manual_annotation_requires_each_page_once_in_the_extraction(
    tmp_path: Path, units: list[dict[str, object]], message: str
) -> None:
    source = _write_annotation(tmp_path, extraction_units=units)

    with pytest.raises(RegistryValidationError, match=message):
        verify_manual_annotation_catalogue(tmp_path, {source.id: source})


@pytest.mark.parametrize("anchor", ["Regional Rule", "regional--rule", "región-rule"])
def test_manual_annotation_refuses_non_canonical_anchor(tmp_path: Path, anchor: str) -> None:
    source = _write_annotation(tmp_path, anchor=anchor)

    with pytest.raises(RegistryValidationError, match="non-canonical anchor"):
        verify_manual_annotation_catalogue(tmp_path, {source.id: source})
