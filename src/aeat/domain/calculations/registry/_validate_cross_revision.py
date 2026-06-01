"""Cross-revision drift validation policies for registry casillas.

Applies two policies over the divergences detected by
:mod:`aeat.domain.calculations.registry._cross_revision_divergence`: the
strict hard-fail continuity policy for overlapping revisions and declared
continuity surfaces, and the advisory non-overlapping drift summary.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from ._cross_revision_divergence import (
    CrossRevisionCasillaDivergence,
    _iter_cross_revision_casilla_divergences,
)
from ._errors import RegistryValidationError
from ._schema import ModeloDefinition

# D3 defines revision-level continuidad_validation = "strict" as
# surface-scoped strictness: declared continuity surfaces hard-fail drift,
# while unannotated repeated-id drift remains advisory until a separate
# corpus-wide completeness gate proves every repeated id has been reviewed.

__all__ = (
    "CrossRevisionCasillaDriftSummary",
    "summarize_non_overlapping_cross_revision_casilla_drift",
    "validate_cross_revision_casilla_consistency",
)


@dataclass(frozen=True, slots=True)
class CrossRevisionCasillaDriftSummary:
    """Grouped advisory drift inventory for non-overlapping revisions."""

    modelo_id: str
    left_revision_id: str
    right_revision_id: str
    field: str
    drift_count: int
    example_casilla_ids: tuple[str, ...]
    continuidad_ids: tuple[str, ...] = ()
    evolution_kinds: tuple[str, ...] = ()
    covered_by_evolution_count: int = 0
    uncovered_count: int = 0


def validate_cross_revision_casilla_consistency(modelos: Iterable[ModeloDefinition]) -> None:
    """Raise when a repeated casilla id drifts across revisions."""
    failures = _validate_cross_revision_casilla_consistency(modelos)
    if failures:
        raise RegistryValidationError(
            "cross-revision casilla drift detected:\n" + "\n".join(f" - {failure}" for failure in failures)
        )


def _validate_cross_revision_casilla_consistency(
    modelos: Iterable[ModeloDefinition],
) -> tuple[str, ...]:
    """Enforce that casillas sharing an id across revisions of a modelo agree.

    Per the AEAT registry design contract, a casilla id is a stable
    handle for a single legal concept within a modelo. Two
    declarations of casilla `0700` in two overlapping revisions
    must declare the same label, section, data_type, role, and
    legal references. Divergence is an authoring or repurposing event
    that needs explicit handling (either deprecate-and-rename or
    reconcile-to-canonical-form), never silent acceptance.
    """
    failures: dict[tuple[str, str, str, str], list[CrossRevisionCasillaDivergence]] = defaultdict(list)
    for divergence in _iter_cross_revision_casilla_divergences(modelos):
        if not divergence.revisions_overlap:
            continue
        key = (
            divergence.modelo_id,
            divergence.casilla_id,
            divergence.left_revision_id,
            divergence.right_revision_id,
        )
        failures[key].append(divergence)
    return tuple(
        _format_cross_revision_failure(modelo_id, casilla_id, left_revision_id, divergences)
        for (
            modelo_id,
            casilla_id,
            left_revision_id,
            _right_revision_id,
        ), divergences in failures.items()
    )


def _validate_strict_cross_revision_casilla_continuity(
    modelos: Iterable[ModeloDefinition],
) -> tuple[str, ...]:
    """Enforce explicit continuity decisions for opted-in declared surfaces."""
    failures: dict[tuple[str, str, str, str], list[CrossRevisionCasillaDivergence]] = defaultdict(list)
    for modelo in modelos:
        for divergence in _iter_cross_revision_casilla_divergences((modelo,)):
            if divergence.revisions_overlap:
                continue
            left_revision = modelo.revisions[divergence.left_revision_id]
            right_revision = modelo.revisions[divergence.right_revision_id]
            if (
                left_revision.continuidad_validation != "strict"
                and right_revision.continuidad_validation != "strict"
            ):
                continue
            if not _has_declared_continuity_surface(divergence):
                continue
            if divergence.evolution_covers_field:
                continue
            key = (
                divergence.modelo_id,
                divergence.casilla_id,
                divergence.left_revision_id,
                divergence.right_revision_id,
            )
            failures[key].append(divergence)
    return tuple(
        _format_strict_continuity_failure(modelo_id, casilla_id, left_revision_id, right_revision_id, divergences)
        for (
            modelo_id,
            casilla_id,
            left_revision_id,
            right_revision_id,
        ), divergences in failures.items()
    )


def _has_declared_continuity_surface(divergence: CrossRevisionCasillaDivergence) -> bool:
    # Strict continuity is intentionally scoped to authored surfaces.
    # Do not infer continuity from repeated numeric casilla ids alone.
    return (
        divergence.left_continuidad_id is not None
        or divergence.right_continuidad_id is not None
        or divergence.evolution_kind is not None
    )


def _format_strict_continuity_failure(
    modelo_id: str,
    casilla_id: str,
    left_revision_id: str,
    right_revision_id: str,
    divergences: Iterable[CrossRevisionCasillaDivergence],
) -> str:
    divergence_tuples = tuple(
        (
            item.field,
            (item.left_value, item.right_value),
            (item.left_continuidad_id, item.right_continuidad_id),
            item.evolution_kind,
        )
        for item in divergences
    )
    return (
        f"strict continuity drift: modelo {modelo_id} casilla {casilla_id!r} "
        f"revisions {left_revision_id!r}->{right_revision_id!r} "
        f"uncovered divergences {divergence_tuples!r}"
    )


def _format_cross_revision_failure(
    modelo_id: str,
    casilla_id: str,
    left_revision_id: str,
    divergences: Iterable[CrossRevisionCasillaDivergence],
) -> str:
    divergence_tuples = tuple(
        (item.right_revision_id, item.field, (item.left_value, item.right_value))
        for item in divergences
    )
    return (
        f"cross-revision drift: modelo {modelo_id} casilla "
        f"{casilla_id!r} canonical revision {left_revision_id!r} "
        f"divergences {divergence_tuples!r}"
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
                }
            )
        )
        evolution_kinds = tuple(
            sorted(
                {
                    divergence.evolution_kind
                    for divergence in divergences
                    if divergence.evolution_kind is not None
                }
            )
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
            )
        )
    return tuple(summaries)
