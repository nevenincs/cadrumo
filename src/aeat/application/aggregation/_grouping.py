"""Shared group-by + name-cache helper for per-modelo aggregators.

Both :mod:`_retenciones` and :mod:`_counterpart` implement the same
shape of aggregation: bucket observations by a composite key, then
roll up each bucket. They additionally need to resolve a stable
human-readable name per (source_kind, identity_nif) pair across
multiple observations.

This module extracts that shared mechanism. The per-domain aggregators
retain their domain-specific rollup composition (e.g. counterpart adds
country + readiness fields) — only the group-and-name-cache step is
shared.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TypeVar

T = TypeVar("T")
GroupKey = TypeVar("GroupKey", bound=tuple[object, ...])
IdentityKey = TypeVar("IdentityKey", bound=tuple[object, ...])


def group_and_collect_names(
    observations: Iterable[T],
    *,
    group_key_fn: Callable[[T], GroupKey],
    identity_key_fn: Callable[[T], IdentityKey],
    name_fn: Callable[[T], str | None],
) -> tuple[dict[GroupKey, list[T]], dict[IdentityKey, str]]:
    """Bucket observations by group key and cache a canonical name per identity.

    Behaviour invariants (shared by both per-modelo aggregators):
      - Iteration order of ``observations`` is preserved within each bucket.
      - The first non-empty ``name_fn(obs)`` per ``identity_key_fn(obs)``
        wins; later non-empty names for the same identity are discarded.
      - An empty / falsy name is skipped (does not overwrite a prior win).

    Args:
        observations: Iterable of observation records.
        group_key_fn: Composite key for bucketing (e.g. (source_kind,
            nif, scheme)).
        identity_key_fn: Sub-key for the name cache (e.g. (source_kind,
            nif)).
        name_fn: Extractor for the human-readable name on each observation.

    Returns:
        A two-tuple ``(grouped, names)`` where ``grouped`` maps each
        ``group_key_fn(obs)`` to the list of observations sharing that
        key (insertion order), and ``names`` maps each
        ``identity_key_fn(obs)`` to the first non-empty name observed.
    """
    grouped: dict[GroupKey, list[T]] = {}
    names: dict[IdentityKey, str] = {}
    for observation in observations:
        group_key = group_key_fn(observation)
        grouped.setdefault(group_key, []).append(observation)
        identity_key = identity_key_fn(observation)
        name = name_fn(observation)
        if name and not names.get(identity_key):
            names[identity_key] = name
    return grouped, names


__all__ = ["group_and_collect_names"]
