"""RecargoBandsRepository: singleton recargo-band tuple."""

from __future__ import annotations

from .._repository import ResourceCacheRepository


class RecargoBandsRepository(ResourceCacheRepository[object, type(None)]):
    """Singleton-keyed repository for the Ley 58/2003 recargo bands.

    Wraps :func:`aeat.domain.deadlines.load_recargo_bands`.
    """

    def _load(self, key: None) -> object:
        from ....domain.deadlines import load_recargo_bands

        return load_recargo_bands()

    @property
    def singleton(self) -> object:
        return self.get(None)
