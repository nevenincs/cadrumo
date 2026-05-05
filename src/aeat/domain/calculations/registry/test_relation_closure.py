"""Tests for registry cross-model relation closure."""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import RegistryCatalogues, RegistryLoadError, RegistryValidationError, load_modelo_file
from ._loader import load_registry_tree
from ._schema import ModeloDefinition, ModeloRevision
from ._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"
_MODELO_180_FILE = _REGISTRY_ROOT / "modelos" / "180.toml"


def _committed_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    return load_registry_tree(_REGISTRY_ROOT)


def _modelo(modelos: tuple[ModeloDefinition, ...], modelo_id: str) -> ModeloDefinition:
    return next(modelo for modelo in modelos if modelo.id == modelo_id)


def _with_revision(modelo: ModeloDefinition, revision: ModeloRevision) -> ModeloDefinition:
    return modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: revision}})


def _replace_modelo(
    modelos: tuple[ModeloDefinition, ...],
    updated: ModeloDefinition,
) -> tuple[ModeloDefinition, ...]:
    return tuple(updated if modelo.id == updated.id else modelo for modelo in modelos)


def _copy_committed_modelo_180(path: Path) -> None:
    path.write_text(_MODELO_180_FILE.read_text(encoding="utf-8"), encoding="utf-8")


def test_registry_validator_checks_cross_model_relation_closure() -> None:
    modelos, catalogues = _committed_tree()

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_registry(modelos)


def test_registry_validator_rejects_relation_to_unknown_source_modelo() -> None:
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "180")
    revision = modelo.revisions["2023-y-siguientes"]
    relation = revision.relations[0].model_copy(update={"source_modelo": "999"})
    mutated_revision = revision.model_copy(update={"relations": (relation, *revision.relations[1:])})
    mutated_modelo = _with_revision(modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match="unknown source modelo"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_registry(
            _replace_modelo(modelos, mutated_modelo)
        )


def test_registry_validator_rejects_relation_source_period_outside_source_revision() -> None:
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "180")
    revision = modelo.revisions["2023-y-siguientes"]
    relation = revision.relations[0].model_copy(update={"source_periods": ("1T", "99")})
    mutated_revision = revision.model_copy(update={"relations": (relation, *revision.relations[1:])})
    mutated_modelo = _with_revision(modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match="does not support source periods"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_registry(
            _replace_modelo(modelos, mutated_modelo)
        )


def test_registry_validator_rejects_relation_to_unknown_source_output() -> None:
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "180")
    revision = modelo.revisions["2023-y-siguientes"]
    relation = revision.relations[0].model_copy(update={"source_output": "missing-output"})
    mutated_revision = revision.model_copy(update={"relations": (relation, *revision.relations[1:])})
    mutated_modelo = _with_revision(modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match="has no source output"):
        RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_registry(
            _replace_modelo(modelos, mutated_modelo)
        )


def test_modelo_file_requires_relation_dependency_role(tmp_path: Path) -> None:
    path = tmp_path / "180.toml"
    _copy_committed_modelo_180(path)
    text = path.read_text(encoding="utf-8").replace(
        'dependency_role = "periodic_to_annual_summary"\n',
        "",
        1,
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="dependency_role"):
        load_modelo_file(path)


def test_modelo_file_rejects_annual_summary_relation_without_summary_role(tmp_path: Path) -> None:
    path = tmp_path / "180.toml"
    _copy_committed_modelo_180(path)
    text = path.read_text(encoding="utf-8").replace(
        'dependency_role = "periodic_to_annual_summary"',
        'dependency_role = "direct_calculation"',
        1,
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="annual summary relation"):
        load_modelo_file(path)
