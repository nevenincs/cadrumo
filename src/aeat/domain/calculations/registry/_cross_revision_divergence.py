"""Cross-revision casilla divergence-detection engine.

Detects field-level divergence when the same casilla id appears in
multiple :class:`ModeloRevision` records of the same
:class:`ModeloDefinition`. The strict-validation and advisory-summary
policies in :mod:`aeat.domain.calculations.registry._validate_cross_revision`
consume the divergences this module produces; keeping detection separate
from policy keeps each module reviewable.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from ._schema import (
    CasillaContinuidadEvolutionDefinition,
    CasillaDefinition,
    ModeloDefinition,
    ModeloRevision,
    PeriodSelector,
)

_CROSS_REVISION_CASILLA_FIELDS: tuple[str, ...] = (
    "label",
    "section",
    "data_type",
    "semantic_role",
    "legal_refs",
)

__all__ = ("CrossRevisionCasillaDivergence",)


@dataclass(frozen=True, slots=True)
class CrossRevisionCasillaDivergence:
    """One field-level difference for a repeated casilla id."""

    modelo_id: str
    casilla_id: str
    left_revision_id: str
    right_revision_id: str
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
    return tuple(getattr(casilla, field) for field in _CROSS_REVISION_CASILLA_FIELDS)


def _period_selector_year_bounds(selector: PeriodSelector) -> tuple[int, int | None]:
    if selector.years:
        return min(selector.years), max(selector.years)
    if selector.year_from is None:
        return 0, None
    return selector.year_from, selector.year_to


def _period_selectors_overlap(left: PeriodSelector, right: PeriodSelector) -> bool:
    left_start, left_end = _period_selector_year_bounds(left)
    right_start, right_end = _period_selector_year_bounds(right)
    if left_end is not None and left_end < right_start:
        return False
    if right_end is not None and right_end < left_start:
        return False
    return bool(set(left.periods).intersection(right.periods))


def _revisions_overlap(left: object, right: object) -> bool:
    left_selector = getattr(left, "period_selector", None)
    right_selector = getattr(right, "period_selector", None)
    if not isinstance(left_selector, PeriodSelector) or not isinstance(right_selector, PeriodSelector):
        return True
    return _period_selectors_overlap(left_selector, right_selector)


def _iter_cross_revision_casilla_divergences(
    modelos: Iterable[ModeloDefinition],
) -> tuple[CrossRevisionCasillaDivergence, ...]:
    divergences: list[CrossRevisionCasillaDivergence] = []
    for modelo in modelos:
        by_id: dict[str, list[tuple[ModeloRevision, CasillaDefinition]]] = defaultdict(list)
        for revision in modelo.revisions.values():
            for casilla in revision.casillas:
                by_id[casilla.id].append((revision, casilla))
        for casilla_id, occurrences in by_id.items():
            if len(occurrences) < 2:
                continue
            for index, (left_revision, left_casilla) in enumerate(occurrences[:-1]):
                left_sig = _cross_revision_signature(left_casilla)
                for right_revision, right_casilla in occurrences[index + 1 :]:
                    revisions_overlap = _revisions_overlap(left_revision, right_revision)
                    right_sig = _cross_revision_signature(right_casilla)
                    if right_sig == left_sig:
                        continue
                    evolution = _matching_evolution(left_revision, right_revision, left_casilla, right_casilla)
                    for field, left_value, right_value in zip(
                        _CROSS_REVISION_CASILLA_FIELDS,
                        left_sig,
                        right_sig,
                        strict=True,
                    ):
                        if left_value == right_value:
                            continue
                        divergences.append(
                            CrossRevisionCasillaDivergence(
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
                                evolution_covers_field=_evolution_covers_field(evolution, field),
                            )
                        )
    return tuple(divergences)


def _matching_evolution(
    left_revision: ModeloRevision,
    right_revision: ModeloRevision,
    left_casilla: CasillaDefinition,
    right_casilla: CasillaDefinition,
) -> CasillaContinuidadEvolutionDefinition | None:
    continuidad_ids = {left_casilla.continuidad_id, right_casilla.continuidad_id} - {None}
    if len(continuidad_ids) != 1:
        return None
    continuidad_id = next(iter(continuidad_ids))
    for revision in (left_revision, right_revision):
        for evolution in revision.casilla_continuidad_evolutions:
            if evolution.continuidad_id != continuidad_id:
                continue
            if {evolution.from_revision, evolution.to_revision} == {left_revision.id, right_revision.id}:
                return evolution
    return None


def _evolution_covers_field(evolution: CasillaContinuidadEvolutionDefinition | None, field: str) -> bool:
    if evolution is None:
        return False
    if evolution.evolution_kind == "label_evolved":
        return field == "label"
    if evolution.evolution_kind == "legal_refs_evolved":
        return field == "legal_refs"
    if evolution.evolution_kind == "label_and_legal_refs_evolved":
        return field in {"label", "legal_refs"}
    return evolution.evolution_kind == "repurposed"
