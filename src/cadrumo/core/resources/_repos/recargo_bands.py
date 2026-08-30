"""Singleton recargo-band repository.

:class:`RecargoBandsRepository` exposes Ley 58/2003 recargo bands through the
shared :class:`ResourceCacheRepository` cache used by :class:`ResourceRegistry`.
"""

from __future__ import annotations

from typing import override

from .._repository import ResourceCacheRepository


class RecargoBandsRepository(ResourceCacheRepository[object, None]):
    """Singleton-keyed repository for the Ley 58/2003 recargo bands.

    Wraps :func:`cadrumo.domain.deadlines.load_recargo_bands` behind
    the shared :class:`ResourceCacheRepository` cache.
    """

    @override
    def _load(self, key: None) -> object:
        from ....domain.deadlines.recargo import load_recargo_bands

        return load_recargo_bands()

    @property
    def singleton(self) -> object:
        return self.get(None)
