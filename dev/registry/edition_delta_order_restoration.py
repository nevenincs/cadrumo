"""Discover, stage, and prove positions that restore each family statement's declared order."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import tomlkit

from cadrumo.domain.calculations.registry.keyed_families import (
    CASILLAS_FAMILY,
    INHERITED_FAMILY_SPECS,
    KeyedFamilySpec,
    family_identity_value,
)
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions

from . import edition_delta_drop_scope as _edition_delta_drop_scope
from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_fields as _edition_delta_fields
from . import edition_delta_proof_source as _edition_delta_proof_source
from . import edition_delta_source as _edition_delta_source
from . import edition_delta_workdir as _edition_delta_workdir
from .compiler.loader import load_modelo_declarations, load_modelo_directory
from .edition_delta_chain_materialisation import chain_materialisation
from .edition_family_delta_difference import minimal_positions
from .edition_round_trip import copy_registry_tree

__all__ = ("OrderRestoration", "declared_order_restorations")


@dataclass(frozen=True, slots=True)
class OrderRestoration:
    """Positions that give one edition's full family statement its stated order."""

    revision_id: str
    family: str
    moves: tuple[tuple[str, int], ...]


def _declared_positions(raw: Mapping[str, object], section: str) -> tuple[str, ...]:
    if section == CASILLAS_FAMILY:
        operations = _edition_delta_source._members(raw, "casilla_positions") or ()
        return tuple(str(operation.get("id")) for operation in operations)
    operations = _edition_delta_source._members(raw, "family_positions") or ()
    return tuple(str(operation.get("id")) for operation in operations if operation.get("family") == section)


def _restoration_for_family(
    revision_id: str,
    modelo_id: str,
    revision: object,
    raw: Mapping[str, object],
    spec: KeyedFamilySpec,
) -> OrderRestoration | None:
    if spec.singleton or _edition_delta_drop_scope._family_storage_baseline(raw, spec.section) is None:
        return None
    orders = _restoration_identity_orders(revision, raw, spec)
    if orders is None:
        return None
    stated, materialised = orders
    if not _complete_statement(stated, materialised) or materialised == stated:
        return None
    positioned = _declared_positions(raw, spec.section)
    _require_unambiguous_positions(revision_id, spec.section, positioned)
    return OrderRestoration(
        revision_id=revision_id,
        family=spec.section,
        moves=minimal_positions(
            materialised, stated, subject=f"modelo {modelo_id} edition {revision_id} {spec.section}"
        ),
    )


def _restoration_identity_orders(
    revision: object, raw: Mapping[str, object], spec: KeyedFamilySpec
) -> tuple[list[str], list[str]] | None:
    identity = spec.storage_identity if spec.section == CASILLAS_FAMILY else spec.identity
    stated_members = _edition_delta_source._members(raw, spec.section)
    materialised_members = getattr(revision, spec.section, None)
    if identity is None or not stated_members or not isinstance(materialised_members, list | tuple):
        return None
    stated = [str(family_identity_value(member, identity)) for member in stated_members]
    materialised = [str(family_identity_value(member, identity)) for member in materialised_members]
    return stated, materialised


def _require_unambiguous_positions(revision_id: str, section: str, positioned: tuple[str, ...]) -> None:
    if positioned:
        raise _edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r} states every {section} member it inherits, in an order its "
            f"materialisation does not keep, and also places {sorted(positioned)!r} by position; the "
            "statement and the positions disagree about the order, so neither is taken",
        )


def _complete_statement(stated: list[str], materialised: list[str]) -> bool:
    return len(stated) > 1 and len(set(stated)) == len(stated) and Counter(stated) == Counter(materialised)


def _revision_restorations(
    revision: object,
    raw: Mapping[str, object],
    revision_id: str,
    modelo_id: str,
) -> list[OrderRestoration]:
    return [
        restoration
        for spec in INHERITED_FAMILY_SPECS
        if (restoration := _restoration_for_family(revision_id, modelo_id, revision, raw, spec)) is not None
    ]


def declared_order_restorations(modelo_dir: Path) -> tuple[OrderRestoration, ...]:
    """Find complete inherited family statements whose declared order needs positions."""
    raw_revisions = load_modelo_declarations(modelo_dir).get("revisions", {})
    if not isinstance(raw_revisions, Mapping):
        raise _edition_delta_errors.MigrationRefusedError(f"{modelo_dir}: revisions are not a mapping")
    definition = load_modelo_directory(modelo_dir)
    restorations = []
    for revision in ordered_revisions(definition):
        revision_id = str(revision.id)
        raw = raw_revisions.get(revision_id)
        if isinstance(raw, Mapping):
            restorations.extend(_revision_restorations(revision, raw, revision_id, str(definition.id)))
    return tuple(restorations)


def _append_revision_positions(document: tomlkit.TOMLDocument, item: OrderRestoration) -> None:
    revisions = document["revisions"]
    revision = revisions[item.revision_id]
    key = "casilla_positions" if item.family == CASILLAS_FAMILY else "family_positions"
    operations = revision.get(key) or tomlkit.aot()
    for identity, position in item.moves:
        entry = tomlkit.table()
        if item.family != CASILLAS_FAMILY:
            entry["family"] = item.family
        entry["id"] = identity
        entry["position"] = position
        operations.append(entry)
    revision[key] = operations


def _write_order_restorations(modelo_dir: Path, restorations: Sequence[OrderRestoration]) -> None:
    """Append restoration positions after the positions each edition already declares."""
    by_revision: dict[str, list[OrderRestoration]] = {}
    for restoration in restorations:
        by_revision.setdefault(restoration.revision_id, []).append(restoration)
    for revision_id, items in by_revision.items():
        manifest_path = modelo_dir / "revisions" / revision_id / _edition_delta_fields._MANIFEST
        document = tomlkit.parse(manifest_path.read_text(encoding="utf-8"))
        for item in items:
            _append_revision_positions(document, item)
        manifest_path.write_text(tomlkit.dumps(document), encoding="utf-8", newline="\n")


def _order_blind(payload: object) -> object:
    if not isinstance(payload, dict):
        return payload
    table = payload.get("table")
    if not isinstance(table, dict):
        return payload
    family_sections = {spec.section for spec in INHERITED_FAMILY_SPECS}
    return {
        **payload,
        "table": {
            key: sorted(value, key=lambda member: json.dumps(member, sort_keys=True))
            if key in family_sections and isinstance(value, list)
            else value
            for key, value in table.items()
        },
    }


def _member_orders(source: _edition_delta_source._EditionSource) -> dict[str, tuple[str, ...]]:
    orders: dict[str, tuple[str, ...]] = {}
    for spec in INHERITED_FAMILY_SPECS:
        identity = spec.storage_identity if spec.section == CASILLAS_FAMILY else spec.identity
        members = source.table.get(spec.section)
        if identity is None or spec.singleton or not isinstance(members, list | tuple):
            continue
        orders[spec.section] = tuple(str(family_identity_value(member, identity)) for member in members)
    return orders


def _prove_revision_order(
    reference_modelo_dir: Path, declared_modelo_dir: Path, revision_id: str
) -> list[tuple[str, str]]:
    before = _edition_delta_proof_source.read_staged_edition(reference_modelo_dir, revision_id, side="reference")
    after = _edition_delta_proof_source.read_staged_edition(declared_modelo_dir, revision_id, side="declared-order")
    before_bytes = _order_blind(json.loads(chain_materialisation(before)))
    after_bytes = _order_blind(json.loads(chain_materialisation(after)))
    if before_bytes != after_bytes:
        raise _edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r}: restoring declared order changed more than the order of its members",
        )
    before_orders, after_orders = _member_orders(before), _member_orders(after)
    return [
        (revision_id, section)
        for section in sorted(before_orders.keys() | after_orders.keys())
        if before_orders.get(section) != after_orders.get(section)
    ]


def _require_no_remaining_restorations(declared_modelo_dir: Path) -> None:
    remaining = declared_order_restorations(declared_modelo_dir)
    if remaining:
        raise _edition_delta_errors.MigrationRefusedError(
            f"restoring declared order left {[(item.revision_id, item.family) for item in remaining]!r} out of the "
            "order their statements give",
        )


def _require_each_restoration_reordered(
    restorations: Sequence[OrderRestoration], reordered: Sequence[tuple[str, str]]
) -> None:
    missing = sorted({(item.revision_id, item.family) for item in restorations} - set(reordered))
    if missing:
        raise _edition_delta_errors.MigrationRefusedError(f"restoring declared order did not reorder {missing!r}")


def _prove_order_restoration(
    *, reference_modelo_dir: Path, declared_modelo_dir: Path, restorations: Sequence[OrderRestoration]
) -> tuple[tuple[str, str], ...]:
    """Prove the staged edit changed only the order of members and restored each named family."""
    _require_no_remaining_restorations(declared_modelo_dir)
    revision_ids = sorted(path.name for path in (reference_modelo_dir / "revisions").iterdir() if path.is_dir())
    reordered = [
        family
        for revision_id in revision_ids
        for family in _prove_revision_order(reference_modelo_dir, declared_modelo_dir, revision_id)
    ]
    _require_each_restoration_reordered(restorations, reordered)
    return tuple(reordered)


def _stage_declared_order(
    *, registry_root: Path, modelo_id: str, work_dir: Path, reference: Path, restorations: Sequence[OrderRestoration]
) -> tuple[Path, tuple[tuple[str, str], ...]]:
    """Stage the declaration order that migration must preserve when positions are needed."""
    if not restorations:
        return reference, ()
    declared = copy_registry_tree(
        registry_root,
        _edition_delta_workdir._scratch_path(work_dir, "declared", "registry", "aeat"),
        modelo_id=modelo_id,
    )
    _write_order_restorations(declared / _edition_delta_fields._MODELOS / modelo_id, restorations)
    reordered = _prove_order_restoration(
        reference_modelo_dir=reference / _edition_delta_fields._MODELOS / modelo_id,
        declared_modelo_dir=declared / _edition_delta_fields._MODELOS / modelo_id,
        restorations=restorations,
    )
    return declared, reordered


def _order_lines(
    modelo_id: str,
    restorations: Sequence[OrderRestoration],
    reordered: Sequence[tuple[str, str]],
) -> list[str]:
    restored = {(item.revision_id, item.family) for item in restorations}
    lines = [
        f"order modelo={modelo_id} revision={item.revision_id} family={item.family} restored=stated_order "
        f"positions={json.dumps([{'id': identity, 'position': position} for identity, position in item.moves])}"
        for item in restorations
    ]
    lines.extend(
        f"order modelo={modelo_id} revision={revision_id} family={family} restored=follows_baseline"
        for revision_id, family in reordered
        if (revision_id, family) not in restored
    )
    return lines
