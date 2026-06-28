"""Advisory cross-revision drift summaries for non-overlapping revisions."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from ._cross_revision_divergence import (
    CrossRevisionCasillaDivergence,
    _iter_cross_revision_casilla_divergences,
)
from ._errors import RegistryValidationError
from ._ids import CasillaId
from ._schema import ModeloDefinition

__all__ = (
    "CrossRevisionCasillaDriftSummary",
    "summarize_non_overlapping_cross_revision_casilla_drift",
)


@dataclass(frozen=True, slots=True)
class CrossRevisionCasillaDriftSummary:
    """Grouped advisory drift inventory for non-overlapping revisions."""

    modelo_id: str
    left_revision_id: str
    right_revision_id: str
    field: str
    drift_count: int
    example_casilla_ids: tuple[CasillaId, ...]
    continuidad_ids: tuple[str, ...] = ()
    evolution_kinds: tuple[str, ...] = ()
    covered_by_evolution_count: int = 0
    uncovered_count: int = 0


def summarize_non_overlapping_cross_revision_casilla_drift(
    modelos: Iterable[ModeloDefinition],
    *,
    example_limit: int = 5,
) -> tuple[CrossRevisionCasillaDriftSummary, ...]:
    """Return advisory drift summaries for repeated ids in non-overlapping revisions.

    The snapshot-build validator raises on overlapping revision windows
    because those revisions can apply to the same filing period. Annual
    non-overlapping forms, such as M100, can legally evolve or repurpose
    repeated numeric ids; this inventory keeps that drift visible without
    turning it into a load-time error before the schema has an explicit
    continuity/evolution contract.

    Args:
        modelos: Iterable of :class:`ModeloDefinition` instances to inspect
            for cross-revision casilla drift.
        example_limit: Maximum number of example casilla ids to include in
            each summary record.

    Returns:
        Tuple of :class:`CrossRevisionCasillaDriftSummary` records, one per drifted casilla id.
    """
    if example_limit < 1:
        raise RegistryValidationError("example_limit must be at least 1")

    grouped: dict[tuple[str, str, str, str], list[CrossRevisionCasillaDivergence]] = defaultdict(list)
    for divergence in _iter_cross_revision_casilla_divergences(modelos):
        if divergence.revisions_overlap:
            continue
        key = (
            divergence.modelo_id,
            divergence.left_revision_id,
            divergence.right_revision_id,
            divergence.field,
        )
        grouped[key].append(divergence)

    summaries: list[CrossRevisionCasillaDriftSummary] = []
    for (modelo_id, left_revision_id, right_revision_id, field), divergences in sorted(grouped.items()):
        casilla_ids = [divergence.casilla_id for divergence in divergences]
        examples = tuple(dict.fromkeys(casilla_ids[:example_limit]))
        continuidad_ids = tuple(
            sorted(
                {
                    continuidad_id
                    for divergence in divergences
                    for continuidad_id in (divergence.left_continuidad_id, divergence.right_continuidad_id)
                    if continuidad_id is not None
                },
            ),
        )
        evolution_kinds = tuple(
            sorted({divergence.evolution_kind for divergence in divergences if divergence.evolution_kind is not None}),
        )
        covered_by_evolution_count = sum(1 for divergence in divergences if divergence.evolution_covers_field)
        summaries.append(
            CrossRevisionCasillaDriftSummary(
                modelo_id=modelo_id,
                left_revision_id=left_revision_id,
                right_revision_id=right_revision_id,
                field=field,
                drift_count=len(casilla_ids),
                example_casilla_ids=examples,
                continuidad_ids=continuidad_ids,
                evolution_kinds=evolution_kinds,
                covered_by_evolution_count=covered_by_evolution_count,
                uncovered_count=len(divergences) - covered_by_evolution_count,
            ),
        )
    return tuple(summaries)
