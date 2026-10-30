"""Reviewed Modelo 280 negative-imputation context validation."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...domain.calculations.export_field_kind import CasillaFieldKind
from ...domain.calculations.registry.export_value_policy import (
    ExportValuePolicy,
    export_value_policy_wire_length,
    project_export_value,
)
from ...domain.calculations.registry.form_codes import resolve_form_codes
from ...domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from ...domain.filing.errors import FilingExportValidationError

_M280_SIGN_ID = "modelo-280-t2-rendimientos-negativos-imputables-sign"
_M280_KEY_ID = "modelo-280-t2-extincion-plan"
_M280_IMPUTABLE_CASILLA = "rendimientos-negativos-imputables"
_M280_KEY_CASILLA = "extincion-plan"
_M280_EXTINCION_FORM_CODES = "modelo-280-extinction-form-codes"
_M280_NEGATIVE_SIGN = str(project_export_value(ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN, Decimal(-1)))
_M280_ABSENT_SIGN = str(project_export_value(ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN, None))
_M280_REVIEWED_SOURCES = {
    "aeat-dr-280-2022": "45cab8f0880dfc4094d6cc8905ae37efba0c10a568d49e8648e1c9a20b2a5701",
}
_M280_CHANGED = "modelo 280 negative imputation components differ from reviewed source"


def _span(field: ExportFieldDefinition) -> tuple[int, int]:
    """Return the field's one-based start and exclusive end as the layout declares them."""
    if field.offset is None or field.length is None:
        raise FilingExportValidationError(_M280_CHANGED)
    return field.offset, field.offset + field.length


def _field_wire(wire: str, field: ExportFieldDefinition) -> str:
    start, end = _span(field)
    return wire[start - 1 : end - 1]


def _m280_components(
    record: ExportRecordDefinition, sign: ExportFieldDefinition
) -> tuple[ExportFieldDefinition | None, ExportFieldDefinition | None]:
    """Find the integer and fractional components that share the sign's casilla."""
    integers, fractions = (
        tuple(field for field in record.fields if field.casilla_id == sign.casilla_id and field.value_policy is policy)
        for policy in (
            ExportValuePolicy.SIGNED_COMPONENT_INTEGER_PART,
            ExportValuePolicy.SIGNED_COMPONENT_FRACTIONAL_DIGITS,
        )
    )
    return (integers[0] if len(integers) == 1 else None, fractions[0] if len(fractions) == 1 else None)


def _m280_component_positions_match(
    sign: ExportFieldDefinition, integer: ExportFieldDefinition, fraction: ExportFieldDefinition
) -> bool:
    return (
        sign.length == export_value_policy_wire_length(ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN)
        and integer.offset == _span(sign)[1]
        and fraction.offset == _span(integer)[1]
    )


def _m280_component_policies_match(integer: ExportFieldDefinition, fraction: ExportFieldDefinition) -> bool:
    return (
        integer.value_policy is ExportValuePolicy.SIGNED_COMPONENT_INTEGER_PART
        and fraction.value_policy is ExportValuePolicy.SIGNED_COMPONENT_FRACTIONAL_DIGITS
    )


def _m280_components_share_casilla(
    sign: ExportFieldDefinition, integer: ExportFieldDefinition, fraction: ExportFieldDefinition
) -> bool:
    return (
        sign.casilla_id == integer.casilla_id
        and sign.casilla_id == fraction.casilla_id
        and str(sign.casilla_id) == _M280_IMPUTABLE_CASILLA
    )


def _m280_components_are_unbound_casillas(
    sign: ExportFieldDefinition, integer: ExportFieldDefinition, fraction: ExportFieldDefinition
) -> bool:
    return all(field.kind is CasillaFieldKind.CASILLA and field.binding is None for field in (sign, integer, fraction))


def _m280_component_sources_match(
    sign: ExportFieldDefinition,
    integer: ExportFieldDefinition,
    fraction: ExportFieldDefinition,
    key: ExportFieldDefinition,
) -> bool:
    refs = tuple(map(str, sign.source_refs))
    return len(refs) == 1 and all(tuple(map(str, field.source_refs)) == refs for field in (integer, fraction, key))


def _m280_key_matches(key: ExportFieldDefinition) -> bool:
    return str(key.casilla_id) == _M280_KEY_CASILLA


def _require_m280_source_digest(sign: ExportFieldDefinition, source_digests: Mapping[str, str] | None) -> None:
    source_ref = str(sign.source_refs[0]) if len(sign.source_refs) == 1 else None
    expected = _M280_REVIEWED_SOURCES.get(source_ref) if source_ref is not None else None
    if source_ref is None or expected is None or source_digests is None or source_digests.get(source_ref) != expected:
        raise FilingExportValidationError(_M280_CHANGED)


def _m280_negative_imputation_key() -> str:
    """Return the extinction key under which negative returns are imputed."""
    return resolve_form_codes(_M280_EXTINCION_FORM_CODES).code("extinction.other_circumstances")


def _m280_wire_matches(key: str, sign_byte: str, magnitude: str) -> bool:
    if not magnitude.isascii() or not magnitude.isdigit():
        return False
    if key == _m280_negative_imputation_key():
        return sign_byte == _M280_NEGATIVE_SIGN
    return sign_byte == _M280_ABSENT_SIGN and magnitude == "0" * len(magnitude)


def _require_m280_component_declaration(
    sign: ExportFieldDefinition,
    integer: ExportFieldDefinition | None,
    fraction: ExportFieldDefinition | None,
) -> tuple[ExportFieldDefinition, ExportFieldDefinition]:
    if integer is None or fraction is None:
        raise FilingExportValidationError(_M280_CHANGED)
    if not _m280_component_positions_match(sign, integer, fraction):
        raise FilingExportValidationError(_M280_CHANGED)
    if not _m280_component_policies_match(integer, fraction):
        raise FilingExportValidationError(_M280_CHANGED)
    if not _m280_components_share_casilla(sign, integer, fraction):
        raise FilingExportValidationError(_M280_CHANGED)
    if not _m280_components_are_unbound_casillas(sign, integer, fraction):
        raise FilingExportValidationError(_M280_CHANGED)
    return integer, fraction


def _require_m280_evidence_declaration(
    sign: ExportFieldDefinition,
    integer: ExportFieldDefinition,
    fraction: ExportFieldDefinition,
    key: ExportFieldDefinition | None,
    source_digests: Mapping[str, str] | None,
) -> ExportFieldDefinition:
    if key is None or not _m280_key_matches(key):
        raise FilingExportValidationError(_M280_CHANGED)
    if not _m280_component_sources_match(sign, integer, fraction, key):
        raise FilingExportValidationError(_M280_CHANGED)
    _require_m280_source_digest(sign, source_digests)
    return key


def _require_m280_wire(
    record: ExportRecordDefinition,
    wire: str,
    *,
    sign: ExportFieldDefinition,
    integer: ExportFieldDefinition,
    fraction: ExportFieldDefinition,
    key: ExportFieldDefinition,
) -> None:
    if len(wire) != max(_span(field)[1] - 1 for field in record.fields):
        raise FilingExportValidationError("modelo 280 negative imputation record is incomplete")
    magnitude = _field_wire(wire, integer) + _field_wire(wire, fraction)
    if not _m280_wire_matches(_field_wire(wire, key), _field_wire(wire, sign), magnitude):
        raise FilingExportValidationError("modelo 280 negative imputation requires key 2 and N or other-key zero fill")


def m280_contextual_sign_byte(
    record: ExportRecordDefinition,
    field: ExportFieldDefinition,
    rendered: str,
    *,
    key_wire: str,
    raw_amount: object,
    source_digests: Mapping[str, str] | None,
) -> str:
    """Use N for an explicitly supplied zero under M280's key-2 source rule."""
    if record.id != "modelo-280-declarado" or field.id != _M280_SIGN_ID:
        return rendered
    if field.value_policy is not ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN:
        raise FilingExportValidationError("modelo 280 negative imputation sign differs from reviewed source")
    by_id = {item.id: item for item in record.fields}
    integer, fraction = _require_m280_component_declaration(field, *_m280_components(record, field))
    _require_m280_evidence_declaration(field, integer, fraction, by_id.get(_M280_KEY_ID), source_digests)
    if key_wire != _m280_negative_imputation_key() or raw_amount is None or raw_amount == "":
        return rendered
    if str(project_export_value(ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN, raw_amount)) == _M280_ABSENT_SIGN:
        if rendered != _M280_ABSENT_SIGN:
            raise FilingExportValidationError("modelo 280 explicit zero sign differs from its reviewed projection")
        return _M280_NEGATIVE_SIGN
    return rendered


def require_m280_negative_imputation_context(
    record: ExportRecordDefinition, wire: str, *, source_digests: Mapping[str, str] | None = None
) -> None:
    """M280 prints N only for a key-2 extinction and zeros otherwise."""
    if record.id != "modelo-280-declarado":
        return
    by_id = {field.id: field for field in record.fields}
    sign = by_id.get(_M280_SIGN_ID)
    if sign is None or sign.value_policy is not ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN:
        return
    integer, fraction = _require_m280_component_declaration(sign, *_m280_components(record, sign))
    key = _require_m280_evidence_declaration(sign, integer, fraction, by_id.get(_M280_KEY_ID), source_digests)
    _require_m280_wire(record, wire, sign=sign, integer=integer, fraction=fraction, key=key)
