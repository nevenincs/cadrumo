"""Unit tests for the file-backed loader and query API."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core import CasillaId, validated_casilla_id
from ....core.config import Settings
from ....tests.aeat_literal_fixtures import manual_practicos_url
from ....tests.fixtures.settings import EnvFileFreeSettings
from ..errors import ManualNotFoundError, ManualParseError
from ..loader import find_rules, load_catalogue, load_manual, load_section, resolve_part_root
from ..schema import ManualCasillaReference, ManualCatalogue, ManualId, ManualPart

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IVA_MANUAL_URL = manual_practicos_url("iva.pdf")
_M303_CASILLA_01: CasillaId = validated_casilla_id("01", surface="_M303_CASILLA_01")
_M130_CASILLA_07: CasillaId = validated_casilla_id("07", surface="_M130_CASILLA_07")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _settings_with_root(root: Path) -> Settings:
    return EnvFileFreeSettings(aeat_manuals_root=root)


def _seed_iva(tmp_path: Path) -> Settings:
    """Seed an IVA 2025 manual part under ``tmp_path/corpus/manuals``."""
    root = tmp_path / "corpus" / "manuals"
    part_root = root / "iva" / "2025"
    structure = part_root / "structure"

    section_payload = {
        "section_id": "sec1",
        "chapter_id": "cap1",
        "title": "Régimen general",
        "summary": "Resumen",
        "prose": [{"paragraph_id": "p1", "text": "Texto", "page": 12}],
        "rules": [
            {
                "rule_id": "iva-2025-cap1-sec1-rule0001",
                "manual_id": "iva",
                "year": 2025,
                "part": "single",
                "chapter_id": "cap1",
                "section_id": "sec1",
                "kind": "formal_obligation",
                "statement": "Regla IVA",
                "applies_when": None,
                "references_casillas": [{"modelo_id": "303", "casilla_id": _M303_CASILLA_01}],
                "references_sections": [],
                "references_legal_acts": ["LEY_37_1992|art. 1"],
                "source": {
                    "manual_url": _IVA_MANUAL_URL,
                    "page": 12,
                    "paragraph": 1,
                },
                "extracted_by": {
                    "provider": "anthropic",
                    "model": "test-model",
                    "prompt_id": "manual_rule_extract_v1",
                    "cache_hit": False,
                    "extracted_at": "2026-04-12T10:00:00Z",
                },
                "definition_reviewed_by": "gw",
                "definition_reviewed_at": "2026-04-12",
            },
        ],
        "references_sections": [],
        "references_legal_acts": [],
        "source": {
            "manual_url": _IVA_MANUAL_URL,
            "page": 10,
        },
        "definition_reviewed_by": "gw",
        "definition_reviewed_at": "2026-04-12",
    }
    _write_json(structure / "sections" / "cap1" / "sec1.json", section_payload)

    chapters_payload = [
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
    ]
    _write_json(structure / "chapters.json", chapters_payload)

    manual_payload = {
        "manual_id": "iva",
        "year": 2025,
        "part": "single",
        "title": "Manual práctico IVA 2025",
        "summary": "Resumen",
        "source_pdf_url": _IVA_MANUAL_URL,
        "source_html_url": None,
        "fetched_at": "2026-04-12T00:00:00Z",
        "definition_reviewed_by": "gw",
        "definition_reviewed_at": "2026-04-12",
    }
    _write_json(structure / "manual.json", manual_payload)
    return _settings_with_root(root)


class TestLoader:
    """Loader happy-path and error behaviour."""

    def test_resolve_part_root_single(self, tmp_path: Path) -> None:
        """SINGLE parts flatten the directory layout."""
        settings = _settings_with_root(tmp_path)
        path = resolve_part_root(
            manual_id=ManualId.IVA,
            year=2025,
            part=ManualPart.SINGLE,
            settings=settings,
        )
        assert path == tmp_path / "iva" / "2025"

    def test_resolve_part_root_part1(self, tmp_path: Path) -> None:
        """Split parts nest a subdirectory under the year."""
        settings = _settings_with_root(tmp_path)
        path = resolve_part_root(
            manual_id=ManualId.RENTA,
            year=2025,
            part=ManualPart.PARTE_1,
            settings=settings,
        )
        assert path == tmp_path / "renta" / "2025" / "part1"

    def test_load_manual_happy_path(self, tmp_path: Path) -> None:
        """A seeded IVA manual loads and reports one chapter."""
        settings = _seed_iva(tmp_path)
        manual = load_manual(ManualId.IVA, 2025, ManualPart.SINGLE, settings=settings)
        assert manual.manual_id is ManualId.IVA
        assert len(manual.chapters) == 1
        assert manual.chapters[0].chapter_id == "cap1"

    def test_load_manual_missing_structure_raises_not_found(self, tmp_path: Path) -> None:
        """A part root without structure/ raises ManualNotFoundError."""
        settings = _settings_with_root(tmp_path)
        with pytest.raises(ManualNotFoundError, match=r"IVA|manual|structure|2025"):
            load_manual(ManualId.IVA, 2025, ManualPart.SINGLE, settings=settings)

    def test_load_manual_rejects_malformed_section(self, tmp_path: Path) -> None:
        """A section file with a missing required field fails loud."""
        settings = _seed_iva(tmp_path)
        bad_section = {
            "section_id": "sec1",
            "chapter_id": "cap1",
            "title": "   ",
            "summary": "Resumen",
            "prose": [],
            "rules": [],
            "references_sections": [],
            "references_legal_acts": [],
            "source": {
                "manual_url": _IVA_MANUAL_URL,
                "page": 10,
            },
            "definition_reviewed_by": "gw",
            "definition_reviewed_at": "2026-04-12",
        }
        _write_json(
            settings.aeat_manuals_root / "iva" / "2025" / "structure" / "sections" / "cap1" / "sec1.json",
            bad_section,
        )
        manual = load_manual(ManualId.IVA, 2025, ManualPart.SINGLE, settings=settings)
        with pytest.raises(ManualParseError, match=r"section.+validation failed"):
            load_section(
                settings.aeat_manuals_root / "iva" / "2025",
                manual.chapters[0].sections[0],
            )

    def test_load_section_rejects_traversal_ref(self, tmp_path: Path) -> None:
        """A tampered section ref must not escape the owning part root."""
        settings = _seed_iva(tmp_path)
        manual = load_manual(ManualId.IVA, 2025, ManualPart.SINGLE, settings=settings)
        bad_ref = manual.chapters[0].sections[0].model_copy(update={"relative_path": "../outside.json"})
        with pytest.raises(ManualParseError, match="must stay within the owning root"):
            load_section(settings.aeat_manuals_root / "iva" / "2025", bad_ref)

    def test_load_section_wraps_missing_file_as_domain_error(self, tmp_path: Path) -> None:
        """A dangling section ref fails as ManualNotFoundError, not builtin FileNotFoundError."""
        settings = _seed_iva(tmp_path)
        manual = load_manual(ManualId.IVA, 2025, ManualPart.SINGLE, settings=settings)
        missing_ref = (
            manual.chapters[0].sections[0].model_copy(update={"relative_path": "structure/sections/cap1/missing.json"})
        )
        with pytest.raises(ManualNotFoundError, match=r"missing required file"):
            load_section(settings.aeat_manuals_root / "iva" / "2025", missing_ref)

    def test_load_catalogue_and_find_rules(self, tmp_path: Path) -> None:
        """find_rules iterates rules loaded through the catalogue."""
        settings = _seed_iva(tmp_path)
        catalogue = load_catalogue([(ManualId.IVA, 2025, ManualPart.SINGLE)], settings=settings)
        assert isinstance(catalogue, ManualCatalogue)
        assert len(catalogue) == 1
        rules = list(find_rules(catalogue, kind="formal_obligation", settings=settings))
        assert len(rules) == 1
        assert rules[0].rule_id == "iva-2025-cap1-sec1-rule0001"

    def test_find_rules_casilla_filter_prunes_non_matching(self, tmp_path: Path) -> None:
        """Casilla filter skips rules without the referenced casilla."""
        settings = _seed_iva(tmp_path)
        catalogue = load_catalogue([(ManualId.IVA, 2025, ManualPart.SINGLE)], settings=settings)
        matches = list(
            find_rules(
                catalogue,
                casilla_reference=ManualCasillaReference(modelo_id="303", casilla_id=_M303_CASILLA_01),
                settings=settings,
            ),
        )
        assert len(matches) == 1
        misses = list(
            find_rules(
                catalogue,
                casilla_reference=ManualCasillaReference(modelo_id="130", casilla_id=_M130_CASILLA_07),
                settings=settings,
            ),
        )
        assert misses == []

    def test_fetched_at_precision_round_trips(self, tmp_path: Path) -> None:
        """fetched_at timestamps survive the load cycle."""
        settings = _seed_iva(tmp_path)
        manual = load_manual(ManualId.IVA, 2025, ManualPart.SINGLE, settings=settings)
        assert manual.fetched_at == datetime(2026, 4, 12, 0, 0, 0, tzinfo=UTC)
