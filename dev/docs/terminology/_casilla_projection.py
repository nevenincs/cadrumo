"""Casilla projection compiler.

Projects every casilla of every modelo revision -- read through the
validated registry authority, never raw TOML -- into a strict
:class:`~dev.docs.terminology._search_record.CasillaSearchRecord`, then
deduplicates across revisions by the canonical ``(modelo, casilla.id)``
identity. The record carries the registry definition contract as well as the
display metadata; none of those fields participate in the search-record
identity.

The calculation-grounding contract binds this compiler: EVERY casilla is
emitted (input, bound, and computed alike -- never dropped), and each
record carries the casilla's ``legal_refs`` and ``source_refs``
provenance verbatim.

Dedup rule: a casilla identity that appears across multiple revisions
collapses to ONE record built from the LATEST revision (greatest
``valid_from``; revision id as a stable tiebreak). The latest revision
carries the current official label and the richest localised coverage
(per-revision locale fragments are authored on recent revisions), so its
text is authoritative. Every contributing revision id is recorded on
``source_revisions`` (latest first) so the collapse is auditable.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

from cadrumo.core import Modelo
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n import lookup_translation_entry
from cadrumo.domain.calculations.registry.authority import (
    ValidatedRegistryAuthority,
    bundled_authority,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ._search_record import CasillaSearchRecord, SearchRecordKind

__all__ = [
    "CasillaProjectionStats",
    "project_casilla_search_records",
    "project_modelo_casillas",
]

# Registry locale codes map 1:1 to the four output languages; only the
# non-Spanish three appear in localized_labels (es is the invariant label).
_LOCALE_TO_LANGUAGE: dict[str, OutputLanguage] = {
    "en": OutputLanguage.EN,
    "ca": OutputLanguage.CA,
    "hu": OutputLanguage.HU,
}


@dataclass(frozen=True, slots=True)
class CasillaProjectionStats:
    """Raw-vs-deduplicated counts for one projection run."""

    raw_casilla_rows: int
    deduplicated_records: int
    records_with_localized: int

    @property
    def collapsed(self) -> int:
        """How many raw rows were collapsed by cross-revision dedup."""
        return self.raw_casilla_rows - self.deduplicated_records


@dataclass(frozen=True, slots=True)
class _RevisionCasilla:
    """One casilla paired with the revision it was read from."""

    modelo: Modelo
    revision_id: str
    valid_from: date
    casilla: CasillaDefinition


def project_casilla_search_records(
    authority: ValidatedRegistryAuthority | None = None,
) -> tuple[tuple[CasillaSearchRecord, ...], CasillaProjectionStats]:
    """Project and deduplicate every casilla of every modelo.

    Args:
        authority: The validated registry authority to read snapshots
            through; defaults to the bundled authority. Injectable so a
            test can drive a narrowed authority deterministically.

    Returns:
        A ``(records, stats)`` pair: the deduplicated records sorted by
        ``(modelo, casilla_id)`` and the raw-vs-deduplicated counts.
    """
    resolved = authority if authority is not None else bundled_authority()
    raw_rows = 0
    by_key: dict[tuple[str, str], _RevisionCasilla] = {}
    sources: dict[tuple[str, str], list[_RevisionCasilla]] = {}

    for entry in _walk_revision_casillas(resolved.modelos):
        raw_rows += 1
        key = (entry.modelo.value, entry.casilla.id)
        sources.setdefault(key, []).append(entry)
        incumbent = by_key.get(key)
        if incumbent is None or _is_later(entry, incumbent):
            by_key[key] = entry

    records: list[CasillaSearchRecord] = []
    localized = 0
    for key in sorted(by_key):
        chosen = by_key[key]
        revisions_latest_first = tuple(
            item.revision_id for item in sorted(sources[key], key=lambda c: (c.valid_from, c.revision_id), reverse=True)
        )
        record = _build_record(chosen, revisions_latest_first)
        if _has_authored_locale(chosen.casilla):
            localized += 1
        records.append(record)

    stats = CasillaProjectionStats(
        raw_casilla_rows=raw_rows,
        deduplicated_records=len(records),
        records_with_localized=localized,
    )
    return tuple(records), stats


def project_modelo_casillas(
    modelo: Modelo,
    authority: ValidatedRegistryAuthority | None = None,
) -> tuple[CasillaSearchRecord, ...]:
    """Project and deduplicate the casillas of one modelo.

    A focused projection used by tests and by per-modelo index builds; it
    walks only ``modelo``'s revisions and applies the same dedup rule.
    """
    resolved = authority if authority is not None else bundled_authority()
    definition = resolved.modelo(modelo.value)
    by_key: dict[tuple[str, str], _RevisionCasilla] = {}
    sources: dict[tuple[str, str], list[_RevisionCasilla]] = {}
    for entry in _walk_modelo_casillas(modelo, definition):
        key = (entry.modelo.value, entry.casilla.id)
        sources.setdefault(key, []).append(entry)
        incumbent = by_key.get(key)
        if incumbent is None or _is_later(entry, incumbent):
            by_key[key] = entry
    records: list[CasillaSearchRecord] = []
    for key in sorted(by_key):
        chosen = by_key[key]
        revisions_latest_first = tuple(
            item.revision_id for item in sorted(sources[key], key=lambda c: (c.valid_from, c.revision_id), reverse=True)
        )
        records.append(_build_record(chosen, revisions_latest_first))
    return tuple(records)


def _walk_revision_casillas(modelos: tuple[ModeloDefinition, ...]) -> Iterator[_RevisionCasilla]:
    for definition in modelos:
        modelo = Modelo(definition.id)
        yield from _walk_modelo_casillas(modelo, definition)


def _walk_modelo_casillas(modelo: Modelo, definition: ModeloDefinition) -> Iterator[_RevisionCasilla]:
    for revision_id, revision in definition.revisions.items():
        yield from _walk_one_revision(modelo, str(revision_id), revision)


def _walk_one_revision(modelo: Modelo, revision_id: str, revision: ModeloRevision) -> Iterator[_RevisionCasilla]:
    for casilla in revision.casillas:
        yield _RevisionCasilla(
            modelo=modelo,
            revision_id=revision_id,
            valid_from=revision.valid_from,
            casilla=casilla,
        )


def _is_later(candidate: _RevisionCasilla, incumbent: _RevisionCasilla) -> bool:
    if candidate.valid_from != incumbent.valid_from:
        return candidate.valid_from > incumbent.valid_from
    return candidate.revision_id > incumbent.revision_id


def _build_record(entry: _RevisionCasilla, source_revisions: tuple[str, ...]) -> CasillaSearchRecord:
    casilla = entry.casilla
    descriptions: dict[OutputLanguage, str] = {OutputLanguage.ES: casilla.get_label(OutputLanguage.ES.value)}
    for locale, language in _LOCALE_TO_LANGUAGE.items():
        descriptions[language] = casilla.get_label(locale)
    localized_help = {
        language.value: help_text
        for language in OutputLanguage
        if (help_text := casilla.get_help(language.value)) is not None
    }
    return CasillaSearchRecord(
        kind=SearchRecordKind.CASILLA,
        descriptions=descriptions,
        modelo=entry.modelo,
        casilla_id=casilla.id,
        localized_help=localized_help,
        data_type=casilla.data_type,
        input_kind=casilla.input_kind,
        required=casilla.required,
        binding=casilla.binding,
        formula_id=casilla.formula,
        number=casilla.number,
        segmento=casilla.segmento,
        section=tuple(casilla.section),
        semantic_role=casilla.semantic_role,
        legal_refs=tuple(casilla.legal_refs),
        source_refs=tuple(casilla.source_refs),
        source_revisions=source_revisions,
    )


def _has_authored_locale(casilla: CasillaDefinition) -> bool:
    """Return whether a non-Spanish label is authored for this casilla."""
    return any(
        present and value is not None
        for locale in _LOCALE_TO_LANGUAGE
        for key in casilla.localization_keys
        for present, value in (lookup_translation_entry(key, locale=locale),)
    )
