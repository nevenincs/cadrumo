"""Semantic-role typo warning helpers."""

from __future__ import annotations

import warnings
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from difflib import SequenceMatcher
from typing import NamedTuple, Protocol

from ._validate_semantic_role_axes import (
    semantic_roles_are_axis_siblings,
    semantic_roles_are_tax_domain_siblings,
)


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
            if semantic_roles_are_tax_domain_siblings(role, known):
                continue
            if semantic_roles_are_axis_siblings(role, known):
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

