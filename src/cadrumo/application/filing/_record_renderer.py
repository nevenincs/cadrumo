"""Canonical fixed-width filing record renderer."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...core.decimal._coerce import coerce_decimal
from ...core.filing_producer_key import FilingProducerKey
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...domain.calculations.export_field_kind import CasillaFieldKind
from ...domain.calculations.registry.export import export_fields_overlap
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from ...domain.filing.errors import FilingExportValidationError
from ...domain.filing.schema import ModeloDraft
from ._export_parity import did_page_suppressed
from ._producer_snapshot import FilingProducerSnapshot
from ._projection import FilingProjectionPlan, FilingRecordRenderContext
from ._record_field_renderer import (
    COMPUTED_VALUE_PRODUCERS,
    DRAFT_VALUE_PRODUCERS,
    complementaria_page_marker,
    format_field,
    m303_complementaria_marker,
    m303_no_activity_marker,
    projection_field_value,
    render_record,
)
from ._record_types import ProjectionAddress, RecordRenderRow, RenderedRecordOccurrence

_COMPUTED_VALUE_PRODUCERS = COMPUTED_VALUE_PRODUCERS
_DRAFT_VALUE_PRODUCERS = DRAFT_VALUE_PRODUCERS
_RecordRenderRow = RecordRenderRow
_RenderedRecordOccurrence = RenderedRecordOccurrence
_format_field = format_field
_m303_complementaria_marker = m303_complementaria_marker
_complementaria_page_marker = complementaria_page_marker
_m303_no_activity_marker = m303_no_activity_marker
_projection_field_value = projection_field_value
_render_record = render_record


def render_layout_records(
    layout: ExportLayoutDefinition,
    *,
    registry_snapshot: RegistrySnapshot,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    prior_domiciliation_election: PriorDomiciliationElection,
    casilla_values: dict[CasillaId, object],
    binding_values: dict[tuple[BindingId, int | None], object],
    projection_plan: FilingProjectionPlan,
    projection_values: dict[ProjectionAddress, object],
) -> tuple[RenderedRecordOccurrence, ...]:
    """Render admitted records after projection preflight has passed."""
    occurrences: list[RenderedRecordOccurrence] = []
    for record in sorted(layout.records, key=lambda item: item.order):
        if did_page_suppressed(
            record,
            draft=draft,
            headers=headers,
            prior_domiciliation_election=prior_domiciliation_election,
        ):
            continue
        rows = _render_rows_for_record(
            record,
            layout=layout,
            registry_snapshot=registry_snapshot,
            binding_values=binding_values,
            casilla_values=casilla_values,
            projection_plan=projection_plan,
        )
        if record.required and not rows:
            raise FilingExportValidationError(f"required export record {record.id!r} has no applicable occurrence")
        for row, context in rows:
            _guard_record_export(record, casilla_values=casilla_values)
            occurrences.append(
                RenderedRecordOccurrence(
                    record_id=record.id,
                    occurrence=context.occurrence,
                    payload=_render_record_bytes(
                        record,
                        draft=draft,
                        headers=headers,
                        producer_snapshot=producer_snapshot,
                        casilla_values=casilla_values,
                        binding_values=binding_values,
                        row=row,
                        render_context=context,
                        projection_values=projection_values,
                    ),
                )
            )
    return tuple(occurrences)


def _render_rows_for_record(
    record: ExportRecordDefinition,
    *,
    layout: ExportLayoutDefinition,
    registry_snapshot: RegistrySnapshot,
    binding_values: dict[tuple[BindingId, int | None], object],
    casilla_values: dict[CasillaId, object],
    projection_plan: FilingProjectionPlan,
) -> tuple[tuple[RecordRenderRow, FilingRecordRenderContext], ...]:
    if record.repeat == "projection_rows":
        return tuple(
            (RecordRenderRow(row_index=None, active_binding_ids=frozenset()), context)
            for context in projection_plan.contexts
            if context.record is record
        )
    return tuple(
        (
            row,
            FilingRecordRenderContext(
                registry_snapshot=registry_snapshot,
                layout=layout,
                record=record,
                occurrence=occurrence,
            ),
        )
        for occurrence, row in enumerate(_record_render_rows(record, binding_values, casilla_values), 1)
    )


def _render_record_bytes(
    record: ExportRecordDefinition,
    *,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    casilla_values: dict[CasillaId, object],
    binding_values: dict[tuple[BindingId, int | None], object],
    row: RecordRenderRow,
    render_context: FilingRecordRenderContext,
    projection_values: dict[ProjectionAddress, object],
) -> bytes:
    text = render_record(
        record,
        draft=draft,
        producer_values=headers,
        producer_snapshot=producer_snapshot,
        casilla_values=casilla_values,
        binding_values=binding_values,
        row=row,
        render_context=render_context,
        projection_values=projection_values,
    )
    line_ending = {"crlf": "\r\n", "lf": "\n"}.get(record.line_ending, "")
    return f"{text}{line_ending}".encode(record.encoding)


def _record_render_rows(
    record: ExportRecordDefinition,
    binding_values: dict[tuple[BindingId, int | None], object],
    casilla_values: dict[CasillaId, object],
) -> tuple[RecordRenderRow, ...]:
    if record.repeat != "binding_rows":
        return _single_record_render_row(record, binding_values, casilla_values)
    return _binding_record_render_rows(record, binding_values)


def _single_record_render_row(
    record: ExportRecordDefinition,
    binding_values: dict[tuple[BindingId, int | None], object],
    casilla_values: dict[CasillaId, object],
) -> tuple[RecordRenderRow, ...]:
    """Emit the one occurrence of a non-repeating record, unless it carries nothing.

    A fixed record deriving fields from a ``binding_record`` is suppressed only
    when it would carry NO operator data at all. Both channels must be consulted,
    because a page can mix them: Modelo 390's pagina 7 files eleven apartado 11
    casillas alongside the apartado 12 prorrata bindings. Testing the binding
    channel alone drops that page for every declarant who has operaciones
    especificas but no prorrata -- and where the record is ``required``, turns the
    whole export into a refusal rather than a silent omission.

    Literal and structural fields deliberately do NOT keep a page alive: an
    otherwise-empty page carrying only its own identifier constants is exactly
    the page this suppression exists to leave out of the fichero.
    """
    if record.record_type == "t3690-estruc-gral":
        return (RecordRenderRow(row_index=None, active_binding_ids=frozenset()),)
    if (
        record.binding_record is not None
        and not _record_has_binding_value(record, binding_values)
        and not _record_has_casilla_value(record, casilla_values)
    ):
        return ()
    return (RecordRenderRow(row_index=None, active_binding_ids=frozenset()),)


def _binding_record_render_rows(
    record: ExportRecordDefinition,
    binding_values: dict[tuple[BindingId, int | None], object],
) -> tuple[RecordRenderRow, ...]:
    binding_fields = _record_binding_fields(record)
    row_indexes = _binding_row_indexes(binding_fields, binding_values)
    return tuple(
        row
        for row_index in row_indexes
        for row in _binding_record_rows_for_index(binding_fields, binding_values, row_index)
    )


def _binding_row_indexes(
    binding_fields: tuple[ExportFieldDefinition, ...],
    binding_values: dict[tuple[BindingId, int | None], object],
) -> tuple[int, ...]:
    return tuple(
        sorted(
            {
                row_index
                for binding_id, row_index in binding_values
                if row_index is not None
                and any(field.binding == binding_id for field in binding_fields)
                and _is_active_binding_value(binding_values[(binding_id, row_index)])
            },
        ),
    )


def _binding_record_rows_for_index(
    binding_fields: tuple[ExportFieldDefinition, ...],
    binding_values: dict[tuple[BindingId, int | None], object],
    row_index: int,
) -> tuple[RecordRenderRow, ...]:
    active_fields = tuple(
        field
        for field in binding_fields
        if field.binding is not None and _is_active_binding_value(binding_values.get((field.binding, row_index)))
    )
    return tuple(
        RecordRenderRow(
            row_index=row_index,
            active_binding_ids=frozenset(field.binding for field in group if field.binding is not None),
        )
        for group in _compatible_binding_field_groups(active_fields)
    )


def preflight_projection_plan(plan: FilingProjectionPlan) -> dict[ProjectionAddress, object]:
    """Prove an exact admitted/produced projection bijection before any bytes."""
    context_addresses = tuple((context.record.id, context.occurrence) for context in plan.contexts)
    _raise_duplicate_projection_addresses(
        context_addresses,
        message="filing projection plan contains duplicate record occurrences",
    )
    expected_fields = _expected_projection_fields(plan.contexts)
    produced_addresses = tuple((value.record_id, value.occurrence, value.projection_ref) for value in plan.values)
    _raise_duplicate_projection_addresses(
        produced_addresses,
        message="filing projectors produced duplicate projection addresses",
    )
    expected = frozenset(expected_fields)
    actual = frozenset(produced_addresses)
    _require_exact_projection_addresses(expected, actual)
    values: dict[ProjectionAddress, object] = {
        address: value.value for address, value in zip(produced_addresses, plan.values, strict=True)
    }
    _validate_projection_values(expected_fields, values)
    return values


def _duplicate_projection_addresses(addresses: tuple[object, ...]) -> tuple[object, ...]:
    return tuple(address for address, count in Counter(addresses).items() if count > 1)


def _raise_duplicate_projection_addresses(addresses: tuple[object, ...], *, message: str) -> None:
    duplicates = _duplicate_projection_addresses(addresses)
    if duplicates:
        raise FilingExportValidationError(f"{message}: {duplicates!r}")


def _expected_projection_fields(
    contexts: tuple[FilingRecordRenderContext, ...],
) -> dict[ProjectionAddress, ExportFieldDefinition]:
    expected_fields: dict[ProjectionAddress, ExportFieldDefinition] = {}
    for context in contexts:
        for field in context.record.fields:
            if field.kind is not CasillaFieldKind.PROJECTION or field.projection_ref is None:
                continue
            address = (context.record.id, context.occurrence, field.projection_ref)
            if address in expected_fields:
                raise FilingExportValidationError(f"filing layout admits duplicate projection address {address!r}")
            expected_fields[address] = field
    return expected_fields


def _require_exact_projection_addresses(
    expected: frozenset[ProjectionAddress],
    actual: frozenset[ProjectionAddress],
) -> None:
    if actual != expected:
        missing = tuple(sorted(repr(address) for address in expected - actual))
        extraneous = tuple(sorted(repr(address) for address in actual - expected))
        raise FilingExportValidationError(
            f"filing projection plan is not an exact layout bijection; missing={missing!r}, extraneous={extraneous!r}",
        )


def _validate_projection_values(
    expected_fields: dict[ProjectionAddress, ExportFieldDefinition],
    values: dict[ProjectionAddress, object],
) -> None:
    for address, field in expected_fields.items():
        format_field(field, values[address])


def _record_binding_fields(record: ExportRecordDefinition) -> tuple[ExportFieldDefinition, ...]:
    return tuple(
        field for field in record.fields if field.kind == CasillaFieldKind.BINDING and field.binding is not None
    )


def _is_active_binding_value(value: object) -> bool:
    return value is not None and value != ""


def _compatible_binding_field_groups(
    fields: tuple[ExportFieldDefinition, ...],
) -> tuple[tuple[ExportFieldDefinition, ...], ...]:
    groups: list[list[ExportFieldDefinition]] = []
    for field in sorted(fields, key=lambda item: (item.offset or 0, str(item.id))):
        for group in groups:
            if not any(export_fields_overlap(field, existing) for existing in group):
                group.append(field)
                break
        else:
            groups.append([field])
    return tuple(tuple(group) for group in groups)


def _record_has_binding_value(
    record: ExportRecordDefinition,
    binding_values: dict[tuple[BindingId, int | None], object],
) -> bool:
    binding_ids = {field.binding for field in _record_binding_fields(record)}
    return any(
        binding_id in binding_ids and value not in {None, ""} for (binding_id, _), value in binding_values.items()
    )


def _record_has_casilla_value(
    record: ExportRecordDefinition,
    casilla_values: dict[CasillaId, object],
) -> bool:
    return any(
        field.kind == CasillaFieldKind.CASILLA
        and field.casilla_id is not None
        and casilla_values.get(field.casilla_id) not in {None, ""}
        for field in record.fields
    )


def _guard_record_export(record: ExportRecordDefinition, *, casilla_values: dict[CasillaId, object]) -> None:
    if record.requires_positive_casilla_id is None:
        return
    raw = casilla_values.get(record.requires_positive_casilla_id)
    amount = coerce_decimal(raw, default=Decimal("0")) or Decimal("0")
    if amount <= 0:
        raise FilingExportValidationError(
            f"export record {record.id!r} requires positive casilla {record.requires_positive_casilla_id!r}",
        )


__all__ = [
    "_COMPUTED_VALUE_PRODUCERS",
    "_DRAFT_VALUE_PRODUCERS",
    "RecordRenderRow",
    "RenderedRecordOccurrence",
    "_RecordRenderRow",
    "_RenderedRecordOccurrence",
    "_complementaria_page_marker",
    "_format_field",
    "_m303_complementaria_marker",
    "_m303_no_activity_marker",
    "_projection_field_value",
    "_render_record",
    "complementaria_page_marker",
    "format_field",
    "m303_complementaria_marker",
    "m303_no_activity_marker",
    "preflight_projection_plan",
    "projection_field_value",
    "render_layout_records",
    "render_record",
]
