"""Unit tests for the manual verification report builder."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ....core.config import Settings
from ....tests.aeat_literal_fixtures import manual_practicos_url
from ....tests.fixtures.settings import EnvFileFreeSettings
from ..errors import ManualNotFoundError, ManualReviewRequiredError
from ..schema import ManualId, ManualPart
from ..verify import raise_on_errors, verify_manual_dir

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IVA_MANUAL_URL = manual_practicos_url("iva.pdf")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _settings(root: Path, *, review_required: bool = True) -> Settings:
    return EnvFileFreeSettings(
        aeat_manuals_root=root,
        cadrumo_manuals_review_required=review_required,
    )


def _seed_structure(root: Path, *, reviewer: str = "gw") -> None:
    """Seed a minimal but well-formed IVA 2025 structure."""
    part_root = root / "iva" / "2025"
    structure = part_root / "structure"

    _write_json(
        structure / "sections" / "cap1" / "sec1.json",
        {
            "section_id": "sec1",
            "chapter_id": "cap1",
            "title": "Régimen general",
            "summary": "Resumen",
            "prose": [],
            "rules": [],
            "references_sections": [],
            "references_legal_acts": [],
            "source": {
                "manual_url": _IVA_MANUAL_URL,
                "page": 10,
            },
            "definition_reviewed_by": reviewer,
            "definition_reviewed_at": "2026-04-12",
        },
    )
    _write_json(
        structure / "chapters.json",
        [
            {
                "chapter_id": "cap1",
                "title": "Capítulo 1",
                "summary": "Introducción",
                "sections": [
                    {
                        "section_id": "sec1",
                        "relative_path": "structure/sections/cap1/sec1.json",
                    },
                ],
            },
        ],
    )
    _write_json(
        structure / "manual.json",
        {
            "manual_id": "iva",
            "year": 2025,
            "part": "single",
            "title": "Manual práctico IVA 2025",
            "summary": "Resumen",
            "source_pdf_url": _IVA_MANUAL_URL,
            "source_html_url": None,
            "fetched_at": "2026-04-12T00:00:00Z",
            "definition_reviewed_by": reviewer,
            "definition_reviewed_at": "2026-04-12",
        },
    )


class TestVerify:
    """Verification walks every record and surfaces issues."""

    def test_missing_part_root_raises(self, tmp_path: Path) -> None:
        """A non-existent part root is a hard error, not a report."""
        settings = _settings(tmp_path)
        with pytest.raises(ManualNotFoundError, match=r"IVA|manual|root|2025"):
            verify_manual_dir(
                manual_id=ManualId.IVA,
                year=2025,
                part=ManualPart.SINGLE,
                settings=settings,
            )

    def test_empty_part_root_reports_missing_manifest(self, tmp_path: Path) -> None:
        """A part directory without a manifest produces a warning, not an error."""
        root = tmp_path / "corpus" / "manuals"
        (root / "iva" / "2025").mkdir(parents=True)
        settings = _settings(root)
        report = verify_manual_dir(
            manual_id=ManualId.IVA,
            year=2025,
            part=ManualPart.SINGLE,
            settings=settings,
        )
        assert report.ok
        assert any(issue.code == "missing-manifest" for issue in report.warnings)

    def test_clean_structure_is_ok(self, tmp_path: Path) -> None:
        """A well-formed structure produces no error-level issues."""
        root = tmp_path / "corpus" / "manuals"
        _seed_structure(root)
        settings = _settings(root)
        report = verify_manual_dir(
            manual_id=ManualId.IVA,
            year=2025,
            part=ManualPart.SINGLE,
            settings=settings,
        )
        assert report.ok is True
        assert report.errors == ()

    def test_empty_reviewer_surfaces_as_load_error(self, tmp_path: Path) -> None:
        """Empty definition_reviewed_by on the manual root fails schema load → verify error.

        The schema-level constraint (_Reviewer min_length=1 after
        stripping) is the absolute review gate. Attempting to land an
        unreviewed record surfaces as a load-failed error in the
        verification report, which the verify CLI converts to a
        non-zero exit.
        """
        root = tmp_path / "corpus" / "manuals"
        _seed_structure(root)
        manual_path = root / "iva" / "2025" / "structure" / "manual.json"
        payload = json.loads(manual_path.read_text(encoding="utf-8"))
        payload["definition_reviewed_by"] = ""
        manual_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        settings = _settings(root, review_required=True)
        report = verify_manual_dir(
            manual_id=ManualId.IVA,
            year=2025,
            part=ManualPart.SINGLE,
            settings=settings,
        )
        assert not report.ok
        assert any(issue.code == "load-failed" for issue in report.errors)

    def test_load_failure_is_error(self, tmp_path: Path) -> None:
        """A corrupt manual.json is reported as a load-failed error."""
        root = tmp_path / "corpus" / "manuals"
        _seed_structure(root)
        (root / "iva" / "2025" / "structure" / "manual.json").write_text("{not json", encoding="utf-8")
        settings = _settings(root)
        report = verify_manual_dir(
            manual_id=ManualId.IVA,
            year=2025,
            part=ManualPart.SINGLE,
            settings=settings,
        )
        assert not report.ok
        assert any(issue.code == "load-failed" for issue in report.errors)

    def test_raise_on_errors_raises_for_non_ok(self, tmp_path: Path) -> None:
        """raise_on_errors turns a failing report into an exception."""
        root = tmp_path / "corpus" / "manuals"
        _seed_structure(root)
        (root / "iva" / "2025" / "structure" / "manual.json").write_text("{bad", encoding="utf-8")
        settings = _settings(root)
        report = verify_manual_dir(
            manual_id=ManualId.IVA,
            year=2025,
            part=ManualPart.SINGLE,
            settings=settings,
        )
        with pytest.raises(ManualReviewRequiredError) as excinfo:
            raise_on_errors(report)
        assert excinfo.value.translated_message == "cli.registry.manuals.verify_failed"
