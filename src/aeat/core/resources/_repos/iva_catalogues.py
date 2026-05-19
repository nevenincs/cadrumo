"""VatCatalogueRepository: int-year-keyed VAT regulation catalogue."""

from __future__ import annotations

from pathlib import Path

from .._errors import ResourceNotFoundError
from .._repository import Repository


class VatCatalogueRepository(Repository[object, int]):
    """Year-keyed repository for the bundled VAT regulation catalogue.

    Wraps :func:`aeat.domain.vat._catalogue.load_vat_catalogues`. The
    Settings env-override seam for ``AEAT_VAT_CATALOGUE_ROOT`` is
    threaded through the constructor's ``root`` parameter; the
    :func:`aeat.core.resources.resources` factory reads Settings and
    passes the resolved root once at construction.
    """

    def __init__(self, root: Path | None = None) -> None:
        super().__init__()
        self._root = root

    def _load(self, key: int) -> object:
        from ....domain.vat._catalogue import load_vat_catalogues

        catalogues = (
            load_vat_catalogues(self._root)
            if self._root is not None
            else load_vat_catalogues()
        )
        try:
            return catalogues[key]
        except KeyError as exc:
            raise ResourceNotFoundError(
                f"no VAT catalogue registered for year {key}"
            ) from exc
