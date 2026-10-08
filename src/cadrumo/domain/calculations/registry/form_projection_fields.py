"""Resolve exact projection endpoints declared by a :class:`ModeloRevision` form block."""

from ..export_field_kind import CasillaFieldKind
from .errors import RegistryValidationError
from .export import derive_export_layouts_from_bindings
from .schema import ModeloRevision
from .schema_exports import ExportFieldDefinition
from .schema_form_layouts import FormRepeatingGroupBlock


def resolve_form_projection_fields(
    revision: ModeloRevision, block: FormRepeatingGroupBlock
) -> tuple[ExportFieldDefinition, ...]:
    """Resolve :class:`ModeloRevision` projections, refusing missing or ambiguous endpoints.

    The form supplies labels and order. Its values retain the typed projection
    references owned by the export declaration, including their slot identity.
    """
    records = tuple(
        record
        for layout in derive_export_layouts_from_bindings(revision)
        for record in layout.records
        if record.id == block.export_record_id
    )
    if len(records) != 1:
        raise RegistryValidationError("projected form columns require one unambiguous export record")
    record = records[0]
    if record.repeat is None:
        if block.max_rows != 1:
            raise RegistryValidationError("a single export record requires a projected form block bounded to one row")
    elif record.repeat != "projection_rows":
        raise RegistryValidationError("projected form columns require a projection_rows or single export record")
    fields = {field.id: field for field in record.fields}
    selected: list[ExportFieldDefinition] = []
    for column in block.columns:
        field = fields.get(column.export_field_id) if column.export_field_id is not None else None
        if field is None or field.kind is not CasillaFieldKind.PROJECTION or field.projection_ref is None:
            raise RegistryValidationError("projected form column must address a typed projection in its own record")
        selected.append(field)
    if not selected:
        raise RegistryValidationError("projected form block requires declared columns")
    return tuple(selected)
