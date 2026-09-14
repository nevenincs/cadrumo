"""Exact, source-bound PDF page annotation tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.corpus_annotation import CorpusPageAnnotation, resolve_annotated_pdf_pages
from cadrumo.core.corpus_text import CorpusAnchorResolutionError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write_fixture(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"official PDF bytes")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    source.with_name("source.pdf.annotation.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_sha256": digest,
                "selections": [{"anchor": "two-pages", "pages": [2, 3]}],
            }
        ),
        encoding="utf-8",
    )
    source.with_name("source.pdf.extracted.json").write_text(
        json.dumps(
            {
                "source_sha256": digest,
                "units": [
                    {"title": "Pag. 1", "text": "outside"},
                    {"title": "Pag. 2", "text": "first exact page"},
                    {"title": "Pag. 3", "text": "second exact page"},
                ],
            }
        ),
        encoding="utf-8",
    )
    return source


def test_annotation_selects_exact_extracted_pages_without_copied_prose(tmp_path: Path) -> None:
    source = _write_fixture(tmp_path)
    assert resolve_annotated_pdf_pages(source, anchor="two-pages", include_title=True) == (
        "# Pag. 2\n\nfirst exact page\n\n# Pag. 3\n\nsecond exact page"
    )


def test_annotation_metadata_can_be_separate_from_companion_pdf(tmp_path: Path) -> None:
    source = _write_fixture(tmp_path / "companion")
    metadata = tmp_path / "primary"
    metadata.mkdir()
    annotation = metadata / "source.pdf.annotation.json"
    extraction = metadata / "source.pdf.extracted.json"
    source.with_name(annotation.name).replace(annotation)
    source.with_name(extraction.name).replace(extraction)

    assert (
        resolve_annotated_pdf_pages(
            source,
            anchor="two-pages",
            annotation_path=annotation,
            extracted_path=extraction,
        )
        == "first exact page\n\nsecond exact page"
    )


@pytest.mark.parametrize("changed", ["source", "extraction"])
def test_annotation_refuses_stale_source_or_extraction(tmp_path: Path, changed: str) -> None:
    source = _write_fixture(tmp_path)
    target = source if changed == "source" else source.with_name("source.pdf.extracted.json")
    target.write_bytes(target.read_bytes() + b"changed")
    with pytest.raises(CorpusAnchorResolutionError, match=r"stale|unreadable"):
        resolve_annotated_pdf_pages(source, anchor="two-pages")


def test_annotation_refuses_unknown_anchor(tmp_path: Path) -> None:
    source = _write_fixture(tmp_path)
    with pytest.raises(CorpusAnchorResolutionError, match="not unique"):
        resolve_annotated_pdf_pages(source, anchor="missing")


def test_annotation_cannot_embed_authored_evidence_text() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        CorpusPageAnnotation.model_validate(
            {
                "schema_version": 1,
                "source_sha256": "0" * 64,
                "selections": ({"anchor": "a", "pages": (1,), "text": "copied prose"},),
            }
        )
