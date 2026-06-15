"""Resolved export layouts for registry-backed AEAT record designs.

Resolves export layouts declared on a :class:`ModeloRevision` and verifies
them against a :class:`RegistrySnapshot`. The resolved layout is a
``ResolvedExportLayout`` ready for fixed-width filing assembly.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Literal, TypeGuard

from ....core.aggregation import BindingAggregationOp
from ._binding_aggregation import binding_aggregation_op
from ._errors import RegistryValidationError
from ._ids import CasillaId, ExportFieldId
from ._schema import (
    CasillaFieldKind,
    DataBindingDefinition,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    ModeloRevision,
    RegistryModel,
    RegistrySnapshot,
)

_BindingExportDataType = Literal["text", "integer", "decimal", "money", "date", "boolean"]
_ExportPadding = Literal["left_zero", "left_space", "right_space", "none"]
_ExportJustification = Literal["left", "right", "none"]


class ResolvedExportLayout(RegistryModel):
    """A selected, validated export layout ready for read-only filing assembly."""

    layout: ExportLayoutDefinition
    ordered_fields: tuple[ExportFieldDefinition, ...]
    fields_by_id: Mapping[ExportFieldId, ExportFieldDefinition]
    fields_by_casilla: Mapping[CasillaId, tuple[ExportFieldDefinition, ...]]


def resolve_export_layout(snapshot: RegistrySnapshot, layout_id: str | None = None) -> ResolvedExportLayout:
    """Resolve one export layout from a validated registry snapshot.

    Args:
        snapshot: The :class:`RegistrySnapshot` to resolve the layout from.
        layout_id: Identifier of the export layout to resolve. May be ``None``
            when the revision declares exactly one layout; otherwise required
            to disambiguate.

    Returns:
        The :class:`ResolvedExportLayout` for the selected layout.
    """
    layouts = snapshot.revision.export_layouts
    if not layouts:
        raise RegistryValidationError(f"modelo {snapshot.modelo.id} revision {snapshot.revision.id} has no exports")
    if layout_id is None:
        if len(layouts) != 1:
            available = sorted(layout.id for layout in layouts)
            raise RegistryValidationError(f"export layout id is required; available layouts: {available!r}")
        layout = layouts[0]
    else:
        matches = [candidate for candidate in layouts if candidate.id == layout_id]
        if not matches:
            available = sorted(candidate.id for candidate in layouts)
            raise RegistryValidationError(f"unknown export layout {layout_id!r}; available layouts: {available!r}")
        layout = matches[0]

    _verify_layout_evidence(snapshot, layout)
    fields = _ordered_fields(layout)
    fields_by_id = _index_fields(layout, fields)
    fields_by_casilla = _index_fields_by_casilla(snapshot, fields)
    _verify_record_offsets(layout)
    return ResolvedExportLayout(
        layout=layout,
        ordered_fields=fields,
        fields_by_id=fields_by_id,
        fields_by_casilla=fields_by_casilla,
    )


def derive_export_layouts_from_bindings(revision: ModeloRevision) -> tuple[ExportLayoutDefinition, ...]:
    """Return revision export layouts with binding-derived fields resolved.

    Some official AEAT record designs expose structured filing records that are
    already represented as registry bindings. In those cases the export layout
    declares the record-level intent via ``binding_record`` and this resolver
    derives field coordinates from the binding selectors instead of requiring a
    second coordinate table in TOML.

    Args:
        revision: The :class:`ModeloRevision` whose export layouts and bindings
            are used to derive the resolved field coordinates.

    Returns:
        Tuple of :class:`ExportLayoutDefinition` with binding-derived fields populated.
    """
    if not revision.export_layouts:
        return ()
    bindings_by_record: dict[str, list[DataBindingDefinition]] = {}
    for binding in revision.bindings:
        binding_record_id = binding.selector.get("record")
        if not isinstance(binding_record_id, str):
            continue
        bindings_by_record.setdefault(binding_record_id, []).append(binding)

    resolved_layouts: list[ExportLayoutDefinition] = []
    for layout in revision.export_layouts:
        resolved_records: list[ExportRecordDefinition] = []
        for record in layout.records:
            if record.binding_record is None:
                resolved_records.append(record)
                continue
            derived = tuple(
                sorted(
                    _export_fields_from_record_bindings(record, bindings_by_record.get(record.binding_record, [])),
                    key=lambda field: (field.offset, field.id),
                ),
            )
            base_fields = tuple(
                field
                for field in record.fields
                if not any(_export_fields_overlap(field, derived_field) for derived_field in derived)
            )
            resolved_records.append(record.model_copy(update={"fields": (*base_fields, *derived)}))
        resolved_layouts.append(layout.model_copy(update={"records": tuple(resolved_records)}))
    return tuple(resolved_layouts)


def _export_fields_overlap(left: ExportFieldDefinition, right: ExportFieldDefinition) -> bool:
    if left.offset is None or left.length is None or right.offset is None or right.length is None:
        return False
    left_end = left.offset + left.length - 1
    right_end = right.offset + right.length - 1
    return left.offset <= right_end and right.offset <= left_end


def _export_fields_from_record_bindings(
    record: ExportRecordDefinition,
    bindings: Sequence[DataBindingDefinition],
) -> tuple[ExportFieldDefinition, ...]:
    fields: list[ExportFieldDefinition] = []
    for binding in bindings:
        if "offset" in binding.selector and "length" in binding.selector:
            fields.append(_export_field_from_binding(record, binding))
            continue
        field = _export_field_from_row_binding(record, binding)
        if field is not None:
            fields.append(field)
    return tuple(fields)


def _export_field_from_row_binding(
    record: ExportRecordDefinition,
    binding: DataBindingDefinition,
) -> ExportFieldDefinition | None:
    if binding_aggregation_op(binding) != BindingAggregationOp.ROWS:
        return None
    if record.binding_record is None:
        return None
    row_field = binding.selector.get("row_field")
    if not isinstance(row_field, str):
        return None
    casilla = record.row_field_casillas.get(row_field)
    if casilla is None:
        raise RegistryValidationError(
            f"export record {record.id!r} binding {binding.id!r} row_field {row_field!r}"
            " has no casilla mapping in row_field_casillas",
        )
    # Pattern A: the record already hand-authors a kind="binding" field pinned
    # to this binding id — trust the operator-pinned offset/length and skip
    # derivation. base_fields will pass the hand-authored field through.
    if any(field.kind == CasillaFieldKind.BINDING and field.binding == binding.id for field in record.fields):
        return None
    # Pattern B: a kind="casilla" template field exists for this casilla — derive
    # a binding-kind field by copying the template's offset/length/data_type.
    template = next(
        (field for field in record.fields if field.kind == CasillaFieldKind.CASILLA and field.casilla == casilla),
        None,
    )
    if template is None:
        raise RegistryValidationError(
            f"export record {record.id!r} binding {binding.id!r} casilla {casilla!r}"
            " has no matching template field in the record",
        )
    return template.model_copy(
        update={
            "id": f"{record.id}.{binding.id}",
            "kind": CasillaFieldKind.BINDING,
            "casilla": None,
            "binding": binding.id,
            "legal_refs": binding.legal_refs,
            "source_refs": binding.source_refs,
        },
    )


def _export_field_from_binding(
    record: ExportRecordDefinition,
    binding: DataBindingDefinition,
) -> ExportFieldDefinition:
    selector = binding.selector
    data_type = _binding_data_type(binding, selector.get("data_type"))
    return ExportFieldDefinition(
        id=f"{record.id}.{binding.id}",
        offset=_selector_int(binding, "offset"),
        length=_selector_int(binding, "length"),
        kind=CasillaFieldKind.BINDING,
        binding=binding.id,
        data_type=data_type,
        required=False,
        padding=_padding_for_binding_data_type(data_type),
        justification=_justification_for_binding_data_type(data_type),
        signed=False,
        legal_refs=binding.legal_refs,
        source_refs=binding.source_refs,
    )


def _selector_int(binding: DataBindingDefinition, key: str) -> int:
    value = binding.selector.get(key)
    if isinstance(value, tuple) or value is None:
        raise RegistryValidationError(f"binding {binding.id!r} selector {key!r} must be numeric")
    if isinstance(value, Decimal):
        return int(value)
    return int(value)


def _is_binding_export_data_type(value: str) -> TypeGuard[_BindingExportDataType]:
    return value in {"text", "integer", "decimal", "money", "date", "boolean"}


def _binding_data_type(binding: DataBindingDefinition, value: object) -> _BindingExportDataType:
    if not isinstance(value, str) or not _is_binding_export_data_type(value):
        raise RegistryValidationError(f"binding {binding.id!r} selector data_type is not exportable")
    return value


def _padding_for_binding_data_type(data_type: _BindingExportDataType) -> _ExportPadding:
    if data_type in {"money", "integer", "decimal"}:
        return "left_zero"
    return "right_space"


def _justification_for_binding_data_type(data_type: _BindingExportDataType) -> _ExportJustification:
    if data_type in {"money", "integer", "decimal"}:
        return "right"
    return "left"


def export_fields_for_casilla(resolved: ResolvedExportLayout, casilla_id: str) -> tuple[ExportFieldDefinition, ...]:
    """Return all :class:`ExportFieldDefinition` entries mapped to ``casilla_id``."""
    return resolved.fields_by_casilla.get(casilla_id, ())


def _verify_layout_evidence(snapshot: RegistrySnapshot, layout: ExportLayoutDefinition) -> None:
    missing_legal = sorted(ref for ref in layout.legal_refs if ref not in snapshot.legal)
    missing_sources = sorted(ref for ref in layout.source_refs if ref not in snapshot.sources)
    if missing_legal:
        raise RegistryValidationError(f"export layout {layout.id!r} has unresolved legal refs: {missing_legal!r}")
    if missing_sources:
        raise RegistryValidationError(f"export layout {layout.id!r} has unresolved source refs: {missing_sources!r}")


def _ordered_fields(layout: ExportLayoutDefinition) -> tuple[ExportFieldDefinition, ...]:
    ordered: list[ExportFieldDefinition] = []
    for record in sorted(layout.records, key=lambda item: item.order):
        ordered.extend(sorted(record.fields, key=lambda item: (-1 if item.offset is None else item.offset, item.id)))
    return tuple(ordered)


def _index_fields(
    layout: ExportLayoutDefinition,
    fields: tuple[ExportFieldDefinition, ...],
) -> dict[str, ExportFieldDefinition]:
    fields_by_id: dict[str, ExportFieldDefinition] = {}
    for field in fields:
        if field.id in fields_by_id:
            raise RegistryValidationError(f"export layout {layout.id!r} has duplicate field id {field.id!r}")
        fields_by_id[field.id] = field
    return fields_by_id


def _index_fields_by_casilla(
    snapshot: RegistrySnapshot,
    fields: tuple[ExportFieldDefinition, ...],
) -> dict[str, tuple[ExportFieldDefinition, ...]]:
    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    grouped: dict[str, list[ExportFieldDefinition]] = {}
    for field in fields:
        if field.casilla is None:
            continue
        if field.casilla not in casillas:
            raise RegistryValidationError(f"export field {field.id!r} references unknown casilla {field.casilla!r}")
        casilla = casillas[field.casilla]
        if field.id not in casilla.export_refs:
            raise RegistryValidationError(
                f"export field {field.id!r} points to casilla {field.casilla!r}, "
                "but the casilla does not declare the export ref",
            )
        grouped.setdefault(field.casilla, []).append(field)
    return {casilla_id: tuple(casilla_fields) for casilla_id, casilla_fields in grouped.items()}


def _verify_record_offsets(layout: ExportLayoutDefinition) -> None:
    for record in layout.records:
        ranges = _record_field_ranges(record)
        _reject_overlapping_ranges(record.id, sorted(ranges))


def _record_field_ranges(record: ExportRecordDefinition) -> list[tuple[int, int, str]]:
    """Return ``(start, end, field_id)`` for every offset-bearing field in ``record``.

    A field is offset-bearing when it declares both ``offset`` and
    ``length``. Declaring exactly one of the two is rejected up front;
    declaring neither marks the field as logical-only (e.g. an
    envelope-segment header that does not occupy a fixed-width slot).
    """
    ranges: list[tuple[int, int, str]] = []
    for field in record.fields:
        if field.offset is None and field.length is None:
            continue
        if field.offset is None or field.length is None:
            raise RegistryValidationError(
                f"export field {field.id!r} must declare both offset and length for fixed-width layouts",
            )
        ranges.append((field.offset, field.offset + field.length, field.id))
    return ranges


def _reject_overlapping_ranges(record_id: str, sorted_ranges: list[tuple[int, int, str]]) -> None:
    """Reject any pair of byte ranges that overlap. ``sorted_ranges`` must be sorted by start."""
    for index, current in enumerate(sorted_ranges):
        for other in sorted_ranges[index + 1 :]:
            if current[1] <= other[0]:
                break
            raise RegistryValidationError(f"export record {record_id!r} fields {current[2]!r} and {other[2]!r} overlap")


__all__ = [
    "ExportFieldDefinition",
    "ExportLayoutDefinition",
    "ExportRecordDefinition",
    "ResolvedExportLayout",
    "derive_export_layouts_from_bindings",
    "export_fields_for_casilla",
    "resolve_export_layout",
]
