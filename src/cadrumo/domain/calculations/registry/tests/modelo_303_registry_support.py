"""Modelo 303 registry loader for the published-authority test family."""

from __future__ import annotations

from ..schema import ModeloDefinition
from ..schema_catalogues import RegistryCatalogues
from .registry_tree import bundled_registry_tree


def load_modelo_303() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = bundled_registry_tree()
    return next(modelo for modelo in modelos if modelo.id == "303"), catalogues
