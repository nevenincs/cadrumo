"""Casilla legal content, composed segment, and lineage translation comparisons."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .modelo_casilla_catalogue import ModeloCasillaCatalogue
from collections import Counter
from collections.abc import Callable, Mapping

from cadrumo.domain.calculations.registry.modelo_localization import (
    modelo_localization_source,
)

from .casilla_catalogue_models import (
    CasillaOccurrence,
    Values,
)
from .casilla_resolution import _served_locale
from .casilla_text_comparison import (
    _content_tokens,
    _segments,
)
from .casilla_text_policy import (
    SOURCE_LOCALE,
)


def _record_dropped_casilla_content(
    self: ModeloCasillaCatalogue,
    index: int,
    occurrence: CasillaOccurrence,
    field_name: str,
    locale: str,
    values: Values | None,
    lookup: Callable[[str, str], str | None],
    dropped: dict[str, tuple[str, ...]],
) -> None:
    """Record dropped casilla content."""
    spanish = self.resolve(index, field_name, SOURCE_LOCALE, values)
    if spanish is None:
        return
    source = _content_tokens(spanish)
    if not source:
        return
    served = modelo_localization_source(occurrence.chain(field_name), locale=locale, lookup=lookup)
    if served is None or served[1] != locale:
        return
    rendered = _content_tokens(self.resolve(index, field_name, locale, values) or "", spelled=True)
    # A reference repeated in one sentence states the same box once.
    missing = Counter({token: 1 for token in source if token not in rendered})
    if missing:
        dropped[served[0]] = tuple(sorted(missing.elements()))


def _record_casilla_segment_renderings(
    key: str, spanish_texts: frozenset[str], locale: str, view: Values, rendered: dict[str, set[str]]
) -> None:
    """Record casilla segment renderings."""
    translation = view.get(locale, {}).get(key)
    if translation is None or len(spanish_texts) != 1:
        return
    spanish = _segments(next(iter(spanish_texts)))
    parts = _segments(translation)
    if len(spanish) != len(parts) or len(spanish) < 2:
        return
    for source_part, rendering in zip(spanish, parts, strict=True):
        rendered[source_part.strip()].add(rendering.strip())


def _record_casilla_rendering_segments(
    key: str, spanish_texts: frozenset[str], locale: str, view: Values, rendered: dict[str, set[str]]
) -> None:
    """Record casilla rendering segments."""
    translation = view.get(locale, {}).get(key)
    if translation is None or len(spanish_texts) != 1:
        return
    spanish = _segments(next(iter(spanish_texts)))
    parts = _segments(translation)
    if len(spanish) != len(parts) or len(spanish) < 2:
        return
    for source_part, rendering in zip(spanish, parts, strict=True):
        rendered[rendering.strip()].add(source_part.strip())


def _record_casilla_lineage_locale_drift(
    self: ModeloCasillaCatalogue,
    locale: str,
    groups: Mapping[tuple[str, str, str, str], list[int]],
    values: Values | None,
    drift: dict[str, tuple[str, ...]],
) -> None:
    """Record casilla lineage locale drift."""
    if locale == SOURCE_LOCALE:
        return
    drift[locale] = tuple(
        sorted(
            f"{modelo}/{lineage}"
            for (modelo, lineage, field_name, _spanish), members in groups.items()
            if len(
                {
                    text
                    for index in members
                    if _served_locale(self, index, field_name, locale, values) == locale
                    and (text := self.resolve(index, field_name, locale, values)) is not None
                }
            )
            > 1
        )
    )


def _record_stale_casilla_translation(
    self: ModeloCasillaCatalogue,
    index: int,
    occurrence: CasillaOccurrence,
    field_name: str,
    locale: str,
    lookup: Callable[[str, str], str | None],
    spanish_by_translation: dict[tuple[str, str, str], set[str]],
) -> None:
    """Record stale casilla translation."""
    source = modelo_localization_source(occurrence.chain(field_name), locale=locale, lookup=lookup)
    spanish = self.resolve(index, field_name, SOURCE_LOCALE)
    if source is None or source[1] != locale or spanish is None:
        return
    translation = self.values[locale][source[0]]
    if translation is None:
        return
    lineage = occurrence.continuidad_id or f"casilla:{occurrence.casilla}"
    spanish_by_translation[(occurrence.modelo, lineage, translation)].add(spanish)
