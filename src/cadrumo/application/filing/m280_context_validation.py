"""Reviewed Modelo 280 negative-imputation context validation."""

from __future__ import annotations

from collections.abc import Mapping

from ...domain.calculations.export_field_kind import CasillaFieldKind
from ...domain.calculations.registry.export_value_policy import ExportValuePolicy, project_export_value
from ...domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from ...domain.filing.errors import FilingExportValidationError


def _m280_component_positions_match(
    sign: ExportFieldDefinition, integer: ExportFieldDefinition, fraction: ExportFieldDefinition
) -> bool:
    return (sign.offset, sign.length, integer.offset, integer.length, fraction.offset, fraction.length) == (
        176,
        1,
        177,
        8,
        185,
        2,
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
        and str(sign.casilla_id) == "rendimientos-negativos-imputables"
    )


def _m280_components_are_unbound_casillas(
    sign: ExportFieldDefinition, integer: ExportFieldDefinition, fraction: ExportFieldDefinition
) -> bool:
    return all(field.kind is CasillaFieldKind.CASILLA and field.binding is None for field in (sign, integer, fraction))


def _m280_component_sources_match(
    sign: ExportFieldDefinition, integer: ExportFieldDefinition, fraction: ExportFieldDefinition
) -> bool:
    return all(tuple(map(str, field.source_refs)) == ("aeat-dr-280-2022",) for field in (sign, integer, fraction))


def _m280_key_position_matches(key: ExportFieldDefinition) -> bool:
    return (key.offset, key.length, str(key.casilla_id)) == (137, 1, "extincion-plan")


def _m280_key_source_matches(key: ExportFieldDefinition) -> bool:
    return tuple(map(str, key.source_refs)) == ("aeat-dr-280-2022",)


def _require_m280_source_digest(source_digests: Mapping[str, str] | None) -> None:
    expected = "45cab8f0880dfc4094d6cc8905ae37efba0c10a568d49e8648e1c9a20b2a5701"
    if source_digests is None or source_digests.get("aeat-dr-280-2022") != expected:
        raise FilingExportValidationError("modelo 280 negative imputation components differ from reviewed source")


def _m280_wire_matches(key: str, sign_byte: str, magnitude: str) -> bool:
    if not magnitude.isascii() or not magnitude.isdigit():
        return False
    if key == "2":
        return sign_byte == "N"
    return sign_byte == "0" and magnitude == "0" * 10


def _require_m280_component_declaration(
    sign: ExportFieldDefinition,
    integer: ExportFieldDefinition | None,
    fraction: ExportFieldDefinition | None,
) -> tuple[ExportFieldDefinition, ExportFieldDefinition]:
    message = "modelo 280 negative imputation components differ from reviewed source"
    if integer is None or fraction is None:
        raise FilingExportValidationError(message)
    if not _m280_component_positions_match(sign, integer, fraction):
        raise FilingExportValidationError(message)
    if not _m280_component_policies_match(integer, fraction):
        raise FilingExportValidationError(message)
    if not _m280_components_share_casilla(sign, integer, fraction):
        raise FilingExportValidationError(message)
    if not _m280_components_are_unbound_casillas(sign, integer, fraction):
        raise FilingExportValidationError(message)
    return integer, fraction


def _require_m280_evidence_declaration(
    sign: ExportFieldDefinition,
    integer: ExportFieldDefinition,
    fraction: ExportFieldDefinition,
    key: ExportFieldDefinition | None,
    source_digests: Mapping[str, str] | None,
) -> None:
    message = "modelo 280 negative imputation components differ from reviewed source"
    if not _m280_component_sources_match(sign, integer, fraction):
        raise FilingExportValidationError(message)
    if key is None:
        raise FilingExportValidationError(message)
    if not _m280_key_position_matches(key) or not _m280_key_source_matches(key):
        raise FilingExportValidationError(message)
    _require_m280_source_digest(source_digests)


def _require_m280_wire(wire: str) -> None:
    if len(wire) != 500:
        raise FilingExportValidationError("modelo 280 negative imputation record is incomplete")
    sign_byte, magnitude = wire[175], wire[176:186]
    if not _m280_wire_matches(wire[136], sign_byte, magnitude):
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
    if (
        str(record.id) != "modelo-280-declarado"
        or str(field.id) != "modelo-280-t2-rendimientos-negativos-imputables-sign"
    ):
        return rendered
    if field.value_policy is not ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN:
        raise FilingExportValidationError("modelo 280 negative imputation sign differs from reviewed source")
    by_id = {str(item.id): item for item in record.fields}
    integer, fraction = _require_m280_component_declaration(
        field,
        by_id.get("modelo-280-t2-rendimientos-negativos-imputables-component-177"),
        by_id.get("modelo-280-t2-rendimientos-negativos-imputables-component-185"),
    )
    _require_m280_evidence_declaration(
        field,
        integer,
        fraction,
        by_id.get("modelo-280-t2-extincion-plan"),
        source_digests,
    )
    if key_wire != "2" or raw_amount is None:
        return rendered
    if project_export_value(ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN, raw_amount) == "0":
        if rendered != "0":
            raise FilingExportValidationError("modelo 280 explicit zero sign differs from its reviewed projection")
        return "N"
    return rendered


def require_m280_negative_imputation_context(
    record: ExportRecordDefinition, wire: str, *, source_digests: Mapping[str, str] | None = None
) -> None:
    """M280 prints N only for a key-2 extinction and zeros otherwise."""
    if str(record.id) != "modelo-280-declarado":
        return
    by_id = {str(field.id): field for field in record.fields}
    sign = by_id.get("modelo-280-t2-rendimientos-negativos-imputables-sign")
    if sign is None or sign.value_policy is not ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN:
        return
    integer, fraction = _require_m280_component_declaration(
        sign,
        by_id.get("modelo-280-t2-rendimientos-negativos-imputables-component-177"),
        by_id.get("modelo-280-t2-rendimientos-negativos-imputables-component-185"),
    )
    key = by_id.get("modelo-280-t2-extincion-plan")
    _require_m280_evidence_declaration(sign, integer, fraction, key, source_digests)
    _require_m280_wire(wire)
