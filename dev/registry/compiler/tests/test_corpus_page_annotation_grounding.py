"""Registry citations resolve page annotations against exact PDF extractions."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_references import LegalReference

from .. import legal_grounding
from ..legal_grounding import verify_legal_reference_grounding

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _reference() -> LegalReference:
    return LegalReference.model_validate(
        {
            "id": "regional-law:art-1",
            "evidence_tier": "legal_authority",
            "authority": "autonomous_community",
            "kind": "ley",
            "corpus_ref": "corpus/manuals/renta/2025/source.pdf#regional-rule",
            "document_id": "BOC-x-2025-1",
            "article": "1",
            "permalink": "https://www.boe.es/example",
            "published_at": date(2025, 1, 1),
            "effective_from": date(2025, 1, 2),
            "review_status": "operator_reviewed",
            "reviewed_at": date(2026, 9, 14),
            "reviewed_by": "operator",
            "required_text": ("exact official clause",),
        }
    )


def _write_evidence(root: Path) -> Path:
    source = root / "corpus/manuals/renta/2025/source.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"official PDF")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    source.with_name("source.pdf.annotation.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_sha256": digest,
                "selections": [{"anchor": "regional-rule", "pages": [7]}],
            }
        ),
        encoding="utf-8",
    )
    source.with_name("source.pdf.extracted.json").write_text(
        json.dumps(
            {
                "source_sha256": digest,
                "units": [{"title": "Pag. 7", "text": "Exact official clause."}],
            }
        ),
        encoding="utf-8",
    )
    return source


def test_legal_grounding_reads_exact_source_bound_page(tmp_path: Path) -> None:
    _write_evidence(tmp_path)
    verify_legal_reference_grounding(_reference(), source_root=tmp_path)


def test_legal_grounding_refuses_annotation_after_source_changes(tmp_path: Path) -> None:
    source = _write_evidence(tmp_path)
    source.write_bytes(b"different PDF")
    with pytest.raises(RegistryValidationError, match="cannot resolve one corpus unit"):
        verify_legal_reference_grounding(_reference(), source_root=tmp_path)


def test_legal_grounding_resolves_pdf_from_companion_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _write_evidence(tmp_path)
    companion = tmp_path / "companion" / "source.pdf"
    companion.parent.mkdir()
    source.replace(companion)
    monkeypatch.setattr(legal_grounding, "resolve_companion_binary", lambda *_parts: companion)

    verify_legal_reference_grounding(_reference(), source_root=tmp_path)
