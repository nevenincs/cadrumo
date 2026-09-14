"""Semantic-role validation helpers for registry definitions.

Validates ``semantic_role`` consistency, cardinality, and required-role
label patterns across all casillas in every :class:`ModeloDefinition`.

The required-role hard-flip gate and the public cross-reference accessor
are extracted into the sibling
:mod:`~cadrumo.domain.calculations.registry._validate_semantic_role_required`
module and re-exported here for call-site stability.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping

from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.i18n.render import MissingTranslationError
from cadrumo.domain.calculations.registry.casilla_lineage_totality import judging_predecessor
from cadrumo.domain.calculations.registry.ids import RevisionId
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions, revisions_coexist
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ._validate_semantic_role_required import (
    collect_casillas_by_semantic_role as collect_casillas_by_semantic_role,
)
from .validate_semantic_role_typos import grouped_semantic_role_typo_twin_failures

__all__ = [
    "semantic_role_cardinality_failures",
    "semantic_role_consistency_failures",
    "semantic_role_typo_twin_failures",
]


class _RoleObservation:
    """One casilla's contribution to a semantic-role consistency check."""

    modelo_id: str
    revision_id: RevisionId
    casilla_id: CasillaId
    continuidad_id: str | None
    data_type: object
    constraints: object
    label: str
    semantic_role_cardinality: str
    semantic_role_cardinality_reason: str | None

    __slots__ = (
        "casilla_id",
        "constraints",
        "continuidad_id",
        "data_type",
        "label",
        "modelo_id",
        "revision_id",
        "semantic_role_cardinality",
        "semantic_role_cardinality_reason",
    )

    def __init__(
        self,
        modelo_id: str,
        revision_id: RevisionId,
        casilla: CasillaDefinition,
    ) -> None:
        self.modelo_id = modelo_id
        self.revision_id = revision_id
        self.casilla_id = casilla.id
        self.continuidad_id = casilla.continuidad_id
        self.data_type = casilla.data_type
        self.constraints = casilla.constraints
        try:
            self.label = casilla.label
        except MissingTranslationError:
            # Semantic-role axes are structural. A custom registry root can be
            # checked before its shared catalogue is enrolled; label-derived
            # required-role checks handle their own missing-key boundary.
            self.label = ""
        self.semantic_role_cardinality = casilla.semantic_role_cardinality
        self.semantic_role_cardinality_reason = casilla.semantic_role_cardinality_reason


def _collect_role_observations(
    modelos: Iterable[ModeloDefinition],
) -> Mapping[str, list[_RoleObservation]]:
    """Group every casilla declaring a ``semantic_role`` by that role."""
    grouped: dict[str, list[_RoleObservation]] = defaultdict(list)
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for casilla in revision.casillas:
                if casilla.semantic_role is None:
                    continue
                grouped[casilla.semantic_role].append(_RoleObservation(modelo.id, revision.id, casilla))
    return grouped


def _constraints_signature(constraints: object) -> tuple[object, ...]:
    """Return a hashable signature for compatibility comparison."""
    if constraints is None:
        return ()
    fields = (
        "sign",
        "min_value",
        "max_value",
        "pattern",
        "min_length",
        "max_length",
        "enum",
    )
    return tuple(getattr(constraints, name) for name in fields)


def _compatible_constraints(left: _RoleObservation, right: _RoleObservation) -> bool:
    """Allow nested enum domains only between exclusive editions of one modelo."""
    lhs = _constraints_signature(left.constraints)
    rhs = _constraints_signature(right.constraints)
    if lhs == rhs:
        return True
    if left.modelo_id != right.modelo_id or left.revision_id == right.revision_id:
        return False
    if not lhs or not rhs or lhs[:-1] != rhs[:-1]:
        return False
    left_enum = getattr(left.constraints, "enum", None)
    right_enum = getattr(right.constraints, "enum", None)
    if not left_enum or not right_enum:
        return False
    return set(left_enum).issubset(right_enum) or set(right_enum).issubset(left_enum)


def _representation_evolved(
    left: _RoleObservation,
    right: _RoleObservation,
    modelos: Mapping[str, ModeloDefinition],
) -> bool:
    """Follow exact predecessor edges; every changed representation must be attested."""
    if (
        left.modelo_id != right.modelo_id
        or left.revision_id == right.revision_id
        or left.continuidad_id is None
        or left.continuidad_id != right.continuidad_id
    ):
        return False
    modelo = modelos[left.modelo_id]
    ordered = ordered_revisions(modelo)
    positions = {revision.id: index for index, revision in enumerate(ordered)}
    earlier, later = sorted((left.revision_id, right.revision_id), key=positions.__getitem__)
    if revisions_coexist(modelo.revisions[earlier], modelo.revisions[later]):
        return False
    current = modelo.revisions[later]
    while current.id != earlier:
        predecessor = judging_predecessor(modelo, ordered, positions[current.id])
        if (
            predecessor is None
            or positions[predecessor.id] < positions[earlier]
            or revisions_coexist(predecessor, current)
        ):
            return False
        previous_rows = [row for row in predecessor.casillas if row.continuidad_id == left.continuidad_id]
        current_rows = [row for row in current.casillas if row.continuidad_id == left.continuidad_id]
        if len(previous_rows) != 1 or len(current_rows) != 1:
            return False
        if previous_rows[0].semantic_role != current_rows[0].semantic_role:
            return False
        if previous_rows[0].data_type != current_rows[0].data_type and not any(
            evolution.continuidad_id == left.continuidad_id
            and evolution.evolution_kind == "representation_evolved"
            and evolution.from_revision == predecessor.id
            and evolution.to_revision == current.id
            for evolution in current.casilla_continuidad_evolutions
        ):
            return False
        current = predecessor
    return True


def semantic_role_consistency_failures(
    modelos: Iterable[ModeloDefinition],
) -> tuple[str, ...]:
    """Enforce intra-role ``data_type`` and ``constraints`` consistency.

    All casillas sharing a ``semantic_role`` must declare the same
    ``data_type`` and structurally compatible ``constraints``. The
    enum domain may expand or narrow across exclusive revisions of one modelo.
    All observation pairs must remain compatible; a common subset cannot hide
    contradictory changes in later editions.
    """
    failures: list[str] = []
    modelo_tuple = tuple(modelos)
    by_modelo = {str(modelo.id): modelo for modelo in modelo_tuple}
    for role, observations in _collect_role_observations(modelo_tuple).items():
        for index, obs in enumerate(observations[1:], start=1):
            canonical = next(
                (
                    prior
                    for prior in observations[:index]
                    if obs.data_type != prior.data_type and not _representation_evolved(prior, obs, by_modelo)
                ),
                None,
            )
            if canonical is not None:
                failures.append(
                    f"semantic_role {role!r}: casilla "
                    f"{obs.modelo_id}.{obs.revision_id}.{obs.casilla_id} declares "
                    f"data_type {obs.data_type!r} but role canonical "
                    f"{canonical.modelo_id}.{canonical.revision_id}.{canonical.casilla_id} "
                    f"declares data_type {canonical.data_type!r}",
                )
            incompatible = next(
                (prior for prior in observations[:index] if not _compatible_constraints(prior, obs)),
                None,
            )
            if incompatible is not None:
                failures.append(
                    f"semantic_role {role!r}: casilla "
                    f"{obs.modelo_id}.{obs.revision_id}.{obs.casilla_id} declares "
                    f"constraints incompatible with role observation "
                    f"{incompatible.modelo_id}.{incompatible.revision_id}.{incompatible.casilla_id}",
                )
    return tuple(failures)


def _co_applying_role_breadth(observations: Iterable[_RoleObservation]) -> tuple[int, int]:
    """Return ``(widest bearer count inside one revision, distinct modelo count)``.

    Cardinality asks whether a role is SHARED, and sharing only means something
    between casillas that can appear in the same filing. AEAT binds every
    ``(modelo, filing_year, period)`` to exactly one revision by publishing
    orden, and the non-overlap window gate makes that resolution unique, so two
    revisions of one modelo are mutually exclusive by law and no filing ever
    sees both.

    Counting raw observations therefore measures the wrong denominator: it
    cannot separate a role duplicated inside one filing context -- the real
    defect this axis exists to catch -- from a role carried by two revisions
    that can never co-apply, which is the unavoidable consequence of splitting
    a revision at an AEAT design re-layout. Splitting clones every casilla, so
    a raw count turns correct authoring into a validation failure, and the cost
    grows with every further split rather than being paid once.
    """
    per_revision: dict[tuple[str, str], int] = defaultdict(int)
    modelo_ids: set[str] = set()
    for obs in observations:
        per_revision[(obs.modelo_id, obs.revision_id)] += 1
        modelo_ids.add(obs.modelo_id)
    return max(per_revision.values(), default=0), len(modelo_ids)


def semantic_role_cardinality_failures(
    modelos: Iterable[ModeloDefinition],
) -> tuple[str, ...]:
    """Enforce declared cardinality policy for semantic roles.

    Most roles are expected to be shared eventually. A singleton role
    can still be legitimate when a legal form adds a new slot with no
    older sibling, but that must be declared explicitly on the casilla.
    If the role later becomes shared, the singleton marker becomes
    stale and validation fails until the marker is removed.

    "Shared" is judged over casillas that can CO-APPLY: more than one bearer
    inside a single revision, or bearers in more than one modelo. A marker is
    not stale merely because a revision was split at a design re-layout, which
    clones every casilla into a sibling revision no filing can also select --
    see :func:`_co_applying_role_breadth`.
    """
    failures: list[str] = []
    for role, observations in _collect_role_observations(modelos).items():
        widest_in_one_revision, distinct_modelos = _co_applying_role_breadth(observations)
        if widest_in_one_revision <= 1 and distinct_modelos <= 1:
            continue
        for obs in observations:
            if obs.semantic_role_cardinality != "intentional_singleton":
                continue
            failures.append(
                f"semantic_role {role!r}: casilla "
                f"{obs.modelo_id}.{obs.revision_id}.{obs.casilla_id} declares "
                "semantic_role_cardinality 'intentional_singleton' but role is shared by "
                f"co-applying casillas ({widest_in_one_revision} in one revision, "
                f"{distinct_modelos} modelo(s))",
            )
    return tuple(failures)


def semantic_role_typo_twin_failures(
    modelos: Iterable[ModeloDefinition],
) -> tuple[str, ...]:
    """Fail when an unreviewed singleton ``semantic_role`` looks like a typo."""
    modelo_tuple = tuple(modelos)
    return grouped_semantic_role_typo_twin_failures(
        _collect_role_observations(modelo_tuple),
        known_modelo_codes=frozenset(str(modelo.id) for modelo in modelo_tuple),
    )
