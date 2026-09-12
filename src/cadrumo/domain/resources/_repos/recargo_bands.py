"""Singleton recargo-band repository.

:class:`RecargoBandsRepository` exposes Ley 58/2003 recargo bands through the
shared published authority without adding a repository cache.
"""

from __future__ import annotations

from collections.abc import Iterable


class RecargoBandsRepository:
    """Singleton-keyed repository for the Ley 58/2003 recargo bands.

    Wraps :func:`cadrumo.domain.deadlines.load_recargo_bands` directly.
    """

    def get(self, key: None) -> object:
        """Resolve through the current published authority without a second cache."""
        return self._load(key)

    def _load(self, key: None) -> object:
        from ...deadlines.recargo import load_recargo_bands

        return load_recargo_bands()

    def all(self) -> Iterable[object]:
        """Preserve the repository contract's non-enumerable behavior."""
        raise NotImplementedError(f"{type(self).__name__} does not implement all(); override per repository")

    def clear_cache(self) -> None:
        """Do nothing; the published authority owns runtime freshness."""

    @property
    def singleton(self) -> object:
        return self.get(None)
