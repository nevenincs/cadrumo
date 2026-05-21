"""ManualRepository: composite-keyed Manual catalogue.

The composite key is ``(manual_id, year, part)`` modelled as a
frozen Pydantic record. The Repository wraps the existing
loader chain in :mod:`aeat.domain.manuals`; the Settings env-
override for ``AEAT_MANUALS_ROOT`` is preserved verbatim by
passing the operator-resolved root through the constructor.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ConfigDict

from .._keys import TypedResourceKey
from .._repository import ResourceCacheRepository

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ....core.config import Settings
    from ....domain.manuals import ManualId, ManualPart

_FROZEN_STRICT = ConfigDict(strict=True, frozen=True, extra="forbid")


class ManualKey(TypedResourceKey):
    """Composite key (manual_id, year, part) for a Manual record."""

    model_config = _FROZEN_STRICT

    manual_id: str
    year: int
    part: str = "single"


class ManualRepository(ResourceCacheRepository[object, ManualKey]):
    """Composite-key repository for the bundled Manual catalogue.

    Wraps :func:`aeat.domain.manuals.load_manual` and stays in
    lockstep with the env-override seam on
    ``Settings.aeat_manuals_root``.
    """

    def __init__(self, root: Path | None = None) -> None:
        super().__init__()
        self._root = root

    def _settings(self) -> Settings | None:
        if self._root is None:
            return None
        from ....core.config import Settings as _Settings

        return _Settings(aeat_manuals_root=self._root)

    def _load(self, key: ManualKey) -> object:
        from ....domain.manuals import ManualId, ManualPart, load_manual

        manual_id = ManualId(key.manual_id)
        try:
            part = ManualPart(key.part)
        except ValueError:
            part = ManualPart.SINGLE
        return load_manual(
            manual_id=manual_id,
            year=key.year,
            part=part,
            settings=self._settings(),
        )

    def catalogue(self, specs: Iterable[tuple[ManualId, int, ManualPart]]) -> object:
        """Return a :class:`ManualCatalogue` aggregate for ``specs``."""
        from ....domain.manuals import load_catalogue

        return load_catalogue(specs, settings=self._settings())

    def find_rules(self, *args: object, **kwargs: object) -> object:
        """Delegate to :func:`aeat.domain.manuals.find_rules` for rule queries."""
        from ....domain.manuals import find_rules

        return find_rules(*args, settings=self._settings(), **kwargs)

    def iter_sections(self, *args: object, **kwargs: object) -> object:
        """Delegate to :func:`aeat.domain.manuals.iter_sections` for section iteration."""
        from ....domain.manuals import iter_sections

        return iter_sections(*args, settings=self._settings(), **kwargs)
