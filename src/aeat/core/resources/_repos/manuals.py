"""ManualRepository: composite-keyed Manual catalogue.

The composite key is ``(manual_id, year, part)`` modelled as a
frozen Pydantic record. The Repository wraps the existing
loader chain in :mod:`aeat.domain.manuals`; the Settings env-
override for ``AEAT_MANUALS_ROOT`` is preserved verbatim by
passing the operator-resolved root through the constructor.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from .._keys import TypedResourceKey
from .._repository import ResourceCacheRepository

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from ....core.config import Settings
    from ....domain.manuals import (
        Manual,
        ManualCasillaReference,
        ManualCatalogue,
        ManualId,
        ManualPart,
        Rule,
        RuleKind,
        Section,
    )


class ManualKey(TypedResourceKey):
    """Composite key (manual_id, year, part) for a Manual record."""

    manual_id: str
    year: int
    part: str = "single"

    @override
    def __hash__(self) -> int:
        return hash((self.manual_id, self.year, self.part))


class ManualRepository(ResourceCacheRepository["Manual", ManualKey]):
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

    @override
    def _load(self, key: ManualKey) -> Manual:
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

    def catalogue(self, specs: Iterable[tuple[ManualId, int, ManualPart]]) -> ManualCatalogue:
        """Return a :class:`ManualCatalogue` aggregate for ``specs``."""
        from ....domain.manuals import load_catalogue

        return load_catalogue(specs, settings=self._settings())

    def find_rules(
        self,
        catalogue: ManualCatalogue,
        *,
        casilla_reference: ManualCasillaReference | None = None,
        kind: RuleKind | None = None,
        lang: str | None = None,
    ) -> Iterator[Rule]:
        """Delegate to :func:`aeat.domain.manuals.find_rules` for rule queries.

        Yields each matching :class:`Rule` from the catalogue in
        encounter order.
        """
        from ....domain.manuals import find_rules

        return find_rules(
            catalogue,
            casilla_reference=casilla_reference,
            kind=kind,
            lang=lang,
            settings=self._settings(),
        )

    def iter_sections(self, manual: Manual) -> Iterator[Section]:
        """Delegate to :func:`aeat.domain.manuals.iter_sections` for section iteration.

        Yields each :class:`Section` from ``manual`` in document order.
        """
        from ....domain.manuals import iter_sections

        return iter_sections(manual, settings=self._settings())
