"""Semantic-role validation helpers for registry definitions.

Validates ``semantic_role`` consistency, cardinality, and required-role
label patterns across all casillas in every :class:`ModeloDefinition`.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping

from . import _validate_semantic_role_typos as _semantic_role_typos
from ._schema import CasillaDefinition, ModeloDefinition


class _RoleObservation:
    """One casilla's contribution to a semantic-role consistency check."""

    modelo_id: str
    revision_id: str
    casilla_id: str
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
        revision_id: str,
        casilla: CasillaDefinition,
    ) -> None:
        self.modelo_id = modelo_id
        self.revision_id = revision_id
        self.casilla_id = casilla.id
        self.data_type = casilla.data_type
        self.constraints = casilla.constraints
        self.label = casilla.label
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
                    f"declares data_type {canonical.data_type!r}"
                )
            obs_sig = _constraints_signature(obs.constraints)
            if obs_sig != canonical_constraints_sig:
                failures.append(
                    f"semantic_role {role!r}: casilla "
                    f"{obs.modelo_id}.{obs.revision_id}.{obs.casilla_id} declares "
                    f"constraints incompatible with role canonical "
                    f"{canonical.modelo_id}.{canonical.revision_id}.{canonical.casilla_id}"
                )
    return tuple(failures)


def _validate_semantic_role_cardinality(
    modelos: Iterable[ModeloDefinition],
) -> tuple[str, ...]:
    """Enforce declared cardinality policy for semantic roles.

    Most roles are expected to be shared eventually. A singleton role
    can still be legitimate when a legal form adds a new slot with no
    older sibling, but that must be declared explicitly on the casilla.
    If the role later becomes shared, the singleton marker becomes
    stale and validation fails until the marker is removed.
    """
    failures: list[str] = []
    for role, observations in _collect_role_observations(modelos).items():
        if len(observations) == 1:
            continue
        for obs in observations:
            if obs.semantic_role_cardinality != "intentional_singleton":
                continue
            failures.append(
                f"semantic_role {role!r}: casilla "
                f"{obs.modelo_id}.{obs.revision_id}.{obs.casilla_id} declares "
                "semantic_role_cardinality 'intentional_singleton' but role appears "
                f"{len(observations)} times"
            )
    return tuple(failures)


def _emit_semantic_role_typo_twin_warnings(
    modelos: Iterable[ModeloDefinition],
) -> None:
    """Warn when a ``semantic_role`` value appears on exactly one casilla."""
    _semantic_role_typos.emit_grouped_semantic_role_typo_twin_warnings(_collect_role_observations(modelos))


def _validate_semantic_role_typo_twins(
    modelos: Iterable[ModeloDefinition],
) -> tuple[str, ...]:
    """Fail when an unreviewed singleton ``semantic_role`` looks like a typo."""
    return _semantic_role_typos.grouped_semantic_role_typo_twin_failures(_collect_role_observations(modelos))


# Enforced semantic_role requirements: each entry is (label_pattern,
# expected_role). A casilla whose label matches the pattern must declare
# the expected semantic_role; missing declarations raise
# RegistryValidationError at snapshot build. The set starts conservative
# — only patterns where corpus rollout is provably complete should land
# here. Modellers extending this set must run a discovery audit first to
# confirm all in-corpus casillas already carry the role.
#
# Today's enforcement set:
# - "Ejercicio al que se refiere la declaracion" -> filing_year
#   (16 casillas covered across 13 modelos, complete rollout
#   per the role-rollout-strategy audit).
_REQUIRED_ROLE_LABEL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^Ejercicio al que se refiere la declaracion$", re.IGNORECASE), "filing_year"),
    # Exact-match "Resultado a ingresar" (not "...o a devolver" or
    # "...de autoliquidaciones anteriores"; those carry distinct
    # semantics - signed cuota vs. prior-period balance - and would
    # need their own roles).
    (re.compile(r"^Resultado a ingresar$", re.IGNORECASE), "cuota_a_ingresar"),
    # "Base imponible general" / "Base imponible imputada" - IRPF
    # base imponible across M100 revisions. 12/12 covered.
    (re.compile(r"^Base imponible (general|imputada)\s*$", re.IGNORECASE), "base_imponible_irpf"),
    # "Base imponible o importe..." / "Base imponible o importes
    # rectificados" - M349 intracomunitario amount + rectifications.
    (re.compile(r"^Base imponible o importe", re.IGNORECASE), "base_intracomunitaria"),
    # "Base imponible negativa o cero" - M200 IS carry-forward.
    (re.compile(r"^Base imponible negativa o cero", re.IGNORECASE), "base_imponible_negativa_is"),
)


def _validate_required_role_declarations(
    modelos: Iterable[ModeloDefinition],
) -> tuple[str, ...]:
    """Hard-flip: every casilla matching a required-role label pattern must declare that role.

    Each entry in :data:`_REQUIRED_ROLE_LABEL_PATTERNS` names a label
    pattern plus the canonical role expected on every matching casilla.
    A miss-declared casilla (wrong role or missing role) is a snapshot-
    build failure. Start the set narrow and widen as role rollouts
    complete.
    """
    failures: list[str] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for casilla in revision.casillas:
                for pattern, expected_role in _REQUIRED_ROLE_LABEL_PATTERNS:
                    if not pattern.match(casilla.label):
                        continue
                    if casilla.semantic_role is None:
                        failures.append(
                            f"required-role gate: casilla "
                            f"{modelo.id}.{revision.id}.{casilla.id} label "
                            f"{casilla.label!r} matches pattern {pattern.pattern!r} "
                            f"but declares no semantic_role (expected "
                            f"{expected_role!r})"
                        )
                    elif casilla.semantic_role != expected_role:
                        failures.append(
                            f"required-role gate: casilla "
                            f"{modelo.id}.{revision.id}.{casilla.id} label "
                            f"{casilla.label!r} matches pattern {pattern.pattern!r} "
                            f"but declares semantic_role "
                            f"{casilla.semantic_role!r} (expected "
                            f"{expected_role!r})"
                        )
    return tuple(failures)


def collect_casillas_by_semantic_role(
    modelos: Iterable[ModeloDefinition],
) -> Mapping[str, tuple[tuple[str, str, str], ...]]:
    """Cross-reference accessor: role -> tuple of (modelo_id, revision_id, casilla_id).

    Used by downstream consumers that need to walk every casilla
    sharing a semantic role across the corpus. The returned mapping
    is immutable and document-order stable per role; the validator
    consumes the same accessor through
    :func:`_collect_role_observations` internally.

    Args:
        modelos: Iterable of :class:`ModeloDefinition` instances to index
            by the semantic roles declared on their casillas.
    """
    grouped: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for casilla in revision.casillas:
                if casilla.semantic_role is None:
                    continue
                grouped[casilla.semantic_role].append((modelo.id, revision.id, casilla.id))
    return {role: tuple(occs) for role, occs in grouped.items()}
