"""Tests for the schema-local registry translation loader and validator."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .....locales import ModeloLocaleFieldKind, ModeloLocaleManager
from .._errors import RegistryValidationError
from .._loader import load_modelo_directory
from .._schema import ModeloDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

MANIFEST_TEXT = """
[modelo]
id = "130"
title = "Modelo 130"
official_name = "MODELO 130"
tax_domain = "irpf"
cadence = "quarterly"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-35-2006"]
source_refs = ["aeat-source"]
"""

REVISION_TEXT = """
[revisions.2019-y-siguientes]
valid_from = 2019-01-01
period_selector = { year_from = 2019, periods = ["1T", "2T", "3T", "4T"] }
legal_refs = ["ley-35-2006"]
source_refs = ["aeat-source"]

[[revisions.2019-y-siguientes.casillas]]
id = "01"
number = "01"
label = "Spanish Label 01"
section = ["section"]
input_kind = "manual"
continuidad_id = "cont_01"
legal_refs = ["ley-35-2006"]
source_refs = ["aeat-source"]

[[revisions.2019-y-siguientes.casillas]]
id = "02"
number = "02"
label = "Spanish Label 02"
section = ["section"]
input_kind = "manual"
legal_refs = ["ley-35-2006"]
source_refs = ["aeat-source"]
"""


def _setup_modelo_dir(
    target_dir: Path,
    *,
    manifest: str = MANIFEST_TEXT,
    revision: str = REVISION_TEXT,
    modelo_locales: dict[str, str] | None = None,
    revision_locales: dict[str, str] | None = None,
) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "manifest.toml").write_text(manifest, encoding="utf-8")

    revisions_dir = target_dir / "revisions"
    revisions_dir.mkdir(exist_ok=True)

    # We write revision.toml directly or as fragment files
    rev_id_dir = revisions_dir / "2019-y-siguientes"
    rev_id_dir.mkdir(exist_ok=True)
    (rev_id_dir / "revision.toml").write_text(revision, encoding="utf-8")

    if modelo_locales:
        locales_dir = target_dir / "locales"
        locales_dir.mkdir(exist_ok=True)
        for locale, content in modelo_locales.items():
            (locales_dir / f"{locale}.toml").write_text(content, encoding="utf-8")

    if revision_locales:
        rev_locales_dir = rev_id_dir / "locales"
        rev_locales_dir.mkdir(exist_ok=True)
        for locale, content in revision_locales.items():
            (rev_locales_dir / f"{locale}.toml").write_text(content, encoding="utf-8")


class TestRegistryLocalesLoader:
    def test_loads_hierarchical_translations(self, tmp_path: Path) -> None:
        modelo_locales = {
            "en": """
[labels]
"cont_01" = "English Concept Label 01"

[help]
"cont_01" = "English Concept Help 01"
""",
        }
        revision_locales = {
            "en": """
[labels]
"01" = "English Overridden Label 01"
"02" = "English Revision Label 02"

[help]
"02" = "English Revision Help 02"
""",
        }
        _setup_modelo_dir(
            tmp_path,
            modelo_locales=modelo_locales,
            revision_locales=revision_locales,
        )

        modelo = load_modelo_directory(tmp_path)
        revision = modelo.revisions["2019-y-siguientes"]

        casilla_01 = next(c for c in revision.casillas if c.id == "01")
        casilla_02 = next(c for c in revision.casillas if c.id == "02")

        # Casilla 01 gets continuity help, but label is overridden by revision
        assert casilla_01.get_label("en") == "English Overridden Label 01"
        assert casilla_01.get_help("en") == "English Concept Help 01"

        # Casilla 02 gets revision-level translations
        assert casilla_02.get_label("en") == "English Revision Label 02"
        assert casilla_02.get_help("en") == "English Revision Help 02"

        # Fallbacks to Spanish invariant
        assert casilla_01.get_label("ca") == "Spanish Label 01"
        assert casilla_01.get_help("ca") is None

    def test_referential_integrity_validation_fails_on_invalid_concept_key(self, tmp_path: Path) -> None:
        modelo_locales = {
            "en": """
[labels]
"non_existent_continuity_id" = "English Label"
""",
        }
        _setup_modelo_dir(tmp_path, modelo_locales=modelo_locales)

        with pytest.raises(RegistryValidationError) as exc_info:
            load_modelo_directory(tmp_path)

        assert "no continuity chain found with this continuity id" in str(exc_info.value)

    def test_referential_integrity_validation_fails_on_invalid_revision_key(self, tmp_path: Path) -> None:
        revision_locales = {
            "en": """
[labels]
"99" = "English Label"
""",
        }
        _setup_modelo_dir(tmp_path, revision_locales=revision_locales)

        with pytest.raises(RegistryValidationError) as exc_info:
            load_modelo_directory(tmp_path)

        assert "no casilla found with this id" in str(exc_info.value)

    def test_locales_file_updates_invalidate_cache(self, tmp_path: Path) -> None:
        modelo_locales = {
            "en": """
[labels]
"cont_01" = "English Concept Label 01"
""",
        }
        _setup_modelo_dir(tmp_path, modelo_locales=modelo_locales)

        # First load
        modelo_1 = load_modelo_directory(tmp_path)
        c01_1 = next(c for c in modelo_1.revisions["2019-y-siguientes"].casillas if c.id == "01")
        assert c01_1.get_label("en") == "English Concept Label 01"

        # Update locale file on disk
        updated_locale = """
[labels]
"cont_01" = "Updated English Label 01"
"""
        (tmp_path / "locales" / "en.toml").write_text(updated_locale, encoding="utf-8")

        # Second load - must reload from disk due to fingerprint change
        modelo_2 = load_modelo_directory(tmp_path)
        c01_2 = next(c for c in modelo_2.revisions["2019-y-siguientes"].casillas if c.id == "01")
        assert c01_2.get_label("en") == "Updated English Label 01"

    def test_roundtrip_preserves_localization_attributes(self, tmp_path: Path) -> None:
        modelo_locales = {
            "en": """
[labels]
"cont_01" = "English Concept Label"
""",
        }
        _setup_modelo_dir(tmp_path, modelo_locales=modelo_locales)
        modelo = load_modelo_directory(tmp_path)

        # Serialize using pydantic model_dump and deserialize back
        dumped = modelo.model_dump()
        reconstituted = ModeloDefinition.model_validate(dumped)

        rev = reconstituted.revisions["2019-y-siguientes"]
        casilla_01 = next(c for c in rev.casillas if c.id == "01")
        assert casilla_01.get_label("en") == "English Concept Label"

    def test_manager_written_locale_file_loads_through_registry_loader(self, tmp_path: Path) -> None:
        registry_root = tmp_path / "registry" / "aeat"
        modelos_root = registry_root / "modelos"
        modelos_root.mkdir(parents=True)
        shutil.copytree(bundled_path("registry", "aeat", "modelos", "130"), modelos_root / "130")

        manager = ModeloLocaleManager(registry_root)
        manager.set_translation_value(
            "en",
            "130",
            "2019-y-siguientes",
            ModeloLocaleFieldKind.LABELS,
            "01",
            "Revenue",
        )

        modelo = load_modelo_directory(modelos_root / "130")
        revision = modelo.revisions["2019-y-siguientes"]
        casilla_01 = next(casilla for casilla in revision.casillas if casilla.id == "01")

        assert casilla_01.label == "Ingresos"
        assert casilla_01.get_label("en") == "Revenue"
