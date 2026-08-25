"""Cross-revision casilla divergence-detection engine.

Detects field-level divergence when the same casilla id appears in
multiple :class:`ModeloRevision` records of the same
:class:`ModeloDefinition`. The strict-validation and advisory-summary
policies in :mod:`cadrumo.domain.calculations.registry.validate_cross_revision`
consume the divergences this module produces; keeping detection separate
from policy keeps each module reviewable.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.schema_surfaces import (
    CasillaContinuidadEvolutionDefinition,
    CasillaDefinition,
)

from ....core import CasillaId
from ....core.i18n import MissingTranslationError
from .ids import RevisionId

_CROSS_REVISION_CASILLA_FIELDS: tuple[str, ...] = (
    "label",
    "section",
    "data_type",
    "semantic_role",
    "legal_refs",
)
_UNRESOLVED_LOCALIZATION = "<unresolved-localization>"

__all__ = ("CrossRevisionCasillaDivergence",)


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


def _revisions_overlap(left: ModeloRevision, right: ModeloRevision) -> bool:
    """Whether two revisions' declared period selectors could both be live at once.

    ``ModeloRevision.period_selector`` is a REQUIRED field (never ``None``),
    and every real caller (all three: :func:`_pair_field_divergences`,
    ``_validate_cross_revision.py``'s ``_period_overlap_requires_evolution``,
    ``_validate_cross_revision_contiguity.py``'s ``_skipped_revisions``)
    always passes real, fully-constructed :class:`ModeloRevision` instances --
    confirmed by reading each call site, and no production code ever builds a
    ``ModeloRevision`` via ``model_construct``. Reading ``.period_selector``
    directly (never ``getattr(..., default=None)`` guarded by an
    ``isinstance`` fallback to ``True``) means a rename of the field fails
    loud instead of silently making every revision pair register as
    "overlapping" -- which is NOT a safe default here: three of the four
    consumers only run their own check when a pair does NOT overlap (the
    strict continuity-evolution requirement, the continuity-coverage
    advisory, and the contiguity gap detector this whole module's own
    docstring says exists to catch "a chain which is present, absent, then
    present again"), so a permanent ``True`` would silently disable all
    three, with nothing downstream to catch the loss.
    """
    return _period_selectors_overlap(left.period_selector, right.period_selector)


def _ordered_revisions(modelo: ModeloDefinition) -> tuple[ModeloRevision, ...]:
    """Return a modelo's revisions in validity order, ties broken by id."""
    return tuple(
        sorted(modelo.revisions.values(), key=lambda revision: (revision.valid_from, revision.id)),
    )


def _group_casillas_by_id(
    modelo: ModeloDefinition,
) -> dict[CasillaId, list[tuple[ModeloRevision, CasillaDefinition]]]:
    by_id: dict[CasillaId, list[tuple[ModeloRevision, CasillaDefinition]]] = defaultdict(list)
    for revision in modelo.revisions.values():
        for casilla in revision.casillas:
            by_id[casilla.id].append((revision, casilla))
    return by_id


def _pair_field_divergences(
    modelo: ModeloDefinition,
    casilla_id: CasillaId,
    left_revision: ModeloRevision,
    left_casilla: CasillaDefinition,
    left_sig: tuple[object, ...],
    right_revision: ModeloRevision,
    right_casilla: CasillaDefinition,
    right_sig: tuple[object, ...],
) -> Iterator[CrossRevisionCasillaDivergence]:
    revisions_overlap = _revisions_overlap(left_revision, right_revision)
    evolution = _matching_evolution(left_revision, right_revision, left_casilla, right_casilla)
    for field, left_value, right_value in zip(
        _CROSS_REVISION_CASILLA_FIELDS,
        left_sig,
        right_sig,
        strict=True,
    ):
        if left_value == right_value:
            continue
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
            evolution_covers_field=_evolution_covers_field(evolution, field),
        )


def _casilla_divergences_for_occurrences(
    modelo: ModeloDefinition,
    casilla_id: CasillaId,
    occurrences: list[tuple[ModeloRevision, CasillaDefinition]],
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
            )


def _iter_cross_revision_casilla_divergences(
    modelos: Iterable[ModeloDefinition],
) -> tuple[CrossRevisionCasillaDivergence, ...]:
    divergences: list[CrossRevisionCasillaDivergence] = []
    for modelo in modelos:
        by_id = _group_casillas_by_id(modelo)
        for casilla_id, occurrences in by_id.items():
            if len(occurrences) < 2:
                continue
            divergences.extend(_casilla_divergences_for_occurrences(modelo, casilla_id, occurrences))
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


revisions_overlap = _revisions_overlap
ordered_revisions = _ordered_revisions
iter_cross_revision_casilla_divergences = _iter_cross_revision_casilla_divergences
