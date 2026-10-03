"""Apply typed field, sequence, removal, and order deltas to inherited keyed families."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from cadrumo.domain.calculations.registry.cleared_families import cleared_family_names
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.keyed_families import KeyedFamilySpec as _KeyedFamily
from cadrumo.domain.calculations.registry.modelo_localization import as_toml_array
from cadrumo.domain.calculations.registry.schema_overrides import (
    FamilyFieldOverride,
    FamilyMemberPosition,
    FamilyMemberRemoval,
)
from dev.registry.compiler._toml_helpers import as_toml_table as _as_toml_table

from .keyed_family_identity import _member_identity

_CLEARED_FAMILIES_FIELD = "cleared_families"


def _patch_family_table(context: str, value: object, fields: Mapping[str, object], removed: tuple[str, ...]) -> object:
    table = _as_toml_table(value)
    if table is None:
        raise RegistryLoadError(f"{context}: selected family member is not a table")
    result: dict[str, object] = dict(table)
    for key, replacement in fields.items():
        if isinstance(replacement, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _patch_family_table(context, result[key], replacement, ())
        else:
            result[key] = replacement
    for path in removed:
        segments = path.split(".")
        target = result
        for segment in segments[:-1]:
            child = target.get(segment)
            if not isinstance(child, Mapping):
                raise RegistryLoadError(f"{context}: removed field {path!r} does not exist")
            copied = dict(child)
            target[segment] = copied
            target = copied
        if target.pop(segments[-1], None) is None:
            raise RegistryLoadError(f"{context}: removed field {path!r} does not exist")
    return result


def patch_family_sequences(
    context: str,
    value: object,
    additions: Mapping[str, tuple[object, ...]],
    removals: Mapping[str, tuple[int, ...]],
    orders: Mapping[str, tuple[int, ...]],
) -> object:
    """Apply a sequence delta and optional order to one nested member table."""
    table = _as_toml_table(value)
    if table is None:
        raise RegistryLoadError(f"{context}: selected family member is not a table")
    result: dict[str, object] = dict(table)
    for path in sorted(set(additions) | set(removals) | set(orders)):
        target, field = _sequence_target(context, result, path)
        target[field] = _patched_sequence(context, path, target.get(field), additions, removals, orders)
    return result


def _sequence_target(context: str, result: dict[str, object], path: str) -> tuple[dict[str, object], str]:
    target = result
    segments = path.split(".")
    for segment in segments[:-1]:
        child = target.get(segment)
        if not isinstance(child, Mapping):
            raise RegistryLoadError(f"{context}: sequence field {path!r} does not exist")
        copied: dict[str, object] = dict(child)
        target[segment] = copied
        target = copied
    return target, segments[-1]


def _patched_sequence(
    context: str,
    path: str,
    existing: object,
    additions: Mapping[str, tuple[object, ...]],
    removals: Mapping[str, tuple[int, ...]],
    orders: Mapping[str, tuple[int, ...]],
) -> tuple[object, ...]:
    if not isinstance(existing, list | tuple):
        raise RegistryLoadError(f"{context}: sequence field {path!r} is not a sequence")
    removed = set(removals.get(path, ()))
    if any(index >= len(existing) for index in removed):
        raise RegistryLoadError(f"{context}: sequence removal for {path!r} is out of range")
    patched = [item for index, item in enumerate(existing) if index not in removed]
    patched.extend(additions.get(path, ()))
    order = orders.get(path)
    if order is not None:
        if sorted(order) != list(range(len(patched))):
            raise RegistryLoadError(f"{context}: sequence order for {path!r} is not a permutation")
        patched = [patched[index] for index in order]
    return tuple(patched)


def _apply_family_storage_delta(
    context: str,
    *,
    predecessor_id: str,
    family: _KeyedFamily,
    inherited: tuple[object, ...],
    successor: Mapping[str, object],
) -> tuple[tuple[object, ...], frozenset[str], tuple[tuple[str, int], ...], frozenset[str]]:
    """Apply the canonical field/removal/order delta to one keyed family."""
    if family.section in cleared_family_names(successor.get(_CLEARED_FAMILIES_FIELD, ())):
        return tuple(), frozenset[str](), tuple(), frozenset[str]()
    overrides, removals, positions = _validated_family_delta(context, family, successor)
    result = list(inherited)
    by_identity = {_member_identity(member, family): index for index, member in enumerate(result)}
    seen, removed = _validated_family_removals(context, predecessor_id, by_identity, removals)
    patched = _apply_family_overrides(context, predecessor_id, family, result, by_identity, seen, overrides)
    return (
        tuple(result),
        frozenset(removed),
        tuple((item.id, item.position) for item in positions),
        frozenset(patched),
    )


def _validated_family_delta(
    context: str,
    family: _KeyedFamily,
    successor: Mapping[str, object],
) -> tuple[tuple[FamilyFieldOverride, ...], tuple[FamilyMemberRemoval, ...], tuple[FamilyMemberPosition, ...]]:
    try:
        overrides = _validated_overrides(successor, family.section)
        removals = _validated_removals(successor, family.section)
        positions = _validated_positions(successor, family.section)
    except ValidationError as exc:
        raise RegistryLoadError(f"{context}: invalid {family.section} storage delta: {exc}") from exc
    return overrides, removals, positions


def _validated_overrides(successor: Mapping[str, object], section: str) -> tuple[FamilyFieldOverride, ...]:
    return tuple(
        FamilyFieldOverride.model_validate(value)
        for value in (as_toml_array(successor.get("family_overrides", ())) or ())
        if isinstance(value, Mapping) and value.get("family") == section
    )


def _validated_removals(successor: Mapping[str, object], section: str) -> tuple[FamilyMemberRemoval, ...]:
    return tuple(
        FamilyMemberRemoval.model_validate(value)
        for value in (as_toml_array(successor.get("family_removals", ())) or ())
        if isinstance(value, Mapping) and value.get("family") == section
    )


def _validated_positions(successor: Mapping[str, object], section: str) -> tuple[FamilyMemberPosition, ...]:
    return tuple(
        FamilyMemberPosition.model_validate(value)
        for value in (as_toml_array(successor.get("family_positions", ())) or ())
        if isinstance(value, Mapping) and value.get("family") == section
    )


def _validated_family_removals(
    context: str,
    predecessor_id: str,
    by_identity: Mapping[str | None, int],
    removals: tuple[FamilyMemberRemoval, ...],
) -> tuple[set[str], set[str]]:
    seen: set[str] = set()
    removed: set[str] = set()
    for declaration in removals:
        if str(declaration.selector.revision) != predecessor_id:
            raise RegistryLoadError(f"{context}: family removal baseline is not predecessor {predecessor_id!r}")
        identity = declaration.selector.id
        if identity not in by_identity or identity in seen:
            raise RegistryLoadError(f"{context}: family removal selector {identity!r} is missing or repeated")
        seen.add(identity)
        removed.add(identity)
    return seen, removed


def _apply_family_overrides(
    context: str,
    predecessor_id: str,
    family: _KeyedFamily,
    result: list[object],
    by_identity: Mapping[str | None, int],
    seen: set[str],
    overrides: tuple[FamilyFieldOverride, ...],
) -> set[str]:
    patched: set[str] = set()
    for declaration in overrides:
        identity = _validate_override_selector(context, predecessor_id, by_identity, seen, declaration)
        index = by_identity[identity]
        result[index] = _patch_family_table(context, result[index], declaration.fields, declaration.removed_fields)
        result[index] = patch_family_sequences(
            context,
            result[index],
            declaration.sequence_additions,
            declaration.sequence_removals,
            declaration.sequence_order,
        )
        if declaration.replacement_id is not None:
            table = _as_toml_table(result[index])
            if table is None or family.identity is None:
                raise RegistryLoadError(f"{context}: family identity replacement selected a non-table member")
            result[index] = {**table, family.identity: declaration.replacement_id}
        patched.add(identity)
    return patched


def _validate_override_selector(
    context: str,
    predecessor_id: str,
    by_identity: Mapping[str | None, int],
    seen: set[str],
    declaration: FamilyFieldOverride,
) -> str:
    if str(declaration.selector.revision) != predecessor_id:
        raise RegistryLoadError(f"{context}: family override baseline is not predecessor {predecessor_id!r}")
    identity = declaration.selector.id
    if identity not in by_identity or identity in seen:
        raise RegistryLoadError(f"{context}: family override selector {identity!r} is missing or repeated")
    seen.add(identity)
    return identity
