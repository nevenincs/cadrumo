"""The casilla an export layout field resolves to, and the back-references that follow from it.

A casilla's ``export_refs`` answer "which export fields carry me". The layout
already answers the converse for every field, so the casilla side is derived
from it here rather than declared a second time: an edition's layout owns the
edge, and a field moved to another casilla moves its back-reference with it.

A field resolves to a casilla along one of two paths:

- its own endpoint, :attr:`~.schema_exports.ExportFieldDefinition.endpoint_casilla_id`,
  which covers a ``casilla_id`` and a numbered ``projection_ref``;
- the record row mapping, for a ``binding`` field in a repeated record: the
  binding's row-set ``row_field`` names a slot, and the record's
  ``row_field_casilla_ids`` names the casilla that slot belongs to.

A binding_record row template contributes no casilla edge. Declaring
``binding_record`` makes the export derivation take the record's field
positions from its bindings' export selectors, so the record's rows are
templates the derivation fills, and neither the ``casilla`` field that
templates a mapped slot nor a ``binding`` field in that record is an edge. A
record whose field positions come from the official record design uses
``row_field_casilla_ids`` only to say which box each field fills; those rows
are real edges and keep their back-references. Declaring ``binding_record``
on such a record would add a second source of field positions beside the
official design, so the two record shapes are deliberately distinct.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ....core.aggregation import BindingAggregationOp
from ....core.casilla_id import CasillaId
from ..export_field_kind import CasillaFieldKind
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import binding_row_set_selector
from .errors import RegistryValidationError
from .ids import ExportFieldId
from .schema import DataBindingDefinition
from .schema_exports import ExportFieldDefinition, ExportLayoutDefinition, ExportRecordDefinition

__all__ = ["derive_casilla_export_refs", "export_field_casilla_id", "layout_fields_in_emission_order"]


def layout_fields_in_emission_order(
    layout: ExportLayoutDefinition,
) -> tuple[tuple[ExportRecordDefinition, ExportFieldDefinition], ...]:
    """Return every field of ``layout`` with its record, in the order the layout emits them.

    Records are taken by their declared ``order``, records of equal order in
    declaration order. Within a record, fields are taken by ``offset``, a field
    declaring no offset ahead of every positioned one, and by field id where
    two share an offset.
    """
    return tuple(
        (record, field)
        for record in sorted(layout.records, key=lambda item: item.order)
        for field in sorted(record.fields, key=lambda item: (-1 if item.offset is None else item.offset, item.id))
    )


def export_field_casilla_id(
    record: ExportRecordDefinition,
    field: ExportFieldDefinition,
    *,
    bindings: Mapping[str, DataBindingDefinition],
) -> CasillaId | None:
    """Return the casilla ``field`` of ``record`` resolves to, or ``None`` when it resolves to none.

    ``bindings`` maps binding id to its declaration. A binding field naming a
    binding absent from it, or one that produces no rows, resolves to nothing;
    reference validation reports the unknown binding.

    A binding_record row template contributes no casilla edge: in a record
    declaring ``binding_record`` the field positions come from the bindings'
    export selectors, so a ``casilla`` field whose casilla is a mapped row slot
    is the template of that slot and resolves to nothing, and a ``binding``
    field never takes the row-mapping path. A record without it takes its
    positions from the official design, and its row mapping names real edges.

    Raises:
        RegistryValidationError: When a row-producing binding the field names
            declares a malformed row-set projection.
    """
    if record.binding_record is not None:
        if field.kind == CasillaFieldKind.CASILLA and field.casilla_id in set(record.row_field_casilla_ids.values()):
            return None
        return field.endpoint_casilla_id
    endpoint = field.endpoint_casilla_id
    if endpoint is not None or field.kind != CasillaFieldKind.BINDING or field.binding is None:
        return endpoint
    binding = bindings.get(field.binding)
    if binding is None or binding_aggregation_op(binding) != BindingAggregationOp.ROWS:
        return None
    selector = binding_row_set_selector(binding)
    if selector is None:
        return None
    return record.row_field_casilla_ids.get(selector.row_field)


def derive_casilla_export_refs(
    export_layouts: Iterable[ExportLayoutDefinition],
    bindings: Iterable[DataBindingDefinition],
) -> dict[CasillaId, tuple[ExportFieldId, ...]]:
    """Return every addressed casilla's export field ids, in the order its layout emits them.

    Only casillas some field resolves to appear. The order is part of the
    value: a casilla's field ids follow
    :func:`layout_fields_in_emission_order`, record order and then field
    offset, never the order the declarations happen to be written in.

    Raises:
        RegistryValidationError: When fields of more than one layout resolve to
            one casilla. Two layouts each claiming a casilla is a conflict to
            resolve in the declarations, never a union to take silently.
    """
    bindings_by_id = {str(binding.id): binding for binding in bindings}
    refs: dict[CasillaId, list[ExportFieldId]] = {}
    owner: dict[CasillaId, str] = {}
    for layout in export_layouts:
        for record, field in layout_fields_in_emission_order(layout):
            casilla_id = export_field_casilla_id(record, field, bindings=bindings_by_id)
            if casilla_id is None:
                continue
            claimed = owner.setdefault(casilla_id, str(layout.id))
            if claimed != str(layout.id):
                raise RegistryValidationError(
                    f"export layouts {claimed!r} and {str(layout.id)!r} both address casilla {casilla_id!r}; "
                    "a casilla's export references are derived from one layout",
                )
            refs.setdefault(casilla_id, []).append(field.id)
    return {casilla_id: tuple(field_ids) for casilla_id, field_ids in refs.items()}
