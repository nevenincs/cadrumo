"""Read saved repeating records through their declared export relationships.

The form consumes persisted channels, never a source query or a recalculation.
An unsupported record or an omitted legacy channel remains unknown. Typed
detail-row projection is shared with filing replay, including its normalization.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from ...domain.calculations.export_field_kind import CasillaFieldKind
from ...domain.calculations.registry.casilla_membership import text_family_casilla_ids
from ...domain.calculations.registry.export import row_binding_casilla_ids_by_field
from ...domain.calculations.registry.export_field_casilla import export_field_casilla_id
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from ...domain.calculations.registry.schema_form_layouts import FormRepeatingGroupBlock, FormRepeatingRowSource
from ...domain.calculations.registry.schema_scalars import registry_scalar_value_type
from ...domain.filing.protocols import ModeloInputScalar
from ...domain.modelos.calculation_revision import CalculationRevision
from .revision_replay_inputs import revision_detail_record_binding_inputs
from .work_form_models import ModeloFormRepeatingRow, ModeloFormScalar
from .work_form_projection_records import saved_projection_form_records


def _saved_value(raw: ModeloFormScalar, data_type: str) -> ModeloFormScalar:
    """Keep recorded text and zero; an invalid numeric token is an unknown cell."""
    if registry_scalar_value_type(data_type) not in {"decimal", "int"} or raw is None:
        return raw
    try:
        amount = Decimal(raw) if isinstance(raw, str | int) else raw
    except InvalidOperation:
        return None
    return None if isinstance(amount, Decimal) and not amount.is_finite() else amount


def _matching_record(
    snapshot: RegistrySnapshot,
    block: FormRepeatingGroupBlock,
) -> tuple[ExportLayoutDefinition, ExportRecordDefinition] | None:
    matches = tuple(
        (layout, record)
        for layout in snapshot.revision.export_layouts
        for record in layout.records
        if record.id == block.export_record_id
    )
    return matches[0] if len(matches) == 1 else None


def _record_fields(
    snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    record: ExportRecordDefinition,
) -> tuple[tuple[ExportFieldDefinition, str | None], ...]:
    bindings = {str(binding.id): binding for binding in snapshot.revision.bindings}
    row_casillas = row_binding_casilla_ids_by_field(snapshot.revision, layout)
    return tuple(
        (
            field,
            None if target is None else str(target),
        )
        for field in record.fields
        if field.kind in {CasillaFieldKind.BINDING, CasillaFieldKind.CASILLA, CasillaFieldKind.PROJECTION}
        for target in (export_field_casilla_id(record, field, bindings=bindings) or row_casillas.get(field.id),)
    )


def _target_columns(
    fields: tuple[tuple[ExportFieldDefinition, str | None], ...],
    column_casillas: tuple[str | None, ...],
) -> tuple[set[str], set[str]]:
    columns = set(column_casillas)
    targets = {target for _, target in fields if target is not None} & columns
    casilla_targets = {
        target for field, target in fields if field.kind is not CasillaFieldKind.BINDING and target is not None
    } & targets
    return targets, casilla_targets


def _put_row_value(
    by_row: dict[int, dict[str, ModeloFormScalar]], index: int, target: str, value: ModeloFormScalar
) -> None:
    by_row.setdefault(index, {})[target] = value


def _saved_casilla_rows(
    revision: CalculationRevision,
    casilla_targets: set[str],
    by_row: dict[int, dict[str, ModeloFormScalar]],
) -> bool:
    known = False
    for (casilla, index), value in revision.row_casilla_values.items():
        if str(casilla) not in casilla_targets:
            continue
        known = True
        _put_row_value(by_row, index, str(casilla), value)
    return known


def _detail_binding_rows(
    snapshot: RegistrySnapshot,
    revision: CalculationRevision,
    record: ExportRecordDefinition,
) -> dict[BindingId, dict[str, ModeloInputScalar]] | None:
    if record.binding_record is None:
        return None
    return revision_detail_record_binding_inputs(
        revision=revision,
        modelo=str(snapshot.modelo.id),
        binding_record=record.binding_record,
    )


def _add_binding_field_rows(
    field: ExportFieldDefinition,
    target: str,
    binding_rows: Mapping[BindingId, Mapping[str, ModeloFormScalar]],
    by_row: dict[int, dict[str, ModeloFormScalar]],
    data_type: str,
) -> bool:
    if field.binding is None or field.binding not in binding_rows:
        return False
    values = binding_rows[field.binding]
    for index, raw in values.items():
        _put_row_value(by_row, int(index), target, _saved_value(raw, data_type))
    return True


def _saved_binding_rows(
    revision: CalculationRevision,
    detail: dict[BindingId, dict[str, ModeloInputScalar]] | None,
    fields: tuple[tuple[ExportFieldDefinition, str | None], ...],
    targets: set[str],
    by_row: dict[int, dict[str, ModeloFormScalar]],
    casilla_data_types: Mapping[str, str],
) -> bool:
    binding_rows: dict[BindingId, Mapping[str, ModeloFormScalar]] = {}
    binding_rows.update(revision.row_binding_values)
    if detail is not None:
        binding_rows.update(detail)
    known = False
    for field, target in fields:
        if target is None or target not in targets:
            continue
        # Human values follow the casilla, not its wire encoding: province
        # "08" stays text, while money in a signed text slot stays numeric.
        data_type = casilla_data_types.get(target, str(field.data_type))
        known = _add_binding_field_rows(field, target, binding_rows, by_row, data_type) or known
    return known


def _record_wide_value(
    revision: CalculationRevision,
    target: str,
    data_type: str,
    text_casillas: frozenset[str],
) -> ModeloFormScalar | None:
    raw = revision.input_values_by_casilla_id.get(target)
    if raw is None and target in text_casillas:
        return None
    value = revision.casilla_values.get(target) if raw is None else raw
    return None if value is None else _saved_value(value, data_type)


def _needs_record_wide_fallback(
    revision: CalculationRevision,
    field: ExportFieldDefinition,
    target: str | None,
    targets: set[str],
    row_field_targets: set[str],
) -> bool:
    return (
        field.kind is CasillaFieldKind.CASILLA
        and target is not None
        and target in targets
        and target not in row_field_targets
        and not any(str(casilla) == target for casilla, _ in revision.row_casilla_values)
    )


def _add_record_wide_casillas(
    revision: CalculationRevision,
    record: ExportRecordDefinition,
    fields: tuple[tuple[ExportFieldDefinition, str | None], ...],
    targets: set[str],
    text_casillas: frozenset[str],
    by_row: dict[int, dict[str, ModeloFormScalar]],
) -> None:
    row_field_targets = {str(target) for target in record.row_field_casilla_ids.values()}
    for field, target in fields:
        if target is None or not _needs_record_wide_fallback(revision, field, target, targets, row_field_targets):
            continue
        value = _record_wide_value(revision, target, str(field.data_type), text_casillas)
        if value is None:
            continue
        for index in by_row:
            _put_row_value(by_row, index, target, value)


def _rows_from_values(
    by_row: dict[int, dict[str, ModeloFormScalar]],
    column_casillas: tuple[str | None, ...],
) -> tuple[ModeloFormRepeatingRow, ...]:
    return tuple(
        ModeloFormRepeatingRow(
            index=index,
            values=tuple(None if target is None else values.get(target) for target in column_casillas),
        )
        for index, values in sorted(by_row.items())
    )


def saved_form_records(
    *,
    snapshot: RegistrySnapshot,
    revision: CalculationRevision | None,
    block: FormRepeatingGroupBlock,
    column_casillas: tuple[str | None, ...],
) -> tuple[bool, tuple[ModeloFormRepeatingRow, ...]]:
    """Read a :class:`CalculationRevision` through a :class:`RegistrySnapshot` record.

    The boolean establishes whether a supported saved channel records the rows.
    Explicitly recorded empty detail families are known-empty; an absent legacy
    field, unsupported projection or unresolved record is unknown. Indices are
    never renumbered. Detail-row bindings take the same precedence over saved
    row bindings as filing replay; a binding field reads its binding channel.
    """
    if revision is None or block.row_source is not FormRepeatingRowSource.EXPORT_RECORD:
        return False, ()
    if any(column.export_field_id is not None for column in block.columns):
        return saved_projection_form_records(snapshot=snapshot, revision=revision, block=block)
    matched = _matching_record(snapshot, block)
    if matched is None:
        return False, ()
    layout, record = matched
    fields = _record_fields(snapshot, layout, record)
    visible_targets, _ = _target_columns(fields, column_casillas)
    if not visible_targets:
        return False, ()
    # Sections may show only unknown fields of an otherwise saved record.
    # Discover rows across this exact record before projecting its visible
    # columns, so every section preserves the same recipient indices.
    targets, casilla_targets = _target_columns(fields, tuple(target for _, target in fields))

    by_row: dict[int, dict[str, ModeloFormScalar]] = {}
    known = _saved_casilla_rows(revision, casilla_targets, by_row)
    detail = _detail_binding_rows(snapshot, revision, record)
    if detail is not None and "detail_rows" in revision.model_fields_set:
        known = True
    text_casillas = text_family_casilla_ids(snapshot.revision.casillas)
    casilla_data_types = {str(casilla.id): str(casilla.data_type) for casilla in snapshot.revision.casillas}
    known = _saved_binding_rows(revision, detail, fields, targets, by_row, casilla_data_types) or known
    _add_record_wide_casillas(
        revision,
        record,
        fields,
        targets,
        text_casillas,
        by_row,
    )
    return known, _rows_from_values(by_row, column_casillas)
