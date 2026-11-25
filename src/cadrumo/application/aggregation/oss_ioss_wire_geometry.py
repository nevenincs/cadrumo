"""Read a Modelo 369 detail record's rows from the revision's bound wire geometry.

Bindings are generated from AEAT's positional workbook and their names are truncated
differently per page, so a row slot is located by offset and data-type shape, then
checked against the export layout's own field positions;
:class:`ModeloRevision`, the registry revision a modelo is calculated against.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

from ...core.i18n.translatable import Translatable as tr
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.manual_input_selector import ManualInputProvider
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_base import CasillaDataType
from ...domain.calculations.registry.schema_exports import ExportFieldDefinition
from .errors import AggregationValidationError

ROW_SHAPES: tuple[tuple[CasillaDataType, ...], ...] = (
    (
        CasillaDataType.TEXT,
        CasillaDataType.DECIMAL,
        CasillaDataType.TEXT,
        CasillaDataType.MONEY,
        CasillaDataType.MONEY,
    ),
    (
        CasillaDataType.TEXT,
        CasillaDataType.TEXT,
        CasillaDataType.TEXT,
        CasillaDataType.DECIMAL,
        CasillaDataType.TEXT,
        CasillaDataType.MONEY,
        CasillaDataType.MONEY,
    ),
    (
        CasillaDataType.TEXT,
        CasillaDataType.INTEGER,
        CasillaDataType.TEXT,
        CasillaDataType.TEXT,
        CasillaDataType.MONEY,
    ),
)
"""The three line layouts of DR369's lists: destination first, establishment first, or a correction.

Columns are told apart by data type and contiguity alone; each column's width is
whatever the revision's own wire geometry declares.

The second names a permanent establishment or a dispatch state the invoice does not
record, and is enumerated solely to close it. The third is destination, exercise, period
type, period and cuota, and is what the corrections of earlier periods take.
"""


def record_row_slots(revision: ModeloRevision, record_id: str) -> tuple[tuple[BindingId, ...], ...]:
    """Read a record's list of rows from its bound wire geometry.

    Bindings are generated from AEAT's positional workbook and their names are
    truncated differently per page, so a slot is located by offset and shape.
    Anything short of one unbroken run of rows is refused: a hole would otherwise
    pass for a row that does not exist.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    fields = _record_fields(revision, record_id)
    if len({field[0] for field in fields}) != len(fields):
        raise AggregationValidationError(tr("aggregation.oss_ioss.errors.detail_not_representable"))
    rows: list[tuple[int, int, tuple[BindingId, ...]]] = []
    index = 0
    while index < len(fields):
        width = next((len(shape) for shape in ROW_SHAPES if _fields_match_shape(fields[index:], shape)), 0)
        if width:
            run = fields[index : index + width]
            rows.append((run[0][0], run[-1][0] + run[-1][1], tuple(field[3] for field in run)))
        index += width or 1
    return _unbroken_rows(rows)


def _record_fields(revision: ModeloRevision, record_id: str) -> list[tuple[int, int, CasillaDataType, BindingId]]:
    """Return a record's positional manual-input bindings ordered by offset."""
    return sorted(
        (
            (binding.provider.offset, binding.provider.length, binding.provider.data_type, binding.id)
            for binding in revision.bindings
            if isinstance(binding.provider, ManualInputProvider)
            and binding.provider.record == record_id
            and binding.provider.offset is not None
            and binding.provider.length is not None
        ),
        key=lambda field: field[0],
    )


def _fields_match_shape(
    fields: Sequence[tuple[int, int, CasillaDataType, BindingId]],
    shape: tuple[CasillaDataType, ...],
) -> bool:
    """Say whether the leading fields are one contiguous line of this shape."""
    if len(fields) < len(shape):
        return False
    offset = fields[0][0]
    for (field_offset, length, data_type, _), expected in zip(fields, shape, strict=False):
        if field_offset != offset or data_type is not expected:
            return False
        offset += length
    return True


def _unbroken_rows(rows: Sequence[tuple[int, int, tuple[BindingId, ...]]]) -> tuple[tuple[BindingId, ...], ...]:
    if not rows or any(previous[1] != following[0] for previous, following in pairwise(rows)):
        raise AggregationValidationError(tr("aggregation.oss_ioss.errors.detail_not_representable"))
    return tuple(row[2] for row in rows)


def _slot_matches_export_field(provider: object, field: ExportFieldDefinition | None) -> bool:
    return (
        field is not None
        and isinstance(provider, ManualInputProvider)
        and provider.offset == field.offset
        and provider.length == field.length
    )


def _export_fields_by_binding(revision: ModeloRevision, record_id: str) -> dict[BindingId, ExportFieldDefinition]:
    """Return the one pinned export record's bound fields, refusing an absent or repeated record."""
    records = [record for layout in revision.export_layouts for record in layout.records if record.id == record_id]
    if len(records) != 1:
        raise AggregationValidationError(tr("aggregation.oss_ioss.errors.detail_not_representable"))
    return {field.binding: field for field in records[0].fields if field.binding is not None}


def require_wire_geometry(revision: ModeloRevision, record_id: str, slots: tuple[tuple[BindingId, ...], ...]) -> None:
    """Require each slot to be the export field of the pinned record at the same position.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    fields = _export_fields_by_binding(revision, record_id)
    bindings = {binding.id: binding for binding in revision.bindings}
    if len(bindings) != len(revision.bindings):
        raise AggregationValidationError(tr("aggregation.oss_ioss.errors.detail_not_representable"))
    for binding_id in (binding for row in slots for binding in row):
        if not _slot_matches_export_field(bindings[binding_id].provider, fields.get(binding_id)):
            raise AggregationValidationError(tr("aggregation.oss_ioss.errors.detail_not_representable"))


def require_slot_coverage(slots: tuple[tuple[BindingId, ...], ...], supplied_binding_ids: frozenset[BindingId]) -> None:
    """Refuse a row the supplied bindings fill only in part."""
    if any(
        bool(supplied_binding_ids.intersection(row)) and not set(row).issubset(supplied_binding_ids) for row in slots
    ):
        raise AggregationValidationError(tr("aggregation.oss_ioss.errors.detail_not_representable"))
