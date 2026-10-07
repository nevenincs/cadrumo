"""Resolve declared form context without inferring presentation from offsets."""

from __future__ import annotations

from ....core.filing_projection_ref import (
    M303Exonerado390ActivityProjectionRef,
    M303Exonerado390OperacionesTercerosProjectionRef,
)
from ..export_field_kind import CasillaFieldKind
from .binding_value_contract import BindingValueChannel
from .errors import RegistryValidationError
from .export import derive_export_layouts_from_bindings
from .export_semantics import ExportDraftAttribute
from .schema import ModeloRevision
from .schema_exports import ExportFieldDefinition
from .schema_form_layouts import FormContextFieldBlock, FormFieldChoice


def resolve_form_context_field(revision: ModeloRevision, block: FormContextFieldBlock) -> ExportFieldDefinition:
    """Refuse absent, ambiguous, repeating or unsupported context addresses."""
    matches = [
        (record, field)
        for layout in derive_export_layouts_from_bindings(revision)
        if layout.id == block.export_layout_id
        for record in layout.records
        if record.id == block.export_record_id
        for field in record.fields
        if field.id == block.export_field_id
    ]
    if len(matches) != 1:
        raise RegistryValidationError("form context must address exactly one declared export field")
    record, field = matches[0]
    if record.repeat is not None:
        raise RegistryValidationError("scalar form context cannot address a repeating export record")
    if block.choices and (
        field.kind is not CasillaFieldKind.HEADER
        or field.producer_key is None
        or not field.allowed_values
        or {choice.value for choice in block.choices} != set(field.allowed_values)
    ):
        raise RegistryValidationError("context choices must cover the exact closed domain of a header producer")
    if field.kind is CasillaFieldKind.BINDING:
        bindings = [binding for binding in revision.bindings if binding.id == field.binding]
        if len(bindings) != 1 or bindings[0].value.channel is BindingValueChannel.ROW_SET:
            raise RegistryValidationError("form context requires one declared scalar binding")
        # The field selects the semantic owner, not its fixed-width fragment.
        # Integer/fractional/sign wire slices all refer to the whole typed value.
        return field
    if field.kind is CasillaFieldKind.HEADER and field.producer_key is not None:
        return field
    if field.kind is CasillaFieldKind.PROJECTION and isinstance(
        field.projection_ref,
        (M303Exonerado390ActivityProjectionRef, M303Exonerado390OperacionesTercerosProjectionRef),
    ):
        return field
    if field.kind is CasillaFieldKind.DRAFT and field.draft_attribute in (
        ExportDraftAttribute.FILING_YEAR,
        ExportDraftAttribute.PERIOD_CODE,
        ExportDraftAttribute.PERIOD_START_DATE,
        ExportDraftAttribute.PERIOD_END_DATE,
    ):
        return field
    raise RegistryValidationError("form context requires a filing producer or supported filing coordinate")


def form_context_choice(block: FormContextFieldBlock, value: object) -> FormFieldChoice | None:
    """Select only an explicitly declared code; missing facts remain unknown."""
    if not block.choices or value is None:
        return None
    if isinstance(value, str) or (isinstance(value, int) and not isinstance(value, bool)):
        for choice in block.choices:
            if choice.value == str(value):
                return choice
    raise RegistryValidationError("form context value is outside its declared choice domain")
