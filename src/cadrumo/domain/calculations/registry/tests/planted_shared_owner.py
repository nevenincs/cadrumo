"""Plant an unadjudicated shared owner into an isolated copy of a registry snapshot.

No bundled edition writes one casilla into unrelated cells any more, but the
export refusal and the verification finding still guard against an edition that
does. A guard is proved against a representative defect: this copies a real
snapshot and points one cell of another record at a box without a segment that
already owns a single cell, so the box now reaches two records with nothing
declaring that they agree. The bundled authority is never modified.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .....core.casilla_id import CasillaId
from ...export_field_kind import CasillaFieldKind
from ..export_shared_owner import canonical_export_layout, unadjudicated_shared_owners
from ..schema import RegistrySnapshot
from ..schema_exports import ExportFieldDefinition, ExportLayoutDefinition


@dataclass(frozen=True, slots=True)
class PlantedSharedOwner:
    """A snapshot copy in which ``casilla_id`` reaches ``target_cell_ids`` in two records."""

    snapshot: RegistrySnapshot
    casilla_id: CasillaId
    target_cell_ids: tuple[str, ...]


def _kind(field: ExportFieldDefinition) -> str:
    return str(getattr(field.data_type, "value", field.data_type))


def _shape(field: ExportFieldDefinition) -> tuple[object, ...]:
    return (_kind(field), field.length, field.decimals, field.signed, field.value_policy)


def _layout(snapshot: RegistrySnapshot) -> ExportLayoutDefinition:
    layout = canonical_export_layout(snapshot.revision.export_layouts)
    assert layout is not None, f"modelo {snapshot.modelo.id} revision {snapshot.revision.id} exports no layout"
    return layout


def plant_shared_owner(
    snapshot: RegistrySnapshot,
    *,
    owner_cell_kind: str,
    target_cell_kind: str | None = None,
    owner_value_policy: object = None,
    avoid: Iterable[str] = (),
) -> PlantedSharedOwner:
    """Point one cell of another record at a box without a segment that owns one ``owner_cell_kind`` cell.

    The moved cell has the owner cell's shape unless ``target_cell_kind`` names
    another kind. ``avoid`` names casillas already planted, so several owners
    can be planted into one copy without disturbing each other.
    """
    avoided = set(avoid)
    layout = _layout(snapshot)
    cells: dict[str, list[tuple[str, ExportFieldDefinition]]] = {}
    for record in layout.records:
        for field in record.fields:
            if field.kind is CasillaFieldKind.CASILLA and field.casilla_id is not None:
                cells.setdefault(str(field.casilla_id), []).append((str(record.id), field))
    bare = sorted(
        str(casilla.id)
        for casilla in snapshot.revision.casillas
        if casilla.segmento is None and str(casilla.id) not in avoided
    )
    for owner in bare:
        own = cells.get(owner, [])
        if len(own) != 1:
            continue
        owner_record, owner_cell = own[0]
        if _kind(owner_cell) != owner_cell_kind or owner_cell.value_policy != owner_value_policy:
            continue
        for casilla_id, placed in sorted(cells.items()):
            if casilla_id in avoided or casilla_id == owner:
                continue
            for record_id, field in placed:
                if record_id == owner_record:
                    continue
                if target_cell_kind is None:
                    if _shape(field) != _shape(owner_cell):
                        continue
                elif _kind(field) != target_cell_kind or field.value_policy is not None:
                    continue
                return _repoint(snapshot, layout, field, owner_cell, owner)
    raise AssertionError(f"no box without a segment owns one {owner_cell_kind} cell to plant from")


def _repoint(
    snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    moved: ExportFieldDefinition,
    owner_cell: ExportFieldDefinition,
    owner: str,
) -> PlantedSharedOwner:
    owner_id = owner_cell.casilla_id
    assert owner_id is not None
    records = tuple(
        record.model_copy(
            update={
                "fields": tuple(
                    field.model_copy(update={"casilla_id": owner_id}) if field.id == moved.id else field
                    for field in record.fields
                )
            }
        )
        for record in layout.records
    )
    planted_layout = layout.model_copy(update={"records": records})
    revision = snapshot.revision.model_copy(
        update={
            "export_layouts": tuple(
                planted_layout if candidate.id == layout.id else candidate
                for candidate in snapshot.revision.export_layouts
            )
        }
    )
    planted = snapshot.model_copy(update={"revision": revision})
    (found,) = [
        candidate
        for candidate in unadjudicated_shared_owners(_layout(planted), planted.revision.casillas)
        if str(candidate.casilla_id) == owner
    ]
    assert set(found.target_cell_ids) == {str(owner_cell.id), str(moved.id)}
    return PlantedSharedOwner(snapshot=planted, casilla_id=owner_id, target_cell_ids=found.target_cell_ids)
