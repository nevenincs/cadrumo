"""ManualRepository: composite-keyed :class:`Manual` catalogue.

The composite key is ``(manual_id, year, part)`` modelled as a
frozen :class:`ManualKey` record. The :class:`ManualRepository`
wraps the existing loader chain in :mod:`cadrumo.domain.manuals`;
the Settings env-override for ``AEAT_MANUALS_ROOT`` is preserved
verbatim by passing the operator-resolved root through the
constructor.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from pydantic import field_validator

from .._keys import TypedResourceKey
from .._repository import ResourceCacheRepository
from ..errors import ResourceValidationError

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
    """Composite key (manual_id, year, part) for a :class:`Manual` record.

    ``part`` is stored as text because this key lives in :mod:`core`, which
    must not import :mod:`domain` at module level. Its value set is still the
    canonical :class:`~domain.manuals.ManualPart` vocabulary: the validator
    resolves every declaration through that enum, so an unknown part is
    refused when the key is built rather than silently rewritten later.
    """

    manual_id: str
    year: int
    part: str = "single"

    @field_validator("part")
    @classmethod
    def _part_is_a_known_volume(cls, value: str) -> str:
        """Reject a part the canonical volume vocabulary does not declare.

        The repository used to swallow the enum's ``ValueError`` and fall back
        to ``SINGLE``, so a typo'd or stale caller key returned a *valid but
        different* authoritative manual — the aggregate a reader would then
        quote regulatory text from. Failing closed at key construction keeps a
        mis-keyed lookup from ever selecting an authority.
        """
        from ....domain.manuals import ManualPart

        try:
            return str(ManualPart(value))
        except ValueError as exc:
            accepted = ", ".join(sorted(part.value for part in ManualPart))
            raise ResourceValidationError(
                f"unknown manual part {value!r}; accepted values are: {accepted}",
            ) from exc

    @override
    def __hash__(self) -> int:
        return hash((self.manual_id, self.year, self.part))


class ManualRepository(ResourceCacheRepository["Manual", ManualKey]):
    """Composite-key repository for the bundled Manual catalogue.

    Wraps :func:`cadrumo.domain.manuals.load_manual` and stays in
    lockstep with the env-override seam on
    ``Settings.aeat_manuals_root``. The repository returns
    :class:`Manual` records keyed by :class:`ManualKey`.
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
        # No fallback: ManualKey already refused any part outside the canonical
        # vocabulary, so this conversion is total for a constructed key.
        part = ManualPart(key.part)
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
        """Delegate to :func:`cadrumo.domain.manuals.find_rules` for rule queries.

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
        """Delegate to :func:`cadrumo.domain.manuals.iter_sections` for section iteration.

        Yields each :class:`Section` from ``manual`` in document order.
        """
        from ....domain.manuals import iter_sections

        return iter_sections(manual, settings=self._settings())
