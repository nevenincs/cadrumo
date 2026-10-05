"""Authored casilla edits, exact change attribution, and grounded continuity joins."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .casilla_catalogue_models import CollapseVerificationError

if TYPE_CHECKING:
    from .modelo_casilla_catalogue import ModeloCasillaCatalogue
from collections.abc import Mapping

from cadrumo.domain.calculations.registry.modelo_localization import (
    modelo_localization_source,
)
from cadrumo.domain.calculations.registry.schema_surfaces import (
    CasillaContinuidadEvolutionDefinition,
    CasillaEvolutionKind,
)

from .casilla_catalogue_models import (
    Coordinate,
)
from .casilla_text_policy import (
    SOURCE_LOCALE,
)
from .manager import LocaleManager


def _add_declared_casilla_label_link(
    self: ModeloCasillaCatalogue,
    evolution: CasillaContinuidadEvolutionDefinition,
    occurrences: Mapping[str, int],
    after: Mapping[Coordinate, str | None],
    links: dict[str | None, set[str | None]],
) -> None:
    """Add declared casilla label link."""
    if evolution.evolution_kind not in (
        CasillaEvolutionKind.LABEL_EVOLVED,
        CasillaEvolutionKind.LABEL_AND_LEGAL_REFS_EVOLVED,
    ) or not (evolution.legal_refs and evolution.source_refs):
        return
    start = occurrences.get(str(evolution.from_revision))
    end = occurrences.get(str(evolution.to_revision))
    if start is None or end is None:
        return
    if any(self.occurrences[index].continuidad_id != str(evolution.continuidad_id) for index in (start, end)):
        return
    left = after.get((start, "label", SOURCE_LOCALE))
    right = after.get((end, "label", SOURCE_LOCALE))
    links[left].add(right)
    links[right].add(left)


def _apply_authored_casilla_locale(manager: LocaleManager, locale: str, values: Mapping[str, str | None]) -> None:
    """Apply authored casilla locale."""
    settings = {key: text for key, text in values.items() if text is not None}
    removals = sorted(key for key, text in values.items() if text is None)
    if settings:
        manager.set_locale_values(locale, settings)
    if removals:
        manager.remove_locale_values(locale, removals)


def _record_authored_casilla_change(
    self: ModeloCasillaCatalogue,
    proof: ModeloCasillaCatalogue,
    before: Mapping[Coordinate, str | None],
    manifest: Mapping[str, Mapping[str, str | None]],
    coordinate: Coordinate,
    text: str | None,
    changed: dict[str, int],
    unattributed: list[Coordinate],
) -> None:
    """Record authored casilla change."""
    if before[coordinate] == text:
        return
    index, field_name, locale = coordinate
    source = modelo_localization_source(
        self.occurrences[index].chain(field_name), locale=locale, lookup=proof.lookup_for(proof.values)
    )
    if source is None or source[0] not in manifest.get(source[1], {}):
        unattributed.append(coordinate)
    changed[locale] += 1


def _record_introduced_casilla_segment_drift(
    self: ModeloCasillaCatalogue,
    proof: ModeloCasillaCatalogue,
    locale: str,
    introduced_drift: list[tuple[str, str, tuple[str, ...]]],
) -> None:
    """Record introduced casilla segment drift."""
    if locale == SOURCE_LOCALE:
        return
    existing = self.segment_drift(locale)
    for segment, renderings in proof.segment_drift(locale).items():
        if set(renderings) - set(existing.get(segment, ())):
            introduced_drift.append((locale, segment, renderings))


def _refuse_unknown_authored_casilla_keys(
    self: ModeloCasillaCatalogue, manifest: Mapping[str, Mapping[str, str | None]]
) -> None:
    """Refuse unknown authored casilla keys."""
    unknown = sorted(
        f"{locale}:{key}"
        for locale, values in manifest.items()
        for key in values
        if locale not in self.locales or key not in self.dependents
    )
    if unknown:
        raise CollapseVerificationError(f"manifest names keys no casilla chain reads: {unknown[:5]}")
