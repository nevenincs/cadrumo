"""Published typed authority and locale shard inventories for casilla catalogues."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import yaml

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema_surfaces import (
    CasillaContinuidadEvolutionDefinition,
)

from ._casilla_keys import is_delta_keyed_leaf
from ._paths import LOCALES_DIR
from .casilla_catalogue_models import CasillaOccurrence, Values
from .casilla_text_policy import _EDITION_TEXT, _EDITION_TEXT_PLACEHOLDER
from .locale_tree import _flatten_raw_locale_leaves
from .locale_yaml import discover_locale_codes


def casilla_occurrences() -> tuple[CasillaOccurrence, ...]:
    """Enumerate every casilla and construct occurrence of the published generation.

    A construct is carried as an occurrence whose label chain is its title chain,
    so both delta-keyed surfaces share one resolution, collapse and audit.
    """
    return _published_surface()[0]


def _published_surface() -> tuple[
    tuple[CasillaOccurrence, ...], dict[str, tuple[CasillaContinuidadEvolutionDefinition, ...]]
]:
    """Read occurrences and their declared evolutions from one authority operation."""
    found: list[CasillaOccurrence] = []
    evolutions: dict[str, tuple[CasillaContinuidadEvolutionDefinition, ...]] = {}
    with bundled_indexed_authority().operation() as operation:
        for modelo_id in operation.modelo_ids():
            model_evolutions: list[CasillaContinuidadEvolutionDefinition] = []
            for metadata in operation.modelo_directory(modelo_id).revisions:
                revision = operation.revision(modelo_id, str(metadata.id))
                model_evolutions.extend(revision.casilla_continuidad_evolutions)
                found.extend(
                    CasillaOccurrence(
                        modelo=str(modelo_id),
                        revision=str(metadata.id),
                        casilla=str(casilla.id),
                        number=str(casilla.number),
                        continuidad_id=None if casilla.continuidad_id is None else str(casilla.continuidad_id),
                        inherited_from=None if casilla.inherited_from is None else str(casilla.inherited_from),
                        label_chain=tuple(casilla.localization_keys),
                    )
                    for casilla in revision.casillas
                )
                found.extend(
                    CasillaOccurrence(
                        modelo=str(modelo_id),
                        revision=str(metadata.id),
                        casilla=f"construct:{construct.id}",
                        number="",
                        continuidad_id=None,
                        inherited_from=None,
                        label_chain=tuple(construct.localization_keys),
                        carries_help=False,
                    )
                    for construct in revision.constructs
                )
            evolutions[str(modelo_id)] = tuple(model_evolutions)
    return tuple(found), evolutions


def load_casilla_values(locales_dir: Path = LOCALES_DIR) -> Values:
    """Read every casilla leaf of every locale's Modelo schema shards."""
    values: Values = {}
    for locale in sorted(discover_locale_codes(locales_dir)):
        leaves: dict[str, str | None] = {}
        for shard in sorted((locales_dir / locale / "modelo" / "schema").glob("*.yml")):
            raw = yaml.safe_load(shard.read_text(encoding="utf-8")) or {}
            for key, value in _flatten_raw_locale_leaves(raw).items():
                if is_delta_keyed_leaf(key):
                    leaves[key] = None if value is None else str(value)
        values[locale] = leaves
    return values


def edition_text_gaps(locales_dir: Path = LOCALES_DIR) -> dict[str, tuple[str, ...]]:
    """Return, per locale, revision labels that are null or a scaffold placeholder.

    A revision label is edition-specific text with no inheritance chain, so every
    declared revision needs its own authored value in every locale. Construct
    titles are delta-keyed and judged through resolution with casilla labels.
    """
    gaps: dict[str, tuple[str, ...]] = {}
    for locale, labels in _edition_labels(locales_dir).items():
        gaps[locale] = tuple(
            sorted(
                key
                for key, value in labels.items()
                if value is None or _EDITION_TEXT_PLACEHOLDER.search(value) is not None
            )
        )
    return gaps


def repeated_edition_text(locales_dir: Path = LOCALES_DIR) -> dict[str, tuple[str, ...]]:
    """Return, per locale, revision labels one modelo repeats across editions.

    A revision label names its own edition, so two editions of a modelo cannot
    carry the same label: the repeated text describes the period of one of them
    and misdescribes the others. Unlike a casilla label, it inherits nothing, so
    the repetition is a copy to re-author rather than a collapse target.
    """
    repeated: dict[str, tuple[str, ...]] = {}
    for locale, labels in _edition_labels(locales_dir).items():
        by_text: dict[tuple[str, str], list[str]] = defaultdict(list)
        for key, value in labels.items():
            match = _EDITION_TEXT.match(key)
            if value is not None and match is not None:
                by_text[(match.group("modelo"), value)].append(key)
        repeated[locale] = tuple(sorted(key for keys in by_text.values() if len(keys) > 1 for key in keys))
    return repeated


def _edition_labels(locales_dir: Path) -> dict[str, dict[str, str | None]]:
    """Return, per locale, every revision-label leaf of the Modelo schema shards."""
    labels: dict[str, dict[str, str | None]] = {}
    for locale in sorted(discover_locale_codes(locales_dir)):
        found: dict[str, str | None] = {}
        for shard in sorted((locales_dir / locale / "modelo" / "schema").glob("*.yml")):
            raw = yaml.safe_load(shard.read_text(encoding="utf-8")) or {}
            for key, value in _flatten_raw_locale_leaves(raw).items():
                if _EDITION_TEXT.match(key):
                    found[key] = None if value is None else str(value)
        labels[locale] = found
    return labels
