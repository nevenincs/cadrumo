"""Payload comparison and patch operations for edition storage deltas."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from enum import Enum
from typing import Final

_STORAGE_REPRESENTATION_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "predecessor",
        "casilla_storage_baseline",
        "casilla_overrides",
        "casilla_removals",
        "casilla_positions",
        "family_storage_baseline",
        "family_overrides",
        "family_removals",
        "family_positions",
        "cleared_families",
        "scoped_families",
        "restated_families",
    }
)

_STRUCTURAL_FIELDS: Final[frozenset[str]] = _STORAGE_REPRESENTATION_FIELDS | frozenset(
    {
        "id",
        "selector",
        "position",
        "removed_fields",
        "restate_provenance",
        "restated_families",
        "family_dispositions",
    }
)


def _field_count(value: object, *, structural: bool) -> tuple[int, int]:
    """Count payload and representation fields without coercing values."""
    if not isinstance(value, Mapping):
        return (0 if structural else 1, 1 if structural else 0)
    payload = overhead = 0
    for key, child in value.items():
        is_structural = structural or str(key) in _STRUCTURAL_FIELDS
        if isinstance(child, Mapping) and child:
            child_payload, child_overhead = _field_count(child, structural=is_structural)
        else:
            child_payload, child_overhead = (0, 1) if is_structural else (1, 0)
        payload += child_payload
        overhead += child_overhead
    return payload, overhead


def _leaf_values(value: object, prefix: tuple[str, ...] = ()) -> dict[tuple[str, ...], object]:
    """Return consistently counted nested values, keeping arrays as ordered values."""
    if not isinstance(value, Mapping) or not value:
        return {prefix: value}
    leaves: dict[tuple[str, ...], object] = {}
    for key, child in value.items():
        leaves.update(_leaf_values(child, (*prefix, str(key))))
    return leaves


def _typed_equal(left: object, right: object) -> bool:
    """Compare registry values without Python's bool/int or container coercions.

    An enum compares by its value: authored TOML states ``"computed"`` where the
    typed model holds ``InputKind.COMPUTED``, and the two are the same fact.
    Sequences compare in order; tables compare by field, whatever order their
    keys were written in.
    """
    if isinstance(left, Enum):
        left = left.value
    if isinstance(right, Enum):
        right = right.value
    if isinstance(left, Mapping) or isinstance(right, Mapping):
        return _mapping_equal(left, right)
    if isinstance(left, list | tuple) or isinstance(right, list | tuple):
        return _sequence_equal(left, right)
    return type(left) is type(right) and left == right


def _mapping_equal(left: object, right: object) -> bool:
    """Compare table fields independent of serialization key order."""
    if not isinstance(left, Mapping) or not isinstance(right, Mapping) or set(left) != set(right):
        return False
    return all(_typed_equal(left[key], right[key]) for key in left)


def _sequence_equal(left: object, right: object) -> bool:
    """Compare ordered values while keeping list and tuple equivalent."""
    if not isinstance(left, list | tuple) or not isinstance(right, list | tuple) or len(left) != len(right):
        return False
    return all(_typed_equal(a, b) for a, b in zip(left, right, strict=True))


def _model_value(value: object) -> object:
    dump = getattr(value, "model_dump", None)
    return dump(mode="python", exclude={"inherited_from"}) if callable(dump) else value


def _stated_leaves(value: object) -> dict[tuple[str, ...], object]:
    """A baseline member's typed leaf values, limited to the leaves its declaration states.

    A value restates its baseline only where the baseline states that value
    too. An explicit empty sequence, ``false`` or zero over a field the
    baseline omits reads the same through the typed default, but it is a
    statement the baseline does not make: the chain proof materialises it, so
    dropping it as redundant would change the edition's storage. Values keep
    their full typed form; only the leaves the baseline leaves to a default
    are withheld from comparison.
    """
    full = _leaf_values(_thaw(_model_value(value)))
    dump = getattr(value, "model_dump", None)
    if not callable(dump):
        return full
    stated = _leaf_values(_thaw(dump(mode="python", exclude={"inherited_from"}, exclude_unset=True)))
    return {path: item for path, item in full.items() if path in stated}


def _remove_toml_leaf(value: object, path: Sequence[str]) -> bool:
    """Remove one assessed redundant leaf, pruning empty nested tables."""
    if not path or not isinstance(value, MutableMapping):
        return False
    key = path[0]
    if len(path) == 1:
        if key not in value:
            return False
        del value[key]
        return True
    child = value.get(key)
    if not _remove_toml_leaf(child, path[1:]):
        return False
    if isinstance(child, Mapping) and not child:
        del value[key]
    return True


def _storage_difference(
    baseline: Mapping[str, object], target: Mapping[str, object]
) -> tuple[dict[str, object], tuple[str, ...]]:
    """Return the recursive field patch that turns one storage row into another."""
    removed: list[str] = []

    def visit(old: Mapping[str, object], new: Mapping[str, object], prefix: str = "") -> dict[str, object]:
        fields: dict[str, object] = {}
        for key in sorted(set(old) | set(new)):
            path = f"{prefix}.{key}" if prefix else key
            if key not in new:
                removed.append(path)
                continue
            if key not in old:
                fields[key] = new[key]
                continue
            old_value, new_value = old[key], new[key]
            if isinstance(old_value, Mapping) and isinstance(new_value, Mapping):
                nested = visit(old_value, new_value, path)
                if nested:
                    fields[key] = nested
            elif old_value != new_value:
                fields[key] = new_value
        return fields

    return visit(baseline, target), tuple(removed)


def _existing_storage_removals(baseline: Mapping[str, object], removed_fields: Sequence[str]) -> tuple[str, ...]:
    """Keep removals that address leaves physically present on the inherited row."""
    existing: list[str] = []
    for path in removed_fields:
        value: object = baseline
        for segment in path.split("."):
            if not isinstance(value, Mapping) or segment not in value:
                break
            value = value[segment]
        else:
            existing.append(path)
    return tuple(existing)


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_thaw(item) for item in value]
    return value
