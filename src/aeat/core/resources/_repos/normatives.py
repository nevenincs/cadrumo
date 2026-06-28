"""NormativeRepository: singleton :class:`NormativeCatalogue` lookup."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from .._repository import ResourceCacheRepository

if TYPE_CHECKING:
    from ....core.config import Settings
    from ....domain.normatives import NormativeCatalogue, NormativeReference
    from ....domain.normatives._schema import Articulo


class NormativeRepository(ResourceCacheRepository["NormativeCatalogue", None]):
    """Singleton-keyed repository for the bundled normatives catalogue.

    Wraps :func:`aeat.domain.normatives.load_catalogue`. The
    Settings env-override seam for ``AEAT_NORMATIVES_ROOT`` is
    threaded through the constructor. Lookup helpers return
    :class:`NormativeReference` and :class:`Articulo` records from
    the singleton catalogue.
    """

    def __init__(self, root: Path | None = None) -> None:
        super().__init__()
        self._root = root

    def _settings(self) -> Settings | None:
        if self._root is None:
            return None
        from ....core.config import Settings as _Settings

        return _Settings(aeat_normatives_root=self._root)

    @override
    def _load(self, key: None) -> NormativeCatalogue:
        from ....domain.normatives import load_catalogue

        return load_catalogue(settings=self._settings())

    @property
    def singleton(self) -> NormativeCatalogue:
        return self.get(None)

    def find_reference(self, ref_id: str) -> NormativeReference:
        """Look up a normative reference by id via the singleton catalogue.

        Returns:
            The matching :class:`NormativeReference` from the catalogue.
        """
        from ....domain.normatives import find_reference

        return find_reference(self.singleton, ref_id)

    def find_articulo(self, ref_id: str, articulo: str) -> Articulo:
        """Look up a normative articulo via the singleton catalogue.

        Returns:
            The matching :class:`Articulo` from the normative reference.
        """
        from ....domain.normatives import find_articulo

        return find_articulo(self.singleton, ref_id, articulo)
