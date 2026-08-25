"""Semantic-role validation helpers for registry definitions.

Validates ``semantic_role`` consistency, cardinality, and required-role
label patterns across all casillas in every :class:`ModeloDefinition`.

The required-role hard-flip gate and the public cross-reference accessor
are extracted into the sibling
:mod:`~cadrumo.domain.calculations.registry.validate_semantic_role_required`
module and re-exported here for call-site stability.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping

from ....core import CasillaId
from ....core.i18n import MissingTranslationError
from . import _validate_semantic_role_typos as _semantic_role_typos
from .ids import RevisionId
from .schema import CasillaDefinition, ModeloDefinition
from ._validate_semantic_role_required import REQUIRED_ROLE_LABEL_PATTERNS, required_role_declaration_failures
from ._validate_semantic_role_required import (
    collect_casillas_by_semantic_role as collect_casillas_by_semantic_role,
)

__all__ = (
    "REQUIRED_ROLE_LABEL_PATTERNS",
    "collect_casillas_by_semantic_role",
    "required_role_declaration_failures",
    "semantic_role_cardinality_failures",
    "semantic_role_consistency_failures",
    "semantic_role_typo_twin_failures",
)


class _RoleObservation:
    """One casilla's contribution to a semantic-role consistency check."""

    modelo_id: str
    revision_id: RevisionId
    casilla_id: CasillaId
    data_type: object
    constraints: object
    label: str
    semantic_role_cardinality: str
    semantic_role_cardinality_reason: str | None

    __slots__ = (
        "casilla_id",
        "constraints",
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


def _validate_semantic_role_consistency(
    modelos: Iterable[ModeloDefinition],
) -> tuple[str, ...]:
    """Enforce intra-role ``data_type`` and ``constraints`` consistency.

    All casillas sharing a ``semantic_role`` must declare the same
    ``data_type`` and structurally compatible ``constraints``. The
    canonical signature is the one declared by the first casilla in
    document order; subsequent divergences are reported as
    validation failures.
    """
    failures: list[str] = []
    for role, observations in _collect_role_observations(modelos).items():
        canonical = observations[0]
        canonical_constraints_sig = _constraints_signature(canonical.constraints)
        for obs in observations[1:]:
            if obs.data_type != canonical.data_type:
                failures.append(
                    f"semantic_role {role!r}: casilla "
                    f"{obs.modelo_id}.{obs.revision_id}.{obs.casilla_id} declares "
                    f"data_type {obs.data_type!r} but role canonical "
                    f"{canonical.modelo_id}.{canonical.revision_id}.{canonical.casilla_id} "
                    f"declares data_type {canonical.data_type!r}",
                )
            obs_sig = _constraints_signature(obs.constraints)
            if obs_sig != canonical_constraints_sig:
                failures.append(
                    f"semantic_role {role!r}: casilla "
                    f"{obs.modelo_id}.{obs.revision_id}.{obs.casilla_id} declares "
                    f"constraints incompatible with role canonical "
                    f"{canonical.modelo_id}.{canonical.revision_id}.{canonical.casilla_id}",
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


def _validate_semantic_role_cardinality(
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


def _validate_semantic_role_typo_twins(
    modelos: Iterable[ModeloDefinition],
) -> tuple[str, ...]:
    """Fail when an unreviewed singleton ``semantic_role`` looks like a typo."""
    return _semantic_role_typos.grouped_semantic_role_typo_twin_failures(_collect_role_observations(modelos))


semantic_role_cardinality_failures = _validate_semantic_role_cardinality
semantic_role_consistency_failures = _validate_semantic_role_consistency
semantic_role_typo_twin_failures = _validate_semantic_role_typo_twins
