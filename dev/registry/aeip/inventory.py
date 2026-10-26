"""Load and group AEIP occurrences from the canonical registry model loader."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from cadrumo.core.i18n.render import MissingTranslationError
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..compiler.loader import load_modelo_directory
from . import constants as _constants
from .adjudications import AdjudicationSet
from .identity import derive_slug
from .types import AeipEvent, AeipInventory, AeipOccurrence

__all__ = ("build_inventory", "extract_occurrences")

_APLICADO_SUFFIX = re.compile(r":\s*Aplicado en esta declaraci[oó]n\s*$", re.IGNORECASE)
_WRAPPING_QUOTES = re.compile(r"^\s*[“”«»\"](?P<title>.+?)[“”«»\"]\s*$")


def _title_from_label(label: str) -> str | None:
    """Pull the programme title out of an anexo-A event label.

    The published label is ``"<title>": Aplicado en esta declaración``. Most
    titles are wrapped in typographic quotes, but a handful carry quotes
    *inside* the title instead (``Celebración del Summit "MADBLUE"``), so the
    wrapping quotes are stripped only when they actually wrap the whole core.
    """
    if not _APLICADO_SUFFIX.search(label):
        return None
    core = _APLICADO_SUFFIX.sub("", label).strip()
    if not core:
        return None
    wrapped = _WRAPPING_QUOTES.match(core)
    if wrapped is None:
        return core.strip()
    title = wrapped.group("title")
    if not isinstance(title, str):
        raise TypeError("wrapped title must be text")
    return title.strip()


def extract_occurrences(
    modelos_root: Path,
    *,
    modelo_id: str = "100",
    locale: str = _constants.SOURCE_LOCALE,
) -> tuple[tuple[AeipOccurrence, ...], dict[str, int]]:
    """Read every anexo-A AEIP event row through the registry loader.

    The schema carries no natural-language label: a casilla declares only its
    ``localization_keys``, and the text is resolved from the shared locale
    catalogues. So the family is read through
    :func:`~cadrumo.domain.calculations.registry.load_modelo_directory` and each
    programme title comes from ``casilla.get_label`` rather than from a
    fragment field, which keeps this planner on the one canonical resolution
    path instead of re-deriving keys or re-reading TOML.

    Returns the event-row occurrences plus a per-revision count of the sibling
    category rows, which the inventory reports but never enrols in a chain.
    """
    definition = _load_modelo(modelos_root, modelo_id)

    occurrences: list[AeipOccurrence] = []
    category_counts: dict[str, int] = defaultdict(int)
    for revision in definition.revisions.values():
        for casilla in revision.casillas:
            if _constants.ANEXO_A_SECTION_LEAF not in tuple(casilla.section or ()):
                continue
            role = str(casilla.semantic_role or "")
            if role == _constants.CATEGORY_SEMANTIC_ROLE:
                category_counts[revision.id] += 1
                continue
            if role != _constants.EVENT_SEMANTIC_ROLE:
                continue
            occurrences.append(_event_occurrence(revision.id, casilla, locale))
    return tuple(occurrences), dict(category_counts)


def _load_modelo(modelos_root: Path, modelo_id: str) -> ModeloDefinition:
    modelo_root = modelos_root / modelo_id
    if not modelo_root.is_dir():
        raise RegistryLoadError(f"no registry directory for modelo {modelo_id} at {modelo_root}")
    try:
        return load_modelo_directory(modelo_root)
    except RegistryLoadError as error:
        raise RegistryLoadError(f"cannot load modelo {modelo_id} registry: {error}") from error


def _event_occurrence(revision_id: str, casilla: CasillaDefinition, locale: str) -> AeipOccurrence:
    # A key with no catalogue entry leaves the occurrence untitled rather than
    # raising; the rest of the family remains plannable and reports the gap.
    try:
        label = casilla.get_label(locale)
    except MissingTranslationError:
        label = ""
    return AeipOccurrence(
        revision_id=str(revision_id),
        casilla_id=str(casilla.id),
        label=label,
        title=_title_from_label(label) or "",
        localization_keys=tuple(casilla.localization_keys),
        legal_refs=tuple(str(ref) for ref in casilla.legal_refs),
        continuidad_id=casilla.continuidad_id,
        source_refs=tuple(str(ref) for ref in casilla.source_refs),
    )


def build_inventory(
    occurrences: tuple[AeipOccurrence, ...],
    *,
    adjudications: AdjudicationSet | None = None,
    category_row_counts: dict[str, int] | None = None,
) -> AeipInventory:
    """Group occurrences into programmes, honouring any alias adjudications."""
    resolved = adjudications or AdjudicationSet.empty()
    grouped: dict[str, list[AeipOccurrence]] = defaultdict(list)
    titles: dict[str, str] = {}
    untitled: list[AeipOccurrence] = []
    for occurrence in occurrences:
        if resolved.is_excluded(occurrence.revision_id, occurrence.casilla_id):
            continue
        if not occurrence.title:
            untitled.append(occurrence)
            continue
        slug = resolved.slug_for(occurrence.title) or derive_slug(occurrence.title)
        grouped[slug].append(occurrence)
        titles.setdefault(slug, occurrence.title)

    events = tuple(
        AeipEvent(slug=slug, title=titles[slug], occurrences=tuple(rows)) for slug, rows in sorted(grouped.items())
    )
    revisions = tuple(sorted({occurrence.revision_id for occurrence in occurrences}))
    return AeipInventory(
        events=events,
        occurrences=occurrences,
        revisions=revisions,
        category_row_counts=dict(category_row_counts or {}),
        untitled_occurrences=tuple(untitled),
    )
