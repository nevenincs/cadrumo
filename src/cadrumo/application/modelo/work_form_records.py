"""Read saved repeating records through their declared export relationships.

The form consumes persisted channels, never a source query or a recalculation.
An unsupported record or an omitted legacy channel remains unknown. Typed
detail-row projection is shared with filing replay, including its normalization.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from ...domain.calculations.export_field_kind import CasillaFieldKind
from ...domain.calculations.registry.casilla_membership import text_family_casilla_ids
from ...domain.calculations.registry.export import row_binding_casilla_ids_by_field
from ...domain.calculations.registry.export_field_casilla import export_field_casilla_id
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_form_layouts import FormRepeatingGroupBlock, FormRepeatingRowSource
from ...domain.modelos.calculation_revision import CalculationRevision
from .revision_replay_inputs import revision_detail_record_binding_inputs
from .work_form_models import ModeloFormRepeatingRow, ModeloFormScalar


def _saved_value(raw: ModeloFormScalar, data_type: str) -> ModeloFormScalar:
    """Keep recorded text and zero; an invalid numeric token is an unknown cell."""
    if data_type not in {"money", "decimal", "integer"} or raw is None:
        return raw
    try:
        amount = Decimal(raw) if isinstance(raw, str | int) else raw
    except InvalidOperation:
        return None
    return None if isinstance(amount, Decimal) and not amount.is_finite() else amount


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
    records = tuple(
        (layout, record)
        for layout in snapshot.revision.export_layouts
        for record in layout.records
        if record.id == block.export_record_id
    )
    if len(records) != 1:
        return False, ()
    layout, record = records[0]
    bindings = {str(binding.id): binding for binding in snapshot.revision.bindings}
    row_casillas = row_binding_casilla_ids_by_field(snapshot.revision, layout)
    fields = tuple(
        (field, export_field_casilla_id(record, field, bindings=bindings) or row_casillas.get(field.id))
        for field in record.fields
        if field.kind in {CasillaFieldKind.BINDING, CasillaFieldKind.CASILLA, CasillaFieldKind.PROJECTION}
    )
    targets = {str(target) for _, target in fields if target is not None} & set(column_casillas)
    if not targets:
        return False, ()
    by_row: dict[int, dict[str, ModeloFormScalar]] = {}
    known = False
    casilla_targets = {
        str(target) for field, target in fields if field.kind is not CasillaFieldKind.BINDING and target is not None
    } & targets

    def put(index: int, target: str, value: ModeloFormScalar) -> None:
        by_row.setdefault(index, {})[target] = value

    for (casilla, index), value in revision.row_casilla_values.items():
        if str(casilla) in casilla_targets:
            known = True
            put(index, str(casilla), value)
    detail = (
        None
        if record.binding_record is None
        else revision_detail_record_binding_inputs(
            revision=revision, modelo=str(snapshot.modelo.id), binding_record=record.binding_record
        )
    )
    if detail is not None and "detail_rows" in revision.model_fields_set:
        known = True
    binding_rows = {**revision.row_binding_values, **(detail or {})}
    for field, target in fields:
        if field.binding is None or target is None or str(target) not in targets:
            continue
        if field.binding not in binding_rows:
            continue
        known = True
        for index, raw in binding_rows[field.binding].items():
            put(int(index), str(target), _saved_value(raw, str(field.data_type)))
    # Record-wide casilla fields (for example a substitute's identity) accompany
    # every saved row; binding-owned templates do not inherit scalar placeholders.
    for field, target in fields:
        if field.kind is not CasillaFieldKind.CASILLA or target is None or str(target) not in targets:
            continue
        if target in record.row_field_casilla_ids.values() or any(
            str(casilla) == str(target) for casilla, _ in revision.row_casilla_values
        ):
            continue
        raw = revision.input_values_by_casilla_id.get(str(target))
        if raw is None and target in text_family_casilla_ids(snapshot.revision.casillas):
            continue
        value = revision.casilla_values.get(str(target)) if raw is None else raw
        if value is None:
            continue
        for index in by_row:
            put(index, str(target), _saved_value(value, str(field.data_type)))
    return known, tuple(
        ModeloFormRepeatingRow(
            index=index, values=tuple(None if target is None else values.get(target) for target in column_casillas)
        )
        for index, values in sorted(by_row.items())
    )
