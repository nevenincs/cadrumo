"""Cross-revision drift validation policies for registry casillas.

Applies two policies over the divergences detected by
:mod:`aeat.domain.calculations.registry._cross_revision_divergence`: the
strict hard-fail continuity policy for overlapping revisions and declared
continuity surfaces, and the advisory non-overlapping drift summary. Both
policies operate over the casillas of each :class:`ModeloRevision`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from itertools import pairwise

from ._cross_revision_divergence import (
    CrossRevisionCasillaDivergence,
    _iter_cross_revision_casilla_divergences,
    _revisions_overlap,
)
from ._errors import RegistryValidationError
from ._schema import (
    CasillaContinuidadEvolutionDefinition,
    ModeloDefinition,
    ModeloRevision,
)
from ._validate_cross_revision_advisory import (
    CrossRevisionCasillaDriftSummary,
    summarize_non_overlapping_cross_revision_casilla_drift,
)

# D3 defines revision-level continuidad_validation = "strict" as
# surface-scoped strictness: declared continuity surfaces hard-fail drift,
# while unannotated repeated-id drift remains advisory until a separate
# corpus-wide completeness gate proves every repeated id has been reviewed.

__all__ = (
    "CrossRevisionCasillaDriftSummary",
    "summarize_non_overlapping_cross_revision_casilla_drift",
    "validate_cross_revision_casilla_consistency",
)


def validate_cross_revision_casilla_consistency(modelos: Iterable[ModeloDefinition]) -> None:
    """Raise when a repeated casilla id drifts across revisions.

    Args:
        modelos: Iterable of :class:`ModeloDefinition` entries to validate.
    """
    failures = _validate_cross_revision_casilla_consistency(modelos)
    if failures:
        raise RegistryValidationError(
            "cross-revision casilla drift detected:\n" + "\n".join(f" - {failure}" for failure in failures),
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
    semantic_failures: list[str] = []
    for modelo in modelos:
        semantic_failures.extend(_validate_strict_continuity_evolution_references(modelo))
        semantic_failures.extend(_validate_strict_retired_continuity_surfaces(modelo))
        for divergence in _iter_cross_revision_casilla_divergences((modelo,)):
            if divergence.revisions_overlap:
                continue
            left_revision = modelo.revisions[divergence.left_revision_id]
            right_revision = modelo.revisions[divergence.right_revision_id]
            if left_revision.continuidad_validation != "strict" and right_revision.continuidad_validation != "strict":
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
    drift_failures = tuple(
        _format_strict_continuity_failure(modelo_id, casilla_id, left_revision_id, right_revision_id, divergences)
        for (
            modelo_id,
            casilla_id,
            left_revision_id,
            right_revision_id,
        ), divergences in failures.items()
    )
    return (*semantic_failures, *drift_failures)


def _validate_strict_continuity_evolution_references(modelo: ModeloDefinition) -> tuple[str, ...]:
    """Validate declared strict continuity evolutions against real casilla surfaces."""
    continuidad_ids_by_revision = _continuidad_ids_by_revision(modelo)
    failures: list[str] = []
    for declaring_revision_id, evolution in _iter_declared_continuity_evolutions(modelo):
        revision_pair = _revision_pair_for_evolution(modelo, evolution)
        if revision_pair is None:
            continue
        left_revision, right_revision = revision_pair
        if not _is_strict_non_overlapping_revision_pair(left_revision, right_revision):
            continue

        left_ids = continuidad_ids_by_revision[left_revision.id]
        right_ids = continuidad_ids_by_revision[right_revision.id]
        if evolution.continuidad_id not in left_ids and evolution.continuidad_id not in right_ids:
            failures.append(
                _format_unmatched_continuity_evolution_failure(
                    modelo.id,
                    declaring_revision_id,
                    evolution,
                    "no matching casilla continuity id in either revision",
                ),
            )
            continue

        if evolution.evolution_kind != "retired":
            continue
        if evolution.continuidad_id not in left_ids:
            failures.append(
                _format_unmatched_continuity_evolution_failure(
                    modelo.id,
                    declaring_revision_id,
                    evolution,
                    "retired evolution has no source casilla continuity id",
                ),
            )
        if evolution.continuidad_id in right_ids:
            failures.append(
                _format_unmatched_continuity_evolution_failure(
                    modelo.id,
                    declaring_revision_id,
                    evolution,
                    "retired evolution target revision still declares the continuity id",
                ),
            )
    return tuple(failures)


def _validate_strict_retired_continuity_surfaces(modelo: ModeloDefinition) -> tuple[str, ...]:
    """Require retired declarations when a strict continuity chain disappears."""
    continuidad_ids_by_revision = _continuidad_ids_by_revision(modelo)
    failures: list[str] = []
    for left_revision, right_revision in _adjacent_revisions(modelo):
        if not _is_strict_non_overlapping_revision_pair(left_revision, right_revision):
            continue
        missing_ids = continuidad_ids_by_revision[left_revision.id] - continuidad_ids_by_revision[right_revision.id]
        for continuidad_id in sorted(missing_ids):
            if _has_retired_evolution(modelo, left_revision.id, right_revision.id, continuidad_id):
                continue
            failures.append(
                "strict continuity retirement missing: "
                f"modelo {modelo.id} continuidad_id {continuidad_id!r} "
                f"revisions {left_revision.id!r}->{right_revision.id!r} "
                "has a source casilla continuity surface but no target casilla "
                "and no retired evolution declaration",
            )
    return tuple(failures)


def _continuidad_ids_by_revision(modelo: ModeloDefinition) -> dict[str, set[str]]:
    return {
        revision.id: {casilla.continuidad_id for casilla in revision.casillas if casilla.continuidad_id is not None}
        for revision in modelo.revisions.values()
    }


def _iter_declared_continuity_evolutions(
    modelo: ModeloDefinition,
) -> tuple[tuple[str, CasillaContinuidadEvolutionDefinition], ...]:
    return tuple(
        (revision.id, evolution)
        for revision in modelo.revisions.values()
        for evolution in revision.casilla_continuidad_evolutions
    )


def _revision_pair_for_evolution(
    modelo: ModeloDefinition,
    evolution: CasillaContinuidadEvolutionDefinition,
) -> tuple[ModeloRevision, ModeloRevision] | None:
    left_revision = modelo.revisions.get(evolution.from_revision)
    right_revision = modelo.revisions.get(evolution.to_revision)
    if left_revision is None or right_revision is None:
        return None
    return left_revision, right_revision


def _adjacent_revisions(modelo: ModeloDefinition) -> tuple[tuple[ModeloRevision, ModeloRevision], ...]:
    ordered_revisions = tuple(
        sorted(
            modelo.revisions.values(),
            key=lambda revision: (revision.valid_from, revision.id),
        ),
    )
    return tuple(pairwise(ordered_revisions))


def _is_strict_non_overlapping_revision_pair(
    left_revision: ModeloRevision,
    right_revision: ModeloRevision,
) -> bool:
    return (
        left_revision.continuidad_validation == "strict" or right_revision.continuidad_validation == "strict"
    ) and not _revisions_overlap(left_revision, right_revision)


def _has_retired_evolution(
    modelo: ModeloDefinition,
    left_revision_id: str,
    right_revision_id: str,
    continuidad_id: str,
) -> bool:
    return any(
        evolution.continuidad_id == continuidad_id
        and evolution.from_revision == left_revision_id
        and evolution.to_revision == right_revision_id
        and evolution.evolution_kind == "retired"
        for _declaring_revision_id, evolution in _iter_declared_continuity_evolutions(modelo)
    )


def _format_unmatched_continuity_evolution_failure(
    modelo_id: str,
    declaring_revision_id: str,
    evolution: CasillaContinuidadEvolutionDefinition,
    reason: str,
) -> str:
    return (
        "strict continuity evolution mismatch: "
        f"modelo {modelo_id} declaring_revision {declaring_revision_id!r} "
        f"evolution {evolution.id!r} continuidad_id {evolution.continuidad_id!r} "
        f"revisions {evolution.from_revision!r}->{evolution.to_revision!r} "
        f"evolution_kind {evolution.evolution_kind!r}: {reason}"
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
        (item.right_revision_id, item.field, (item.left_value, item.right_value)) for item in divergences
    )
    return (
        f"cross-revision drift: modelo {modelo_id} casilla "
        f"{casilla_id!r} canonical revision {left_revision_id!r} "
        f"divergences {divergence_tuples!r}"
    )
