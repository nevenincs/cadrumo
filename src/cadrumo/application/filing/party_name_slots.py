"""Refuse a party-name slot that would file no declared name, before the fixed-width codec sees it.

A layout field carrying a ``party_name`` composition is filled from the party's
declared filing name, composed when the calculation produced its row. A row that
reaches the export without that value, or with one wider than the slot, has no
truthful content for the slot: the design allows no blank for the party it
lists and no shortening. Both refuse here as the declared-party-name refusal
with its door, rather than as spaces or as the codec's generic overflow. The
refusal names the row's party by the identifier and country the same record
occurrence files, so the door can state that party's name.
"""

from __future__ import annotations

from typing import Final

from ...domain.calculations.export_field_kind import CasillaFieldKind
from ...domain.calculations.registry.binding_selector_utils import selector_as_dict
from ...domain.calculations.registry.export import export_fields_overlap
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from ...domain.filing.declared_party_name_filing import DECLARED_PARTY_NAME_DOOR_ACTION_ID
from ...domain.filing.errors import (
    FilingExportDeclaredPartyNameMissingError,
    FilingExportDeclaredPartyNameTooWideError,
)
from ...domain.iva.establishment import SPAIN_COUNTRY_CODE
from .record_types import RecordRenderRow

#: Row fields that file the party's identifier, in the order one is preferred.
_TAX_IDENTIFIER_ROW_FIELDS: Final = (
    "party_tax_id",
    "declarado_tax_id",
    "community_iva_number",
    "perceptor_tax_id",
    "perceptor_nif",
    "contributor_tax_id",
)
#: Row fields that file the party's country.
_COUNTRY_ROW_FIELDS: Final = ("country_code", "residence_country_code")
#: The declarado NIF slot holds only "NIF asignados en España".
_SPANISH_ONLY_ROW_FIELD: Final = "declarado_tax_id"


def require_declared_party_names(
    record: ExportRecordDefinition,
    *,
    modelo: str,
    revision: ModeloRevision,
    binding_values: dict[tuple[BindingId, int | None], object],
    row: RecordRenderRow,
) -> None:
    """Refuse when a party-name slot of this record occurrence has no fitting declared name.

    Raises:
        FilingExportDeclaredPartyNameMissingError: The slot's row carries no name.
        FilingExportDeclaredPartyNameTooWideError: The carried name is wider than the slot.
    """
    for field in record.fields:
        if not _is_party_name_slot(field) or _slot_taken_by_another_field(record, field, row):
            continue
        length = field.length
        if length is None:
            continue
        value = binding_values.get((field.binding, row.row_index))
        if _is_stated(value) and len(str(value)) <= length:
            continue
        tax_identifier, country_code = _row_party(record, revision=revision, binding_values=binding_values, row=row)
        composed_length = len(str(value)) if _is_stated(value) else None
        error_type = (
            FilingExportDeclaredPartyNameMissingError
            if composed_length is None
            else FilingExportDeclaredPartyNameTooWideError
        )
        raise error_type(
            modelo=modelo,
            export_record_id=str(record.id),
            export_field_id=str(field.id),
            field_length=length,
            door_action_id=DECLARED_PARTY_NAME_DOOR_ACTION_ID,
            row_index=row.row_index,
            composed_length=composed_length,
            tax_identifier=tax_identifier,
            country_code=country_code,
        )


def _is_party_name_slot(field: ExportFieldDefinition) -> bool:
    """Whether the field is a binding-filled party-name slot."""
    return field.party_name is not None and field.kind == CasillaFieldKind.BINDING and field.binding is not None


def _is_stated(value: object) -> bool:
    """Whether the bound value is a non-blank string."""
    return isinstance(value, str) and bool(value.strip())


def _slot_taken_by_another_field(
    record: ExportRecordDefinition, field: ExportFieldDefinition, row: RecordRenderRow
) -> bool:
    """Whether this occurrence fills the slot's positions from another, overlapping binding instead."""
    return any(
        other is not field
        and other.binding is not None
        and other.binding in row.active_binding_ids
        and export_fields_overlap(field, other)
        for other in record.fields
    )


def _row_party(
    record: ExportRecordDefinition,
    *,
    revision: ModeloRevision,
    binding_values: dict[tuple[BindingId, int | None], object],
    row: RecordRenderRow,
) -> tuple[str | None, str | None]:
    """Return the identifier and country this record occurrence files for its party."""
    by_row_field = _row_values_by_field(record, revision=revision, binding_values=binding_values, row=row)
    tax_field = next((name for name in _TAX_IDENTIFIER_ROW_FIELDS if name in by_row_field), None)
    country = next((by_row_field[name] for name in _COUNTRY_ROW_FIELDS if name in by_row_field), None)
    if country is None and tax_field == _SPANISH_ONLY_ROW_FIELD:
        country = SPAIN_COUNTRY_CODE
    return (None if tax_field is None else by_row_field[tax_field]), country


def _row_values_by_field(
    record: ExportRecordDefinition,
    *,
    revision: ModeloRevision,
    binding_values: dict[tuple[BindingId, int | None], object],
    row: RecordRenderRow,
) -> dict[str, str]:
    """Map each row field this occurrence files to its first non-blank value."""
    bindings = {binding.id: binding for binding in revision.bindings}
    by_row_field: dict[str, str] = {}
    for field in record.fields:
        if field.kind != CasillaFieldKind.BINDING or field.binding is None:
            continue
        binding = bindings.get(field.binding)
        if binding is None:
            continue
        row_field = selector_as_dict(binding).get("row_field")
        value = binding_values.get((field.binding, row.row_index))
        if isinstance(row_field, str) and isinstance(value, str) and value.strip():
            by_row_field.setdefault(row_field, value.strip())
    return by_row_field


__all__ = ["require_declared_party_names"]
