"""Year-resolved IVA regulation-catalogue repository.

:class:`IvaCatalogueRepository` adapts the published IVA authority without
adding a repository identity map.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from ....core.resources.errors import ResourceNotFoundError


class IvaCatalogueRepository:
    """Year-resolved repository over the bundled IVA regulation catalogue.

    The year is a resolution key projected by the shared published authority.
    A year the catalogue does not ground raises :class:`ResourceNotFoundError`.
    """

    def get(self, key: int) -> object:
        """Resolve through the current published authority without a second cache."""
        return self._load(key)

    def _load(self, key: int) -> object:
        from ...iva.catalogue import resolve_catalogue
        from ...iva.errors import IvaCatalogueError

        try:
            return resolve_catalogue(on=date(key, 1, 1))
        except IvaCatalogueError as exc:
            raise ResourceNotFoundError(f"no IVA catalogue grounded for year {key}") from exc

    def all(self) -> Iterable[object]:
        """Preserve the repository contract's non-enumerable behavior."""
        raise NotImplementedError(f"{type(self).__name__} does not implement all(); override per repository")

    def clear_cache(self) -> None:
        """Do nothing; the published authority owns runtime freshness."""
