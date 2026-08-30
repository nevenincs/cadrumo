"""Semantic-role typo diagnostic helpers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from difflib import SequenceMatcher
from functools import lru_cache
from typing import NamedTuple, Protocol

from ....core.casilla_id import CasillaId
from ._validate_semantic_role_axes import (
    semantic_roles_are_axis_siblings,
    semantic_roles_are_modelo_prefix_siblings,
    semantic_roles_are_month_axis_siblings,
    semantic_roles_are_quarter_axis_siblings,
    semantic_roles_are_tax_domain_siblings,
)
from .ids import RevisionId


class _RoleObservationLike(Protocol):
    modelo_id: str
    revision_id: RevisionId
    casilla_id: CasillaId
    semantic_role_cardinality: str


def grouped_semantic_role_typo_twin_failures(
    grouped: Mapping[str, Sequence[_RoleObservationLike]],
) -> tuple[str, ...]:
    """Return failures for singleton ``semantic_role`` values that look like typos."""
    typo_index = _build_semantic_role_typo_index(grouped.keys())
    failures: list[str] = []
    for role, observations in grouped.items():
        if len(observations) != 1:
            continue
        obs = observations[0]
        if obs.semantic_role_cardinality == "intentional_singleton":
            continue
        if not _semantic_role_looks_like_typo(role, typo_index):
            continue
        failures.append(_format_semantic_role_typo_twin_failure(role, obs))
    return tuple(failures)


def _format_semantic_role_typo_twin_failure(role: str, obs: _RoleObservationLike) -> str:
    return (
        f"semantic_role {role!r} appears on exactly one casilla "
        f"({obs.modelo_id}.{obs.revision_id}.{obs.casilla_id}); "
        "likely typo or missing role declarations on sibling casillas"
    )


class _SemanticRoleTypoIndex(NamedTuple):
    normalised: Mapping[str, tuple[str, ...]]
    by_length: Mapping[int, tuple[str, ...]]
    lengths: tuple[int, ...]
    sets: Mapping[str, set[str]]


_SEMANTIC_ROLE_TYPO_RATIO = 0.92


def _build_semantic_role_typo_index(known_roles: Iterable[str]) -> _SemanticRoleTypoIndex:
    normalised: dict[str, list[str]] = defaultdict(list)
    by_length: dict[int, list[str]] = defaultdict(list)
    sets: dict[str, set[str]] = {}
    for known in known_roles:
        normalised[known.replace("-", "_")].append(known)
        by_length[len(known)].append(known)
        sets[known] = set(known)
    return _SemanticRoleTypoIndex(
        normalised={key: tuple(values) for key, values in normalised.items()},
        by_length={key: tuple(values) for key, values in by_length.items()},
        lengths=tuple(sorted(by_length)),
        sets=sets,
    )


def _fast_similarity_check(s1: str, s2: str, max_diff: int) -> bool:
    i = 0
    min_len = min(len(s1), len(s2))
    while i < min_len and s1[i] == s2[i]:
        i += 1
    j = 0
    remaining1 = len(s1) - i
    remaining2 = len(s2) - i
    min_remaining = min(remaining1, remaining2)
    while j < min_remaining and s1[-1 - j] == s2[-1 - j]:
        j += 1
    return (i + j) >= min_len - max_diff


@lru_cache(maxsize=8192)
def _get_ratio(role1: str, role2: str) -> float:
    matcher = SequenceMatcher(None, role1, role2)
    if matcher.real_quick_ratio() < _SEMANTIC_ROLE_TYPO_RATIO:
        return 0.0
    if matcher.quick_ratio() < _SEMANTIC_ROLE_TYPO_RATIO:
        return 0.0
    return matcher.ratio()


def _semantic_role_looks_like_typo(role: str, index: _SemanticRoleTypoIndex) -> bool:
    if "-" in role:
        return True
    normalised = role.replace("-", "_")
    for known in index.normalised.get(normalised, ()):
        if known == role:
            continue
        return True

    return _scan_length_buckets_for_typo_twin(role, index)


def _scan_length_buckets_for_typo_twin(role: str, index: _SemanticRoleTypoIndex) -> bool:
    """Scan the length-bucketed known roles for a near-duplicate non-sibling twin."""
    role_length = len(role)
    role_set = set(role)
    for known_length in index.lengths:
        if _max_sequence_match_ratio(role_length, known_length) < _SEMANTIC_ROLE_TYPO_RATIO:
            continue
        max_diff = int(0.08 * (role_length + known_length))
        for known in index.by_length[known_length]:
            if _candidate_is_typo_twin(role, role_set, role_length, known, known_length, max_diff, index):
                return True
    return False


def _candidate_is_typo_twin(
    role: str,
    role_set: set[str],
    role_length: int,
    known: str,
    known_length: int,
    max_diff: int,
    index: _SemanticRoleTypoIndex,
) -> bool:
    """Return whether ``known`` is a near-duplicate typo twin of ``role``.

    Applies, in order, the cheap-to-expensive filter chain: identity skip, the
    fast O(N) prefix/suffix check, the unique-character-set filter, the
    SequenceMatcher ratio, then the tax-domain and axis sibling exemptions.
    """
    if known == role:
        return False

    # Run the fast O(N) prefix/suffix check first
    if not _fast_similarity_check(role, known, max_diff):
        return False

    # Unique character set check as a secondary filter
    known_set = index.sets[known]
    max_edits = 0.08 * (role_length + known_length)
    if len(role_set & known_set) < max(len(role_set), len(known_set)) - max_edits:
        return False

    if _get_ratio(role, known) < _SEMANTIC_ROLE_TYPO_RATIO:
        return False

    # Only run sibling checks on potential typo matches!
    if semantic_roles_are_tax_domain_siblings(role, known):
        return False
    if semantic_roles_are_modelo_prefix_siblings(role, known):
        return False
    if semantic_roles_are_month_axis_siblings(role, known):
        return False
    if semantic_roles_are_quarter_axis_siblings(role, known):
        return False
    return not semantic_roles_are_axis_siblings(role, known)


def _max_sequence_match_ratio(left_length: int, right_length: int) -> float:
    if left_length == 0 and right_length == 0:
        return 1.0
    return (2 * min(left_length, right_length)) / (left_length + right_length)
