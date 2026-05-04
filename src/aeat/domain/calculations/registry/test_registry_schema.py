"""Tests for the registry-backed AEAT calculation schema."""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import RegistryCatalogues, RegistryLoadError, RegistryValidationError, build_snapshot, load_modelo_file
from ._loader import load_registry_tree
from ._schema import ModeloDefinition, ModeloRevision
from ._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"
_MODELO_130_FILE = _REGISTRY_ROOT / "modelos" / "130.toml"


def _committed_registry() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    return next(modelo for modelo in modelos if modelo.id == "130"), catalogues


def _revision(modelo: ModeloDefinition) -> ModeloRevision:
    return modelo.revisions["2019-y-siguientes"]


def _with_revision(modelo: ModeloDefinition, revision: ModeloRevision) -> ModeloDefinition:
    return modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: revision}})


def _copy_committed_modelo(path: Path) -> None:
    path.write_text(_MODELO_130_FILE.read_text(encoding="utf-8"), encoding="utf-8")


def test_modelo_file_loads_and_snapshot_selects_committed_revision() -> None:
    modelo, catalogues = _committed_registry()

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(modelo)
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2024, period="3T")

    assert snapshot.modelo.id == "130"
    assert snapshot.revision.id == "2019-y-siguientes"
    assert "rd-439-2007:art-110" in snapshot.legal
    assert "aeat-dr-130-2019-v12" in snapshot.sources


def test_modelo_file_rejects_local_source_catalogue(tmp_path: Path) -> None:
    path = tmp_path / "130.toml"
    _copy_committed_modelo(path)
    path.write_text(path.read_text(encoding="utf-8") + '\n[source."local"]\nkind = "record_design"\n', encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="must not define local legal/source"):
        load_modelo_file(path)


def test_modelo_file_rejects_empty_filing_grade_evidence(tmp_path: Path) -> None:
    path = tmp_path / "130.toml"
    _copy_committed_modelo(path)
    text = path.read_text(encoding="utf-8").replace(
        'legal_refs = ["rd-439-2007:art-110"]',
        "legal_refs = []",
        1,
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="too_short"):
        load_modelo_file(path)


def test_snapshot_requires_source_integrity(tmp_path: Path) -> None:
    modelo, catalogues = _committed_registry()

    with pytest.raises(RegistryValidationError, match="missing corpus file"):
        build_snapshot(modelo, catalogues, source_root=tmp_path, filing_year=2024, period="3T")


def test_validator_rejects_duplicate_formula_targets() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    duplicate = revision.formulas[0].model_copy(update={"id": f"{revision.formulas[0].id}-duplicate"})
    mutated = revision.model_copy(update={"formulas": (*revision.formulas, duplicate)})

    with pytest.raises(RegistryValidationError, match="duplicate formula target"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_formula_id_matching_casilla_id() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    formula = revision.formulas[0]
    renamed_formula = formula.model_copy(update={"id": formula.target})
    casillas = tuple(
        casilla.model_copy(update={"formula": renamed_formula.id}) if casilla.id == formula.target else casilla
        for casilla in revision.casillas
    )
    formulas = (renamed_formula, *revision.formulas[1:])
    mutated = revision.model_copy(update={"casillas": casillas, "formulas": formulas})

    with pytest.raises(RegistryValidationError, match=f"duplicate registry id '{formula.target}'"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_formula_target_mismatch() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    formula = revision.formulas[0]
    mismatched_formula = formula.model_copy(update={"target": "01"})
    mutated = revision.model_copy(update={"formulas": (mismatched_formula, *revision.formulas[1:])})

    with pytest.raises(RegistryValidationError, match="targeting '01'"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_missing_legal_reference() -> None:
    modelo, catalogues = _committed_registry()
    missing_legal = catalogues.model_copy(update={"legal": {}})

    with pytest.raises(RegistryValidationError, match="unknown legal id"):
        RegistryValidator(missing_legal, source_root=PROJECT_ROOT).validate_modelo(modelo)
