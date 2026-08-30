"""Year-resolved IVA regulation-catalogue repository.

:class:`IvaCatalogueRepository` is the :class:`ResourceCacheRepository` adapter
for the bundled IVA catalogue and the resource factory's catalogue-file
override.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import override

from .._repository import ResourceCacheRepository
from ..errors import ResourceNotFoundError


class IvaCatalogueRepository(ResourceCacheRepository[object, int]):
    """Year-resolved repository over the bundled IVA regulation catalogue.

    The catalogue itself is undated; the year is a RESOLUTION key, projecting
    the corpus onto the citations asserted over that filing year. The Settings
    env-override seam for ``CADRUMO_IVA_CATALOGUE_FILE`` is threaded through the
    constructor's ``path`` parameter; the
    :func:`cadrumo.core.resources.resources` factory reads Settings and passes
    the resolved path once at construction. A year the catalogue does not ground
    raises :class:`ResourceNotFoundError`.
    """

    def __init__(self, path: Path | None = None) -> None:
        super().__init__()
        self._path = path

    @override
    def _load(self, key: int) -> object:
        from ....domain.iva.catalogue import iva_catalogue_years, resolve_catalogue
        from ....domain.iva.errors import IvaCatalogueError

        if self._path is not None and key not in iva_catalogue_years(self._path):
            raise ResourceNotFoundError(f"no IVA catalogue grounded for year {key}")
        try:
            return resolve_catalogue(on=date(key, 1, 1))
        except IvaCatalogueError as exc:
            raise ResourceNotFoundError(f"no IVA catalogue grounded for year {key}") from exc
