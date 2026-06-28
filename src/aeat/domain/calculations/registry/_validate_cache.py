"""Validation failure cache storage for registry validators.

Stores memoised validation results keyed by identity of
:class:`ModeloDefinition` instances and catalogue mappings.
"""

from __future__ import annotations

from collections.abc import Mapping

from ._schema import LegalReference, ModeloDefinition, SourceReference

_CatalogueCacheKey = tuple[int, int, str | None, bool]
_CatalogueCacheValue = tuple[Mapping[str, LegalReference], Mapping[str, SourceReference], tuple[str, ...]]
_ModeloValidationCacheKey = tuple[int, int, int, str | None, str | None, bool]
_ModeloValidationCacheValue = tuple[
    ModeloDefinition,
    Mapping[str, LegalReference],
    Mapping[str, SourceReference],
    tuple[str, ...],
]
_RegistryValidationCacheKey = tuple[tuple[int, ...], int, int, str | None, str | None, bool]
_RegistryValidationCacheValue = tuple[
    tuple[ModeloDefinition, ...],
    Mapping[str, LegalReference],
    Mapping[str, SourceReference],
    tuple[str, ...],
]

CATALOGUE_FAILURE_CACHE: dict[_CatalogueCacheKey, _CatalogueCacheValue] = {}
MODELO_VALIDATION_CACHE: dict[_ModeloValidationCacheKey, _ModeloValidationCacheValue] = {}
REGISTRY_VALIDATION_CACHE: dict[_RegistryValidationCacheKey, _RegistryValidationCacheValue] = {}
