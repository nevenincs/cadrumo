"""Modelo 303 registry loader for the authored-source test family."""

from __future__ import annotations

from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from dev.registry.compiler.authority import compiled_bundled_authority


def load_modelo_303() -> tuple[ModeloDefinition, RegistryCatalogues]:
    authority = compiled_bundled_authority()
    return authority.modelo("303"), authority.catalogues
