"""Runtime-test access to the committed registry authority artifact.

This support is deliberately a thin test-local spelling of the shipped
``compiled_bundled_authority`` loader.  It has no source-tree, compiler, validator, or
publication dependency.
"""

from __future__ import annotations

from dev.registry.compiler.authority import compiled_bundled_authority

from .....core.authority_grade import RegistryAuthorityGrade
from ..schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot


def artifact_modelo(modelo_id: str) -> ModeloDefinition:
    return compiled_bundled_authority().modelo(modelo_id)


def artifact_components(modelo_id: str) -> tuple[ModeloDefinition, RegistryCatalogues]:
    authority = compiled_bundled_authority()
    return authority.modelo(modelo_id), authority.catalogues


def artifact_snapshot(
    modelo_id: str,
    filing_year: int,
    period: str,
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> RegistrySnapshot:
    return compiled_bundled_authority().snapshot(modelo_id, filing_year=filing_year, period=period, grade=grade)
