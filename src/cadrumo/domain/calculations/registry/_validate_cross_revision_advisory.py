"""Advisory cross-revision drift summaries for non-overlapping revisions."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from ....core import CasillaId
from ._cross_revision_divergence import (
    CrossRevisionCasillaDivergence,
    iter_cross_revision_casilla_divergences,
)
from .errors import RegistryValidationError
from ._ids import RevisionId
from ._schema import ModeloDefinition

__all__ = (
    "CrossRevisionCasillaDriftSummary",
    "summarize_non_overlapping_cross_revision_casilla_drift",
)


@dataclass(frozen=True, slots=True)
class CrossRevisionCasillaDriftSummary:
    """Grouped advisory drift inventory for non-overlapping revisions."""

    modelo_id: str
    left_revision_id: RevisionId
    right_revision_id: RevisionId
    field: str
    drift_count: int
    example_casilla_ids: tuple[CasillaId, ...]
    continuidad_ids: tuple[str, ...] = ()
    evolution_kinds: tuple[str, ...] = ()
    covered_by_evolution_count: int = 0
    uncovered_count: int = 0


def _group_non_overlapping_divergences(
    modelos: Iterable[ModeloDefinition],
) -> dict[tuple[str, str, str, str], list[CrossRevisionCasillaDivergence]]:
    grouped: dict[tuple[str, str, str, str], list[CrossRevisionCasillaDivergence]] = defaultdict(list)
    for divergence in iter_cross_revision_casilla_divergences(modelos):
        if divergence.revisions_overlap:
            continue
        key = (
            divergence.modelo_id,
            divergence.left_revision_id,
            divergence.right_revision_id,
            divergence.field,
        )
        grouped[key].append(divergence)
    return grouped


def _drift_continuity_ids(divergences: list[CrossRevisionCasillaDivergence]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                continuity_id
                for divergence in divergences
                for continuity_id in (divergence.left_continuidad_id, divergence.right_continuidad_id)
                if continuity_id is not None
            },
        ),
    )


def _drift_evolution_kinds(divergences: list[CrossRevisionCasillaDivergence]) -> tuple[str, ...]:
    return tuple(
        sorted({divergence.evolution_kind for divergence in divergences if divergence.evolution_kind is not None})
    )


def _summarize_drift_group(
    key: tuple[str, str, str, str],
    divergences: list[CrossRevisionCasillaDivergence],
    *,
    example_limit: int,
) -> CrossRevisionCasillaDriftSummary:
    modelo_id, left_revision_id, right_revision_id, field = key
    casilla_ids = [divergence.casilla_id for divergence in divergences]
    covered_by_evolution_count = sum(1 for divergence in divergences if divergence.evolution_covers_field)
    return CrossRevisionCasillaDriftSummary(
        modelo_id=modelo_id,
        left_revision_id=left_revision_id,
        right_revision_id=right_revision_id,
        field=field,
        drift_count=len(casilla_ids),
        example_casilla_ids=tuple(dict.fromkeys(casilla_ids[:example_limit])),
        continuidad_ids=_drift_continuity_ids(divergences),
        evolution_kinds=_drift_evolution_kinds(divergences),
        covered_by_evolution_count=covered_by_evolution_count,
        uncovered_count=len(divergences) - covered_by_evolution_count,
    )


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

    grouped = _group_non_overlapping_divergences(modelos)
    return tuple(
        _summarize_drift_group(key, divergences, example_limit=example_limit)
        for key, divergences in sorted(grouped.items())
    )
