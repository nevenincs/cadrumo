"""Unit tests for the file-backed loader."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from ....core.config import Settings
from .. import (
    NormativeCatalogue,
    NormativeNotFoundError,
    NormativeParseError,
    load_catalogue,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _settings_with_root(root: Path) -> Settings:
    return Settings.model_validate({"aeat_normatives_root": root})


def _valid_payload(ref_id: str = "ley-35-2006") -> dict[str, object]:
    return {
        "id": ref_id,
        "kind": "ley",
        "number": "35/2006",
        "title": {"es": "Ley 35/2006", "en": "Law 35/2006", "hu": "35/2006. törvény"},
        "published_at": "2006-11-29",
        "boe_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
        "boe_id": "BOE-A-2006-20764",
        "articulos": [
            {
                "numero": "32",
                "titulo": {"es": "Reducciones"},
                "summary": {"es": "Resumen."},
                "permalink": "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a32",
            },
        ],
        "tags": ["irpf"],
        "last_reviewed_at": "2026-04-12",
        "reviewed_by": "wgergely",
    }


class TestLoadCatalogue:
    """End-to-end coverage for :func:`aeat.domain.normatives.load_catalogue`."""

    def test_happy_path(self, tmp_path: Path) -> None:
        (tmp_path / "ley-35-2006.json").write_text(json.dumps(_valid_payload()), encoding="utf-8")
        catalogue = load_catalogue(settings=_settings_with_root(tmp_path))
        assert isinstance(catalogue, NormativeCatalogue)
        assert len(catalogue) == 1
        assert "ley-35-2006" in catalogue
        ref = catalogue.get("ley-35-2006")
        assert ref is not None
        assert ref.published_at == date(2006, 11, 29)

    def test_missing_root_raises(self, tmp_path: Path) -> None:
        with pytest.raises(NormativeNotFoundError, match=r"normatives|root|nowhere|missing"):
            load_catalogue(settings=_settings_with_root(tmp_path / "nowhere"))

    def test_malformed_json_raises(self, tmp_path: Path) -> None:
        (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(NormativeParseError, match=r"json|JSON|broken|parse"):
            load_catalogue(settings=_settings_with_root(tmp_path))

    def test_schema_violation_raises(self, tmp_path: Path) -> None:
        payload = _valid_payload()
        payload["title"] = {"en": "missing es"}
        (tmp_path / "bad.json").write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(NormativeParseError, match=r"title|es|schema|missing"):
            load_catalogue(settings=_settings_with_root(tmp_path))

    def test_duplicate_ids_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "a.json").write_text(json.dumps(_valid_payload()), encoding="utf-8")
        (tmp_path / "b.json").write_text(json.dumps(_valid_payload()), encoding="utf-8")
        with pytest.raises(NormativeParseError, match=r"duplicate|id|ley-35-2006"):
            load_catalogue(settings=_settings_with_root(tmp_path))

    def test_roundtrip_preserves_articulos(self, tmp_path: Path) -> None:
        payload = _valid_payload()
        (tmp_path / "ley-35-2006.json").write_text(json.dumps(payload), encoding="utf-8")
        catalogue = load_catalogue(settings=_settings_with_root(tmp_path))
        reference = catalogue.get("ley-35-2006")
        assert reference is not None
        assert len(reference.articulos) == 1
        assert reference.articulos[0].numero == "32"
