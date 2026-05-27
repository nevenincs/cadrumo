"""Validation failure cache storage for registry validators."""

from __future__ import annotations

from collections.abc import Mapping

from ._schema import LegalReference, ModeloDefinition, SourceReference

_CatalogueCacheKey = tuple[int, int, str | None, bool]
_CatalogueCacheValue = tuple[Mapping[str, LegalReference], Mapping[str, SourceReference], tuple[str, ...]]
_ModeloValidationCacheKey = tuple[int, int, int, str | None, str | None]
_ModeloValidationCacheValue = tuple[
    ModeloDefinition,
    Mapping[str, LegalReference],
    Mapping[str, SourceReference],
    tuple[str, ...],
]
_RegistryValidationCacheKey = tuple[tuple[int, ...], int, int, str | None, str | None]
_RegistryValidationCacheValue = tuple[
    tuple[ModeloDefinition, ...],
    Mapping[str, LegalReference],
    Mapping[str, SourceReference],
    tuple[str, ...],
]

_CATALOGUE_FAILURE_CACHE: dict[_CatalogueCacheKey, _CatalogueCacheValue] = {}
_MODELO_VALIDATION_CACHE: dict[_ModeloValidationCacheKey, _ModeloValidationCacheValue] = {}
_REGISTRY_VALIDATION_CACHE: dict[_RegistryValidationCacheKey, _RegistryValidationCacheValue] = {}
