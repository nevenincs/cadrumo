"""Cross-revision drift validation policies for registry casillas.

Applies two policies over the divergences detected by
:mod:`cadrumo.domain.calculations.registry._cross_revision_divergence`: the
strict hard-fail continuity policy for overlapping revisions and declared
continuity surfaces, and the advisory non-overlapping drift summary. Both
policies operate over the casillas of each :class:`ModeloRevision`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from ....core.casilla_id import CasillaId
from ._cross_revision_divergence import (
    CrossRevisionCasillaDivergence,
    iter_cross_revision_casilla_divergences,
    revisions_overlap,
)
from ._validate_cross_revision_evolution import strict_continuity_evolution_failures
from .errors import RegistryValidationError
from .ids import RevisionId
from .schema import ModeloDefinition, ModeloRevision
from .schema_surfaces import CasillaDefinition

# D3 defines revision-level continuidad_validation = "strict" as
# surface-scoped strictness: declared continuity surfaces hard-fail drift,
# while unannotated repeated-id drift remains advisory until a separate
# corpus-wide completeness gate proves every repeated id has been reviewed.

__all__ = [
    "declared_cross_revision_continuity_semantic_linkage_failures",
    "validate_cross_revision_casilla_consistency",
]


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


def declared_cross_revision_continuity_semantic_linkage_failures(
    modelos: Iterable[ModeloDefinition],
) -> tuple[str, ...]:
    """Report semantic-linkage gaps on chains that cross a real revision boundary.

    The registry records an id as a continuity assertion, not as a label
    heuristic. This audit consequently requires a semantic role for every
    casilla on a chain that appears in two non-overlapping revisions. It only
    derives the id from the role when that role is unique throughout that
    chain; changed or ambiguous roles remain evidence questions rather than
    being silently renamed.
    """
    failures: list[str] = []
    for modelo in modelos:
        casillas_by_continuidad_id: dict[str, list[tuple[ModeloRevision, CasillaDefinition]]] = defaultdict(list)
        for revision in modelo.revisions.values():
            for casilla in revision.casillas:
                if casilla.continuidad_id is not None:
                    casillas_by_continuidad_id[casilla.continuidad_id].append((revision, casilla))

        for continuidad_id, occurrences in sorted(casillas_by_continuidad_id.items()):
            chain_revisions = tuple(dict.fromkeys(revision.id for revision, _casilla in occurrences))
            if not any(
                not revisions_overlap(modelo.revisions[left_revision_id], modelo.revisions[right_revision_id])
                for index, left_revision_id in enumerate(chain_revisions)
                for right_revision_id in chain_revisions[index + 1 :]
            ):
                continue

            missing_roles = [(revision, casilla) for revision, casilla in occurrences if casilla.semantic_role is None]
            for revision, casilla in missing_roles:
                failures.append(
                    "cross-revision continuity semantic linkage missing: "
                    f"modelo {modelo.id} continuidad_id {continuidad_id!r} "
                    f"revision {revision.id!r} casilla {casilla.id!r} has no semantic_role",
                )
            if missing_roles:
                continue

            # Only non-None roles enter the set: the loop above already
            # `continue`d past any chain carrying a missing one, so the filter
            # narrows the type without changing which chains are considered.
            semantic_roles = {
                casilla.semantic_role for _revision, casilla in occurrences if casilla.semantic_role is not None
            }
            if len(semantic_roles) != 1:
                continue
            semantic_role = semantic_roles.pop()
            if any(
                sum(casilla.semantic_role == semantic_role for casilla in revision.casillas) != 1
                for revision_id in chain_revisions
                for revision in (modelo.revisions[revision_id],)
            ):
                continue

            expected_continuidad_id = semantic_role.lower().replace("_", "-")
            if continuidad_id != expected_continuidad_id:
                failures.append(
                    "cross-revision continuity semantic linkage mismatch: "
                    f"modelo {modelo.id} role-unique continuity chain {continuidad_id!r} "
                    f"must equal semantic-role-derived id {expected_continuidad_id!r}",
                )
    return tuple(failures)


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
    failures: dict[tuple[str, CasillaId, str, str], list[CrossRevisionCasillaDivergence]] = defaultdict(list)
    for divergence in iter_cross_revision_casilla_divergences(modelos):
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
    failures: dict[tuple[str, CasillaId, str, str], list[CrossRevisionCasillaDivergence]] = defaultdict(list)
    semantic_failures: list[str] = []
    for modelo in modelos:
        semantic_failures.extend(strict_continuity_evolution_failures(modelo))
        for divergence in iter_cross_revision_casilla_divergences((modelo,)):
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
    casilla_id: CasillaId,
    left_revision_id: RevisionId,
    right_revision_id: RevisionId,
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
    casilla_id: CasillaId,
    left_revision_id: RevisionId,
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


cross_revision_casilla_consistency_failures = _validate_cross_revision_casilla_consistency
strict_cross_revision_casilla_continuity_failures = _validate_strict_cross_revision_casilla_continuity
