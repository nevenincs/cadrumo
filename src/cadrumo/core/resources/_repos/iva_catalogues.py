"""Year-keyed IVA regulation-catalogue repository.

:class:`IvaCatalogueRepository` is the :class:`ResourceCacheRepository` adapter
for bundled IVA catalogues and the resource factory's IVA-catalogue root
override.
"""

from __future__ import annotations

from pathlib import Path
from typing import override

from ..errors import ResourceNotFoundError
from .._repository import ResourceCacheRepository


class IvaCatalogueRepository(ResourceCacheRepository[object, int]):
    """Year-keyed repository for the bundled IVA regulation catalogue.

    Wraps :func:`cadrumo.domain.iva.load_iva_catalogues`. The
    Settings env-override seam for ``CADRUMO_IVA_CATALOGUE_ROOT`` is
    threaded through the constructor's ``root`` parameter; the
    :func:`cadrumo.core.resources.resources` factory reads Settings and
    passes the resolved root once at construction. Missing years raise
    :class:`ResourceNotFoundError`.
    """

    def __init__(self, root: Path | None = None) -> None:
        super().__init__()
        self._root = root

    @override
    def _load(self, key: int) -> object:
        from ....domain.iva import load_iva_catalogues

        catalogues = load_iva_catalogues(self._root) if self._root is not None else load_iva_catalogues()
        try:
            return catalogues[key]
        except KeyError as exc:
            raise ResourceNotFoundError(f"no IVA catalogue registered for year {key}") from exc
