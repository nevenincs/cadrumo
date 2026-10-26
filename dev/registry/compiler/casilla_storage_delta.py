"""Apply casilla storage patches while keeping label and text origins aligned."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.modelo_localization import as_toml_array
from cadrumo.domain.calculations.registry.schema_overrides import (
    CasillaFieldOverride,
    CasillaMemberPosition,
    CasillaMemberRemoval,
)
from dev.registry.compiler._toml_helpers import as_toml_table as _as_toml_table

from . import casilla_identity as _casilla_identity
from .casilla_identity import LINEAGE_CLAIM_FIELDS
from .keyed_family_storage_delta import _patch_family_table
from .loader_fields import _ROW_SOURCE_ADDITIONS_FIELD, _ROW_SOURCE_FIELD

_ROW_LABEL_IDENTITY_FIELDS = frozenset({"id", "number", "continuidad_id"})


def _apply_casilla_storage_delta(
    context: str,
    *,
    predecessor_id: str,
    inherited: tuple[object, ...],
    origins: list[tuple[str | None, str | None]],
    successor: Mapping[str, object],
) -> tuple[tuple[object, ...], list[tuple[str | None, str | None]], frozenset[str], frozenset[str]]:
    """Apply storage-only patches while preserving each kept row's origin."""
    overrides, removals = _validated_casilla_storage_declarations(context, successor)
    by_id = _index_inherited_casillas(context, inherited)
    seen, removed = _validate_casilla_removals(context, predecessor_id, by_id, removals)
    result = list(inherited)
    carried_origins = list(origins)
    overridden, relabelled = _apply_casilla_overrides(
        context, predecessor_id, overrides, by_id, seen, result, carried_origins
    )
    kept_rows, kept_origins = _remove_casilla_rows(result, carried_origins, removed)
    return kept_rows, kept_origins, frozenset(overridden), frozenset(relabelled)


def _validated_casilla_storage_declarations(
    context: str, successor: Mapping[str, object]
) -> tuple[tuple[CasillaFieldOverride, ...], tuple[CasillaMemberRemoval, ...]]:
    raw_overrides = as_toml_array(successor.get("casilla_overrides", ())) or ()
    raw_removals = as_toml_array(successor.get("casilla_removals", ())) or ()
    try:
        overrides = tuple(CasillaFieldOverride.model_validate(value) for value in raw_overrides)
        removals = tuple(CasillaMemberRemoval.model_validate(value) for value in raw_removals)
    except ValidationError as exc:
        raise RegistryLoadError(f"{context}: invalid casilla storage delta: {exc}") from exc
    return overrides, removals


def _index_inherited_casillas(context: str, inherited: tuple[object, ...]) -> dict[str, int]:
    by_id: dict[str, int] = {}
    for index, row in enumerate(inherited):
        row_id = _casilla_identity._row_id(row)
        if row_id is None:
            continue
        if row_id in by_id:
            raise RegistryLoadError(f"{context}: predecessor has duplicate casilla storage id {row_id!r}")
        by_id[row_id] = index
    return by_id


def _validate_casilla_removals(
    context: str,
    predecessor_id: str,
    by_id: Mapping[str, int],
    removals: tuple[CasillaMemberRemoval, ...],
) -> tuple[set[str], set[str]]:
    seen: set[str] = set()
    removed: set[str] = set()
    for declaration in removals:
        selector = declaration.selector
        if str(selector.revision) != predecessor_id:
            raise RegistryLoadError(
                f"{context}: casilla removal baseline {selector.revision!s} is not predecessor {predecessor_id!r}"
            )
        identity = str(selector.id)
        if identity not in by_id or identity in seen:
            raise RegistryLoadError(f"{context}: casilla removal selector {identity!r} is missing or repeated")
        seen.add(identity)
        removed.add(identity)
    return seen, removed


def _apply_casilla_overrides(
    context: str,
    predecessor_id: str,
    overrides: tuple[CasillaFieldOverride, ...],
    by_id: Mapping[str, int],
    seen: set[str],
    result: list[object],
    origins: list[tuple[str | None, str | None]],
) -> tuple[set[str], set[str]]:
    overridden: set[str] = set()
    relabelled: set[str] = set()
    for declaration in overrides:
        identity, changed_label = _patch_casilla_override(
            context, predecessor_id, declaration, by_id, seen, result, origins
        )
        if identity is not None:
            overridden.add(identity)
            if changed_label:
                relabelled.add(identity)
    return overridden, relabelled


def _patch_casilla_override(
    context: str,
    predecessor_id: str,
    declaration: CasillaFieldOverride,
    by_id: Mapping[str, int],
    seen: set[str],
    result: list[object],
    origins: list[tuple[str | None, str | None]],
) -> tuple[str | None, bool]:
    identity, index = _casilla_override_target(context, predecessor_id, declaration, by_id, seen)
    table = _as_toml_table(result[index])
    if table is None:
        raise RegistryLoadError(f"{context}: selected casilla {identity!r} is not a table")
    patched = {key: value for key, value in table.items() if key not in LINEAGE_CLAIM_FIELDS}
    if _ROW_SOURCE_FIELD in declaration.fields:
        patched.pop(_ROW_SOURCE_ADDITIONS_FIELD, None)
    result[index] = _patch_family_table(
        f"{context}: casilla {identity!r}", patched, declaration.fields, declaration.removed_fields
    )
    resulting_id = _casilla_identity._row_id(result[index])
    changed_label = bool(
        _ROW_LABEL_IDENTITY_FIELDS.intersection(declaration.fields)
        or _ROW_LABEL_IDENTITY_FIELDS.intersection(declaration.removed_fields)
    )
    statement, text = origins[index]
    origins[index] = (None, None if changed_label else text or statement or predecessor_id)
    return resulting_id, changed_label


def _casilla_override_target(
    context: str,
    predecessor_id: str,
    declaration: CasillaFieldOverride,
    by_id: Mapping[str, int],
    seen: set[str],
) -> tuple[str, int]:
    selector = declaration.selector
    if str(selector.revision) != predecessor_id:
        raise RegistryLoadError(
            f"{context}: casilla override baseline {selector.revision!s} is not predecessor {predecessor_id!r}"
        )
    identity = str(selector.id)
    if identity not in by_id or identity in seen:
        raise RegistryLoadError(f"{context}: casilla override selector {identity!r} is missing or repeated")
    seen.add(identity)
    return identity, by_id[identity]


def _remove_casilla_rows(
    result: list[object],
    origins: list[tuple[str | None, str | None]],
    removed: set[str],
) -> tuple[tuple[object, ...], list[tuple[str | None, str | None]]]:
    kept_indexes = [index for index, row in enumerate(result) if (_casilla_identity._row_id(row) or "") not in removed]
    return tuple(result[index] for index in kept_indexes), [origins[index] for index in kept_indexes]


def _apply_casilla_positions[OriginT](
    context: str,
    rows: list[object],
    origins: list[OriginT],
    successor: Mapping[str, object],
) -> tuple[list[object], list[OriginT]]:

    raw = as_toml_array(successor.get("casilla_positions", ())) or ()

    try:
        positions = tuple(CasillaMemberPosition.model_validate(value) for value in raw)

    except ValidationError as exc:
        raise RegistryLoadError(f"{context}: invalid casilla positions: {exc}") from exc

    seen: set[str] = set()

    # Row ids move with their rows, so one derivation per row serves every

    # declaration; deriving them afresh per declaration made a large edition

    # quadratic in its member count.

    row_ids: list[str | None] = [_casilla_identity._row_id(row) for row in rows]

    for declaration in positions:
        identity = str(declaration.id)

        if identity in seen:
            raise RegistryLoadError(f"{context}: duplicate casilla position for {identity!r}")

        seen.add(identity)

        try:
            index = row_ids.index(identity)

        except ValueError:
            index = None

        if index is None or declaration.position >= len(rows):
            raise RegistryLoadError(f"{context}: casilla position for {identity!r} is outside the effective member set")

        row, origin, row_id = rows.pop(index), origins.pop(index), row_ids.pop(index)

        rows.insert(declaration.position, row)

        origins.insert(declaration.position, origin)

        row_ids.insert(declaration.position, row_id)

    return rows, origins
