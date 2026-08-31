"""Apoderamiento-scope catalogue repository.

:class:`ApoderamientosRepository` exposes the singleton apoderamientos catalogue
through the shared :class:`ResourceCacheRepository` cache used by
:class:`ResourceRegistry`.
"""

from __future__ import annotations

from typing import override

from .._repository import ResourceCacheRepository


class ApoderamientosRepository(ResourceCacheRepository[object, None]):
    """Singleton-keyed repository for the apoderamientos scope catalogue.

    Wraps :func:`cadrumo.domain.auth.apoderamientos.load_default_catalogue`
    behind the shared :class:`ResourceCacheRepository` cache.
    """

    @override
    def _load(self, key: None) -> object:
        from ....domain.auth.apoderamientos.catalogue import load_default_catalogue

        return load_default_catalogue()

    @property
    def singleton(self) -> object:
        """Convenience accessor for the singleton resource."""
        return self.get(None)
