"""Field-level rendering for canonical fixed-width filing records."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from ...core.casilla_id import CasillaId
from ...core.filing_producer_key import FilingProducerKey
from ...core.operator_action_enums import NoRecoveryOutcome
from ...core.result_disposition import ResultDisposition
from ...domain.calculations.export_field_kind import CasillaFieldKind
from ...domain.calculations.registry.errors import (
    FixedWidthUnrepresentableCharacterError,
    FixedWidthValueOverflowError,
    RegistryValidationError,
)
from ...domain.calculations.registry.export import export_fields_overlap
from ...domain.calculations.registry.export_scheme_period import contradicts_scheme_period, scheme_period_value
from ...domain.calculations.registry.export_semantics import ExportComputedKey, ExportDraftAttribute
from ...domain.calculations.registry.fixed_width_codec import (
    render_empty_block_slot,
    render_fixed_width_export_field,
)
from ...domain.calculations.registry.form_codes import resolve_form_codes
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from ...domain.filing.errors import (
    FilingExportDesignIntegrityError,
    FilingExportFieldUnrenderableError,
    FilingExportIntegrityError,
    FilingExportUnrepresentableCharacterError,
    FilingExportValidationError,
    FilingExportValueOverflowError,
)
from ...domain.filing.schema import ModeloDraft
from ...domain.iva.sepa_marca import derive_sepa_marca
from ...domain.modelos.perceptor_clave_scope import PerceptorClaveScope
from .errors import FilingPreconditionCondition, filing_no_recovery_verdict
from .m190_context_validation import require_m190_signed_reintegro_context
from .m193_context_validation import require_m193_perceptor_devengo_context
from .m280_context_validation import m280_contextual_sign_byte, m280_key_wire, require_m280_negative_imputation_context
from .producer_snapshot import ChargeAccountSelection, FilingProducerSnapshot, RefundAccountSelection
from .projection import FilingRecordRenderContext
from .record_types import ProjectionAddress, RecordRenderRow

_FORM_ROW_CODES_FACT = "form-row-codes"


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
    source_digests: Mapping[str, str] | None = None,
    clave_scope: PerceptorClaveScope | None = None,
) -> str:
    """Render one registry record, positioned when every field declares an offset.

    Core types:
    :class:`~cadrumo.domain.filing.schema.ModeloDraft`.
    """
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
            source_digests=source_digests,
            clave_scope=clave_scope,
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
            record=record,
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
    source_digests: Mapping[str, str] | None,
    clave_scope: PerceptorClaveScope | None,
) -> str:
    length = max((field.offset or 0) + (field.length or 0) - 1 for field in record.fields)
    buffer = [" "] * length
    for field in sorted(record.fields, key=lambda item: item.offset or 0):
        active_for_row = _field_is_active_for_row(field, row)
        if _skip_inactive_alternative(field, record, active_for_row):
            # An inactive alternative must not overwrite another binding's
            # slot. An unambiguous absent slot still needs its declared fill.
            continue
        start, rendered = _render_positioned_field_bytes(
            record,
            field,
            buffer,
            draft=draft,
            producer_values=producer_values,
            producer_snapshot=producer_snapshot,
            casilla_values=casilla_values,
            binding_values=binding_values if active_for_row else {},
            row=row,
            render_context=render_context,
            projection_values=projection_values,
            source_digests=source_digests,
        )
        end = start + len(rendered)
        if any(char != " " for char in buffer[start:end]):
            raise FilingExportIntegrityError(
                f"export field {field.id!r} overlaps another field",
                translated_message="errors.integrity.filing_export_field_overlap",
                context={"field": field.id},
            )
        buffer[start:end] = rendered
    wire = "".join(buffer)
    require_m190_signed_reintegro_context(record, wire, clave_scope=clave_scope, source_digests=source_digests)
    require_m193_perceptor_devengo_context(record, wire)
    require_m280_negative_imputation_context(record, wire, source_digests=source_digests)
    return wire


def _skip_inactive_alternative(
    field: ExportFieldDefinition,
    record: ExportRecordDefinition,
    active_for_row: bool,
) -> bool:
    return not active_for_row and any(
        export_fields_overlap(field, other) for other in record.fields if other is not field
    )


def _render_positioned_field_bytes(
    record: ExportRecordDefinition,
    field: ExportFieldDefinition,
    buffer: list[str],
    *,
    draft: ModeloDraft,
    producer_values: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    casilla_values: dict[CasillaId, object],
    binding_values: dict[tuple[BindingId, int | None], object],
    row: RecordRenderRow,
    render_context: FilingRecordRenderContext | None,
    projection_values: Mapping[ProjectionAddress, object],
    source_digests: Mapping[str, str] | None,
) -> tuple[int, str]:
    offset = field.offset
    if offset is None:
        raise FilingExportDesignIntegrityError(
            f"export field {field.id!r} must declare offset",
            translated_message="errors.integrity.filing_export_field_offset_undeclared",
            context={"field": field.id},
        )
    rendered = _render_positioned_field(
        field,
        record=record,
        draft=draft,
        producer_values=producer_values,
        producer_snapshot=producer_snapshot,
        casilla_values=casilla_values,
        binding_values=binding_values,
        row=row,
        render_context=render_context,
        projection_values=projection_values,
    )
    rendered = m280_contextual_sign_byte(
        record,
        field,
        rendered,
        key_wire=m280_key_wire(record, buffer),
        raw_amount=casilla_values.get(field.casilla_id) if field.casilla_id is not None else None,
        source_digests=source_digests,
    )
    return offset - 1, rendered


def _render_positioned_field(
    field: ExportFieldDefinition,
    *,
    record: ExportRecordDefinition,
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
        raise FilingExportDesignIntegrityError(
            f"export field {field.id!r} must declare offset",
            translated_message="errors.integrity.filing_export_field_offset_undeclared",
            context={"field": field.id},
        )
    return _render_field(
        field,
        record=record,
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
    record: ExportRecordDefinition,
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
        raise FilingExportDesignIntegrityError(
            f"export field {field.id!r} must declare length",
            translated_message="errors.integrity.filing_export_field_length_undeclared",
            context={"field": field.id},
        )
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
    if field.required_with is not None and _is_blank(casilla_values.get(field.required_with)):
        # The block carries no occurrence; _casilla_field_value refused any stray campo.
        return render_empty_block_slot(field)
    return format_field(field, raw, record=record)


def _scheme_period_field_value(
    field: ExportFieldDefinition,
    draft: ModeloDraft,
    binding_values: dict[tuple[BindingId, int | None], object],
    row_index: int | None,
) -> object | None:
    """Return the value the scheme's period gives the field, refusing a bound value that contradicts it."""
    derived_period_value = scheme_period_value(field, draft.period)
    if derived_period_value is None:
        return None
    bound_value = None if field.binding is None else binding_values.get((field.binding, row_index))
    if contradicts_scheme_period(field, draft.period, bound_value):
        raise FilingExportDesignIntegrityError(
            f"export field {field.id!r} contradicts the period being filed",
            translated_message="errors.integrity.filing_export_field_contradicts_period",
            context={"field": field.id},
        )
    return derived_period_value


def _computed_slot_value(
    field: ExportFieldDefinition,
    draft: ModeloDraft,
    producer_snapshot: FilingProducerSnapshot,
    render_context: FilingRecordRenderContext | None,
) -> object:
    computed = _computed_field_value(field, draft, producer_snapshot, render_context)
    # The blank is the slot's populated negative answer, not a missing byte.
    return " " if computed is None and field.presence_marker is not None else computed


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
    derived_period_value = _scheme_period_field_value(field, draft, binding_values, row_index)
    if derived_period_value is not None:
        return derived_period_value
    match field.kind:
        case CasillaFieldKind.LITERAL:
            return field.literal
        case CasillaFieldKind.FILLER:
            return ""
        case CasillaFieldKind.CASILLA:
            return _casilla_field_value(field, casilla_values)
        case CasillaFieldKind.BINDING:
            return binding_field_value(field, binding_values, row_index)
        case CasillaFieldKind.HEADER:
            return header_field_value(field, headers)
        case CasillaFieldKind.PROJECTION:
            return projection_field_value(field, render_context, projection_values)
        case CasillaFieldKind.DRAFT:
            return _draft_value(field, draft)
        case CasillaFieldKind.COMPUTED:
            return _computed_slot_value(field, draft, producer_snapshot, render_context)
        case _:
            raise FilingExportIntegrityError(
                f"unsupported export field kind {field.kind!r}",
                translated_message="errors.integrity.filing_export_field_kind_unsupported",
                context={"kind": str(field.kind)},
            )


def _casilla_field_value(field: ExportFieldDefinition, casilla_values: dict[CasillaId, object]) -> object:
    if field.casilla_id is None:
        raise FilingExportDesignIntegrityError(
            f"export field {field.id!r} must declare casilla_id",
            translated_message="errors.integrity.filing_export_field_casilla_undeclared",
            context={"field": field.id},
        )
    value = casilla_values.get(field.casilla_id)
    if field.required_with is not None and _is_blank(casilla_values.get(field.required_with)) and not _is_blank(value):
        # An empty block has no occurrence to carry this campo.
        raise FilingExportValidationError(
            f"export field {field.id!r} has a value but its block anchor {field.required_with!r} has none",
        )
    return value


def binding_field_value(
    field: ExportFieldDefinition,
    binding_values: dict[tuple[BindingId, int | None], object],
    row_index: int | None,
) -> object:
    """Return the value an export field takes from its binding and row index."""
    if field.binding is None:
        raise FilingExportDesignIntegrityError(
            f"export field {field.id!r} must declare binding",
            translated_message="errors.integrity.filing_export_field_binding_undeclared",
            context={"field": field.id},
        )
    value = binding_values.get((field.binding, row_index))
    if isinstance(value, bool) and field.data_type == "text":
        return _text_presence_marker(field, value)
    return value


def projection_field_value(
    field: ExportFieldDefinition,
    context: FilingRecordRenderContext | None,
    values: Mapping[ProjectionAddress, object],
) -> object:
    """Return the preflighted projection value one field addresses in its record occurrence."""
    if field.projection_ref is None:
        raise FilingExportDesignIntegrityError(
            f"export field {field.id!r} must declare projection_ref",
            translated_message="errors.integrity.filing_export_field_projection_ref_undeclared",
            context={"field": field.id},
        )
    if context is None:
        raise FilingExportDesignIntegrityError(
            f"export field {field.id!r} requires a snapshot-owned render context to address its projection",
            translated_message="errors.integrity.filing_export_field_projection_context_absent",
            context={"field": field.id},
        )
    address = (context.record.id, context.occurrence, field.projection_ref)
    try:
        return values[address]
    except KeyError as exc:
        raise FilingExportDesignIntegrityError(
            f"export projection address {address!r} has no preflighted value",
            translated_message="errors.integrity.filing_export_projection_address_unpreflighted",
            context={"address": str(address)},
        ) from exc


def header_field_value(field: ExportFieldDefinition, headers: Mapping[FilingProducerKey, object]) -> object:
    """Return the value an export field takes from the header producers, enforcing requirement."""
    if field.producer_key is None:
        raise FilingExportDesignIntegrityError(
            f"export field {field.id!r} must declare producer_key",
            translated_message="errors.integrity.filing_export_field_producer_key_undeclared",
            context={"field": field.id},
        )
    value = headers.get(field.producer_key)
    if field.presence_marker is not None:
        return _presence_marker_value(field, headers, value)
    if _is_blank(value) and (field.required or _required_for_this_taxpayer(field, headers)):
        raise FilingExportValidationError(
            f"export producer {field.producer_key!r} is required",
            context={"missing_producer_key": field.producer_key.value},
        )
    if isinstance(value, bool) and field.data_type == "text":
        return _text_presence_marker(field, value)
    return value.strip() if isinstance(value, str) else value


def _presence_marker_value(
    field: ExportFieldDefinition,
    headers: Mapping[FilingProducerKey, object],
    value: object,
) -> str:
    # The design requires the slot itself, with a blank or its constant. No
    # evidence describes an ordinary return; neither that absence nor a false
    # fact means a missing wire byte.
    if field.producer_key not in headers:
        raise FilingExportValidationError(f"export field {field.id!r} requires its producer fact")
    if value is True and field.presence_marker is not None:
        return field.presence_marker
    if value is False or value is None:
        return " "
    raise FilingExportDesignIntegrityError(
        f"export field {field.id!r} requires a typed boolean producer fact",
        translated_message="errors.integrity.filing_export_producer_fact_not_boolean",
        context={"field": field.id},
    )


def _text_presence_marker(field: ExportFieldDefinition, value: bool) -> str | None:
    """Write a boolean producer fact into a one-byte alphanumeric marker slot.

    The official designs reserve such slots for an ``X`` when the fact holds and
    a blank otherwise; any wider text slot has no such reading.
    """
    if field.length != 1:
        raise FilingExportDesignIntegrityError(
            f"export field {field.id!r} cannot write a boolean producer fact into a {field.length}-byte text slot",
            translated_message="errors.integrity.filing_export_boolean_in_text_slot",
            context={"field": field.id, "length": field.length},
        )
    return "X" if value else None


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _required_for_this_taxpayer(field: ExportFieldDefinition, headers: Mapping[FilingProducerKey, object]) -> bool:
    """Evaluate a legal-form requirement against the filing's own taxpayer.

    The form is read from the identity facts, which carry an entity's legal name
    or a natural person's names and never both. A taxpayer whose form cannot be
    read is treated as required: the export cannot show the condition does not
    apply, so a blank is refused rather than written.
    """
    return field.required_for is not None and _is_blank(headers.get(FilingProducerKey.TAXPAYER_LEGAL_NAME))


def _envelope_closing_tag(
    draft: ModeloDraft,
    snapshot: FilingProducerSnapshot,
    context: FilingRecordRenderContext | None = None,
) -> str:
    del snapshot, context
    year = str(draft.period.filing_year)
    period_code = _draft_period_code(draft)
    return f"</T{draft.modelo}0{year}{period_code}0000>"


def _draft_filing_year(draft: ModeloDraft) -> str:
    return str(draft.period.filing_year)


def _draft_period_code(draft: ModeloDraft) -> str:
    return draft.period.registry_token


def _draft_period_start_date(draft: ModeloDraft) -> str:
    return draft.period.start_date.strftime("%d%m%Y")


def _draft_period_end_date(draft: ModeloDraft) -> str:
    return draft.period.end_date.strftime("%d%m%Y")


def _sepa_marca(
    draft: ModeloDraft,
    snapshot: FilingProducerSnapshot,
    context: FilingRecordRenderContext | None = None,
) -> str | None:
    del draft, context
    selected = snapshot.selected_account
    if selected is None or isinstance(selected, ChargeAccountSelection):
        return None
    if not isinstance(selected, RefundAccountSelection):
        raise FilingExportValidationError("SEPA marker requires a selected refund account")
    return derive_sepa_marca(
        iban=selected.account.iban,
        bank_country_code=selected.account.bank_country_code,
    ).code


def continuation_page_marker(
    draft: ModeloDraft,
    snapshot: FilingProducerSnapshot,
    context: FilingRecordRenderContext | None = None,
) -> str | None:
    """Render the declared marker on a continuation page of its record and blank on the principal page.

    The marker says the page continues an earlier page of the same type, which
    is a fact of the record occurrence being written, never of the declaration's
    amendment kind. A record rendered without an occurrence context is a single,
    principal page.

    Core types:
    :class:`~cadrumo.domain.filing.schema.ModeloDraft`.
    """
    del draft, snapshot
    if context is None or context.occurrence <= 1:
        return None
    return resolve_form_codes(_FORM_ROW_CODES_FACT).code("aeat.page.continuation_marker")


def m303_complementaria_marker(
    draft: ModeloDraft,
    snapshot: FilingProducerSnapshot,
    context: FilingRecordRenderContext | None = None,
) -> str | None:
    """Render the official binary amendment marker from immutable amendment evidence.

    Core types:
    :class:`~cadrumo.domain.filing.schema.ModeloDraft`.
    """
    del draft, context
    return "X" if snapshot.amendment_evidence and snapshot.amendment_evidence.is_complementaria else None


def m303_no_activity_marker(
    draft: ModeloDraft,
    snapshot: FilingProducerSnapshot,
    context: FilingRecordRenderContext | None = None,
) -> str | None:
    """Render ``X`` only for the closed Modelo 303 no-activity disposition.

    Core types:
    :class:`~cadrumo.domain.filing.schema.ModeloDraft`.
    """
    del draft, context
    return "X" if snapshot.elections.result_disposition is ResultDisposition.NEGATIVA else None


COMPUTED_VALUE_PRODUCERS: Mapping[
    ExportComputedKey,
    Callable[[ModeloDraft, FilingProducerSnapshot, FilingRecordRenderContext | None], str | None],
] = {
    ExportComputedKey.ENVELOPE_CLOSING_TAG: _envelope_closing_tag,
    ExportComputedKey.SEPA_MARCA: _sepa_marca,
    ExportComputedKey.M303_COMPLEMENTARIA_MARKER: m303_complementaria_marker,
    ExportComputedKey.CONTINUATION_PAGE_MARKER: continuation_page_marker,
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
    render_context: FilingRecordRenderContext | None,
) -> str | None:
    if field.computed_key is None:
        raise FilingExportDesignIntegrityError(
            f"export field {field.id!r} must declare computed_key",
            translated_message="errors.integrity.filing_export_field_computed_key_undeclared",
            context={"field": field.id},
        )
    return COMPUTED_VALUE_PRODUCERS[field.computed_key](draft, producer_snapshot, render_context)


def _draft_value(field: ExportFieldDefinition, draft: ModeloDraft) -> str:
    if field.draft_attribute is None:
        raise FilingExportDesignIntegrityError(
            f"export field {field.id!r} must declare draft_attribute",
            translated_message="errors.integrity.filing_export_field_draft_attribute_undeclared",
            context={"field": field.id},
        )
    return DRAFT_VALUE_PRODUCERS[field.draft_attribute](draft)


def format_field(field: ExportFieldDefinition, value: object, *, record: ExportRecordDefinition | None = None) -> str:
    """Render one value through the field's fixed-width codec, as a filing export refusal on failure.

    Every record render passes ``record``, whose text rule and encoding govern
    a text value; a slot checked on its own omits it. A value wider than
    its slot is refused as that slot's overflow, never cut to fit, and a
    character the record cannot write is refused by name, never dropped.
    """
    try:
        return render_fixed_width_export_field(field, value, record=record)
    except FixedWidthUnrepresentableCharacterError as exc:
        raise FilingExportUnrepresentableCharacterError(
            field_id=field.id,
            first_position=field.offset,
            field_length=field.length,
            character=exc.character,
            rendered=exc.rendered,
            precondition_verdict=filing_no_recovery_verdict(
                FilingPreconditionCondition.OPERATION_ADMISSIBLE,
                facts={"error_type": "FilingExportUnrepresentableCharacterError", "field_id": field.id},
            ),
        ) from exc
    except FixedWidthValueOverflowError as exc:
        raise FilingExportValueOverflowError(
            field_id=field.id,
            first_position=field.offset,
            field_length=exc.field_length,
            rendered=exc.rendered,
            data_type=field.data_type.value,
        ) from exc
    except RegistryValidationError as exc:
        raise FilingExportFieldUnrenderableError(
            field_id=field.id,
            casilla_id=field.casilla_id,
            data_type=field.data_type.value,
            reason=str(exc),
            precondition_verdict=filing_no_recovery_verdict(
                FilingPreconditionCondition.OPERATION_ADMISSIBLE,
                facts={"error_type": "FilingExportFieldUnrenderableError", "field_id": field.id},
                outcome=NoRecoveryOutcome.TERMINAL,
            ),
        ) from exc


__all__ = [
    "COMPUTED_VALUE_PRODUCERS",
    "DRAFT_VALUE_PRODUCERS",
    "continuation_page_marker",
    "format_field",
    "m303_complementaria_marker",
    "m303_no_activity_marker",
    "projection_field_value",
    "render_record",
]
