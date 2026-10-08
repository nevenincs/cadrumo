"""Build keyed-family storage differences and minimal order moves."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def _difference(
    left: Mapping[str, object], right: Mapping[str, object], *, identity: str
) -> tuple[dict[str, object], list[str], dict[str, list[object]], dict[str, list[int]], dict[str, list[int]]]:
    fields: dict[str, object] = {}
    removed: list[str] = []
    additions: dict[str, list[object]] = {}
    removals: dict[str, list[int]] = {}
    orders: dict[str, list[int]] = {}

    fields.update(_mapping_difference(left, right, "", identity, removed, additions, removals, orders))
    return fields, removed, additions, removals, orders


def _mapping_difference(
    old: Mapping[str, object],
    new: Mapping[str, object],
    prefix: str,
    identity: str,
    removed: list[str],
    additions: dict[str, list[object]],
    removals: dict[str, list[int]],
    orders: dict[str, list[int]],
) -> dict[str, object]:
    patch: dict[str, object] = {}
    for key in sorted(set(old) | set(new)):
        path = f"{prefix}.{key}" if prefix else key
        if not prefix and key == identity:
            continue
        if key not in new:
            removed.append(path)
            continue
        proposed = _field_difference(old, new, key, path, identity, removed, additions, removals, orders)
        if proposed is not _NO_PATCH:
            patch[key] = proposed
    return patch


_NO_PATCH = object()


def _field_difference(
    old: Mapping[str, object],
    new: Mapping[str, object],
    key: str,
    path: str,
    identity: str,
    removed: list[str],
    additions: dict[str, list[object]],
    removals: dict[str, list[int]],
    orders: dict[str, list[int]],
) -> object:
    if key not in old:
        return new[key]
    old_value = old[key]
    new_value = new[key]
    if isinstance(old_value, Mapping) and isinstance(new_value, Mapping):
        return _nested_difference(old_value, new_value, path, identity, removed, additions, removals, orders)
    if isinstance(old_value, list | tuple) and isinstance(new_value, list | tuple):
        _sequence_difference(path, list(old_value), list(new_value), additions, removals, orders)
        return _NO_PATCH
    return _NO_PATCH if old_value == new_value else new_value


def _nested_difference(
    old: Mapping[str, object],
    new: Mapping[str, object],
    path: str,
    identity: str,
    removed: list[str],
    additions: dict[str, list[object]],
    removals: dict[str, list[int]],
    orders: dict[str, list[int]],
) -> object:
    nested = _mapping_difference(old, new, path, identity, removed, additions, removals, orders)
    return nested if nested else _NO_PATCH


def _sequence_difference(
    path: str,
    old: list[object],
    new: list[object],
    additions: dict[str, list[object]],
    removals: dict[str, list[int]],
    orders: dict[str, list[int]],
) -> None:
    used_new, kept, removed_items = _matched_sequence_items(old, new)
    added = [item for index, item in enumerate(new) if index not in used_new]
    natural = [*kept, *added]
    order = _sequence_order(new, natural)
    if removed_items:
        removals[path] = removed_items
    if added:
        additions[path] = added
    if order != list(range(len(natural))):
        orders[path] = order


def _matched_sequence_items(old: list[object], new: list[object]) -> tuple[set[int], list[object], list[int]]:
    used_new: set[int] = set()
    kept: list[object] = []
    removed: list[int] = []
    for old_index, item in enumerate(old):
        match = _first_unmatched(new, used_new, item)
        if match is None:
            removed.append(old_index)
            continue
        used_new.add(match)
        kept.append(item)
    return used_new, kept, removed


def _first_unmatched(values: list[object], used: set[int], target: object) -> int | None:
    return next((index for index, candidate in enumerate(values) if index not in used and candidate == target), None)


def _sequence_order(new: list[object], natural: list[object]) -> list[int]:
    used_natural: set[int] = set()
    order: list[int] = []
    for item in new:
        index = next(i for i, candidate in enumerate(natural) if i not in used_natural and candidate == item)
        used_natural.add(index)
        order.append(index)
    return order


def _longest_ordered_run(sequence: Sequence[int]) -> set[int]:
    """Indexes into ``sequence`` of one longest strictly increasing subsequence, chosen deterministically."""
    tails: list[int] = []
    previous: list[int | None] = [None] * len(sequence)
    for index, value in enumerate(sequence):
        low, high = 0, len(tails)
        while low < high:
            middle = (low + high) // 2
            if sequence[tails[middle]] < value:
                low = middle + 1
            else:
                high = middle
        previous[index] = tails[low - 1] if low > 0 else None
        if low == len(tails):
            tails.append(index)
        else:
            tails[low] = index
    kept: set[int] = set()
    cursor = tails[-1] if tails else None
    while cursor is not None:
        kept.add(cursor)
        cursor = previous[cursor]
    return kept


def minimal_positions(natural: Sequence[str], target: Sequence[str], *, subject: str) -> tuple[tuple[str, int], ...]:
    """The fewest ``(identity, position)`` moves that turn ``natural`` into ``target``.

    The loader applies positions one after another, each removing its member
    and inserting it at the stated index. Members already in target order - one
    longest run of them - never move; every other member moves once, in target
    order, to just after the nearest member already where it belongs. No set of
    moves is smaller, since every member left unmoved keeps its relative order.
    """
    if sorted(natural) != sorted(target) or len(set(target)) != len(target):
        raise RuntimeError(f"{subject}: merge order {list(natural)!r} is not a permutation of {list(target)!r}")
    settled = _settled_identities(natural, target)
    working, moves = _move_unsettled_identities(natural, target, settled)
    if working != list(target):
        raise RuntimeError(f"{subject}: minimal positions do not reconstruct the family order")
    return tuple(moves)


def _settled_identities(natural: Sequence[str], target: Sequence[str]) -> set[str]:
    target_index = {identity: index for index, identity in enumerate(target)}
    return {natural[index] for index in _longest_ordered_run([target_index[identity] for identity in natural])}


def _move_unsettled_identities(
    natural: Sequence[str], target: Sequence[str], settled: set[str]
) -> tuple[list[str], list[tuple[str, int]]]:
    working = list(natural)
    moves: list[tuple[str, int]] = []
    for index, identity in enumerate(target):
        if identity in settled:
            continue
        position = _move_before_settled_anchor(working, target, index, identity, settled)
        settled.add(identity)
        moves.append((identity, position))
    return working, moves


def _move_before_settled_anchor(
    working: list[str], target: Sequence[str], index: int, identity: str, settled: set[str]
) -> int:
    working.remove(identity)
    anchor = next((target[earlier] for earlier in range(index - 1, -1, -1) if target[earlier] in settled), None)
    position = 0 if anchor is None else working.index(anchor) + 1
    working.insert(position, identity)
    return position
