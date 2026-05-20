"""ApoderamientosRepository: singleton catalogue of apoderamiento scopes."""

from __future__ import annotations

from .._repository import ResourceCacheRepository


class ApoderamientosRepository(ResourceCacheRepository[object, type(None)]):
    """Singleton-keyed repository for the apoderamientos scope catalogue.

    Wraps :func:`aeat.domain.auth.apoderamientos.load_default_catalogue`.
    """

    def _load(self, key: None) -> object:
        from ....domain.auth.apoderamientos import load_default_catalogue

        return load_default_catalogue()

    @property
    def singleton(self) -> object:
        """Convenience accessor for the singleton resource."""
        return self.get(None)
