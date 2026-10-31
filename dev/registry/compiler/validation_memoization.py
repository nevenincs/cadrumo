"""Validation-result memoization storage for the registry validator.

Not itself a validator: this module holds no checks, only the three
identity-keyed caches :class:`~cadrumo.domain.calculations.registry.RegistryValidator`
reads and writes to avoid re-validating an unchanged
:class:`ModeloDefinition` or catalogue mapping, and :class:`ModeloIdentityMemo`
for the registry-scope checks that fold one pure per-modelo projection over a
whole tree. Named without the
``_validate`` prefix its predecessor carried (``_validate_cache.py``), which
asserted a validation role this module never had.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable, Mapping
from threading import RLock

from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.runtime_catalogues import RuntimeRegistryCatalogues
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference

from .source_evidence_fingerprint import SourceEvidenceFingerprint

_CatalogueCacheKey = tuple[int, int, int, int, str | None, SourceEvidenceFingerprint]
_CatalogueCacheValue = tuple[
    Mapping[str, LegalReference],
    Mapping[str, SourceReference],
    GovernedFactCatalogue,
    RuntimeRegistryCatalogues,
    tuple[str, ...],
]
_ModeloValidationCacheKey = tuple[
    int, int, int, int, int, tuple[int, ...], str | None, str | None, SourceEvidenceFingerprint
]
_ModeloValidationCacheValue = tuple[
    ModeloDefinition,
    Mapping[str, LegalReference],
    Mapping[str, SourceReference],
    GovernedFactCatalogue,
    RuntimeRegistryCatalogues,
    tuple[str, ...],
]
_RegistryValidationCacheKey = tuple[
    tuple[int, ...],
    int,
    int,
    int,
    int,
    tuple[int, ...],
    str | None,
    str | None,
    SourceEvidenceFingerprint,
]
_RegistryValidationCacheValue = tuple[
    tuple[ModeloDefinition, ...],
    Mapping[str, LegalReference],
    Mapping[str, SourceReference],
    GovernedFactCatalogue,
    RuntimeRegistryCatalogues,
    tuple[str, ...],
]

CATALOGUE_FAILURE_CACHE: dict[_CatalogueCacheKey, _CatalogueCacheValue] = {}
MODELO_VALIDATION_CACHE: dict[_ModeloValidationCacheKey, _ModeloValidationCacheValue] = {}
REGISTRY_VALIDATION_CACHE: dict[_RegistryValidationCacheKey, _RegistryValidationCacheValue] = {}


class ModeloIdentityMemo[R]:
    """Process-local results of one pure per-modelo projection, keyed by the modelo object.

    Registry-scope checks fold a per-modelo projection over every modelo in a
    tree, and a generated-tree candidate validates a scope in which all but one
    modelo are the very objects the bundled authority already holds. Keying by
    object lets those unchanged modelos answer from the projection computed for
    them once, while the substituted candidate modelo is a new object and is
    always computed afresh. Registry models are frozen, so an object's content
    cannot change under its identity.

    The address alone cannot key this: CPython reuses a collected object's
    address. A weak reference decides identity, so a recycled address never
    serves another modelo's result, and the memo never keeps a modelo alive.
    """

    __slots__ = ("_entries", "_lock")

    def __init__(self) -> None:
        """Start with no memoised projections."""
        self._entries: dict[int, tuple[weakref.ref[ModeloDefinition], R]] = {}
        self._lock = RLock()

    def get_or_compute(self, modelo: ModeloDefinition, compute: Callable[[ModeloDefinition], R]) -> R:
        """Return ``compute(modelo)``, computing it at most once per live modelo object."""
        key = id(modelo)
        with self._lock:
            entry = self._entries.get(key)
        if entry is not None and entry[0]() is modelo:
            return entry[1]
        result = compute(modelo)
        reference = weakref.ref(modelo, self._forget(key))
        with self._lock:
            self._entries[key] = (reference, result)
        return result

    def clear(self) -> None:
        """Forget every memoised projection."""
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        """Return how many live modelo objects hold a memoised projection."""
        with self._lock:
            return len(self._entries)

    def _forget(self, key: int) -> Callable[[weakref.ref[ModeloDefinition]], None]:
        def forget(reference: weakref.ref[ModeloDefinition]) -> None:
            with self._lock:
                entry = self._entries.get(key)
                if entry is not None and entry[0] is reference:
                    del self._entries[key]

        return forget
