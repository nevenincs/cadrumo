"""Semantic-role validation helpers for registry definitions."""

from __future__ import annotations

import re
import warnings
from collections import defaultdict
from collections.abc import Iterable, Mapping
from difflib import SequenceMatcher
from typing import NamedTuple

from ._schema import CasillaDefinition, ModeloDefinition


class _RoleObservation:
    """One casilla's contribution to a semantic-role consistency check."""

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
                grouped[casilla.semantic_role].append(
                    _RoleObservation(modelo.id, revision.id, casilla)
                )
    return grouped


def _constraints_signature(constraints: object) -> tuple[object, ...]:
    """Return a hashable signature for compatibility comparison."""

    if constraints is None:
        return ()
    fields = (
        "sign", "min_value", "max_value",
        "pattern", "min_length", "max_length", "enum",
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
    """Warn when a ``semantic_role`` value appears on exactly one casilla.

    Inline role declaration loses the central-catalogue typo-detection
    guarantee that a closed enumeration would provide. Single-occurrence
    role values are most often spelling typos (``taxpayer_nif`` vs
    ``taxpayer-nif``); this surface flags them without blocking
    snapshot load.
    """

    grouped = _collect_role_observations(modelos)
    typo_index = _build_semantic_role_typo_index(grouped.keys())
    for role, observations in grouped.items():
        if len(observations) != 1:
            continue
        obs = observations[0]
        if obs.semantic_role_cardinality == "intentional_singleton":
            continue
        if not _semantic_role_looks_like_typo(role, typo_index):
            continue
        warnings.warn(
            f"semantic_role {role!r} appears on exactly one casilla "
            f"({obs.modelo_id}.{obs.revision_id}.{obs.casilla_id}); "
            "likely typo or missing role declarations on sibling casillas",
            stacklevel=2,
        )


class _SemanticRoleTypoIndex(NamedTuple):
    normalised: Mapping[str, tuple[str, ...]]
    by_length: Mapping[int, tuple[str, ...]]
    lengths: tuple[int, ...]


_SEMANTIC_ROLE_TYPO_RATIO = 0.92


def _build_semantic_role_typo_index(known_roles: Iterable[str]) -> _SemanticRoleTypoIndex:
    normalised: dict[str, list[str]] = defaultdict(list)
    by_length: dict[int, list[str]] = defaultdict(list)
    for known in known_roles:
        normalised[known.replace("-", "_")].append(known)
        by_length[len(known)].append(known)
    return _SemanticRoleTypoIndex(
        normalised={key: tuple(values) for key, values in normalised.items()},
        by_length={key: tuple(values) for key, values in by_length.items()},
        lengths=tuple(sorted(by_length)),
    )


def _semantic_role_looks_like_typo(role: str, index: _SemanticRoleTypoIndex) -> bool:
    if "-" in role:
        return True
    normalised = role.replace("-", "_")
    for known in index.normalised.get(normalised, ()):
        if known == role:
            continue
        return True

    matcher = SequenceMatcher()
    matcher.set_seq1(role)
    role_length = len(role)
    for known_length in index.lengths:
        if _max_sequence_match_ratio(role_length, known_length) < _SEMANTIC_ROLE_TYPO_RATIO:
            continue
        for known in index.by_length[known_length]:
            if known == role:
                continue
            if _semantic_roles_are_tax_domain_siblings(role, known):
                continue
            if _semantic_roles_are_axis_siblings(role, known):
                continue
            matcher.set_seq2(known)
            if matcher.real_quick_ratio() < _SEMANTIC_ROLE_TYPO_RATIO:
                continue
            if matcher.quick_ratio() < _SEMANTIC_ROLE_TYPO_RATIO:
                continue
            if matcher.ratio() >= _SEMANTIC_ROLE_TYPO_RATIO:
                return True
    return False


def _max_sequence_match_ratio(left_length: int, right_length: int) -> float:
    if left_length == 0 and right_length == 0:
        return 1.0
    return (2 * min(left_length, right_length)) / (left_length + right_length)


def _semantic_roles_are_tax_domain_siblings(left: str, right: str) -> bool:
    domain_suffixes = {"irpf", "is", "iva"}
    left_parts = left.split("_")
    right_parts = right.split("_")
    return (
        len(left_parts) > 1
        and len(right_parts) > 1
        and left_parts[:-1] == right_parts[:-1]
        and left_parts[-1] in domain_suffixes
        and right_parts[-1] in domain_suffixes
    )


_SEMANTIC_ROLE_AXIS_SUFFIXES: tuple[tuple[str, ...], ...] = (
    ("permanente", "aumento"),
    ("permanente", "disminucion"),
    ("temporaria", "ejercicio", "aumento"),
    ("temporaria", "ejercicio", "disminucion"),
    ("temporaria", "anteriores", "aumento"),
    ("temporaria", "anteriores", "disminucion"),
    ("saldo", "inicial"),
    ("saldo", "final"),
    ("saldo", "inicial", "aumento"),
    ("saldo", "final", "aumento"),
)


def _semantic_roles_are_axis_siblings(left: str, right: str) -> bool:
    left_stem, left_axis = _split_semantic_role_axis_suffix(left)
    right_stem, right_axis = _split_semantic_role_axis_suffix(right)
    if (
        left_stem is not None
        and right_stem is not None
        and left_stem == right_stem
        and left_axis != right_axis
    ):
        return True
    if _semantic_roles_are_anexo_c_carryforward_siblings(left, right):
        return True
    if _semantic_roles_are_deferred_imputation_slot_siblings(left, right):
        return True
    if _semantic_roles_are_family_local_generated_pending_siblings(left, right):
        return True
    return _semantic_roles_are_axis_token_siblings(left, right)


def _split_semantic_role_axis_suffix(role: str) -> tuple[tuple[str, ...] | None, tuple[str, ...] | None]:
    parts = tuple(role.split("_"))
    for suffix in _SEMANTIC_ROLE_AXIS_SUFFIXES:
        if len(parts) <= len(suffix):
            continue
        if parts[-len(suffix):] == suffix:
            return parts[: -len(suffix)], suffix
    return None, None


_SEMANTIC_ROLE_AXIS_TOKEN_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"clave", "subclave"}),
    frozenset({"count", "amount"}),
    frozenset({"anteriores", "posteriores"}),
    frozenset({"interna", "internacional"}),
    frozenset({"i", "ii", "iii", "iv"}),
    frozenset({"detalle", "otras"}),
    frozenset({"ascendiente", "descendiente"}),
    frozenset({"nacimiento", "fallecimiento"}),
    frozenset({"periodo", "aplicado"}),
    frozenset({"transmision", "adquisicion"}),
    frozenset({"ab", "c"}),
)

_SEMANTIC_ROLE_OPTIONAL_AXIS_TOKENS: frozenset[str] = frozenset(
    {"agr", "pub", "aav", "b", "anio", "precio"}
)


def _semantic_roles_are_axis_token_siblings(left: str, right: str) -> bool:
    left_parts = tuple(left.split("_"))
    right_parts = tuple(right.split("_"))
    if len(left_parts) == len(right_parts):
        differing = [
            (left_part, right_part)
            for left_part, right_part in zip(left_parts, right_parts, strict=True)
            if left_part != right_part
        ]
        if len(differing) == 1 and _semantic_role_tokens_share_axis(*differing[0]):
            return True
        if differing and all(left.isdigit() and right.isdigit() for left, right in differing):
            return True

    return _semantic_role_optional_axis_token_siblings(left_parts, right_parts)


def _semantic_role_tokens_share_axis(left: str, right: str) -> bool:
    return any(left in group and right in group for group in _SEMANTIC_ROLE_AXIS_TOKEN_GROUPS)


def _semantic_role_optional_axis_token_siblings(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    left_stripped = _strip_semantic_role_optional_axis_tokens(left)
    right_stripped = _strip_semantic_role_optional_axis_tokens(right)
    return left_stripped == right_stripped and (left_stripped != left or right_stripped != right)


def _strip_semantic_role_optional_axis_tokens(parts: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        part
        for part in parts
        if part not in _SEMANTIC_ROLE_OPTIONAL_AXIS_TOKENS and not part.isdigit()
    )


_ANEXO_C_CARRYFORWARD_STATE_SUFFIXES: tuple[tuple[str, ...], ...] = (
    ("pendiente", "inicio"),
    ("pendiente", "fin"),
    ("aplicado",),
    ("generado",),
)

_ANEXO_C_CARRYFORWARD_BASKETS: frozenset[tuple[str, ...]] = frozenset(
    {
        ("saldo", "neg", "gyp", "general"),
        ("saldo", "neg", "gyp", "ahorro"),
        ("rdto", "cm", "negativo"),
        ("exceso", "sps", "rt"),
        ("exceso", "scd"),
        ("exceso", "sps", "disc", "propias"),
        ("exceso", "sps", "disc", "parientes"),
        ("exceso", "patrim", "protegido"),
        ("exceso", "deportistas"),
        ("base", "liq", "neg"),
        ("exceso", "eeficiencia"),
    }
)


def _semantic_roles_are_anexo_c_carryforward_siblings(left: str, right: str) -> bool:
    left_stem = _normalise_anexo_c_carryforward_role(left)
    right_stem = _normalise_anexo_c_carryforward_role(right)
    return left_stem is not None and left_stem == right_stem and left != right


def _normalise_anexo_c_carryforward_role(role: str) -> tuple[str, ...] | None:
    parts = tuple(role.split("_"))
    if len(parts) < 5 or parts[:3] != ("irpf", "anexo", "c"):
        return None
    for suffix in _ANEXO_C_CARRYFORWARD_STATE_SUFFIXES:
        if len(parts) <= len(suffix):
            continue
        if parts[-len(suffix):] != suffix:
            continue
        basket = parts[3 : -len(suffix)]
        if basket in _ANEXO_C_CARRYFORWARD_BASKETS:
            return parts[: -len(suffix)]
    return None


_DEFERRED_IMPUTATION_BRANCH_PREFIXES: frozenset[tuple[str, ...]] = frozenset(
    {
        ("irpf", "ganancia", "otros"),
        ("irpf", "perdida", "otros"),
        ("irpf", "ganancia", "cripto"),
        ("irpf", "perdida", "cripto"),
        ("irpf", "ganancia", "inmueble"),
        ("irpf", "perdida", "inmueble"),
    }
)

_DEFERRED_IMPUTATION_FIELD_SUFFIXES: frozenset[tuple[str, ...]] = frozenset(
    {
        ("anio", "imputacion"),
        ("importe", "percibir"),
        ("ganancia", "pendiente"),
        ("pendiente",),
    }
)


def _semantic_roles_are_deferred_imputation_slot_siblings(left: str, right: str) -> bool:
    left_stem = _normalise_deferred_imputation_slot_role(left)
    right_stem = _normalise_deferred_imputation_slot_role(right)
    return left_stem is not None and left_stem == right_stem and left != right


def _normalise_deferred_imputation_slot_role(role: str) -> tuple[str, ...] | None:
    parts = tuple(role.split("_"))
    if len(parts) < 4 or parts[:3] not in _DEFERRED_IMPUTATION_BRANCH_PREFIXES:
        return None
    normalised = parts
    if normalised[-1].isdigit() or normalised[-1] == "resto":
        normalised = normalised[:-1]
    if len(normalised) >= 5 and normalised[-2:] == ("pendiente", "imputacion"):
        normalised = normalised[:-1]
    return normalised if normalised[3:] in _DEFERRED_IMPUTATION_FIELD_SUFFIXES else None


_FAMILY_LOCAL_GENERATED_PENDING_BASES: frozenset[tuple[str, ...]] = frozenset(
    {
        ("irpf", "deduccion", "c", "valenciana", "autoconsumo"),
        ("irpf", "deduccion", "murcia", "infraestructuras"),
        ("irpf", "deduccion", "madrid", "nuevos", "contribuyentes"),
    }
)

_FAMILY_LOCAL_GENERATED_PENDING_SUFFIXES: tuple[tuple[str, ...], ...] = (
    ("generado",),
    ("pendiente",),
    ("2025", "generado"),
    ("2025", "pendiente"),
    ("2024", "pendiente"),
)


def _semantic_roles_are_family_local_generated_pending_siblings(left: str, right: str) -> bool:
    left_base = _normalise_family_local_generated_pending_role(left)
    right_base = _normalise_family_local_generated_pending_role(right)
    return left_base is not None and left_base == right_base and left != right


def _normalise_family_local_generated_pending_role(role: str) -> tuple[str, ...] | None:
    parts = tuple(role.split("_"))
    for suffix in _FAMILY_LOCAL_GENERATED_PENDING_SUFFIXES:
        if len(parts) <= len(suffix):
            continue
        if parts[-len(suffix):] != suffix:
            continue
        base = parts[: -len(suffix)]
        if base in _FAMILY_LOCAL_GENERATED_PENDING_BASES:
            return base
    return None


# Plan C W05 validator hard-flip surface (semantic_role requirement).
#
# Each entry is (label_pattern, expected_role). A casilla whose label
# matches the pattern must declare the expected semantic_role; missing
# declarations raise RegistryValidationError at snapshot build. The set
# starts conservative - only patterns where corpus rollout is provably
# complete should land here. Modellers extending this set must run a
# discovery audit first to confirm all in-corpus casillas already carry
# the role.
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
    """

    grouped: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for casilla in revision.casillas:
                if casilla.semantic_role is None:
                    continue
                grouped[casilla.semantic_role].append(
                    (modelo.id, revision.id, casilla.id)
                )
    return {role: tuple(occs) for role, occs in grouped.items()}
