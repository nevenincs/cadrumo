"""Apoderamiento-scope catalogue repository.

:class:`ApoderamientosRepository` exposes the singleton apoderamientos catalogue
directly from the shared published authority.
"""

from __future__ import annotations

from collections.abc import Iterable


class ApoderamientosRepository:
    """Singleton-keyed repository for the apoderamientos scope catalogue.

    Wraps :func:`cadrumo.domain.auth.apoderamientos.load_default_catalogue`
    without adding a second cache.
    """

    def get(self, key: None) -> object:
        """Resolve through the current published authority without a second cache."""
        return self._load(key)

    def _load(self, key: None) -> object:
        from ...auth.apoderamientos.catalogue import load_default_catalogue

        return load_default_catalogue()

    def all(self) -> Iterable[object]:
        """Preserve the repository contract's non-enumerable behavior."""
        raise NotImplementedError(f"{type(self).__name__} does not implement all(); override per repository")

    def clear_cache(self) -> None:
        """Do nothing; the published authority owns runtime freshness."""

    @property
    def singleton(self) -> object:
        """Convenience accessor for the singleton resource."""
        return self.get(None)
