"""Runtime-test access to the committed registry authority artifact.

This support is deliberately a thin test-local spelling of the shipped
``compiled_bundled_authority`` loader.  It has no source-tree, compiler, validator, or
publication dependency.
"""

from __future__ import annotations

from .....core.authority_grade import RegistryAuthorityGrade
from ..authority import bundled_indexed_authority
from ..schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from .registry_tree import bundled_registry_tree, full_published_modelo


def artifact_modelo(modelo_id: str) -> ModeloDefinition:
    with bundled_indexed_authority().operation() as operation:
        return full_published_modelo(operation, modelo_id)


def artifact_components(modelo_id: str) -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = bundled_registry_tree()
    return next(modelo for modelo in modelos if modelo.id == modelo_id), catalogues


def artifact_snapshot(
    modelo_id: str,
    filing_year: int,
    period: str,
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> RegistrySnapshot:
    with bundled_indexed_authority().operation() as operation:
        return operation.snapshot(modelo_id, filing_year=filing_year, period=period, grade=grade)
