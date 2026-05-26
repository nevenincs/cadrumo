"""Semantic-role typo warning helpers."""

from __future__ import annotations

import warnings
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from difflib import SequenceMatcher
from typing import NamedTuple, Protocol


class _RoleObservationLike(Protocol):
    modelo_id: str
    revision_id: str
    casilla_id: str
    semantic_role_cardinality: str


def emit_grouped_semantic_role_typo_twin_warnings(
    grouped: Mapping[str, Sequence[_RoleObservationLike]],
) -> None:
    """Warn when a ``semantic_role`` value appears on exactly one casilla."""

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
    if _semantic_roles_are_legal_reference_siblings(left, right):
        return True
    if _semantic_roles_are_ccaa_siblings(left, right):
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
    {"sin", "agr", "pub", "coti", "aav", "b", "anio", "precio"}
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


_SEMANTIC_ROLE_CCAA_TOKENS: frozenset[str] = frozenset(
    {
        "andalucia",
        "aragon",
        "asturias",
        "baleares",
        "canarias",
        "cantabria",
        "galicia",
        "madrid",
        "murcia",
    }
)


def _semantic_roles_are_ccaa_siblings(left: str, right: str) -> bool:
    left_parts = tuple(left.split("_"))
    right_parts = tuple(right.split("_"))
    left_normalised = _normalise_semantic_role_ccaa_tokens(left_parts)
    right_normalised = _normalise_semantic_role_ccaa_tokens(right_parts)
    return (
        left_normalised == right_normalised
        and (left_normalised != left_parts or right_normalised != right_parts)
        and left_parts != right_parts
    )


def _normalise_semantic_role_ccaa_tokens(parts: tuple[str, ...]) -> tuple[str, ...]:
    normalised: list[str] = []
    index = 0
    while index < len(parts):
        part = parts[index]
        if part == "c" and index + 1 < len(parts) and parts[index + 1] == "valenciana":
            normalised.append("ccaa")
            index += 2
            continue
        if part == "la" and index + 1 < len(parts) and parts[index + 1] == "rioja":
            normalised.append("ccaa")
            index += 2
            continue
        if part in _SEMANTIC_ROLE_CCAA_TOKENS:
            normalised.append("ccaa")
            index += 1
            continue
        normalised.append(part)
        index += 1
    return tuple(normalised)


def _semantic_roles_are_legal_reference_siblings(left: str, right: str) -> bool:
    left_parts = tuple(left.split("_"))
    right_parts = tuple(right.split("_"))
    left_stripped = _strip_semantic_role_legal_reference_tokens(left_parts)
    right_stripped = _strip_semantic_role_legal_reference_tokens(right_parts)
    return (
        left_stripped == right_stripped
        and (left_stripped != left_parts or right_stripped != right_parts)
        and left_parts != right_parts
    )


def _strip_semantic_role_legal_reference_tokens(parts: tuple[str, ...]) -> tuple[str, ...]:
    stripped: list[str] = []
    index = 0
    while index < len(parts):
        part = parts[index]
        if part.startswith("art"):
            index += 1
            while index < len(parts) and parts[index].isdigit():
                index += 1
            continue
        if part.startswith("dt") or part in {"rdleg", "lis"}:
            index += 1
            continue
        stripped.append(part)
        index += 1
    return tuple(stripped)
