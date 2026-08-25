"""Singleton legal-parameter repository.

:class:`LegalParameterRepository` loads registry-wide :class:`LegalParameter`
records through the shared :class:`ResourceCacheRepository` cache.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, override

from .._repository import ResourceCacheRepository

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema_references import LegalParameter


class LegalParameterRepository(ResourceCacheRepository[Mapping[str, "LegalParameter"], None]):
    """Singleton-keyed repository for the registry-wide legal parameters.

    Wraps :func:`cadrumo.domain.calculations.registry.load_legal_parameters_only`
    rooted at the bundled registry tree and returns
    :class:`LegalParameter` records.
    """

    @override
    def _load(self, key: None) -> Mapping[str, LegalParameter]:
        from ....domain.calculations.registry.loader import load_legal_parameters_only
        from .._boundary import bundled_path

        return load_legal_parameters_only(bundled_path("registry", "aeat"))

    @property
    def singleton(self) -> Mapping[str, LegalParameter]:
        return self.get(None)
