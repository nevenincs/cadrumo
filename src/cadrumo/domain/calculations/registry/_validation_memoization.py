"""Validation-result memoization storage for the registry validator.

Not itself a validator: this module holds no checks, only the three
identity-keyed caches :class:`~cadrumo.domain.calculations.registry.RegistryValidator`
reads and writes to avoid re-validating an unchanged
:class:`ModeloDefinition` or catalogue mapping. Named without the
``_validate`` prefix its predecessor carried (``_validate_cache.py``), which
asserted a validation role this module never had.
"""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference

from ._source_evidence_fingerprint import SourceEvidenceFingerprint

_CatalogueCacheKey = tuple[int, int, str | None, SourceEvidenceFingerprint]
_CatalogueCacheValue = tuple[Mapping[str, LegalReference], Mapping[str, SourceReference], tuple[str, ...]]
_ModeloValidationCacheKey = tuple[int, int, int, str | None, str | None, SourceEvidenceFingerprint]
_ModeloValidationCacheValue = tuple[
    ModeloDefinition,
    Mapping[str, LegalReference],
    Mapping[str, SourceReference],
    tuple[str, ...],
]
_RegistryValidationCacheKey = tuple[
    tuple[int, ...],
    int,
    int,
    str | None,
    str | None,
    SourceEvidenceFingerprint,
]
_RegistryValidationCacheValue = tuple[
    tuple[ModeloDefinition, ...],
    Mapping[str, LegalReference],
    Mapping[str, SourceReference],
    tuple[str, ...],
]

CATALOGUE_FAILURE_CACHE: dict[_CatalogueCacheKey, _CatalogueCacheValue] = {}
MODELO_VALIDATION_CACHE: dict[_ModeloValidationCacheKey, _ModeloValidationCacheValue] = {}
REGISTRY_VALIDATION_CACHE: dict[_RegistryValidationCacheKey, _RegistryValidationCacheValue] = {}
