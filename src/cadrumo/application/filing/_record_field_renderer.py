"""Field-level rendering for canonical fixed-width filing records."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from ...core import CasillaId, FilingProducerKey, ResultDisposition
from ...domain.calculations.registry import (
    BindingId,
    CasillaFieldKind,
    ExportComputedKey,
    ExportDraftAttribute,
    ExportFieldDefinition,
    ExportRecordDefinition,
    RegistryValidationError,
    render_fixed_width_export_field,
)
from ...domain.filing import FilingExportError, FilingExportValidationError, ModeloDraft
from ...domain.iva import derive_sepa_marca
from ._producer_snapshot import ChargeAccountSelection, FilingProducerSnapshot, RefundAccountSelection
from ._projection import FilingRecordRenderContext
from ._record_types import ProjectionAddress, RecordRenderRow


def render_record(
    record: ExportRecordDefinition,
    *,
    draft: ModeloDraft,
    producer_values: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    casilla_values: dict[CasillaId, object],
    binding_values: dict[tuple[BindingId, int | None], object],
    row: RecordRenderRow,
    render_context: FilingRecordRenderContext | None,
    projection_values: Mapping[ProjectionAddress, object],
) -> str:
    if all(field.offset is not None for field in record.fields):
        return _render_positioned_record(
            record,
            draft=draft,
            producer_values=producer_values,
            producer_snapshot=producer_snapshot,
            casilla_values=casilla_values,
            binding_values=binding_values,
            row=row,
            render_context=render_context,
            projection_values=projection_values,
        )
    return _render_unpositioned_record(
        record,
        draft=draft,
        producer_values=producer_values,
        producer_snapshot=producer_snapshot,
        casilla_values=casilla_values,
        binding_values=binding_values,
        row=row,
        render_context=render_context,
        projection_values=projection_values,
    )


def _render_unpositioned_record(
    record: ExportRecordDefinition,
    *,
    draft: ModeloDraft,
    producer_values: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    casilla_values: dict[CasillaId, object],
    binding_values: dict[tuple[BindingId, int | None], object],
    row: RecordRenderRow,
    render_context: FilingRecordRenderContext | None,
    projection_values: Mapping[ProjectionAddress, object],
) -> str:
    return "".join(
        _render_field(
            field,
            draft=draft,
            headers=producer_values,
            producer_snapshot=producer_snapshot,
            casilla_values=casilla_values,
            binding_values=binding_values,
            row_index=row.row_index,
            render_context=render_context,
            projection_values=projection_values,
        )
        for field in record.fields
        if _field_is_active_for_row(field, row)
    )


def _render_positioned_record(
    record: ExportRecordDefinition,
    *,
    draft: ModeloDraft,
    producer_values: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    casilla_values: dict[CasillaId, object],
    binding_values: dict[tuple[BindingId, int | None], object],
    row: RecordRenderRow,
    render_context: FilingRecordRenderContext | None,
    projection_values: Mapping[ProjectionAddress, object],
) -> str:
    length = max((field.offset or 0) + (field.length or 0) - 1 for field in record.fields)
    buffer = [" "] * length
    for field in sorted(record.fields, key=lambda item: item.offset or 0):
        if not _field_is_active_for_row(field, row):
            continue
        offset = field.offset
        if offset is None:
            raise FilingExportValidationError(f"export field {field.id!r} must declare offset")
        rendered = _render_positioned_field(
            field,
            draft=draft,
            producer_values=producer_values,
            producer_snapshot=producer_snapshot,
            casilla_values=casilla_values,
            binding_values=binding_values,
            row=row,
            render_context=render_context,
            projection_values=projection_values,
        )
        start = offset - 1
        end = start + len(rendered)
        if any(char != " " for char in buffer[start:end]):
            raise FilingExportError(f"export field {field.id!r} overlaps another field")
        buffer[start:end] = rendered
    return "".join(buffer)


def _render_positioned_field(
    field: ExportFieldDefinition,
    *,
    draft: ModeloDraft,
    producer_values: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    casilla_values: dict[CasillaId, object],
    binding_values: dict[tuple[BindingId, int | None], object],
    row: RecordRenderRow,
    render_context: FilingRecordRenderContext | None,
    projection_values: Mapping[ProjectionAddress, object],
) -> str:
    if field.offset is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare offset")
    return _render_field(
        field,
        draft=draft,
        headers=producer_values,
        producer_snapshot=producer_snapshot,
        casilla_values=casilla_values,
        binding_values=binding_values,
        row_index=row.row_index,
        render_context=render_context,
        projection_values=projection_values,
    )


def _field_is_active_for_row(field: ExportFieldDefinition, row: RecordRenderRow) -> bool:
    if not row.active_binding_ids:
        return True
    if field.kind != CasillaFieldKind.BINDING:
        return True
    return field.binding in row.active_binding_ids


def _render_field(
    field: ExportFieldDefinition,
    *,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    casilla_values: dict[CasillaId, object],
    binding_values: dict[tuple[BindingId, int | None], object],
    row_index: int | None,
    render_context: FilingRecordRenderContext | None,
    projection_values: Mapping[ProjectionAddress, object],
) -> str:
    if field.length is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare length")
    raw = _field_value(
        field,
        draft=draft,
        headers=headers,
        producer_snapshot=producer_snapshot,
        casilla_values=casilla_values,
        binding_values=binding_values,
        row_index=row_index,
        render_context=render_context,
        projection_values=projection_values,
    )
    return format_field(field, raw)


def _field_value(
    field: ExportFieldDefinition,
    *,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    casilla_values: dict[CasillaId, object],
    binding_values: dict[tuple[BindingId, int | None], object],
    row_index: int | None,
    render_context: FilingRecordRenderContext | None,
    projection_values: Mapping[ProjectionAddress, object],
) -> object:
    match field.kind:
        case CasillaFieldKind.LITERAL:
            return field.literal
        case CasillaFieldKind.FILLER:
            return ""
        case CasillaFieldKind.CASILLA:
            return _casilla_field_value(field, casilla_values)
        case CasillaFieldKind.BINDING:
            return _binding_field_value(field, binding_values, row_index)
        case CasillaFieldKind.HEADER:
            return _header_field_value(field, headers)
        case CasillaFieldKind.PROJECTION:
            return projection_field_value(field, render_context, projection_values)
        case CasillaFieldKind.DRAFT:
            return _draft_value(field, draft)
        case CasillaFieldKind.COMPUTED:
            return _computed_field_value(field, draft, producer_snapshot)
        case _:
            raise FilingExportError(f"unsupported export field kind {field.kind!r}")


def _casilla_field_value(field: ExportFieldDefinition, casilla_values: dict[CasillaId, object]) -> object:
    if field.casilla_id is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare casilla_id")
    return casilla_values.get(field.casilla_id)


def _binding_field_value(
    field: ExportFieldDefinition,
    binding_values: dict[tuple[BindingId, int | None], object],
    row_index: int | None,
) -> object:
    if field.binding is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare binding")
    return binding_values.get((field.binding, row_index))


def projection_field_value(
    field: ExportFieldDefinition,
    context: FilingRecordRenderContext | None,
    values: Mapping[ProjectionAddress, object],
) -> object:
    if field.projection_ref is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare projection_ref")
    if context is None:
        raise FilingExportValidationError(
            f"export field {field.id!r} requires a snapshot-owned render context to address its projection",
        )
    address = (context.record.id, context.occurrence, field.projection_ref)
    try:
        return values[address]
    except KeyError as exc:
        raise FilingExportValidationError(f"export projection address {address!r} has no preflighted value") from exc


def _header_field_value(field: ExportFieldDefinition, headers: Mapping[FilingProducerKey, object]) -> object:
    if field.producer_key is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare producer_key")
    value = headers.get(field.producer_key)
    if field.required and (value is None or (isinstance(value, str) and not value.strip())):
        raise FilingExportValidationError(f"export producer {field.producer_key!r} is required")
    return value.strip() if isinstance(value, str) else value


def _envelope_closing_tag(draft: ModeloDraft, snapshot: FilingProducerSnapshot) -> str:
    del snapshot
    year = str(draft.period.filing_year)
    period_code = draft.period.registry_token
    return f"</T{draft.modelo}0{year}{period_code}0000>"


def _draft_filing_year(draft: ModeloDraft) -> str:
    return str(draft.period.filing_year)


def _draft_period_code(draft: ModeloDraft) -> str:
    return draft.period.registry_token


def _draft_period_start_date(draft: ModeloDraft) -> str:
    return draft.period.start_date.strftime("%d%m%Y")


def _draft_period_end_date(draft: ModeloDraft) -> str:
    return draft.period.end_date.strftime("%d%m%Y")


def _sepa_marca(draft: ModeloDraft, snapshot: FilingProducerSnapshot) -> str | None:
    del draft
    selected = snapshot.selected_account
    if isinstance(selected, ChargeAccountSelection):
        return None
    if not isinstance(selected, RefundAccountSelection):
        raise FilingExportValidationError("SEPA marker requires a selected refund account")
    return derive_sepa_marca(
        iban=selected.account.iban,
        bank_country_code=selected.account.bank_country_code,
    ).value


def complementaria_page_marker(draft: ModeloDraft, snapshot: FilingProducerSnapshot) -> str | None:
    """Render the official ``C`` page marker from amendment evidence alone."""
    del draft
    return "C" if snapshot.amendment_evidence and snapshot.amendment_evidence.is_complementaria else None


def m303_complementaria_marker(draft: ModeloDraft, snapshot: FilingProducerSnapshot) -> str | None:
    """Render the official binary amendment marker from immutable amendment evidence."""
    del draft
    return "X" if snapshot.amendment_evidence and snapshot.amendment_evidence.is_complementaria else None


def m303_no_activity_marker(draft: ModeloDraft, snapshot: FilingProducerSnapshot) -> str | None:
    """Render ``X`` only for the closed Modelo 303 no-activity disposition."""
    del draft
    return "X" if snapshot.elections.result_disposition is ResultDisposition.NEGATIVA else None


COMPUTED_VALUE_PRODUCERS: Mapping[
    ExportComputedKey,
    Callable[[ModeloDraft, FilingProducerSnapshot], str | None],
] = {
    ExportComputedKey.ENVELOPE_CLOSING_TAG: _envelope_closing_tag,
    ExportComputedKey.SEPA_MARCA: _sepa_marca,
    ExportComputedKey.M303_COMPLEMENTARIA_MARKER: m303_complementaria_marker,
    ExportComputedKey.COMPLEMENTARIA_PAGE_MARKER: complementaria_page_marker,
    ExportComputedKey.M303_NO_ACTIVITY_MARKER: m303_no_activity_marker,
}

DRAFT_VALUE_PRODUCERS: Mapping[ExportDraftAttribute, Callable[[ModeloDraft], str]] = {
    ExportDraftAttribute.FILING_YEAR: _draft_filing_year,
    ExportDraftAttribute.PERIOD_CODE: _draft_period_code,
    ExportDraftAttribute.PERIOD_START_DATE: _draft_period_start_date,
    ExportDraftAttribute.PERIOD_END_DATE: _draft_period_end_date,
}


def _computed_field_value(
    field: ExportFieldDefinition,
    draft: ModeloDraft,
    producer_snapshot: FilingProducerSnapshot,
) -> str | None:
    if field.computed_key is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare computed_key")
    return COMPUTED_VALUE_PRODUCERS[field.computed_key](draft, producer_snapshot)


def _draft_value(field: ExportFieldDefinition, draft: ModeloDraft) -> str:
    if field.draft_attribute is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare draft_attribute")
    return DRAFT_VALUE_PRODUCERS[field.draft_attribute](draft)


def format_field(field: ExportFieldDefinition, value: object) -> str:
    try:
        return render_fixed_width_export_field(field, value)
    except RegistryValidationError as exc:
        raise FilingExportValidationError(f"export field {field.id!r} cannot render its fixed-width value") from exc


__all__ = [
    "COMPUTED_VALUE_PRODUCERS",
    "DRAFT_VALUE_PRODUCERS",
    "RecordRenderRow",
    "format_field",
    "m303_complementaria_marker",
    "complementaria_page_marker",
    "m303_no_activity_marker",
    "projection_field_value",
    "render_record",
]
