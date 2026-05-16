"""NormativeRepository: singleton catalogue + typed lookup."""

from __future__ import annotations

from pathlib import Path

from .._repository import Repository


class NormativeRepository(Repository[object, type(None)]):
    """Singleton-keyed repository for the bundled normatives catalogue.

    Wraps :func:`aeat.domain.normatives.load_catalogue`. The
    Settings env-override seam for ``AEAT_NORMATIVES_ROOT`` is
    threaded through the constructor.
    """

    def __init__(self, root: Path | None = None) -> None:
        super().__init__()
        self._root = root

    def _settings(self) -> object | None:
        if self._root is None:
            return None
        from ....core.config import Settings

        return Settings(aeat_normatives_root=self._root)

    def _load(self, key: None) -> object:
        from ....domain.normatives import load_catalogue

        return load_catalogue(settings=self._settings())  # type: ignore[arg-type]

    @property
    def singleton(self) -> object:
        return self.get(None)

    def find_reference(self, ref_id: str) -> object:
        """Look up a normative reference by id via the singleton catalogue."""
        from ....domain.normatives import find_reference

        return find_reference(self.singleton, ref_id)  # type: ignore[arg-type]

    def find_articulo(self, ref_id: str, articulo: str) -> object:
        """Look up a normative articulo via the singleton catalogue."""
        from ....domain.normatives import find_articulo

        return find_articulo(self.singleton, ref_id, articulo)  # type: ignore[arg-type]
