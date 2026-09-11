"""Shared committed-source helpers for development registry validation tests."""

from __future__ import annotations

from functools import cache

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_formula import KeyedBracketEntry
from dev.registry.compiler.authority import compile_validated_authority
from dev.registry.compiler.loader import load_registry_tree


@cache
def _committed_registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    return load_registry_tree(bundled_path("registry", "aeat"))


def _committed_registry() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = _committed_registry_tree()
    return modelos[0], catalogues


def _revision(modelo: ModeloDefinition):
    return next(iter(modelo.revisions.values()))


def _with_revision(modelo: ModeloDefinition, revision):
    return modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: revision}})


_NUMERIC_CASILLA_01 = validated_casilla_id("01", surface="registry_schema_support")


def _keyed_bracket(key: str, rate: str) -> KeyedBracketEntry:
    return KeyedBracketEntry(key=key, value=rate)


def _as_communication_revision(revision):
    return revision.model_copy(update={"application_links": ()})


@cache
def _committed_modelo(modelo_id: str) -> ModeloDefinition:
    modelos, _catalogues = _committed_registry_tree()
    return next(modelo for modelo in modelos if modelo.id == modelo_id)


@cache
def _committed_snapshot(modelo_id: str, filing_year: int, period: str) -> RegistrySnapshot:
    return compile_validated_authority(
        bundled_path("registry", "aeat"), bundled_path()
    ).snapshot(modelo_id, filing_year=filing_year, period=period)
