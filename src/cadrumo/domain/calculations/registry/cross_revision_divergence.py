"""Cross-revision casilla divergence-detection engine.

Detects field-level divergence when the same casilla id appears in
multiple :class:`ModeloRevision` records of the same
:class:`ModeloDefinition`. The strict-validation and advisory-summary
policies applied while the registry authority is built consume the
divergences this module produces; keeping detection separate from policy
keeps each module reviewable.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass

from ....core.casilla_id import CasillaId
from ....core.i18n.render import MissingTranslationError
from .ids import RevisionId
from .revision_order import revisions_overlap as _revisions_overlap
from .schema import ModeloDefinition, ModeloRevision
from .schema_surfaces import CasillaContinuidadEvolutionDefinition, CasillaDefinition

_CROSS_REVISION_CASILLA_FIELDS: tuple[str, ...] = (
    "label",
    "section",
    "data_type",
    "semantic_role",
    "legal_refs",
)
_UNRESOLVED_LOCALIZATION = "<unresolved-localization>"

__all__ = ("CrossRevisionCasillaDivergence", "iter_cross_revision_casilla_divergences")


@dataclass(frozen=True, slots=True)
class CrossRevisionCasillaDivergence:
    """One field-level difference for a repeated casilla id."""

    modelo_id: str
    casilla_id: CasillaId
    left_revision_id: RevisionId
    right_revision_id: RevisionId
    field: str
    left_value: object
    right_value: object
    revisions_overlap: bool
    left_continuidad_id: str | None = None
    right_continuidad_id: str | None = None
    evolution_id: str | None = None
    evolution_kind: str | None = None
    evolution_covers_field: bool = False


def _cross_revision_signature(casilla: CasillaDefinition) -> tuple[object, ...]:
    """Return the stable cross-revision fingerprint for a casilla."""
    values: list[object] = []
    for field in _CROSS_REVISION_CASILLA_FIELDS:
        try:
            values.append(getattr(casilla, field))
        except MissingTranslationError:
            # Structural roots may be checked before their shared catalogue
            # is available. Keep both unresolved labels equal so this gate
            # reports only evidence it can actually compare; bundled roots
            # are covered by the strict catalogue enrollment gate.
            values.append(_UNRESOLVED_LOCALIZATION)
    return tuple(values)


def _group_casillas_by_id(
    modelo: ModeloDefinition,
) -> dict[CasillaId, list[tuple[ModeloRevision, CasillaDefinition]]]:
    by_id: dict[CasillaId, list[tuple[ModeloRevision, CasillaDefinition]]] = defaultdict(list)
    for revision in modelo.revisions.values():
        for casilla in revision.casillas:
            by_id[casilla.id].append((revision, casilla))
    return by_id


type _LineageEvolutions = Mapping[str, tuple[CasillaContinuidadEvolutionDefinition, ...]]
type _EvolutionsByLineage = Mapping[RevisionId, _LineageEvolutions]
_NO_LINEAGE_EVOLUTIONS: _LineageEvolutions = dict[str, tuple[CasillaContinuidadEvolutionDefinition, ...]]()


def _evolutions_by_lineage(modelo: ModeloDefinition) -> _EvolutionsByLineage:
    """Group each revision's declared evolutions by lineage so a pair resolves by lookup."""
    index: dict[RevisionId, dict[str, tuple[CasillaContinuidadEvolutionDefinition, ...]]] = {}
    for revision_id, revision in modelo.revisions.items():
        grouped: dict[str, list[CasillaContinuidadEvolutionDefinition]] = defaultdict(list)
        for evolution in revision.casilla_continuidad_evolutions:
            grouped[evolution.continuidad_id].append(evolution)
        index[revision_id] = {lineage: tuple(items) for lineage, items in grouped.items()}
    return index


def _pair_field_divergences(
    modelo: ModeloDefinition,
    casilla_id: CasillaId,
    left_revision: ModeloRevision,
    left_casilla: CasillaDefinition,
    left_sig: tuple[object, ...],
    right_revision: ModeloRevision,
    right_casilla: CasillaDefinition,
    right_sig: tuple[object, ...],
    evolutions: _EvolutionsByLineage,
) -> Iterator[CrossRevisionCasillaDivergence]:
    revisions_overlap = _revisions_overlap(left_revision, right_revision)
    for field, left_value, right_value in zip(
        _CROSS_REVISION_CASILLA_FIELDS,
        left_sig,
        right_sig,
        strict=True,
    ):
        if left_value == right_value:
            continue
        evolution = _matching_evolution(left_revision, right_revision, left_casilla, right_casilla, field, evolutions)
        yield CrossRevisionCasillaDivergence(
            modelo_id=modelo.id,
            casilla_id=casilla_id,
            left_revision_id=left_revision.id,
            right_revision_id=right_revision.id,
            field=field,
            left_value=left_value,
            right_value=right_value,
            revisions_overlap=revisions_overlap,
            left_continuidad_id=left_casilla.continuidad_id,
            right_continuidad_id=right_casilla.continuidad_id,
            evolution_id=evolution.id if evolution is not None else None,
            evolution_kind=evolution.evolution_kind if evolution is not None else None,
            evolution_covers_field=evolution is not None and field in evolution.evolution_kind.covered_fields,
        )


def _casilla_divergences_for_occurrences(
    modelo: ModeloDefinition,
    casilla_id: CasillaId,
    occurrences: list[tuple[ModeloRevision, CasillaDefinition]],
    evolutions: _EvolutionsByLineage,
) -> Iterator[CrossRevisionCasillaDivergence]:
    for index, (left_revision, left_casilla) in enumerate(occurrences[:-1]):
        left_sig = _cross_revision_signature(left_casilla)
        for right_revision, right_casilla in occurrences[index + 1 :]:
            right_sig = _cross_revision_signature(right_casilla)
            if right_sig == left_sig:
                continue
            yield from _pair_field_divergences(
                modelo,
                casilla_id,
                left_revision,
                left_casilla,
                left_sig,
                right_revision,
                right_casilla,
                right_sig,
                evolutions,
            )


def iter_cross_revision_casilla_divergences(
    modelos: Iterable[ModeloDefinition],
) -> tuple[CrossRevisionCasillaDivergence, ...]:
    """Compare repeated casillas while retaining their field-specific attestations."""
    divergences: list[CrossRevisionCasillaDivergence] = []
    for modelo in modelos:
        by_id = _group_casillas_by_id(modelo)
        evolutions = _evolutions_by_lineage(modelo)
        for casilla_id, occurrences in by_id.items():
            if len(occurrences) < 2:
                continue
            divergences.extend(_casilla_divergences_for_occurrences(modelo, casilla_id, occurrences, evolutions))
    return tuple(divergences)


def _matching_evolution(
    left_revision: ModeloRevision,
    right_revision: ModeloRevision,
    left_casilla: CasillaDefinition,
    right_casilla: CasillaDefinition,
    field: str,
    evolutions: _EvolutionsByLineage,
) -> CasillaContinuidadEvolutionDefinition | None:
    continuidad_ids = {left_casilla.continuidad_id, right_casilla.continuidad_id} - {None}
    if len(continuidad_ids) != 1:
        return None
    continuidad_id = next(iter(continuidad_ids))
    fallback = None
    for revision in (left_revision, right_revision):
        for evolution in evolutions.get(revision.id, _NO_LINEAGE_EVOLUTIONS).get(continuidad_id, ()):
            if {evolution.from_revision, evolution.to_revision} == {left_revision.id, right_revision.id}:
                if field in evolution.evolution_kind.covered_fields:
                    return evolution
                fallback = evolution
    return fallback
