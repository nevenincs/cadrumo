"""Cross-revision drift validation policies for registry casillas.

Applies two policies over the divergences detected by
:mod:`cadrumo.domain.calculations.registry.cross_revision_divergence`: the
strict hard-fail continuity policy for overlapping revisions and declared
continuity surfaces, and the advisory non-overlapping drift summary. Both
policies operate over the casillas of each :class:`ModeloRevision`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from itertools import combinations

from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.i18n.render import MissingTranslationError
from cadrumo.domain.calculations.registry.cross_revision_divergence import (
    CrossRevisionCasillaDivergence,
    iter_cross_revision_casilla_divergences,
)
from cadrumo.domain.calculations.registry.ids import RevisionId
from cadrumo.domain.calculations.registry.revision_order import revisions_coexist
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from .validate_cross_revision_evolution import strict_continuity_evolution_failures
from .validate_cross_revision_lineage_origin import role_exempt_occurrences

# D3 defines revision-level continuidad_validation = "strict" as
# surface-scoped strictness: declared continuity surfaces hard-fail drift,
# while unannotated repeated-id drift remains advisory until a separate
# corpus-wide completeness gate proves every repeated id has been reviewed.

__all__ = [
    "cross_revision_casilla_consistency_failures",
    "declared_cross_revision_continuity_semantic_linkage_failures",
    "strict_cross_revision_casilla_continuity_failures",
]

type _ContinuityOccurrence = tuple[ModeloRevision, CasillaDefinition]
type _CoverageNode = tuple[RevisionId, CasillaId]
type _CoverageKey = tuple[str, str]

_UNRESOLVED_LOCALIZATION = "<unresolved-localization>"


def declared_cross_revision_continuity_semantic_linkage_failures(
    modelos: Iterable[ModeloDefinition],
) -> tuple[str, ...]:
    """Report semantic-linkage gaps on chains that cross a real revision boundary.

    The registry records an id as a continuity assertion, not as a label
    heuristic. This audit consequently requires a semantic role for every
    casilla on a chain that appears in two non-overlapping revisions, unless
    every lineage link that casilla takes part in is grounded in cited
    evidence: a matching role is the weaker proof of the same link. A seeded
    or unmarked link never lifts the requirement. It only derives the id from
    the role when that role is unique throughout that chain; changed or
    ambiguous roles remain evidence questions rather than being silently
    renamed.
    """
    failures: list[str] = []
    for modelo in modelos:
        grounded = role_exempt_occurrences(modelo)
        for continuidad_id, occurrences in sorted(_continuity_occurrences(modelo).items()):
            failures.extend(_semantic_linkage_failures(modelo, continuidad_id, occurrences, grounded))
    return tuple(failures)


def _continuity_occurrences(modelo: ModeloDefinition) -> dict[str, list[_ContinuityOccurrence]]:
    """Group stamped casillas by their declared continuity id."""
    occurrences: dict[str, list[_ContinuityOccurrence]] = defaultdict(list)
    for revision in modelo.revisions.values():
        for casilla in revision.casillas:
            continuidad_id = casilla.continuidad_id
            if continuidad_id is not None:
                occurrences[continuidad_id].append((revision, casilla))
    return occurrences


def _semantic_linkage_failures(
    modelo: ModeloDefinition,
    continuidad_id: str,
    occurrences: list[_ContinuityOccurrence],
    grounded: frozenset[tuple[RevisionId, CasillaId]],
) -> tuple[str, ...]:
    """Return semantic-linkage failures for one declared continuity chain."""
    chain_revisions = _chain_revision_ids(occurrences)
    if not _crosses_revision_boundary(modelo, chain_revisions):
        return ()

    missing_roles = _missing_semantic_role_failures(modelo, continuidad_id, occurrences, grounded)
    if missing_roles:
        return missing_roles

    semantic_role = _unique_semantic_role(occurrences)
    if semantic_role is None or not _role_is_unique_in_revisions(modelo, chain_revisions, semantic_role):
        return ()

    expected_continuidad_id = semantic_role.lower().replace("_", "-")
    if continuidad_id == expected_continuidad_id:
        return ()
    return (
        "cross-revision continuity semantic linkage mismatch: "
        f"modelo {modelo.id} role-unique continuity chain {continuidad_id!r} "
        f"must equal semantic-role-derived id {expected_continuidad_id!r}",
    )


def _chain_revision_ids(occurrences: Iterable[_ContinuityOccurrence]) -> tuple[RevisionId, ...]:
    """Return the first-seen revision ids represented in one continuity chain."""
    return tuple(dict.fromkeys(revision.id for revision, _casilla in occurrences))


def _crosses_revision_boundary(modelo: ModeloDefinition, revision_ids: tuple[RevisionId, ...]) -> bool:
    """Return whether any pair of chain revisions cannot both be in force at once.

    A boundary is real only when the pair does not coexist: sharing a period
    vocabulary across successive editions whose windows merely meet is a
    temporal succession, not a simultaneity.
    """
    return any(
        not revisions_coexist(modelo.revisions[left_revision_id], modelo.revisions[right_revision_id])
        for left_revision_id, right_revision_id in combinations(revision_ids, 2)
    )


def _missing_semantic_role_failures(
    modelo: ModeloDefinition,
    continuidad_id: str,
    occurrences: Iterable[_ContinuityOccurrence],
    grounded: frozenset[tuple[RevisionId, CasillaId]],
) -> tuple[str, ...]:
    """Format every occurrence that lacks the semantic role required by a chain."""
    return tuple(
        "cross-revision continuity semantic linkage missing: "
        f"modelo {modelo.id} continuidad_id {continuidad_id!r} "
        f"revision {revision.id!r} casilla {casilla.id!r} has no semantic_role"
        for revision, casilla in occurrences
        if casilla.semantic_role is None and (revision.id, casilla.id) not in grounded
    )


def _unique_semantic_role(occurrences: Iterable[_ContinuityOccurrence]) -> str | None:
    """Return the chain role when all occurrences carry the same role."""
    semantic_roles = {casilla.semantic_role for _revision, casilla in occurrences if casilla.semantic_role is not None}
    if len(semantic_roles) != 1:
        return None
    return semantic_roles.pop()


def _role_is_unique_in_revisions(
    modelo: ModeloDefinition,
    revision_ids: Iterable[RevisionId],
    semantic_role: str,
) -> bool:
    """Return whether a role occurs exactly once in every chain revision."""
    return all(
        sum(casilla.semantic_role == semantic_role for casilla in modelo.revisions[revision_id].casillas) == 1
        for revision_id in revision_ids
    )


def cross_revision_casilla_consistency_failures(
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
    modelo_by_id = {modelo.id: modelo for modelo in modelos}
    failures: dict[tuple[str, CasillaId, str, str], list[CrossRevisionCasillaDivergence]] = defaultdict(list)
    for divergence in iter_cross_revision_casilla_divergences(modelo_by_id.values()):
        modelo = modelo_by_id[divergence.modelo_id]
        left_revision = modelo.revisions[divergence.left_revision_id]
        right_revision = modelo.revisions[divergence.right_revision_id]
        if not revisions_coexist(left_revision, right_revision):
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


def strict_cross_revision_casilla_continuity_failures(
    modelos: Iterable[ModeloDefinition],
) -> tuple[str, ...]:
    """Enforce explicit continuity decisions for opted-in declared surfaces."""
    failures: dict[tuple[str, CasillaId, str, str], list[CrossRevisionCasillaDivergence]] = defaultdict(list)
    semantic_failures: list[str] = []
    for modelo in modelos:
        transitive_coverage: dict[_CoverageKey, dict[_CoverageNode, int]] = {}
        semantic_failures.extend(strict_continuity_evolution_failures(modelo))
        for divergence in iter_cross_revision_casilla_divergences((modelo,)):
            left_revision = modelo.revisions[divergence.left_revision_id]
            right_revision = modelo.revisions[divergence.right_revision_id]
            if revisions_coexist(left_revision, right_revision):
                continue
            if left_revision.continuidad_validation != "strict" and right_revision.continuidad_validation != "strict":
                continue
            if not _has_declared_continuity_surface(divergence):
                continue
            if divergence.evolution_covers_field or _transitive_evolution_covers_field(
                modelo,
                divergence,
                cache=transitive_coverage,
            ):
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


def _transitive_evolution_covers_field(
    modelo: ModeloDefinition,
    divergence: CrossRevisionCasillaDivergence,
    *,
    cache: dict[_CoverageKey, dict[_CoverageNode, int]],
) -> bool:
    """Return whether an evolution path proves a non-adjacent field change.

    An adjacent evolution is evidence for every earlier occurrence whose field
    value reaches that boundary unchanged.  Requiring an otherwise redundant
    declaration for every pair of revisions makes the all-pairs drift detector
    disagree with the edge-local evolution and edition-inheritance contracts.
    The path remains field-specific: equal values form implicit edges, while a
    changed value forms an edge only when an authored evolution covers it.
    """
    continuidad_id = divergence.left_continuidad_id
    if continuidad_id is None or divergence.right_continuidad_id != continuidad_id:
        return False
    key = (continuidad_id, divergence.field)
    components = cache.get(key)
    if components is None:
        components = _field_coverage_components(modelo, continuidad_id, divergence.field)
        cache[key] = components
    left = (divergence.left_revision_id, divergence.casilla_id)
    right = (divergence.right_revision_id, divergence.casilla_id)
    return left in components and right in components and components[left] == components[right]


def _field_coverage_components(
    modelo: ModeloDefinition,
    continuidad_id: str,
    field: str,
) -> dict[_CoverageNode, int]:
    occurrences = tuple(
        ((revision.id, casilla.id), casilla)
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
        if casilla.continuidad_id == continuidad_id
    )
    neighbours: dict[_CoverageNode, set[_CoverageNode]] = {node: set() for node, _casilla in occurrences}
    for index, (left_node, left_casilla) in enumerate(occurrences[:-1]):
        left_value = _continuity_field_value(left_casilla, field)
        for right_node, right_casilla in occurrences[index + 1 :]:
            if left_value == _continuity_field_value(right_casilla, field):
                _connect_coverage_nodes(neighbours, left_node, right_node)

    nodes_by_revision: dict[RevisionId, tuple[_CoverageNode, ...]] = defaultdict(tuple)
    for node, _casilla in occurrences:
        nodes_by_revision[node[0]] = (*nodes_by_revision[node[0]], node)
    for revision in modelo.revisions.values():
        for evolution in revision.casilla_continuidad_evolutions:
            if evolution.continuidad_id != continuidad_id or field not in evolution.evolution_kind.covered_fields:
                continue
            for left_node in nodes_by_revision[evolution.from_revision]:
                for right_node in nodes_by_revision[evolution.to_revision]:
                    _connect_coverage_nodes(neighbours, left_node, right_node)
    return _connected_component_index(neighbours)


def _continuity_field_value(casilla: CasillaDefinition, field: str) -> object:
    try:
        return getattr(casilla, field)
    except MissingTranslationError:
        return _UNRESOLVED_LOCALIZATION


def _connect_coverage_nodes(
    neighbours: dict[_CoverageNode, set[_CoverageNode]],
    left: _CoverageNode,
    right: _CoverageNode,
) -> None:
    neighbours[left].add(right)
    neighbours[right].add(left)


def _connected_component_index(neighbours: dict[_CoverageNode, set[_CoverageNode]]) -> dict[_CoverageNode, int]:
    components: dict[_CoverageNode, int] = {}
    for node in neighbours:
        if node in components:
            continue
        component = len(components)
        pending = [node]
        while pending:
            candidate = pending.pop()
            if candidate in components:
                continue
            components[candidate] = component
            pending.extend(neighbours[candidate] - components.keys())
    return components


def _has_declared_continuity_surface(divergence: CrossRevisionCasillaDivergence) -> bool:
    # Strict continuity is intentionally scoped to authored surfaces.
    # One annotated endpoint starts or ends a chain; it does not prove that an
    # unannotated row with the same numeric casilla id belongs to that chain.
    # An evolution concerns the continuity id wherever it occurs in each
    # revision, which may be a renumbered row; it cannot turn an unrelated reuse
    # of the old numeric id into a continuity surface. Only the shared chain id
    # establishes that the two compared rows are the same declared concept.
    return divergence.left_continuidad_id is not None and (
        divergence.left_continuidad_id == divergence.right_continuidad_id
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
