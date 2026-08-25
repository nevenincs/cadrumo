"""Strict continuity-evolution declaration validation.

Validates the declaration side of strict cross-revision continuity: evolution
endpoints, duplicate ownership, and explicit retirements. Drift detection
stays in :mod:`._validate_cross_revision`, which combines these accumulated
facts with divergence evidence in its established diagnostic order.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import pairwise

from ._cross_revision_divergence import ordered_revisions, revisions_overlap
from ._ids import RevisionId
from ._schema import CasillaContinuidadEvolutionDefinition, ModeloDefinition, ModeloRevision
from ._validate_cross_revision_contiguity import strict_continuity_chain_contiguity_failures


def strict_continuity_evolution_failures(modelo: ModeloDefinition) -> tuple[str, ...]:
    """Return declaration-side strict-continuity failures for ``modelo``."""
    return (
        *_validate_strict_continuity_evolution_references(modelo),
        *_validate_strict_retired_continuity_surfaces(modelo),
        *strict_continuity_chain_contiguity_failures(modelo),
    )


def _validate_strict_continuity_evolution_references(modelo: ModeloDefinition) -> tuple[str, ...]:
    """Validate every declared continuity evolution against its real casilla surfaces.

    Declaring an evolution is an authority assertion even when either endpoint
    keeps advisory continuity validation. Strictness still governs the
    separate requirement to declare a retirement for a disappearing surface.
    """
    continuidad_ids_by_revision = _continuidad_ids_by_revision(modelo)
    failures: list[str] = []
    declared_evolutions = _iter_declared_continuity_evolutions(modelo)
    evolutions_by_boundary: dict[
        tuple[str, RevisionId, RevisionId],
        list[CasillaContinuidadEvolutionDefinition],
    ] = defaultdict(list)
    for _declaring_revision_id, evolution in declared_evolutions:
        evolutions_by_boundary[(evolution.continuidad_id, evolution.from_revision, evolution.to_revision)].append(
            evolution,
        )
    for (continuidad_id, from_revision, to_revision), evolutions in sorted(evolutions_by_boundary.items()):
        if len(evolutions) > 1:
            failures.append(
                "continuity evolution duplicate: "
                f"modelo {modelo.id} continuidad_id {continuidad_id!r} "
                f"revisions {from_revision!r}->{to_revision!r} has overlapping declarations "
                f"{tuple(sorted(evolution.id for evolution in evolutions))!r}",
            )

    for declaring_revision_id, evolution in declared_evolutions:
        revision_pair = _revision_pair_for_evolution(modelo, evolution)
        if revision_pair is None:
            failures.append(
                _format_unmatched_continuity_evolution_failure(
                    modelo.id,
                    declaring_revision_id,
                    evolution,
                    "evolution references a revision that the modelo does not declare",
                ),
            )
            continue
        left_revision, right_revision = revision_pair
        if declaring_revision_id != evolution.to_revision:
            failures.append(
                _format_unmatched_continuity_evolution_failure(
                    modelo.id,
                    declaring_revision_id,
                    evolution,
                    "evolution must be declared under its target revision",
                ),
            )

        left_ids = continuidad_ids_by_revision[left_revision.id]
        right_ids = continuidad_ids_by_revision[right_revision.id]
        source_present = evolution.continuidad_id in left_ids
        target_present = evolution.continuidad_id in right_ids
        if not source_present and not target_present:
            failures.append(
                _format_unmatched_continuity_evolution_failure(
                    modelo.id,
                    declaring_revision_id,
                    evolution,
                    "no matching casilla continuity id in either revision",
                ),
            )
            continue

        if evolution.evolution_kind == "retired":
            if not source_present:
                failures.append(
                    _format_unmatched_continuity_evolution_failure(
                        modelo.id,
                        declaring_revision_id,
                        evolution,
                        "retired evolution has no source casilla continuity id",
                    ),
                )
            if target_present:
                failures.append(
                    _format_unmatched_continuity_evolution_failure(
                        modelo.id,
                        declaring_revision_id,
                        evolution,
                        "retired evolution target revision still declares the continuity id",
                    ),
                )
            continue

        if not source_present:
            failures.append(
                _format_unmatched_continuity_evolution_failure(
                    modelo.id,
                    declaring_revision_id,
                    evolution,
                    "non-retired evolution has no source casilla continuity id",
                ),
            )
        if not target_present:
            failures.append(
                _format_unmatched_continuity_evolution_failure(
                    modelo.id,
                    declaring_revision_id,
                    evolution,
                    "non-retired evolution has no target casilla continuity id",
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
    return tuple(pairwise(ordered_revisions(modelo)))


def _is_strict_non_overlapping_revision_pair(
    left_revision: ModeloRevision,
    right_revision: ModeloRevision,
) -> bool:
    return (
        left_revision.continuidad_validation == "strict" or right_revision.continuidad_validation == "strict"
    ) and not revisions_overlap(left_revision, right_revision)


def _has_retired_evolution(
    modelo: ModeloDefinition,
    left_revision_id: RevisionId,
    right_revision_id: RevisionId,
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
    declaring_revision_id: RevisionId,
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
